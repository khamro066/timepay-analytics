from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.core.database import SessionLocal
from app.models.attendance import Employee

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
