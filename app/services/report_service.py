import io
from collections import defaultdict

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.services.analytics_service import get_all_employees_ranking
from app.services.notes_service import get_notes

# (data key, Excel column header, column width)
COLUMNS = [
    ("full_name", "Ism", 26),
    ("present_days", "Ishlagan kunlar soni", 14),
    ("absent_days", "Ishlamagan kunlar soni", 16),
    ("unexcused_absence_days", "Sababsiz ishga kelmagan kunlar soni", 20),
    ("excused_absence_days", "Sababli ishga kelmagan kunlar soni", 20),
    ("late_days", "Kech qolgan kunlar soni", 16),
    ("total_late_minutes", "Jami kechikkan daqiqa", 16),
    ("average_check_in_time", "O'rtacha ishga kelish vaqti", 18),
    ("early_leaving_days", "Erta ketgan kunlar soni", 16),
    ("average_check_out_time", "O'rtacha ishdan ketish vaqti", 18),
    ("total_worked_formatted", "Umumiy ish soati", 16),
    ("note", "Izoh", 32),
]


def _uzbek_worked_hours(total_minutes: int) -> str:
    return f"{total_minutes // 60} soat {total_minutes % 60} daq"


def get_report_rows(date_from: str, date_to: str, period_key: str) -> list[dict]:
    """Per-employee report data: the ranking fields (which already carry
    everything from _summarize_rows, computed over date_from..date_to) plus
    that employee's note for the given calendar period_key, if any. Shared
    by the on-screen Reports page and the Excel export so both always
    agree."""
    ranking = get_all_employees_ranking(date_from, date_to)
    notes_by_employee = {n["employee_id"]: n["note"] for n in get_notes(period_key)}

    return [{**r, "note": notes_by_employee.get(r["employee_id"], "")} for r in ranking]


def build_report_workbook(date_from: str, date_to: str, period_key: str) -> io.BytesIO:
    rows = get_report_rows(date_from, date_to, period_key)

    by_department: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_department[r["department"] or "Unknown"].append(r)

    wb = Workbook()
    ws = wb.active
    ws.title = "Hisobot"

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4C1D95", end_color="4C1D95", fill_type="solid")
    dept_font = Font(bold=True, size=12)
    dept_fill = PatternFill(start_color="EDE9FE", end_color="EDE9FE", fill_type="solid")

    for col_idx, (_, _, width) in enumerate(COLUMNS, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    row_idx = 1
    for department in sorted(by_department):
        emp_rows = by_department[department]

        ws.cell(row=row_idx, column=1, value=department)
        ws.cell(row=row_idx, column=1).font = dept_font
        for col_idx in range(1, len(COLUMNS) + 1):
            ws.cell(row=row_idx, column=col_idx).fill = dept_fill
        row_idx += 1

        for col_idx, (_, label, _) in enumerate(COLUMNS, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=label)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(wrap_text=True, vertical="center")
        row_idx += 1

        for emp in sorted(emp_rows, key=lambda e: e["full_name"] or ""):
            for col_idx, (key, _, _) in enumerate(COLUMNS, start=1):
                if key == "total_worked_formatted":
                    value = _uzbek_worked_hours(emp.get("total_worked_minutes") or 0)
                elif key in ("average_check_in_time", "average_check_out_time"):
                    value = emp.get(key) or "—"
                else:
                    value = emp.get(key, "")
                ws.cell(row=row_idx, column=col_idx, value=value)
            row_idx += 1

        row_idx += 1

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
