
import os
import logging
import threading
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
from flask import Flask, jsonify, request
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler

# Load environment variables before importing telegram.py
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

from telegram import handle_telegram_update

IST = ZoneInfo("Asia/Kolkata")
app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ---------------- FLASK ROUTES ----------------

@app.get("/")
def home():
    return jsonify({
        "app": "USPARK Market Updates",
        "status": "running",
        "timezone": "Asia/Kolkata",
        "hourly_schedule": "Every hour at HH:00",
        "prewake_schedule": "Every hour at HH:55",
    })


@app.get("/health")
def health():
    return jsonify({"status": "ok"}), 200


# NEW: Receive Telegram /start updates
@app.post("/telegram-webhook")
def telegram_webhook():
    update = request.get_json(silent=True)

    if not isinstance(update, dict):
        return jsonify({"ok": False, "error": "Invalid update"}), 400

    try:
        logging.info("Telegram update received")

        handle_telegram_update(update)

        return jsonify({"ok": True}), 200

    except Exception:
        logging.exception("Telegram webhook processing failed")
        return jsonify({"ok": False}), 500


if __name__ == "__main__":


    port = int(os.environ.get("PORT", "5000"))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
