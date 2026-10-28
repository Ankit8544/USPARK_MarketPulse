
import os
import logging
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, request
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler

# Load environment variables first
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

from telegram import (
    handle_telegram_update,
    send_pre_market_brief_to_all,
)

IST = ZoneInfo("Asia/Kolkata")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)
app = Flask(__name__)


def run_pre_market_job():
    """Run the job and log success or failure."""
    logger.info("Pre-market brief job started")

    try:
        send_pre_market_brief_to_all()
        logger.info("Pre-market brief job completed")
    except Exception:
        logger.exception("Pre-market brief job failed")
        raise


# Start scheduler when this module is loaded.
scheduler = BackgroundScheduler(
    timezone=IST,
    job_defaults={"coalesce": True, "max_instances": 1},
)

scheduler.add_job(
    func=run_pre_market_job,
    trigger="cron",
    hour=19,
    minute=00,
    id="pre_market_brief",
    replace_existing=True,
    misfire_grace_time=3600,
)

scheduler.start()

logger.info(
    "Scheduler started. Next run: %s",
    scheduler.get_job("pre_market_brief").next_run_time,
)


@app.get("/")
def home():
    job = scheduler.get_job("pre_market_brief")

    return jsonify({
        "app": "USPARK Market Updates",
        "status": "running",
        "timezone": "Asia/Kolkata",
        "scheduler_running": scheduler.running,
        "next_run": (
            job.next_run_time.isoformat()
            if job and job.next_run_time
            else None
        ),
    })


@app.get("/health")
def health():
    return jsonify({"status": "ok"}), 200


@app.post("/telegram-webhook")
def telegram_webhook():
    update = request.get_json(silent=True)

    if not isinstance(update, dict):
        return jsonify({
            "ok": False,
            "error": "Invalid update",
        }), 400

    try:
        handle_telegram_update(update)
        return jsonify({"ok": True}), 200
    except Exception:
        logger.exception("Telegram webhook processing failed")
        return jsonify({"ok": False}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))

    try:
        app.run(
            host="0.0.0.0",
            port=port,
            debug=False,
            use_reloader=False,
        )
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)
