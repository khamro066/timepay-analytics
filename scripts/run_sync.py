import sys
from datetime import date as date_cls
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.core.database import Base, engine
from app.services.sync_service import sync_day


def main() -> None:
    if len(sys.argv) == 1:
        date = date_cls.today().isoformat()
    elif len(sys.argv) == 2:
        date = sys.argv[1]
    else:
        print("Usage: python scripts/run_sync.py [YYYY-MM-DD]")
        print("  With no argument, syncs today's date.")
        sys.exit(1)

    Base.metadata.create_all(bind=engine)

    count = sync_day(date)
    print(f"Synced {count} employee record(s) for {date}")


if __name__ == "__main__":
    main()
