from datetime import date as date_cls
from datetime import datetime

from app.core.database import SessionLocal
from app.models.attendance import DailyAttendance
from app.models.attendance_correction import AttendanceCorrection
from app.models.user import User


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
    """A DailyAttendance-shaped, read-only view with any admin correction
    overlaid on top. Every analytics function reads attendance through
    apply_corrections() below instead of the raw DailyAttendance rows, so
    the corrected-vs-original decision lives in exactly one place rather
    than being re-checked in every function that touches hours or
    check-in/out times.

    Only first_check_in, last_check_out, actual_worked_minutes, and absent
    can differ from the underlying row. late/late_minutes/early_leaving
    are left exactly as Time Pay recorded them: correcting a check-in/out
    stamp doesn't give us the schedule data Time Pay used to judge
    lateness, so we don't attempt to re-derive it.
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
        else:
            self.first_check_in = row.first_check_in
            self.last_check_out = row.last_check_out
            self.absent = row.absent
            self.actual_worked_minutes = row.actual_worked_minutes


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


def apply_corrections(rows: list[DailyAttendance]) -> list[EffectiveAttendance]:
    """Overlays any admin correction onto each row's check-in/out (and the
    hours/presence derived from them), falling back to the original Time
    Pay value when no correction exists for that day. Call this
    immediately after every DailyAttendance query in analytics_service so
    every caller downstream is correction-aware without needing to know
    corrections exist at all."""
    if not rows:
        return []
    employee_ids = {r.employee_id for r in rows}
    dates = [r.date for r in rows]
    correction_map = get_correction_map(employee_ids, min(dates), max(dates))
    return [EffectiveAttendance(r, correction_map.get((r.employee_id, r.date))) for r in rows]


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
