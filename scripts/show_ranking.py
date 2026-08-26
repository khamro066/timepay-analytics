import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.services.analytics_service import get_all_employees_ranking


def format_rate(rate) -> str:
    return f"{rate * 100:.1f}%" if rate is not None else "N/A"


def print_table(title: str, ranked_rows: list[tuple[int, dict]]) -> None:
    print(f"\n=== {title} ===")
    header = (
        f"{'Rank':<6}{'Name':<26}{'Department':<16}"
        f"{'Rate':<8}{'Punct.':<8}{'Score':<8}{'Late':<6}{'Absent':<7}"
    )
    print(header)
    print("-" * len(header))
    for rank, row in ranked_rows:
        name = (row["full_name"] or "")[:25]
        department = (row["department"] or "")[:15]
        print(
            f"{rank:<6}{name:<26}{department:<16}"
            f"{format_rate(row['attendance_rate']):<8}{format_rate(row['punctuality_rate']):<8}"
            f"{format_rate(row['overall_score']):<8}{row['late_days']:<6}{row['absent_days']:<7}"
        )


def main() -> None:
    if len(sys.argv) == 3:
        date_from, date_to = sys.argv[1], sys.argv[2]
    elif len(sys.argv) == 1:
        end = date.today()
        start = end - timedelta(days=29)
        date_from, date_to = start.isoformat(), end.isoformat()
    else:
        print("Usage: python scripts/show_ranking.py [DATE_FROM DATE_TO]")
        print("  With no arguments, uses the last 30 days.")
        sys.exit(1)

    ranking = get_all_employees_ranking(date_from, date_to)
    total = len(ranking)

    print(f"Attendance ranking: {date_from} to {date_to} ({total} employee(s))")

    top = list(enumerate(ranking[:10], start=1))

    bottom_start_rank = max(total - 9, 1)
    bottom = list(enumerate(ranking[-10:], start=bottom_start_rank))
    bottom.reverse()

    print_table("Top performers", top)
    print_table("Needs attention", bottom)


if __name__ == "__main__":
    main()
