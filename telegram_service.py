import os
import requests
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parent / ".env", override=True)


def send_telegram_message(message: str) -> dict:
    """Send one text message to the configured Telegram chat."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables")

    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={"chat_id": chat_id, "text": message},
        timeout=25,
    )
    response.raise_for_status()
    result = response.json()
    if not result.get("ok"):
        raise RuntimeError(f"Telegram API rejected message: {result}")
    return result
