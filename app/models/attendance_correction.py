from datetime import datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String

from app.core.database import Base


class AttendanceCorrection(Base):
    """An admin-entered fix for a check-in/out time Time Pay recorded
    wrong (e.g. a remote/field day where the employee only badged into
    the Face ID terminal hours after they actually started). Purely
    additive — the underlying daily_attendance row from Time Pay is never
    modified or deleted; this table is an audit trail layered on top, and
    original_check_in/original_check_out are always a snapshot of what
    daily_attendance held at the moment this correction was made."""

    __tablename__ = "attendance_corrections"

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    date = Column(Date, nullable=False)
    original_check_in = Column(String, nullable=True)
    original_check_out = Column(String, nullable=True)
    corrected_check_in = Column(String, nullable=True)
    corrected_check_out = Column(String, nullable=True)
    reason = Column(String, nullable=False)
    corrected_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
