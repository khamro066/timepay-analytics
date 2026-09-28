from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_current_user, require_admin_user, require_elevated_session
from app.core.database import SessionLocal
from app.models.attendance import Employee
from app.models.user import User
from app.services.corrections_service import create_correction, list_corrections
from app.services.leave_service import create_leave, delete_leave, list_leaves
from app.services.manual_entry_service import create_or_update_manual_entry, has_daily_attendance_row

router = APIRouter(prefix="/api/employees", tags=["employees"], dependencies=[Depends(get_current_user)])

VALID_STATUSES = {"active", "paused", "archived"}


class StatusUpdateRequest(BaseModel):
    status: str


@router.put("/{employee_id}/status")
def update_status(employee_id: int, payload: StatusUpdateRequest):
    if payload.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {sorted(VALID_STATUSES)}")

    db = SessionLocal()
    try:
        employee = db.get(Employee, employee_id)
        if employee is None:
            raise HTTPException(status_code=404, detail="Employee not found")

        employee.status = payload.status
        db.commit()
        return {"employee_id": employee_id, "status": employee.status}
    finally:
        db.close()


class LeaveCreateRequest(BaseModel):
    date_from: date
    date_to: date
    reason: str


@router.get("/{employee_id}/leave")
def get_employee_leaves(employee_id: int):
    return list_leaves(employee_id)


@router.post("/{employee_id}/leave")
def add_employee_leave(employee_id: int, payload: LeaveCreateRequest, current_user: User = Depends(get_current_user)):
    if payload.date_from > payload.date_to:
        raise HTTPException(status_code=400, detail="date_from must not be after date_to")
    if not payload.reason.strip():
        raise HTTPException(status_code=400, detail="reason is required")

    db = SessionLocal()
    try:
        if db.get(Employee, employee_id) is None:
            raise HTTPException(status_code=404, detail="Employee not found")
    finally:
        db.close()

    return create_leave(employee_id, payload.date_from, payload.date_to, payload.reason.strip(), current_user.username)


@router.delete("/{employee_id}/leave/{leave_id}")
def remove_employee_leave(employee_id: int, leave_id: int):
    if not delete_leave(employee_id, leave_id):
        raise HTTPException(status_code=404, detail="Leave record not found")
    return {"deleted": True}


def _validate_time(value: str | None, field: str) -> None:
    if value is None:
        return
    try:
        datetime.strptime(value, "%H:%M")
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{field} must be HH:MM (24-hour)")


class CorrectionCreateRequest(BaseModel):
    date: date
    corrected_check_in: str | None = None
    corrected_check_out: str | None = None
    reason: str


@router.post("/{employee_id}/corrections")
def add_correction(
    employee_id: int,
    payload: CorrectionCreateRequest,
    current_user: User = Depends(require_elevated_session),
):
    if not payload.reason.strip():
        raise HTTPException(status_code=400, detail="reason is required")
    if not payload.corrected_check_in and not payload.corrected_check_out:
        raise HTTPException(
            status_code=400, detail="at least one of corrected_check_in/corrected_check_out is required"
        )
    _validate_time(payload.corrected_check_in, "corrected_check_in")
    _validate_time(payload.corrected_check_out, "corrected_check_out")

    # Real constraint, not just a UI omission: an admin can never correct
    # their own linked employee record. No admin is linked to an Employee
    # today, so this is currently a no-op — but it's enforced here, not
    # just left out of the UI, so linking one later is immediately safe.
    if current_user.linked_employee_id is not None and current_user.linked_employee_id == employee_id:
        raise HTTPException(status_code=403, detail="Cannot create a correction for your own linked employee record")

    db = SessionLocal()
    try:
        if db.get(Employee, employee_id) is None:
            raise HTTPException(status_code=404, detail="Employee not found")
    finally:
        db.close()

    return create_correction(
        employee_id,
        payload.date,
        payload.corrected_check_in,
        payload.corrected_check_out,
        payload.reason.strip(),
        current_user.id,
    )


@router.get("/{employee_id}/corrections")
def get_corrections(employee_id: int, _current_user: User = Depends(require_elevated_session)):
    return list_corrections(employee_id)


class ManualEntryRequest(BaseModel):
    date: date
    check_in: str
    check_out: str
    note: str | None = None


@router.post("/{employee_id}/manual-entry")
def add_manual_entry(
    employee_id: int,
    payload: ManualEntryRequest,
    current_user: User = Depends(require_admin_user),
):
    """Regular admin auth only — no elevated session. This is routine,
    transparent HR data entry (unlike corrections), and only ever applies
    to a day Time Pay has no record of at all; a day it does have a
    record for, even a wrong one, belongs to the corrections tool."""
    _validate_time(payload.check_in, "check_in")
    _validate_time(payload.check_out, "check_out")

    db = SessionLocal()
    try:
        if db.get(Employee, employee_id) is None:
            raise HTTPException(status_code=404, detail="Employee not found")
    finally:
        db.close()

    if has_daily_attendance_row(employee_id, payload.date):
        raise HTTPException(
            status_code=409,
            detail="A Time Pay record already exists for this date — use the corrections tool to fix it instead.",
        )

    return create_or_update_manual_entry(
        employee_id, payload.date, payload.check_in, payload.check_out, payload.note, current_user.id
    )
