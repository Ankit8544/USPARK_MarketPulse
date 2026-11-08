import os
import logging
from pathlib import Path
from zoneinfo import ZoneInfo
import requests

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

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL")

if BOT_TOKEN and RENDER_URL:
    webhook_url = f"{RENDER_URL}/telegram-webhook"

    response = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
        json={"url": webhook_url},
        timeout=20
    )

    logger.info("Telegram webhook registration: %s", response.text)
    print("Telegram webhook registration response:", response.text)
else:
    logger.error("Telegram webhook configuration missing")
    print("Error: TELEGRAM_BOT_TOKEN or RENDER_EXTERNAL_URL not set in environment variables")


def run_pre_market_job():
    """Run the job and log success or failure."""
    logger.info("Pre-market brief job started")
    print("Running pre-market brief job...")

    try:
        send_pre_market_brief_to_all()
        logger.info("Pre-market brief job completed")
        print("Pre-market brief job completed successfully")
    except Exception:
        logger.exception("Pre-market brief job failed")
        print("Error occurred during pre-market brief job execution")
        raise


# Start scheduler when this module is loaded.
scheduler = BackgroundScheduler(
    timezone=IST,
    job_defaults={"coalesce": True, "max_instances": 1},
)

scheduler.add_job(
    func=run_pre_market_job,
    trigger="cron",
    hour=0,
    minute=10,
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
    print("Scheduler status:", scheduler.running)
    print("Next run time:", job.next_run_time if job else None)

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
    print("Received Telegram update:", update)

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
        print("Error processing Telegram update:", update)
        return jsonify({"ok": False}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    print(f"Starting Flask app on port {port}...")

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

