import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.core.database import Base, engine
from app.services.sync_service import sync_day
from app.services.timepay_client import TimePayClient


def daterange(start: date, end: date):
    for offset in range((end - start).days + 1):
        yield start + timedelta(days=offset)


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python scripts/backfill.py START_DATE END_DATE  (YYYY-MM-DD, inclusive)")
        sys.exit(1)

    start = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
    end = datetime.strptime(sys.argv[2], "%Y-%m-%d").date()

    if start > end:
        print(f"START_DATE ({start}) must not be after END_DATE ({end})")
        sys.exit(1)

    Base.metadata.create_all(bind=engine)

    client = TimePayClient()
    succeeded: list[tuple[str, int]] = []
    failed: list[tuple[str, str]] = []

    for day in daterange(start, end):
        day_str = day.isoformat()
        print(f"Syncing {day_str}...", end=" ", flush=True)
        try:
            count = sync_day(day_str, client=client)
            print(f"done, {count} records")
            succeeded.append((day_str, count))
        except Exception as exc:
            print(f"FAILED: {exc}")
            failed.append((day_str, str(exc)))

    total_records = sum(count for _, count in succeeded)

    print()
    print("=== Backfill summary ===")
    print(f"Date range: {start} to {end} ({len(succeeded) + len(failed)} day(s))")
    print(f"Succeeded: {len(succeeded)} day(s), {total_records} total record(s)")
    print(f"Failed: {len(failed)} day(s)")
    for day_str, err in failed:
        print(f"  - {day_str}: {err}")


if __name__ == "__main__":
    main()
