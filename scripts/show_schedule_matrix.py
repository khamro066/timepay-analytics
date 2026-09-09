import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.services.analytics_service import get_schedule_matrix

GLYPH = {
    "on_time": "#",
    "late": "L",
    "absent": "X",
    "excused": "e",
    "holiday": "H",
    "day_off": ".",
    "no_data": " ",
}


def main() -> None:
    if len(sys.argv) == 3:
        date_from, date_to = sys.argv[1], sys.argv[2]
    elif len(sys.argv) == 1:
        end = date.today()
        start = end - timedelta(days=13)
        date_from, date_to = start.isoformat(), end.isoformat()
    else:
        print("Usage: python scripts/show_schedule_matrix.py [DATE_FROM DATE_TO]")
        print("  With no arguments, uses the last 14 days.")
        sys.exit(1)

    matrix = get_schedule_matrix(date_from, date_to)
    dates = matrix["dates"]
    employees = matrix["employees"]

    print(f"Schedule matrix: {date_from} to {date_to} ({len(dates)} days, {len(employees)} employees)")
    print("Legend: # on-time  L late  X absent  e excused  H holiday  . day-off  (blank) no-data\n")

    header = f"{'':<24}" + "".join(d[-2:] for d in dates)
    print(header)
    print("-" * len(header))

    tally: dict[str, int] = {}
    current_department = None
    for emp in employees:
        if emp["department"] != current_department:
            current_department = emp["department"]
            print(f"\n[{current_department or 'Unknown'}]")
        line = "".join(GLYPH.get(day["status"], "?") for day in emp["days"])
        for day in emp["days"]:
            tally[day["status"]] = tally.get(day["status"], 0) + 1
        print(f"{(emp['full_name'] or '')[:23]:<24}{line}")

    print("\nCell totals:")
    for status in GLYPH:
        if tally.get(status):
            print(f"  {status:<10} {tally[status]}")


if __name__ == "__main__":
    main()
