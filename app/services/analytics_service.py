from collections import defaultdict
from datetime import date as date_cls
from datetime import datetime

from app.core.database import SessionLocal
from app.models.attendance import DailyAttendance, Employee


def _parse_date(value: str) -> date_cls:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _avg_time_str(time_strings: list[str]) -> str | None:
    """Averages a list of "HH:MM" strings by converting to minutes-since-
    midnight, averaging, and converting back. None if the list is empty."""
    minutes = []
    for value in time_strings:
        if not value:
            continue
        try:
            hours, mins = value.split(":")
            minutes.append(int(hours) * 60 + int(mins))
        except (ValueError, AttributeError):
            continue

    if not minutes:
        return None

    avg = round(sum(minutes) / len(minutes))
    return f"{avg // 60:02d}:{avg % 60:02d}"


def _format_worked_minutes(total_minutes: int) -> str:
    return f"{total_minutes // 60}h {total_minutes % 60}m"


def _summarize_rows(rows: list[DailyAttendance]) -> dict:
    """Aggregates a set of DailyAttendance rows into summary metrics.

    "Expected working days" = rows where is_working_day is True.
    "Present days" = expected working days where absent is False.
    attendance_rate = present_days / expected_working_days (None if no
    working days fall in the range, to avoid a misleading 0%).
    punctuality_rate = (present AND not late) days / expected_working_days.
    overall_score = simple average of attendance_rate and punctuality_rate,
    so a perfect-attendance-but-often-late employee doesn't rank above a
    mostly-on-time one purely on presence.

    late/absent/early_leaving are only counted on days is_working_day is
    True: Time Pay sets absent=True (and occasionally early_leaving=True)
    as a default filler value on non-working days too, so counting those
    would report days off as "absences".
    """
    working_rows = [r for r in rows if r.is_working_day]
    expected_working_days = len(working_rows)
    present_days = sum(1 for r in working_rows if not r.absent)
    punctual_present_days = sum(1 for r in working_rows if not r.absent and not r.late)

    attendance_rate = (present_days / expected_working_days) if expected_working_days else None
    punctuality_rate = (punctual_present_days / expected_working_days) if expected_working_days else None
    overall_score = (
        (attendance_rate + punctuality_rate) / 2
        if attendance_rate is not None and punctuality_rate is not None
        else None
    )

    total_worked_minutes = sum(r.actual_worked_minutes or 0 for r in rows)
    absent_days = sum(1 for r in working_rows if r.absent)

    # Time Pay has no signal that distinguishes an excused absence (approved
    # leave) from an unexcused one — every absence in real data has
    # has_day_application=False (see investigation notes). excused_absence_days
    # is a placeholder for a future manual-override flow; unexcused is
    # derived from it so the two always sum to absent_days.
    excused_absence_days = 0
    unexcused_absence_days = absent_days - excused_absence_days

    present_rows = [r for r in working_rows if not r.absent]

    return {
        "total_worked_minutes": total_worked_minutes,
        "total_worked_formatted": _format_worked_minutes(total_worked_minutes),
        "total_late_minutes": sum(r.late_minutes or 0 for r in rows),
        "late_days": sum(1 for r in working_rows if r.late),
        "absent_days": absent_days,
        "excused_absence_days": excused_absence_days,
        "unexcused_absence_days": unexcused_absence_days,
        "early_leaving_days": sum(1 for r in working_rows if r.early_leaving),
        "expected_working_days": expected_working_days,
        "present_days": present_days,
        "attendance_rate": attendance_rate,
        "punctuality_rate": punctuality_rate,
        "overall_score": overall_score,
        "average_check_in_time": _avg_time_str([r.first_check_in for r in present_rows]),
        "average_check_out_time": _avg_time_str([r.last_check_out for r in present_rows]),
    }


def get_employee_summary(employee_id: int, date_from: str, date_to: str) -> dict:
    start = _parse_date(date_from)
    end = _parse_date(date_to)

    db = SessionLocal()
    try:
        employee = db.get(Employee, employee_id)
        rows = (
            db.query(DailyAttendance)
            .filter(
                DailyAttendance.employee_id == employee_id,
                DailyAttendance.date >= start,
                DailyAttendance.date <= end,
            )
            .order_by(DailyAttendance.date)
            .all()
        )

        days = [
            {
                "date": r.date.isoformat(),
                "is_working_day": r.is_working_day,
                "is_holiday": r.is_holiday,
                "absent": r.absent,
                "on_leave": r.on_leave,
                "late": r.late,
                "late_minutes": r.late_minutes,
                "early_leaving": r.early_leaving,
                "actual_worked_minutes": r.actual_worked_minutes,
                "first_check_in": r.first_check_in,
                "last_check_out": r.last_check_out,
                "last_action": r.last_action,
            }
            for r in rows
        ]

        return {
            "employee_id": employee_id,
            "full_name": employee.full_name if employee else None,
            "department": employee.department if employee else None,
            "position": employee.position if employee else None,
            "profile_image": employee.profile_image if employee else None,
            "date_from": date_from,
            "date_to": date_to,
            **_summarize_rows(rows),
            "days": days,
        }
    finally:
        db.close()


def get_all_employees_ranking(date_from: str, date_to: str, department: str | None = None) -> list[dict]:
    start = _parse_date(date_from)
    end = _parse_date(date_to)

    db = SessionLocal()
    try:
        rows = (
            db.query(DailyAttendance)
            .filter(DailyAttendance.date >= start, DailyAttendance.date <= end)
            .all()
        )

        rows_by_employee: dict[int, list[DailyAttendance]] = defaultdict(list)
        for row in rows:
            rows_by_employee[row.employee_id].append(row)

        employees = {e.id: e for e in db.query(Employee).all()}

        ranking = []
        for employee_id, emp_rows in rows_by_employee.items():
            employee = employees.get(employee_id)
            employee_department = employee.department if employee else None
            if department and employee_department != department:
                continue
            ranking.append(
                {
                    "employee_id": employee_id,
                    "full_name": employee.full_name if employee else None,
                    "department": employee_department,
                    "position": employee.position if employee else None,
                    "profile_image": employee.profile_image if employee else None,
                    **_summarize_rows(emp_rows),
                }
            )

        ranking.sort(
            key=lambda r: (
                -(r["overall_score"] if r["overall_score"] is not None else 0.0),
                r["late_days"],
                r["absent_days"],
            )
        )
        return ranking
    finally:
        db.close()


def get_department_summary(date_from: str, date_to: str) -> list[dict]:
    """Per-department metrics, pooling every employee's attendance rows in
    that department together — so average_attendance_rate is total present
    days / total expected days across the whole department, not a simple
    mean of each employee's individual rate."""
    start = _parse_date(date_from)
    end = _parse_date(date_to)

    db = SessionLocal()
    try:
        rows = (
            db.query(DailyAttendance, Employee.department)
            .join(Employee, Employee.id == DailyAttendance.employee_id)
            .filter(DailyAttendance.date >= start, DailyAttendance.date <= end)
            .all()
        )

        attendance_by_department: dict[str, list[DailyAttendance]] = defaultdict(list)
        employees_by_department: dict[str, set[int]] = defaultdict(set)
        for attendance, department in rows:
            key = department or "Unknown"
            attendance_by_department[key].append(attendance)
            employees_by_department[key].add(attendance.employee_id)

        summaries = []
        for department, dept_rows in attendance_by_department.items():
            summary = _summarize_rows(dept_rows)
            summaries.append(
                {
                    "department": department,
                    "employee_count": len(employees_by_department[department]),
                    "average_attendance_rate": summary["attendance_rate"],
                    "average_punctuality_rate": summary["punctuality_rate"],
                    "average_overall_score": summary["overall_score"],
                    "total_late_incidents": summary["late_days"],
                    "total_absent_incidents": summary["absent_days"],
                    "total_early_leaving_incidents": summary["early_leaving_days"],
                    "total_worked_minutes": summary["total_worked_minutes"],
                }
            )

        summaries.sort(key=lambda d: -(d["average_overall_score"] or 0.0))
        return summaries
    finally:
        db.close()


def get_daily_company_stats(date: str) -> dict:
    day = _parse_date(date)

    db = SessionLocal()
    try:
        rows = db.query(DailyAttendance).filter(DailyAttendance.date == day).all()

        return {
            "date": date,
            "total_employees": len(rows),
            "present": sum(1 for r in rows if r.is_working_day and not r.absent),
            "late": sum(1 for r in rows if r.late),
            "absent": sum(1 for r in rows if r.absent),
            "on_leave": sum(1 for r in rows if r.on_leave),
        }
    finally:
        db.close()
