
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

from Functions import Gold_Price
from telegram import handle_telegram_update

IST = ZoneInfo("Asia/Kolkata")
app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

scheduler = BackgroundScheduler(timezone=IST)
send_lock = threading.Lock()


# ---------------- TELEGRAM WEBHOOK SETUP ----------------

def configure_telegram_webhook():
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is missing")
        return

    base_url = (
        os.getenv("TELEGRAM_WEBHOOK_URL")
        or os.getenv("RENDER_EXTERNAL_URL")
    )

    if not base_url:
        logger.error(
            "Set RENDER_EXTERNAL_URL or TELEGRAM_WEBHOOK_URL"
        )
        return

    webhook_url = base_url.rstrip("/") + "/telegram-webhook"

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
            json={"url": webhook_url},
            timeout=20,
        )
        response.raise_for_status()
        result = response.json()

        if result.get("ok"):
            logger.info("Telegram webhook configured: %s", webhook_url)
        else:
            logger.error("Webhook registration failed: %s", result)

    except Exception:
        logger.exception("Could not configure Telegram webhook")


# ---------------- GOLD PRICE UPDATE ----------------

def send_gold_update():
    if not send_lock.acquire(blocking=False):
        logger.warning("Gold update already running")
        return False

    try:
        if not BOT_TOKEN or not CHAT_ID:
            raise RuntimeError("Missing Telegram environment variables")

        data = Gold_Price.get_gold_price()

        if not data or not data.get("ok", True):
            raise RuntimeError(f"Invalid gold data: {data}")

        price = data.get("price")
        if price is None:
            raise RuntimeError("Gold price is missing")

        change = data.get("change")
        change_percent = data.get("change_percent")

        change_text = (
            f"{change:+,.2f}" if change is not None else "N/A"
        )
        percent_text = (
            f"{change_percent:+.2f}%"
            if change_percent is not None else "N/A"
        )

        now = datetime.now(IST).strftime(
            "%d-%m-%Y %I:%M:%S %p IST"
        )

        message = (
            f"🟡 {data['name']} ({data['symbol']})\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"💰 Price: ${price:,.2f}\n"
            f"📊 Change: {change_text} ({percent_text})\n"
            f"🕒 Updated: {now}"
        )

        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": message},
            timeout=20,
        )
        response.raise_for_status()

        result = response.json()
        if not result.get("ok"):
            raise RuntimeError(f"Telegram rejected message: {result}")

        logger.info("Gold update sent successfully")
        return True

    except Exception:
        logger.exception("Could not send gold update")
        return False

    finally:
        send_lock.release()


# ---------------- FLASK ROUTES ----------------

@app.get("/")
def home():
    return jsonify({
        "app": "USPARK Market Updates",
        "status": "running",
        "timezone": "Asia/Kolkata",
    })


@app.get("/health")
def health():
    return jsonify({"status": "ok"}), 200


@app.post("/telegram-webhook")
def telegram_webhook():
    update = request.get_json(silent=True)

    if not isinstance(update, dict):
        return jsonify({"ok": False, "error": "Invalid update"}), 400

    try:
        logger.info(
            "Telegram update received; update_id=%s",
            update.get("update_id")
        )

        handle_telegram_update(update)

        return jsonify({"ok": True}), 200

    except Exception:
        logger.exception("Telegram update processing failed")
        return jsonify({"ok": False}), 500


@app.post("/send-now")
def send_now():
    threading.Thread(
        target=send_gold_update,
        daemon=True
    ).start()

    return jsonify({"status": "triggered"}), 202


# ---------------- SCHEDULER ----------------

def start_scheduler():
    if scheduler.running:
        return

    scheduler.add_job(
        send_gold_update,
        "cron",
        minute=0,
        id="hourly_gold",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )

    def prewake():
        base_url = (
            os.getenv("RENDER_EXTERNAL_URL")
            or "http://127.0.0.1:5000"
        )

        try:
            requests.get(
                base_url.rstrip("/") + "/health",
                timeout=10,
            ).raise_for_status()
        except requests.RequestException:
            logger.exception("Pre-wakeup request failed")

    scheduler.add_job(
        prewake,
        "cron",
        minute=55,
        id="hourly_prewake",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )

    scheduler.start()
    logger.info("Gold price scheduler started")


# Register webhook and start scheduler when the app loads.
# Use a single Gunicorn worker to avoid duplicate schedulers.
configure_telegram_webhook()
start_scheduler()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
