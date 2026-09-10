from collections import defaultdict
from datetime import date as date_cls
from datetime import datetime, timedelta

from sqlalchemy import func

from app.core.database import SessionLocal
from app.models.attendance import DailyAttendance, Employee
from app.services.leave_service import get_leave_day_set


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


def _summarize_rows(rows: list[DailyAttendance], leave_days: set[tuple[int, date_cls]] | None = None) -> dict:
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

    # Time Pay has no signal that distinguishes an excused absence from an
    # unexcused one — every absence in real data has has_day_application=
    # False. We fill that gap with manually-recorded EmployeeLeave ranges:
    # an absent working day covered by a leave range is excused, everything
    # else absent counts as unexcused.
    leave_days = leave_days or set()
    excused_absence_days = sum(1 for r in working_rows if r.absent and (r.employee_id, r.date) in leave_days)
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
        leave_days = get_leave_day_set({employee_id}, start, end)

        days = [
            {
                "date": r.date.isoformat(),
                "is_working_day": r.is_working_day,
                "is_holiday": r.is_holiday,
                "absent": r.absent,
                "on_leave": r.on_leave,
                "excused": (r.employee_id, r.date) in leave_days,
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
            "status": employee.status if employee else None,
            "date_from": date_from,
            "date_to": date_to,
            **_summarize_rows(rows, leave_days),
            "days": days,
        }
    finally:
        db.close()


def get_all_employees_ranking(
    date_from: str, date_to: str, department: str | None = None, include_archived: bool = False
) -> list[dict]:
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
        leave_days = get_leave_day_set(set(rows_by_employee.keys()), start, end)

        ranking = []
        for employee_id, emp_rows in rows_by_employee.items():
            employee = employees.get(employee_id)
            employee_department = employee.department if employee else None
            if department and employee_department != department:
                continue
            # "active" is the only status included by default — paused and
            # archived employees are hidden from rankings/reports unless the
            # caller explicitly asks to see them (e.g. a historical report).
            if not include_archived and employee is not None and employee.status != "active":
                continue
            ranking.append(
                {
                    "employee_id": employee_id,
                    "full_name": employee.full_name if employee else None,
                    "department": employee_department,
                    "position": employee.position if employee else None,
                    "profile_image": employee.profile_image if employee else None,
                    "status": employee.status if employee else None,
                    **_summarize_rows(emp_rows, leave_days),
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


def get_department_summary(date_from: str, date_to: str, include_archived: bool = False) -> list[dict]:
    """Per-department metrics, pooling every employee's attendance rows in
    that department together — so average_attendance_rate is total present
    days / total expected days across the whole department, not a simple
    mean of each employee's individual rate."""
    start = _parse_date(date_from)
    end = _parse_date(date_to)

    db = SessionLocal()
    try:
        query = (
            db.query(DailyAttendance, Employee.department)
            .join(Employee, Employee.id == DailyAttendance.employee_id)
            .filter(DailyAttendance.date >= start, DailyAttendance.date <= end)
        )
        if not include_archived:
            query = query.filter(Employee.status == "active")
        rows = query.all()

        attendance_by_department: dict[str, list[DailyAttendance]] = defaultdict(list)
        employees_by_department: dict[str, set[int]] = defaultdict(set)
        all_employee_ids: set[int] = set()
        for attendance, department in rows:
            key = department or "Unknown"
            attendance_by_department[key].append(attendance)
            employees_by_department[key].add(attendance.employee_id)
            all_employee_ids.add(attendance.employee_id)
        leave_days = get_leave_day_set(all_employee_ids, start, end)

        summaries = []
        for department, dept_rows in attendance_by_department.items():
            summary = _summarize_rows(dept_rows, leave_days)
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


LATENESS_BUCKETS = [
    ("on_time", 0, 0),
    ("late_5_15", 1, 14),
    ("late_15_30", 15, 29),
    ("late_30_plus", 30, None),
]


def get_lateness_distribution(date_from: str, date_to: str, department: str | None = None) -> dict:
    """Buckets check-ins by how late they were, using Time Pay's own
    late_minutes (there is no schedule/expected-start-time model on our side
    to compute "how early" someone arrived, so — unlike a from-scratch
    lateness calculation — this has no "arrived early" bucket; on-time and
    early are indistinguishable in our data and are reported together as
    "on_time")."""
    start = _parse_date(date_from)
    end = _parse_date(date_to)

    db = SessionLocal()
    try:
        query = (
            db.query(DailyAttendance)
            .join(Employee, Employee.id == DailyAttendance.employee_id)
            .filter(
                DailyAttendance.date >= start,
                DailyAttendance.date <= end,
                DailyAttendance.is_working_day.is_(True),
                DailyAttendance.absent.is_(False),
                DailyAttendance.first_check_in.isnot(None),
            )
        )
        if department:
            query = query.filter(Employee.department == department)
        rows = query.all()

        counts = {key: 0 for key, _, _ in LATENESS_BUCKETS}
        for r in rows:
            minutes = r.late_minutes or 0 if r.late else 0
            for key, lo, hi in LATENESS_BUCKETS:
                if minutes >= lo and (hi is None or minutes <= hi):
                    counts[key] += 1
                    break

        total = len(rows)
        return {
            "total": total,
            "buckets": [
                {
                    "key": key,
                    "count": counts[key],
                    "pct": round((counts[key] / total) * 100) if total else 0,
                }
                for key, _, _ in LATENESS_BUCKETS
            ],
        }
    finally:
        db.close()


WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def get_day_of_week_stats(date_from: str, date_to: str, department: str | None = None) -> list[dict]:
    """Buckets working-day attendance rows by weekday (Python's date.weekday():
    0=Monday..6=Sunday) so callers can see which day of the week tends to have
    the most lateness/absence. Rates are out of working-day rows only, matching
    how attendance_rate/punctuality_rate are computed elsewhere."""
    start = _parse_date(date_from)
    end = _parse_date(date_to)

    db = SessionLocal()
    try:
        query = (
            db.query(DailyAttendance)
            .join(Employee, Employee.id == DailyAttendance.employee_id)
            .filter(
                DailyAttendance.date >= start,
                DailyAttendance.date <= end,
                DailyAttendance.is_working_day.is_(True),
            )
        )
        if department:
            query = query.filter(Employee.department == department)
        rows = query.all()

        totals = [0] * 7
        late_counts = [0] * 7
        absent_counts = [0] * 7
        for r in rows:
            idx = r.date.weekday()
            totals[idx] += 1
            if r.late:
                late_counts[idx] += 1
            if r.absent:
                absent_counts[idx] += 1

        return [
            {
                "key": WEEKDAY_KEYS[i],
                "total": totals[i],
                "late_count": late_counts[i],
                "absent_count": absent_counts[i],
                "late_rate": (late_counts[i] / totals[i]) if totals[i] else None,
                "absent_rate": (absent_counts[i] / totals[i]) if totals[i] else None,
            }
            for i in range(7)
        ]
    finally:
        db.close()


def _schedule_day_status(row: DailyAttendance | None, excused: bool) -> str:
    """Status for a single employee/day cell in the schedule matrix.

    Precedence mirrors the Employee-detail calendar (EmployeeCalendarHeatmap):
    a missing row is "no_data" (a day with no file uploaded is not an
    absence — see the design-reference notes), then holiday / non-working
    day take precedence over attendance, then an absence covered by a
    recorded EmployeeLeave range is "excused", then plain absence, then
    lateness, otherwise "on_time" (Time Pay can't tell "on time" from
    "early", so the two are reported together — same as
    get_lateness_distribution)."""
    if row is None:
        return "no_data"
    if row.is_holiday:
        return "holiday"
    if not row.is_working_day:
        return "day_off"
    if row.absent:
        return "excused" if excused else "absent"
    if row.late:
        return "late"
    return "on_time"


def get_schedule_matrix(
    date_from: str, date_to: str, department: str | None = None, include_archived: bool = False
) -> dict:
    """Company-wide attendance grid: one row per employee, one column per
    calendar date in [date_from, date_to], every cell a derived status.

    Employee selection matches the ranking/report endpoints — only
    employees with at least one attendance row somewhere in the range, and
    only "active" staff unless include_archived is set, optionally narrowed
    to a single department. Rows come back ordered by department then name
    so the grid reads top-to-bottom like an org list; each employee's
    "days" list is aligned to (and the same length as) the top-level
    "dates" list.
    """
    start = _parse_date(date_from)
    end = _parse_date(date_to)

    dates: list[date_cls] = []
    day = start
    while day <= end:
        dates.append(day)
        day += timedelta(days=1)

    db = SessionLocal()
    try:
        rows = (
            db.query(DailyAttendance)
            .filter(DailyAttendance.date >= start, DailyAttendance.date <= end)
            .all()
        )

        rows_by_employee: dict[int, dict[date_cls, DailyAttendance]] = defaultdict(dict)
        for row in rows:
            rows_by_employee[row.employee_id][row.date] = row

        employees = {e.id: e for e in db.query(Employee).all()}
        leave_days = get_leave_day_set(set(rows_by_employee.keys()), start, end)

        matrix = []
        for employee_id, by_date in rows_by_employee.items():
            employee = employees.get(employee_id)
            employee_department = employee.department if employee else None
            if department and employee_department != department:
                continue
            if not include_archived and employee is not None and employee.status != "active":
                continue

            matrix.append(
                {
                    "employee_id": employee_id,
                    "full_name": employee.full_name if employee else None,
                    "department": employee_department,
                    "position": employee.position if employee else None,
                    "profile_image": employee.profile_image if employee else None,
                    "status": employee.status if employee else None,
                    "days": [
                        {
                            "date": d.isoformat(),
                            "status": _schedule_day_status(
                                by_date.get(d), (employee_id, d) in leave_days
                            ),
                        }
                        for d in dates
                    ],
                }
            )

        matrix.sort(key=lambda r: ((r["department"] or "").lower(), (r["full_name"] or "").lower()))

        return {
            "date_from": date_from,
            "date_to": date_to,
            "dates": [d.isoformat() for d in dates],
            "employees": matrix,
        }
    finally:
        db.close()


def get_latest_attendance_date() -> str | None:
    """The most recent date any attendance row exists for. Used by the
    dashboard to fall back off "today" when the Time Pay sync for the
    current day hasn't run yet."""
    db = SessionLocal()
    try:
        latest = db.query(func.max(DailyAttendance.date)).scalar()
        return latest.isoformat() if latest else None
    finally:
        db.close()


def get_daily_company_stats(date: str, department: str | None = None) -> dict:
    """Today's headcount only ever reflects currently-active employees —
    paused/archived people never show up as "absent today". An optional
    department narrows the counts to one business/branch."""
    day = _parse_date(date)

    db = SessionLocal()
    try:
        query = (
            db.query(DailyAttendance)
            .join(Employee, Employee.id == DailyAttendance.employee_id)
            .filter(DailyAttendance.date == day, Employee.status == "active")
        )
        if department:
            query = query.filter(Employee.department == department)
        rows = query.all()

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
