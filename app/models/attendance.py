from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True)
    full_name = Column(String, nullable=False)
    department = Column(String, nullable=True)
    position = Column(String, nullable=True)
    branch = Column(String, nullable=True)
    profile_image = Column(String, nullable=True)
    status = Column(String, nullable=False, default="active")

    attendances = relationship("DailyAttendance", back_populates="employee")


class DailyAttendance(Base):
    __tablename__ = "daily_attendance"
    __table_args__ = (UniqueConstraint("employee_id", "date", name="uq_employee_date"),)

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    date = Column(Date, nullable=False)

    is_working_day = Column(Boolean, nullable=True)
    is_holiday = Column(Boolean, nullable=True)
    absent = Column(Boolean, nullable=True)
    on_leave = Column(Boolean, nullable=True)
    late = Column(Boolean, nullable=True)
    late_minutes = Column(Integer, nullable=True)
    early_leaving = Column(Boolean, nullable=True)
    early_leaving_minutes = Column(Integer, nullable=True)
    expected_worked_minutes = Column(Integer, nullable=True)
    actual_worked_minutes = Column(Integer, nullable=True)
    extra_worked_minutes = Column(Integer, nullable=True)
    first_check_in = Column(String, nullable=True)
    last_check_out = Column(String, nullable=True)
    last_action = Column(String, nullable=True)
    synced_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    employee = relationship("Employee", back_populates="attendances")
