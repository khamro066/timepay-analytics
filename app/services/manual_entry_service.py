from datetime import date as date_cls
from datetime import datetime

from app.core.database import SessionLocal
from app.models.attendance import DailyAttendance
from app.models.manual_attendance_entry import ManualAttendanceEntry
from app.models.user import User


def has_daily_attendance_row(employee_id: int, day: date_cls) -> bool:
    db = SessionLocal()
    try:
        return (
            db.query(DailyAttendance)
            .filter(DailyAttendance.employee_id == employee_id, DailyAttendance.date == day)
            .first()
            is not None
        )
    finally:
        db.close()


def _serialize(db, entry: ManualAttendanceEntry) -> dict:
    admin = db.get(User, entry.entered_by)
    return {
        "id": entry.id,
        "employee_id": entry.employee_id,
        "date": entry.date.isoformat(),
        "check_in": entry.check_in,
        "check_out": entry.check_out,
        "note": entry.note,
        "entered_by": entry.entered_by,
        "entered_by_username": admin.username if admin else None,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }


def create_or_update_manual_entry(
    employee_id: int,
    day: date_cls,
    check_in: str,
    check_out: str,
    note: str | None,
    entered_by: int,
) -> dict:
    """Upsert: routine HR data entry, not an audit trail — resubmitting the
    same employee/date (e.g. to fix a typo) updates the existing row rather
    than creating a new one."""
    db = SessionLocal()
    try:
        existing = (
            db.query(ManualAttendanceEntry)
            .filter(ManualAttendanceEntry.employee_id == employee_id, ManualAttendanceEntry.date == day)
            .one_or_none()
        )
        if existing is None:
            existing = ManualAttendanceEntry(employee_id=employee_id, date=day, created_at=datetime.utcnow())
            db.add(existing)
        existing.check_in = check_in
        existing.check_out = check_out
        existing.note = note
        existing.entered_by = entered_by
        db.commit()
        db.refresh(existing)
        return _serialize(db, existing)
    finally:
        db.close()


def get_manual_entry_map(
    employee_ids: set[int], start: date_cls, end: date_cls
) -> dict[tuple[int, date_cls], ManualAttendanceEntry]:
    if not employee_ids:
        return {}
    db = SessionLocal()
    try:
        rows = (
            db.query(ManualAttendanceEntry)
            .filter(
                ManualAttendanceEntry.employee_id.in_(employee_ids),
                ManualAttendanceEntry.date >= start,
                ManualAttendanceEntry.date <= end,
            )
            .all()
        )
        return {(r.employee_id, r.date): r for r in rows}
    finally:
        db.close()
