from datetime import datetime

from app.core.database import SessionLocal
from app.models.attendance import DailyAttendance, Employee
from app.services.timepay_client import TimePayClient


def sync_day(date: str) -> int:
    """Fetches employee daily stats for `date` (YYYY-MM-DD) from Time Pay
    and upserts them into the Employee and DailyAttendance tables.

    Returns the number of employee records synced.
    """
    client = TimePayClient()
    records = client.fetch_daily_stats(date)
    attendance_date = datetime.strptime(date, "%Y-%m-%d").date()

    db = SessionLocal()
    try:
        for item in records:
            employee_id = item["id"]
            stats = item.get("stats", {})

            employee = db.get(Employee, employee_id)
            if employee is None:
                employee = Employee(id=employee_id)
                db.add(employee)

            employee.full_name = item.get("full_name")
            employee.department = item.get("department")
            employee.position = item.get("position")
            employee.branch = ", ".join(item.get("branches") or [])
            employee.profile_image = item.get("profile_image")

            attendance = (
                db.query(DailyAttendance)
                .filter_by(employee_id=employee_id, date=attendance_date)
                .one_or_none()
            )
            if attendance is None:
                attendance = DailyAttendance(employee_id=employee_id, date=attendance_date)
                db.add(attendance)

            attendance.is_working_day = stats.get("is_working_day")
            attendance.is_holiday = stats.get("is_holiday")
            attendance.absent = stats.get("absent")
            attendance.on_leave = stats.get("on_leave")
            attendance.late = stats.get("late")
            attendance.late_minutes = stats.get("late_minutes")
            attendance.early_leaving = stats.get("early_leaving")
            attendance.early_leaving_minutes = stats.get("early_leaving_minutes")
            attendance.expected_worked_minutes = stats.get("expected_worked_minutes")
            attendance.actual_worked_minutes = stats.get("actual_worked_minutes")
            attendance.first_check_in = stats.get("first_check_in")
            attendance.last_check_out = stats.get("last_check_out")
            attendance.last_action = stats.get("last_action")
            attendance.synced_at = datetime.utcnow()

        db.commit()
        return len(records)
    finally:
        db.close()
