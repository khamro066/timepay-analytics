from datetime import date as date_cls
from datetime import datetime

from app.core.database import SessionLocal
from app.models.attendance import DailyAttendance
from app.models.attendance_correction import AttendanceCorrection
from app.models.manual_attendance_entry import ManualAttendanceEntry
from app.models.user import User
from app.services.manual_entry_service import get_manual_entry_map

SOURCE_TIME_PAY = "TIME_PAY"
SOURCE_TIME_PAY_CORRECTED = "TIME_PAY_CORRECTED"
SOURCE_MANUAL = "MANUAL"


def _minutes_between(checkin: str | None, checkout: str | None) -> int | None:
    """Worked minutes from two "HH:MM" strings, or None if either is
    missing or checkout isn't after checkin (a same-day span only — we
    have no way to tell an overnight shift from bad data here)."""
    if not checkin or not checkout:
        return None
    try:
        ch, cm = (int(x) for x in checkin.split(":"))
        oh, om = (int(x) for x in checkout.split(":"))
    except (ValueError, AttributeError):
        return None
    start = ch * 60 + cm
    end = oh * 60 + om
    return end - start if end > start else None


class EffectiveAttendance:
    """A DailyAttendance-shaped, read-only view with any admin correction or
    manual entry overlaid on top. Every analytics function reads attendance
    through apply_corrections() below instead of the raw DailyAttendance
    rows, so the corrected/manual-vs-original decision lives in exactly one
    place rather than being re-checked in every function that touches hours
    or check-in/out times.

    Only first_check_in, last_check_out, actual_worked_minutes, and absent
    can differ from the underlying row. late/late_minutes/early_leaving
    are left exactly as Time Pay recorded them: correcting a check-in/out
    stamp (or filling one in from scratch) doesn't give us the schedule
    data Time Pay used to judge lateness, so we don't attempt to re-derive
    it. `source` tells the frontend which of the three cases it is —
    TIME_PAY_CORRECTED stays invisible everywhere except the hidden
    corrections tool; MANUAL must be visibly tagged everywhere.
    """

    __slots__ = (
        "employee_id",
        "date",
        "is_working_day",
        "is_holiday",
        "on_leave",
        "late",
        "late_minutes",
        "early_leaving",
        "early_leaving_minutes",
        "last_action",
        "first_check_in",
        "last_check_out",
        "absent",
        "actual_worked_minutes",
        "corrected",
        "source",
    )

    def __init__(self, row: DailyAttendance, correction: AttendanceCorrection | None):
        self.employee_id = row.employee_id
        self.date = row.date
        self.is_working_day = row.is_working_day
        self.is_holiday = row.is_holiday
        self.on_leave = row.on_leave
        self.late = row.late
        self.late_minutes = row.late_minutes
        self.early_leaving = row.early_leaving
        self.early_leaving_minutes = row.early_leaving_minutes
        self.last_action = row.last_action
        self.corrected = correction is not None

        if correction is not None:
            self.first_check_in = correction.corrected_check_in or row.first_check_in
            self.last_check_out = correction.corrected_check_out or row.last_check_out
            # A correction exists specifically to assert the employee *was*
            # working that day — Time Pay's absent flag is what was wrong.
            self.absent = False
            worked = _minutes_between(self.first_check_in, self.last_check_out)
            self.actual_worked_minutes = worked if worked is not None else row.actual_worked_minutes
            self.source = SOURCE_TIME_PAY_CORRECTED
        else:
            self.first_check_in = row.first_check_in
            self.last_check_out = row.last_check_out
            self.absent = row.absent
            self.actual_worked_minutes = row.actual_worked_minutes
            self.source = SOURCE_TIME_PAY

    @classmethod
    def from_manual_entry(cls, entry: ManualAttendanceEntry) -> "EffectiveAttendance":
        """A day with no daily_attendance row at all, filled in entirely
        from an admin-entered ManualAttendanceEntry."""
        obj = cls.__new__(cls)
        obj.employee_id = entry.employee_id
        obj.date = entry.date
        obj.is_working_day = True
        obj.is_holiday = False
        obj.on_leave = False
        obj.late = False
        obj.late_minutes = None
        obj.early_leaving = False
        obj.early_leaving_minutes = None
        obj.last_action = None
        obj.first_check_in = entry.check_in
        obj.last_check_out = entry.check_out
        obj.absent = False
        obj.actual_worked_minutes = _minutes_between(entry.check_in, entry.check_out)
        obj.corrected = False
        obj.source = SOURCE_MANUAL
        return obj


def get_correction_map(
    employee_ids: set[int], start: date_cls, end: date_cls
) -> dict[tuple[int, date_cls], AttendanceCorrection]:
    """Latest correction per (employee_id, date) in [start, end]. Ordering
    by created_at ascending and letting later rows overwrite earlier ones
    in the dict keeps only the most recent correction for a day that was
    corrected more than once."""
    if not employee_ids:
        return {}
    db = SessionLocal()
    try:
        rows = (
            db.query(AttendanceCorrection)
            .filter(
                AttendanceCorrection.employee_id.in_(employee_ids),
                AttendanceCorrection.date >= start,
                AttendanceCorrection.date <= end,
            )
            .order_by(AttendanceCorrection.created_at.asc())
            .all()
        )
        return {(r.employee_id, r.date): r for r in rows}
    finally:
        db.close()


def apply_corrections(
    rows: list[DailyAttendance],
    employee_ids: set[int] | None = None,
    start: date_cls | None = None,
    end: date_cls | None = None,
) -> list[EffectiveAttendance]:
    """Overlays any admin correction onto each row's check-in/out (and the
    hours/presence derived from them), falling back to the original Time
    Pay value when no correction exists for that day. Also synthesizes an
    entirely new day for any (employee_id, date) in `employee_ids` x
    [start, end] that has a manual entry but no daily_attendance row at
    all — the whole point of the manual-entry feature is filling a gap
    Time Pay never recorded.

    employee_ids/start/end default to being inferred from `rows` — the
    original, corrections-only behavior — for callers that don't have a
    natural "who/what range am I asking about" set of their own (e.g.
    get_lateness_distribution, get_day_of_week_stats), since without an
    explicit range there's no employee to attribute a manual-only day to.
    Callers that already know their target employees/range (ranking,
    employee summary, department summary, schedule matrix, the daily
    company views) should pass them explicitly so an employee who is
    *entirely* covered by manual entries for a day still shows up.

    Call this immediately after every DailyAttendance query in
    analytics_service so every caller downstream is correction/manual-entry
    aware without needing to know either exists at all."""
    if employee_ids is None:
        employee_ids = {r.employee_id for r in rows}
    if start is None or end is None:
        dates = [r.date for r in rows]
        if not dates:
            return []
        start, end = min(dates), max(dates)

    correction_map = get_correction_map(employee_ids, start, end)
    manual_map = get_manual_entry_map(employee_ids, start, end)

    covered = {(r.employee_id, r.date) for r in rows}
    effective = [EffectiveAttendance(r, correction_map.get((r.employee_id, r.date))) for r in rows]

    for key, entry in manual_map.items():
        if key not in covered:
            effective.append(EffectiveAttendance.from_manual_entry(entry))

    effective.sort(key=lambda r: (r.employee_id, r.date))
    return effective


def _serialize(db, correction: AttendanceCorrection) -> dict:
    admin = db.get(User, correction.corrected_by)
    return {
        "id": correction.id,
        "employee_id": correction.employee_id,
        "date": correction.date.isoformat(),
        "original_check_in": correction.original_check_in,
        "original_check_out": correction.original_check_out,
        "corrected_check_in": correction.corrected_check_in,
        "corrected_check_out": correction.corrected_check_out,
        "reason": correction.reason,
        "corrected_by": correction.corrected_by,
        "corrected_by_username": admin.username if admin else None,
        "created_at": correction.created_at.isoformat() if correction.created_at else None,
    }


def create_correction(
    employee_id: int,
    day: date_cls,
    corrected_check_in: str | None,
    corrected_check_out: str | None,
    reason: str,
    corrected_by: int,
) -> dict:
    db = SessionLocal()
    try:
        original = (
            db.query(DailyAttendance)
            .filter(DailyAttendance.employee_id == employee_id, DailyAttendance.date == day)
            .one_or_none()
        )
        correction = AttendanceCorrection(
            employee_id=employee_id,
            date=day,
            original_check_in=original.first_check_in if original else None,
            original_check_out=original.last_check_out if original else None,
            corrected_check_in=corrected_check_in,
            corrected_check_out=corrected_check_out,
            reason=reason,
            corrected_by=corrected_by,
            created_at=datetime.utcnow(),
        )
        db.add(correction)
        db.commit()
        db.refresh(correction)
        return _serialize(db, correction)
    finally:
        db.close()


def list_corrections(employee_id: int) -> list[dict]:
    db = SessionLocal()
    try:
        rows = (
            db.query(AttendanceCorrection)
            .filter(AttendanceCorrection.employee_id == employee_id)
            .order_by(AttendanceCorrection.date.desc(), AttendanceCorrection.created_at.desc())
            .all()
        )
        return [_serialize(db, r) for r in rows]
    finally:
        db.close()
