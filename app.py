import os
import logging
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, request
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler

# Load environment variables before importing telegram.py
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

from telegram import (
    handle_telegram_update,
    send_pre_market_brief_to_all,
)

IST = ZoneInfo("Asia/Kolkata")
app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ---------------- SCHEDULER ----------------

scheduler = BackgroundScheduler(timezone=IST)

scheduler.add_job(
    func=send_pre_market_brief_to_all,
    trigger="cron",
    hour=8,
    minute=45,
    id="pre_market_brief",
    replace_existing=True,
    misfire_grace_time=3600,
)


# ---------------- FLASK ROUTES ----------------

@app.get("/")
def home():
    return jsonify({
        "app": "USPARK Market Updates",
        "status": "running",
        "timezone": "Asia/Kolkata",
        "pre_market_schedule": "Every day at 08:45 AM IST",
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
            "error": "Invalid update"
        }), 400

    try:
        logging.info("Telegram update received")
        handle_telegram_update(update)
        return jsonify({"ok": True}), 200

    except Exception:
        logging.exception("Telegram webhook processing failed")
        return jsonify({"ok": False}), 500


# ---------------- START APPLICATION ----------------

if __name__ == "__main__":
    scheduler.start()
    logging.info(
        "Pre-market scheduler started: "
        "daily at 08:45 AM IST"
    )

    print("Starting Flask app...")
    print("Pre-market scheduler started: daily at 08:45 AM IST")
    
    port = int(os.environ.get("PORT", "5000"))

    try:
        app.run(
            host="0.0.0.0",
            port=port,
            debug=False
        )
    finally:
        scheduler.shutdown(wait=False)

