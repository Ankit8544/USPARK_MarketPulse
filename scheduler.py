
import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from zoneinfo import ZoneInfo
from apscheduler.schedulers.blocking import BlockingScheduler

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

from telegram import send_pre_market_brief_to_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

scheduler = BlockingScheduler(
    timezone=ZoneInfo("Asia/Kolkata"),
)


def run_pre_market_job():
    logger.info("Pre-market job started")
    print("Pre-market job started")

    try:
        send_pre_market_brief_to_all()
        logger.info("Pre-market job completed")
        print("Pre-market job completed")

    except Exception:
        logger.exception("Pre-market job failed")
        print("Pre-market job failed")


scheduler.add_job(
    run_pre_market_job,
    trigger="cron",
    hour=20,
    minute=00,
    id="pre_market_brief",
    replace_existing=True,
    max_instances=1,
    coalesce=True,
    misfire_grace_time=3600,
)


if __name__ == "__main__":
    logger.info("Scheduler starting: 08:00 PM IST")
    print("Scheduler starting: 08:00 PM IST")
    scheduler.start()
