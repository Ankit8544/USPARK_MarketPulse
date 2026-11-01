import os
import re
import json
import logging
import requests
from html import escape
from datetime import datetime
from zoneinfo import ZoneInfo
from pymongo import ReturnDocument

from Functions.MongoDB import users_collection, get_all_chat_ids
from Functions.Pre_Market_Brief import get_pre_market_brief
from Functions.Openroute import AI_Generated_Answer
from Functions import (
    Gold_Price,
    Silver_Price,
    USD_INR_rate,
    BSE_Sensex,
    NSE_Nifty_50,
    Ujjivan_SFB_NSE,
    Ujjivan_SFB_BSE,
)

IST = ZoneInfo("Asia/Kolkata")
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is missing")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_message(chat_id, text, reply_to_message_id=None):
    """Send a normal Telegram message without quoting the original."""
    response = requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
        },
        timeout=20,
    )
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
    first_name = (user.get("first_name") or "").strip()

    if not first_name:
        first_name = get_display_name(user)

    name = escape(first_name)
    greeting = get_time_greeting()

    return f"👋 <b>{greeting} {name}</b>, how can I help you today? 😊"


def create_welcome_post(user):
    """Create a personalised welcome post for /start."""
    name = get_display_name(user)
    greeting = get_time_greeting()

    return (
        f"👋 <b>{greeting}, {name}!</b> Welcome to your daily market companion! 🚀\n\n"
        "💰 <b>What you can explore:</b>\n"
        "🪙 Gold and Silver Price Updates\n"
        "💵 USD/INR Exchange Rate\n"
        "📈 BSE Sensex and NSE Nifty 50 Updates\n"
        "🏦 Ujjivan Small Finance Bank Share Price\n"
        "🌍 Research-backed market news and explanations\n"
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
        "$setOnInsert": {
            "user_id": user_id,
            "first_start_at": now,
        },
    }

    if is_start:
        update["$set"]["last_start_at"] = now
        update["$inc"] = {"start_count": 1}

    users_collection.find_one_and_update(
        {"user_id": user_id},
        update,
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )


def _fetch_market_item(label, fetch_function):
    """Fetch one market source without failing the whole snapshot."""
    try:
        result = fetch_function()

        if isinstance(result, dict):
            if result.get("ok"):
                return result

            return {
                "ok": False,
                "error": result.get("error", f"{label} data unavailable"),
            }

        return {"ok": False, "error": f"{label} returned an invalid response"}

    except Exception as exc:
        logger.exception("Could not fetch %s market data", label)
        return {"ok": False, "error": f"{label} fetch failed: {type(exc).__name__}"}


def get_live_market_context():
    """
    Collect all market instruments exposed by the existing Functions modules.
    This is a fresh snapshot, not a complete exchange feed or historical database.
    """
    generated_at = datetime.now(IST).isoformat()

    sources = {
        "bse_sensex": ("BSE Sensex", BSE_Sensex.get_bse_sensex),
        "nse_nifty_50": ("NSE Nifty 50", NSE_Nifty_50.get_nse_nifty50),
        "ujjivan_sfb_nse": ("Ujjivan SFB NSE", Ujjivan_SFB_NSE.get_ujjivan_sfb_nse),
        "ujjivan_sfb_bse": ("Ujjivan SFB BSE", Ujjivan_SFB_BSE.get_ujjivan_sfb_bse),
        "gold": ("COMEX Gold", Gold_Price.get_gold_price),
        "silver": ("Silver Futures", Silver_Price.get_silver_price),
        "usd_inr": ("USD/INR", USD_INR_rate.get_usd_inr),
    }

    snapshot = {
        "generated_at_ist": generated_at,
        "timezone": "Asia/Kolkata",
        "data_note": (
            "Values come from the bot's existing Yahoo Finance-based functions. "
            "They represent the latest available provider candles/quotes, may be "
            "delayed, and must be interpreted using each instrument's market_time "
            "and fetched_at. Missing values are not zero."
        ),
        "instruments": {},
    }

    for key, (label, fetch_function) in sources.items():
        snapshot["instruments"][key] = _fetch_market_item(label, fetch_function)

    return snapshot


def _format_ai_answer_for_telegram(answer):
    """Escape AI output safely while preserving Markdown source links as Telegram links."""
    links = []

    def save_link(match):
        label, url = match.group(1), match.group(2)
        placeholder = f"__TELEGRAM_LINK_{len(links)}__"

        links.append(
            f'<a href="{escape(url, quote=True)}">{escape(label)}</a>'
        )

        return placeholder

    answer_with_placeholders = re.sub(
        r"\[([^\]]+)\]\((https?://[^\s)]+)\)",
        save_link,
        answer,
    )

    safe_text = escape(answer_with_placeholders)

    for index, anchor in enumerate(links):
        safe_text = safe_text.replace(f"__TELEGRAM_LINK_{index}__", anchor)

    return safe_text


def answer_with_ai(chat_id, message_text, message_id=None):
    """Fetch the available market snapshot and ask OpenRouter for a researched answer."""
    send_message(
        chat_id,
        "⏳ <b>Researching your question and checking available market data...</b>",
        reply_to_message_id=message_id,
    )

    market_context = get_live_market_context()

    prompt = (
        "CURRENT DATE AND TIME (India Standard Time): "
        f"{datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST')}\n\n"
        "LIVE MARKET SNAPSHOT FROM THIS BOT (JSON):\n"
        f"{json.dumps(market_context, ensure_ascii=False, default=str)}\n\n"
        "INSTRUCTIONS:\n"
        "- Use the snapshot whenever it is relevant to the question.\n"
        "- Check the timestamps for every instrument; do not assume all quotes "
        "are from the same time or are live.\n"
        "- For current market explanations, research the latest relevant news, "
        "official announcements and macro/market data using web search.\n"
        "- Explain the strongest evidence-backed reasons, and distinguish "
        "confirmed facts from likely contributors and unconfirmed possibilities.\n"
        "- Include source names, dates and URLs/citations. Do not invent missing data.\n"
        "- If the question is unrelated to markets, answer it normally.\n\n"
        f"USER'S QUESTION:\n{message_text}"
    )

    answer = AI_Generated_Answer(prompt)

    if not answer or not answer.strip():
        answer = "⚠️ I couldn't generate an answer just now. Please try again."

    safe_answer = _format_ai_answer_for_telegram(answer.strip())

    send_message(
        chat_id,
        safe_answer,
        reply_to_message_id=message_id,
    )


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
        send_message(
            chat_id,
            create_welcome_post(user),
            reply_to_message_id=message_id,
        )
        return

    if command == "/help":
        send_message(
            chat_id,
            "💬 Say <b>Hi</b> for a personalised greeting or send me a question.\n"
            "📊 I can help with market data, current market news and research-backed "
            "explanations of market movements.",
            reply_to_message_id=message_id,
        )
        return

    if is_simple_greeting(text):
        send_message(
            chat_id,
            create_personal_greeting(user),
            reply_to_message_id=message_id,
        )
        return

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
            cleaned = (
                str(result)
                .replace(",", "")
                .replace("₹", "")
                .replace("$", "")
                .strip()
            )
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
        f"<b>🌅 Good Morning {safe_name}</b>, Your Daily Market Update for {generated_at} — Stay Informed, Stay Ahead! 🚀\n\n"
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

        except Exception:
            failed += 1
            logger.exception(
                "Could not send pre-market brief to chat_id=%s",
                chat_id,
            )

    logger.info(
        "Pre-market brief delivery complete: sent=%s failed=%s",
        sent,
        failed,
    )