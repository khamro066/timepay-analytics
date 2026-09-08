from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.core.database import SessionLocal
from app.models.attendance import Employee
from app.models.user import User
from app.services.leave_service import create_leave, delete_leave, list_leaves

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
