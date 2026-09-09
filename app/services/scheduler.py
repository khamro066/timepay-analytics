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

# Built lazily (not at import time) so run_scheduler.py gets a chance to
# create the app_config table first; shared across scheduled runs afterward
# so the rotating refresh token carries forward in memory between them.
_client: TimePayClient | None = None


def _get_client() -> TimePayClient:
    global _client
    if _client is None:
        _client = TimePayClient()
    return _client


def run_daily_sync() -> None:
    today = date.today().isoformat()
    logger.info("Starting scheduled sync for %s", today)
    try:
        count = sync_day(today, client=_get_client())
        logger.info("Sync succeeded for %s: %d record(s)", today, count)
    except Exception:
        logger.exception("Sync failed for %s", today)


def build_scheduler() -> BlockingScheduler:
    scheduler = BlockingScheduler()
    scheduler.add_job(run_daily_sync, "cron", hour=23, minute=55, id="daily_timepay_sync")
    return scheduler
