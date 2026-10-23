
import os
import logging
import threading
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from flask import Flask, jsonify
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler

from Functions import Gold_Price

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

IST = ZoneInfo("Asia/Kolkata")
app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

scheduler = BackgroundScheduler(timezone=IST)
send_lock = threading.Lock()


def send_gold_update():
    if not send_lock.acquire(blocking=False):
        logging.warning("Gold update already running")
        return False

    try:
        if not BOT_TOKEN or not CHAT_ID:
            raise RuntimeError("Missing Telegram environment variables")

        data = Gold_Price.get_gold_price()

        if not data or not data.get("ok", True):
            raise RuntimeError(f"Gold API returned invalid data: {data}")

        price = data.get("price")
        if price is None:
            raise RuntimeError("Gold price is missing")

        change = data.get("change")
        change_percent = data.get("change_percent")

        change_text = f"{change:+,.2f}" if change is not None else "N/A"
        percent_text = (
            f"{change_percent:+.2f}%"
            if change_percent is not None else "N/A"
        )

        now = datetime.now(IST).strftime("%d-%m-%Y %I:%M:%S %p IST")

        message = (
            f"🟡 {data['name']} ({data['symbol']})\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💰 Price: ${price:,.2f}\n"
            f"📊 Change: {change_text} ({percent_text})\n"
            f"🕒 Updated: {now}"
        )

        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": message},
            timeout=20,
        )
        response.raise_for_status()

        result = response.json()
        if not result.get("ok"):
            raise RuntimeError(f"Telegram rejected message: {result}")

        logging.info("Gold update sent successfully")
        return True

    except Exception:
        logging.exception("Could not send gold update")
        return False

    finally:
        send_lock.release()


@app.get("/")
def home():
    return jsonify({
        "app": "Gold Price Telegram Bot",
        "status": "running",
        "timezone": "Asia/Kolkata",
        "hourly_schedule": "Every hour at HH:00",
        "prewake_schedule": "Every hour at HH:55",
    })


@app.get("/health")
def health():
    return jsonify({"status": "ok"}), 200


@app.post("/send-now")
def send_now():
    threading.Thread(target=send_gold_update, daemon=True).start()
    return jsonify({"status": "triggered"}), 202


def start_scheduler():
    if scheduler.running:
        return

    # Internal scheduler: useful while the process is awake.
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

    # Pre-wakeup request to this app five minutes before each hour.
    # This is a fallback only; it cannot run while the app sleeps.
    def prewake():
        logging.info("Pre-wakeup time reached: %s", datetime.now(IST))
        try:
            requests.get(
                os.getenv("RENDER_EXTERNAL_URL", "http://127.0.0.1:5000")
                + "/health",
                timeout=10,
            )
        except requests.RequestException:
            logging.exception("Pre-wakeup request failed")

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


if __name__ == "__main__":
    start_scheduler()

    # Send one message immediately when this process starts.
    send_gold_update()

    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
