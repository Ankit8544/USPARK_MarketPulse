
import os
import logging
from pathlib import Path

import requests
from flask import Flask, jsonify, request
from dotenv import load_dotenv
from redis import Redis
from rq import Queue, Retry

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

from telegram import handle_telegram_update

app = Flask(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL")
REDIS_URL = os.getenv("REDIS_URL")

if not REDIS_URL:
    raise RuntimeError("REDIS_URL is missing")

redis_conn = Redis.from_url(
    REDIS_URL,
    socket_connect_timeout=10,
    socket_timeout=10,
    health_check_interval=30,
)

redis_conn.ping()

telegram_queue = Queue(
    "telegram",
    connection=redis_conn,
    default_timeout=240,
)


def register_webhook():
    if not BOT_TOKEN or not RENDER_URL:
        logger.warning("Webhook configuration missing")
        return

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
            json={
                "url": f"{RENDER_URL.rstrip('/')}/telegram-webhook"
            },
            timeout=20,
        )
        response.raise_for_status()

        result = response.json()
        if not result.get("ok"):
            logger.error("Webhook registration failed: %s", result)
        else:
            logger.info("Telegram webhook registered")

    except requests.RequestException:
        logger.exception("Webhook registration error")


register_webhook()


@app.get("/")
def home():
    return jsonify({
        "app": "USPARK Market Updates",
        "status": "running",
    })


@app.get("/health")
def health():
    try:
        redis_conn.ping()
        return jsonify({
            "status": "ok",
            "redis": "connected",
        }), 200
    except Exception:
        logger.exception("Redis health check failed")
        return jsonify({
            "status": "error",
            "redis": "disconnected",
        }), 503


@app.post("/telegram-webhook")
def telegram_webhook():
    update = request.get_json(silent=True)

    if not isinstance(update, dict):
        return jsonify({"ok": False}), 400

    update_id = update.get("update_id")

    if update_id is None:
        return jsonify({"ok": False}), 400

    dedupe_key = f"telegram:update:{update_id}"

    try:
        is_new = redis_conn.set(
            dedupe_key,
            "queued",
            nx=True,
            ex=86400,
        )

        if not is_new:
            return jsonify({"ok": True}), 200

        telegram_queue.enqueue(
            handle_telegram_update,
            update,
            job_id=f"telegram-{update_id}",
            job_timeout=240,
            result_ttl=0,
            failure_ttl=86400,
            retry=Retry(
                max=3,
                interval=[5, 15, 30],
            ),
        )

        return jsonify({"ok": True}), 200

    except Exception:
        redis_conn.delete(dedupe_key)
        logger.exception("Telegram update enqueue failed")
        return jsonify({"ok": False}), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=False,
        use_reloader=False,
    )
