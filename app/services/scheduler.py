import logging
from datetime import date

from apscheduler.schedulers.blocking import BlockingScheduler

from app.services.sync_service import sync_day
from app.services.timepay_client import TimePayClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("timepay.scheduler")

# Shared across every scheduled run so the rotating refresh token carries
# forward correctly instead of each run starting from a stale one.
client = TimePayClient()


def run_daily_sync() -> None:
    today = date.today().isoformat()
    logger.info("Starting scheduled sync for %s", today)
    try:
        count = sync_day(today, client=client)
        logger.info("Sync succeeded for %s: %d record(s)", today, count)
    except Exception:
        logger.exception("Sync failed for %s", today)


def build_scheduler() -> BlockingScheduler:
    scheduler = BlockingScheduler()
    scheduler.add_job(run_daily_sync, "cron", hour=23, minute=55, id="daily_timepay_sync")
    return scheduler
