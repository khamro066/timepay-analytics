from datetime import datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String

from app.core.database import Base


class EmployeeLeave(Base):
    """An approved excused-absence range (leave/sick/vacation) for an
    employee. Any DailyAttendance day that falls inside [date_from, date_to]
    of one of these rows counts as excused_absence_days instead of
    unexcused_absence_days going forward."""

    __tablename__ = "employee_leave"

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    date_from = Column(Date, nullable=False)
    date_to = Column(Date, nullable=False)
    reason = Column(String, nullable=False)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
