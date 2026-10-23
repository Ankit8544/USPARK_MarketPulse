
import os
import requests
from html import escape
from datetime import datetime
from zoneinfo import ZoneInfo
from pymongo import ReturnDocument
from Functions.MongoDB import users_collection, get_all_chat_ids
from Functions.Pre_Market_Brief import get_pre_market_brief

IST = ZoneInfo("Asia/Kolkata")

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
    last_name = user.get("last_name") or ""
    username = user.get("username")

    full_name = f"{first_name.strip()} {last_name.strip()}".strip()

    if full_name:
        name = full_name
    elif username:
        name = f"@{username}"
    else:
        name = "there"

    name = escape(name)

    return (
        f"👋 <b>WELCOME, {name}!</b>\n"
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
    """Save/update Telegram user details when /start is received."""

    message = update.get("message") or {}
    text = message.get("text") or ""
    chat = message.get("chat") or {}
    user = message.get("from") or {}
    chat_id = chat.get("id")

    if not chat_id:
        return

    command = text.split()[0].split("@")[0] if text.strip() else ""

    if command != "/start":
        return

    user_id = user.get("id")

    if not user_id:
        return

    now = datetime.now(IST)

    # Save a new user or update the existing user's document.
    # user_id is unique, so repeated /start commands won't
    # create duplicate documents.
    saved_user = users_collection.find_one_and_update(
        {"user_id": user_id},
        {
            "$set": {
                "username": user.get("username"),
                "first_name": user.get("first_name"),
                "last_name": user.get("last_name"),
                "language_code": user.get("language_code"),
                "is_bot": user.get("is_bot", False),
                "chat_id": chat_id,
                "chat_type": chat.get("type"),
                "last_start_at": now,
                "updated_at": now,
            },
            "$setOnInsert": {
                "user_id": user_id,
                "first_start_at": now,
            },
            "$inc": {
                "start_count": 1,
            },
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )

    # Send welcome message after the database operation succeeds.
    welcome_post = create_welcome_post(user)
    send_message(chat_id, welcome_post)

def format_pre_market_post(data):
    """Format pre-market data as a Telegram HTML post."""

    def value(item, key, default="N/A"):
        result = item.get(key)
        return escape(str(result)) if result is not None else default

    gold = data["gold"]
    usd = data["usd_inr"]
    sensex = data["bse_sensex"]
    nifty = data["nse_nifty_50"]
    nse = data["ujjivan_sfb_nse"]
    bse = data["ujjivan_sfb_bse"]

    generated_at = datetime.fromisoformat(
        data["generated_at"]
    ).astimezone(IST).strftime("%d %b %Y | %I:%M %p IST")

    return (
        "📊 <b>USPARK MARKET UPDATES</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🌅 <b>PRE-MARKET BRIEF</b>\n"
        f"📅 {generated_at}\n\n"

        "🪙 <b>GOLD</b>\n"
        f"Price: ₹{value(gold, 'price')}\n"
        f"Change: {value(gold, 'change')}"
        f" ({value(gold, 'change_percent')})\n\n"

        "💵 <b>USD / INR</b>\n"
        f"Rate: ₹{value(usd, 'rate')}\n"
        f"Change: {value(usd, 'change_percent')}\n\n"

        "📈 <b>BSE SENSEX</b>\n"
        f"Level: {value(sensex, 'price')}\n"
        f"Change: {value(sensex, 'change')}"
        f" ({value(sensex, 'change_percent')})\n\n"

        "📉 <b>NSE NIFTY 50</b>\n"
        f"Level: {value(nifty, 'price')}\n"
        f"Change: {value(nifty, 'change')}"
        f" ({value(nifty, 'change_percent')})\n\n"

        "🏦 <b>UJJIVAN SFB</b>\n"
        f"NSE: ₹{value(nse, 'price')} | "
        f"Change: {value(nse, 'change_percent')}\n"
        f"BSE: ₹{value(bse, 'price')} | "
        f"Change: {value(bse, 'change_percent')}\n\n"

        "━━━━━━━━━━━━━━━━━━━━\n"
        "ℹ️ Market data may be delayed or indicative.\n"
        "💚 <b>Stay Informed. Understand the Market.</b>"
    )

def send_pre_market_brief_to_all():
    """Send the pre-market brief to all saved Telegram chats."""

    data = get_pre_market_brief()
    post = format_pre_market_post(data)
    chat_ids = get_all_chat_ids()

    sent = 0
    failed = 0

    for chat_id in chat_ids:
        try:
            send_message(chat_id, post)
            sent += 1
        except Exception as exc:
            failed += 1

