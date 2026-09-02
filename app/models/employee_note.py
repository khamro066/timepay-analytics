from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint

from app.core.database import Base


class EmployeeNote(Base):
    """A note attached to an employee for a fixed calendar period, not a
    rolling date range — e.g. "2026-09-02" (a day), "2026-W36" (an ISO
    week), or "2026-09" (a month). This way a note written on any day of
    a given week/month reappears whenever that same week/month is viewed
    later, instead of being tied to the exact date_from/date_to a rolling
    period tab happened to compute on the day it was written.
    """

    __tablename__ = "employee_notes"
    __table_args__ = (UniqueConstraint("employee_id", "period_key", name="uq_employee_note_period"),)

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    period_key = Column(String, nullable=False)
    note = Column(String, nullable=False)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
