import sys
from datetime import date as date_cls
from datetime import timedelta
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.core.database import Base, engine
from app.services.sync_service import sync_day
from app.services.timepay_client import TimePayClient

# How many trailing days (today included) the no-argument nightly run
# re-syncs. Time Pay sometimes hasn't finished ingesting a day's device data
# by the time our cron asks for it that same night (every employee comes
# back absent with no check-in — see the 2026-09-30/10-01 incident); always
# re-covering the last few days lets a gap like that self-heal on the next
# run instead of sitting there until someone notices and backfills by hand.
RESYNC_DAYS = 3


def main() -> None:
    Base.metadata.create_all(bind=engine)

    if len(sys.argv) == 1:
        client = TimePayClient()
        today = date_cls.today()
        for offset in range(RESYNC_DAYS):
            date = (today - timedelta(days=offset)).isoformat()
            count = sync_day(date, client=client)
            print(f"Synced {count} employee record(s) for {date}")
    elif len(sys.argv) == 2:
        date = sys.argv[1]
        count = sync_day(date)
        print(f"Synced {count} employee record(s) for {date}")
    else:
        print("Usage: python scripts/run_sync.py [YYYY-MM-DD]")
        print(f"  With no argument, re-syncs today and the previous {RESYNC_DAYS - 1} day(s).")
        print("  With a date, syncs only that one day (manual backfill).")
        sys.exit(1)


if __name__ == "__main__":
    main()
