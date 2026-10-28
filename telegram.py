import os
import re
import logging
import requests
from html import escape
from datetime import datetime
from zoneinfo import ZoneInfo
from pymongo import ReturnDocument
from Functions.MongoDB import users_collection, get_all_chat_ids
from Functions.Pre_Market_Brief import get_pre_market_brief
from Functions.GeminiAI import AI_Generated_Answer

IST = ZoneInfo("Asia/Kolkata")
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is missing")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_message(chat_id, text, reply_to_message_id=None):
    """Send a Telegram HTML message to the specified chat only."""
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_to_message_id is not None:
        payload["reply_to_message_id"] = reply_to_message_id
        payload["allow_sending_without_reply"] = True
    response = requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=20)
    response.raise_for_status()
    result = response.json()
    if not result.get("ok"):
        raise RuntimeError("Telegram message could not be sent")
    return result


def get_display_name(user):
    """Return the user's Telegram name, safely escaped for Telegram HTML."""
    first_name = (user.get("first_name") or "").strip()
    last_name = (user.get("last_name") or "").strip()
    full_name = f"{first_name} {last_name}".strip()
    if not full_name:
        username = (user.get("username") or "").strip()
        full_name = f"@{username}" if username else "there"
    return escape(full_name)


def get_time_greeting(now=None):
    """Choose a greeting using India Standard Time."""
    now = now or datetime.now(IST)
    hour = now.astimezone(IST).hour
    if 5 <= hour < 12:
        return "Good Morning"
    if 12 <= hour < 17:
        return "Good Afternoon"
    if 17 <= hour < 21:
        return "Good Evening"
    return "Hello"


def create_personal_greeting(user):
    name = get_display_name(user)
    greeting = get_time_greeting()
    return f"👋 <b>{greeting}, {name}!</b>\n\nHow can I help you today? 😊"


def create_welcome_post(user):
    """Create a personalised welcome post for /start."""
    name = get_display_name(user)
    greeting = get_time_greeting()
    return (
        f"👋 <b>{greeting}, {name}!</b> Welcome to your daily market companion! 🚀\n\n"
        "💰 <b>What you can explore:</b>\n"
        "🪙 Gold Price Updates\n"
        "💵 USD/INR Exchange Rate\n"
        "📈 BSE Sensex Updates\n"
        "🏦 Ujjivan Small Finance Bank Share Price\n"
        "🤖 AI-powered answers and market insights\n\n"
        "💬 Send <b>Hi</b> to get started or type your question."
    )


_GREETING_MESSAGES = {
    "hi", "hii", "hiii", "hello", "hey", "heyy", "helo",
    "good morning", "good afternoon", "good evening", "good night",
}


def is_simple_greeting(text):
    """Match greetings without accidentally swallowing real questions."""
    cleaned = re.sub(r"[^a-z\s]", "", (text or "").lower()).strip()
    return cleaned in _GREETING_MESSAGES


def save_or_update_user(user, chat, is_start=False):
    """Persist the sender's Telegram profile, keyed by Telegram user ID."""
    user_id = user.get("id")
    chat_id = chat.get("id")
    if not user_id or not chat_id or user.get("is_bot", False):
        return
    now = datetime.now(IST)
    update = {
        "$set": {
            "username": user.get("username"),
            "first_name": user.get("first_name"),
            "last_name": user.get("last_name"),
            "language_code": user.get("language_code"),
            "is_bot": user.get("is_bot", False),
            "chat_id": chat_id,
            "chat_type": chat.get("type"),
            "updated_at": now,
        },
        "$setOnInsert": {"user_id": user_id, "first_start_at": now},
    }
    if is_start:
        update["$set"]["last_start_at"] = now
        update["$inc"] = {"start_count": 1}
    users_collection.find_one_and_update(
        {"user_id": user_id}, update, upsert=True,
        return_document=ReturnDocument.AFTER,
    )


def answer_with_ai(chat_id, message_text, message_id=None):
    """Send a processing notice, ask Gemini, and reply to this same chat."""
    send_message(
        chat_id,
        "⏳ <b>Please wait...</b>\nAI is preparing your answer.",
        reply_to_message_id=message_id,
    )
    prompt = (
        "You are a helpful assistant inside a Telegram bot. "
        "Answer the user's question clearly, accurately, and concisely. "
        "If you are unsure, say so instead of inventing facts.\n\n"
        f"User's question:\n{message_text}"
    )
    answer = AI_Generated_Answer(prompt)
    if not answer or not answer.strip():
        answer = "⚠️ I couldn't generate an answer just now. Please try again."
    safe_answer = escape(answer.strip())
    send_message(chat_id, f"🤖 <b>Answer</b>\n\n{safe_answer}", reply_to_message_id=message_id)


def handle_telegram_update(update):
    """Handle /start, simple greetings, and AI questions from Telegram."""
    message = update.get("message") or update.get("edited_message") or {}
    text = (message.get("text") or "").strip()
    chat = message.get("chat") or {}
    user = message.get("from") or {}
    chat_id = chat.get("id")
    message_id = message.get("message_id")
    if not chat_id or not user.get("id") or not text or user.get("is_bot", False):
        return

    command = text.split()[0].split("@")[0].lower()
    save_or_update_user(user, chat, is_start=(command == "/start"))
    if command == "/start":
        send_message(chat_id, create_welcome_post(user), reply_to_message_id=message_id)
        return
    if command == "/help":
        send_message(
            chat_id,
            "💬 Say <b>Hi</b> for a personalised greeting or send me a question.\n"
            "📊 I can also help with market-related questions.",
            reply_to_message_id=message_id,
        )
        return
    if is_simple_greeting(text):
        send_message(chat_id, create_personal_greeting(user), reply_to_message_id=message_id)
        return

    # Both processing and final answers use this incoming update's chat_id.
    answer_with_ai(chat_id, text, message_id)


def format_pre_market_post(data, user=None):
    """Format the morning market update as a personalised Telegram HTML post."""
    user = user or {}
    first_name = (user.get("first_name") or "").strip()
    last_name = (user.get("last_name") or "").strip()
    full_name = f"{first_name} {last_name}".strip()
    if not full_name:
        full_name = (user.get("username") or "there").strip()
        if full_name != "there":
            full_name = f"@{full_name}"
    safe_name = escape(full_name)

    def value(item, key, default="N/A"):
        result = item.get(key)
        return escape(str(result)) if result is not None else default

    def number(item, key, prefix="", suffix="", default="N/A"):
        """Format numeric values to two decimal places with separators and symbols."""
        result = item.get(key)
        if result is None:
            return default
        try:
            cleaned = str(result).replace(",", "").replace("₹", "").replace("$", "").strip()
            formatted = f"{float(cleaned):,.2f}"
        except (TypeError, ValueError):
            return escape(str(result))
        return f"{prefix}{formatted}{suffix}"

    def percent(item, key):
        return number(item, key, suffix="%")

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
        f"<b>🌅 Good Morning, {safe_name}!</b> 👋 | 📊 Your Daily Market Update for {generated_at} — Stay Informed, Stay Ahead! 🚀\n\n"

        "🪙 <b>GOLD</b>\n"
        f"Price per 10gm: {number(gold, 'price_after_import_duty_per_10g', prefix='₹')}\n"
        f"Change: {number(gold, 'change_inr_per_10g', prefix='₹')}"
        f" ({percent(gold, 'change_inr_percent')})\n\n"

        "💵 <b>USD / INR</b>\n"
        f"Rate: {number(usd, 'rate', prefix='₹')}\n"
        f"Change: {percent(usd, 'change_percent')}\n\n"

        "📈 <b>BSE SENSEX</b>\n"
        f"Level: {number(sensex, 'price')}\n"
        f"Change: {number(sensex, 'change')}"
        f" ({percent(sensex, 'change_percent')})\n\n"

        "📉 <b>NSE NIFTY 50</b>\n"
        f"Level: {number(nifty, 'price')}\n"
        f"Change: {number(nifty, 'change')}"
        f" ({percent(nifty, 'change_percent')})\n\n"

        "🏦 <b>UJJIVAN SFB</b>\n"
        f"NSE: {number(nse, 'price', prefix='₹')} | "
        f"Change: {percent(nse, 'change_percent')}\n"
        f"BSE: {number(bse, 'price', prefix='₹')} | "
        f"Change: {percent(bse, 'change_percent')}\n\n"

        "━━━━━━━━━━━━━━━━━━━━\n"
        "ℹ️ Market data may be delayed or indicative.\n"
        "💚 <b>Stay Informed. Understand the Market.</b>"
    )

def send_pre_market_brief_to_all():
    """Send the pre-market brief to all saved Telegram chats."""

    data = get_pre_market_brief()
    chat_ids = get_all_chat_ids()

    sent = 0
    failed = 0

    for chat_id in chat_ids:
        try:
            user = users_collection.find_one({"chat_id": chat_id}) or {}
            post = format_pre_market_post(data, user)
            send_message(chat_id, post)
            sent += 1
        except Exception as exc:
            failed += 1

