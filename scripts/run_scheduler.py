import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.core.database import Base, engine
from app.services.scheduler import build_scheduler, logger


def main() -> None:
    Base.metadata.create_all(bind=engine)
    scheduler = build_scheduler()
    logger.info("Scheduler started — daily sync scheduled for 23:55. Press Ctrl+C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
