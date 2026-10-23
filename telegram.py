
import os
import requests
from html import escape

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is missing")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_message(chat_id, text):
    """Send a Telegram message."""
    response = requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        },
        timeout=15
    )
    response.raise_for_status()
    result = response.json()

    if not result.get("ok"):
        raise RuntimeError("Telegram message could not be sent")

    return result


def create_welcome_post(user):
    """Create a personalised welcome post."""
    first_name = user.get("first_name") or ""
    username = user.get("username")

    if first_name.strip():
        name = first_name.strip()
    elif username:
        name = f"@{username}"
    else:
        name = "there"

    name = escape(name)

    return (
        f"👋 <b>WELCOME, {name.upper()}!</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "📊 <b>USPARK Market Updates</b>\n\n"
        "Welcome to your daily market companion! 🚀\n\n"
        "💰 <b>What you can explore:</b>\n\n"
        "🪙 Gold Price Updates\n"
        "💵 USD/INR Exchange Rate\n"
        "📈 BSE Sensex Updates\n"
        "🏦 Ujjivan Small Finance Bank Share Price\n"
        "🤖 AI-Powered Market Insights\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "✨ <b>Stay Informed. Understand the Market.</b>\n\n"
        "Market data may be delayed or indicative. "
        "AI insights are for informational purposes only.\n\n"
        f"💚 Thanks for joining us, {name}!"
    )


def handle_telegram_update(update):
    """Process incoming Telegram updates."""
    message = update.get("message") or {}

    text = message.get("text") or ""
    chat = message.get("chat") or {}
    user = message.get("from") or {}
    chat_id = chat.get("id")

    if not chat_id:
        return

    command = text.split()[0].split("@")[0] if text.strip() else ""

    if command == "/start":
        welcome_post = create_welcome_post(user)
        send_message(chat_id, welcome_post)
