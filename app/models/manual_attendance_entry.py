from datetime import datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint

from app.core.database import Base


class ManualAttendanceEntry(Base):
    """A fully admin-entered attendance day for when Time Pay has no record
    at all — e.g. a remote/off-site day where the employee never badged
    into a Face ID terminal. Distinct from AttendanceCorrection: a
    correction fixes a wrong Time Pay value; this fills a gap where Time
    Pay has nothing. One row per employee/date — resubmitting the same day
    updates it in place (routine HR data entry, not an audit trail, unlike
    corrections)."""

    __tablename__ = "manual_attendance_entries"
    __table_args__ = (UniqueConstraint("employee_id", "date", name="uq_manual_entry_employee_date"),)

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    date = Column(Date, nullable=False)
    check_in = Column(String, nullable=True)
    check_out = Column(String, nullable=True)
    note = Column(String, nullable=True)
    entered_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
