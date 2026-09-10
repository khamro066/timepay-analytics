from datetime import date as date_cls
from datetime import timedelta

from app.core.database import SessionLocal
from app.models.employee_leave import EmployeeLeave


def _serialize(leave: EmployeeLeave) -> dict:
    return {
        "id": leave.id,
        "employee_id": leave.employee_id,
        "date_from": leave.date_from.isoformat(),
        "date_to": leave.date_to.isoformat(),
        "reason": leave.reason,
        "created_by": leave.created_by,
        "created_at": leave.created_at.isoformat() if leave.created_at else None,
    }


def list_leaves(employee_id: int) -> list[dict]:
    db = SessionLocal()
    try:
        leaves = (
            db.query(EmployeeLeave)
            .filter(EmployeeLeave.employee_id == employee_id)
            .order_by(EmployeeLeave.date_from.desc())
            .all()
        )
        return [_serialize(leave) for leave in leaves]
    finally:
        db.close()


def create_leave(employee_id: int, date_from: date_cls, date_to: date_cls, reason: str, created_by: str) -> dict:
    db = SessionLocal()
    try:
        leave = EmployeeLeave(
            employee_id=employee_id,
            date_from=date_from,
            date_to=date_to,
            reason=reason,
            created_by=created_by,
        )
        db.add(leave)
        db.commit()
        db.refresh(leave)
        return _serialize(leave)
    finally:
        db.close()


def delete_leave(employee_id: int, leave_id: int) -> bool:
    db = SessionLocal()
    try:
        leave = (
            db.query(EmployeeLeave)
            .filter(EmployeeLeave.id == leave_id, EmployeeLeave.employee_id == employee_id)
            .one_or_none()
        )
        if leave is None:
            return False
        db.delete(leave)
        db.commit()
        return True
    finally:
        db.close()


def get_leave_day_set(employee_ids: set[int], start: date_cls, end: date_cls) -> set[tuple[int, date_cls]]:
    """Expands every leave range overlapping [start, end] for the given
    employees into a flat set of (employee_id, date) pairs, so callers can
    do an O(1) membership check per attendance row instead of a per-row
    range scan."""
    if not employee_ids:
        return set()

    db = SessionLocal()
    try:
        leaves = (
            db.query(EmployeeLeave)
            .filter(
                EmployeeLeave.employee_id.in_(employee_ids),
                EmployeeLeave.date_from <= end,
                EmployeeLeave.date_to >= start,
            )
            .all()
        )

        day_set: set[tuple[int, date_cls]] = set()
        for leave in leaves:
            day = max(leave.date_from, start)
            last = min(leave.date_to, end)
            while day <= last:
                day_set.add((leave.employee_id, day))
                day += timedelta(days=1)
        return day_set
    finally:
        db.close()


def get_leave_reason_map(
    employee_ids: set[int], start: date_cls, end: date_cls
) -> dict[tuple[int, date_cls], str]:
    """Like get_leave_day_set, but maps each covered (employee_id, date)
    pair to the reason text of the leave range covering it — for callers
    that need to show *why* a day is excused without a second query. On
    overlapping ranges the most recently created leave wins."""
    if not employee_ids:
        return {}

    db = SessionLocal()
    try:
        leaves = (
            db.query(EmployeeLeave)
            .filter(
                EmployeeLeave.employee_id.in_(employee_ids),
                EmployeeLeave.date_from <= end,
                EmployeeLeave.date_to >= start,
            )
            .order_by(EmployeeLeave.created_at.asc())
            .all()
        )

        reason_map: dict[tuple[int, date_cls], str] = {}
        for leave in leaves:
            day = max(leave.date_from, start)
            last = min(leave.date_to, end)
            while day <= last:
                reason_map[(leave.employee_id, day)] = leave.reason
                day += timedelta(days=1)
        return reason_map
    finally:
        db.close()
