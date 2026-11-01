from dotenv import load_dotenv
import os
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import requests
import re
import yfinance as yf

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# OpenRouter API credentials
OPENROUTER_API_KEYS = [
    os.getenv("OPENROUTER_API_KEY"),
    os.getenv("OPENROUTER_API_KEY_2"),
    os.getenv("OPENROUTER_API_KEY_3"),
]
OPENROUTER_API_KEYS = [key.strip() for key in OPENROUTER_API_KEYS if key and key.strip()]

# OpenRouter model
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")
BASE_URL = "https://openrouter.ai/api/v1/chat/completions"


TAVILY_URL = "https://api.tavily.com/search"


def _tavily_market_research(prompt: str, symbol: str = None) -> str:
    """Research dated real-world catalysts; never use quote/price movement as causal evidence."""
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        return "NEWS_RESEARCH_UNAVAILABLE: TAVILY_API_KEY is not configured."

    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    today = now.strftime("%d %B %Y")
    start_date = (now - timedelta(days=7)).strftime("%d %B %Y")
    company = "Ujjivan Small Finance Bank" if symbol == "UJJIVANSFB.NS" or "ujjivan" in prompt.lower() else "the company or market named in the user's question"

    prompt_lower = (prompt or "").lower()
    if "nifty" in prompt_lower:
        focus_queries = [
            f"Nifty 50 latest completed trading session {today} market drivers sector contribution heavyweight stocks earnings",
            f"Nifty 50 October 30 2026 why market rose or fell IT stocks corporate earnings crude oil FII",
            f"India stock market latest seven days Nifty 50 sector rotation banking IT energy financials corporate results",
        ]
    elif "sensex" in prompt_lower:
        focus_queries = [
            f"BSE Sensex latest completed trading session {today} market drivers top constituent contributions earnings",
            f"Sensex October 30 2026 market drivers sector performance crude oil FII corporate earnings",
            f"India large cap stocks latest seven days sector news earnings policy developments",
        ]
    elif "usd" in prompt_lower or "inr" in prompt_lower or "rupee" in prompt_lower:
        focus_queries = [
            f"USD INR rupee latest seven days actual drivers RBI intervention dollar index US yields crude oil FPI flows",
            f"India rupee currency market latest official RBI forex policy trade balance oil prices",
            f"US dollar latest seven days Fed data Treasury yields currency markets",
        ]
    elif "gold" in prompt_lower or "silver" in prompt_lower:
        asset = "gold silver precious metals" if "gold" in prompt_lower and "silver" in prompt_lower else ("gold" if "gold" in prompt_lower else "silver")
        focus_queries = [
            f"{asset} latest seven days actual market drivers US real yields dollar central bank purchases ETF flows industrial demand",
            f"international {asset} market news latest week supply demand geopolitical central bank",
            f"India {asset} prices import duty rupee MCX latest week drivers",
        ]
    elif "ujjivan" in prompt_lower:
        focus_queries = [
            f"Ujjivan Small Finance Bank latest seven days NSE BSE official announcements results management asset quality credit cost",
            f"Ujjivan Small Finance Bank latest news October 30 2026 stock underperformance small finance bank peers",
            f"India small finance bank sector latest week RBI regulation credit growth deposits slippages funding costs",
        ]
    else:
        focus_queries = [
            f"India financial markets latest seven days verified market-moving economic events policy data earnings",
            f"global markets latest seven days verified macroeconomic events central bank decisions commodities geopolitical risks",
        ]

    queries = focus_queries + [
        f"India economic and financial news {start_date} to {today}: RBI policy liquidity inflation bond yields rupee crude oil FII flows",
        f"global macroeconomic events {start_date} to {today}: US Federal Reserve Treasury yields dollar oil geopolitical developments emerging markets",
        f"India stock market catalysts {start_date} to {today}: corporate earnings policy announcements sector developments institutional flows",
        f"latest official economic releases and central bank decisions India US Europe Japan {start_date} to {today}",
        f"{company} latest official announcements earnings guidance regulatory news sector developments {start_date} to {today}",
        f"Indian banking and financial sector developments {start_date} to {today}: credit growth deposits asset quality funding costs RBI",
    ]

    results, seen_urls = [], set()
    for index, query in enumerate(queries):
        try:
            response = requests.post(
                TAVILY_URL,
                json={
                    "api_key": api_key,
                    "query": query,
                    "topic": "news",
                    "search_depth": "advanced",
                    "max_results": 7,
                    "include_answer": False,
                    "include_raw_content": False,
                    "time_range": "week",
                },
                timeout=(8, 25),
            )
            response.raise_for_status()
            data = response.json()
            for item in data.get("results", []):
                title = (item.get("title") or "").strip()
                content = (item.get("content") or "").strip()
                url = (item.get("url") or "").strip()
                published = item.get("published_date") or item.get("date") or "Publication date not supplied"
                if url and url in seen_urls:
                    continue
                if url:
                    seen_urls.add(url)
                if title or content:
                    results.append(
                        f"Search: {query}\nHeadline: {title}\nPublished: {published}\n"
                        f"URL: {url}\nEvidence: {content}"
                    )
        except (requests.RequestException, ValueError, TypeError) as exc:
            logger.warning("Market news search %s failed: %s", index + 1, exc)

    if not results:
        return "NO_RECENT_NEWS_RESULTS: No reliable current-week news found. Do not invent reasons."
    return (
        f"Research date: {today} IST. Strict event window: {start_date} to {today}.\n"
        "Use only events in this window as current catalysts. Older events are background only.\n\n"
        + "\n\n---\n\n".join(results[:35])
    )[:30000]

YAHOO_TICKERS = {
    "ujjivan": "UJJIVANSFB.NS",
    "ujjivan small finance bank": "UJJIVANSFB.NS",
    "nifty": "^NSEI",
    "sensex": "^BSESN",
    "gold": "GC=F",
    "silver": "SI=F",
    "usd/inr": "USDINR=X",
}


def _is_market_impact_question(prompt: str) -> bool:
    text = (prompt or "").lower()
    keywords = (
        "why", "reason", "fall", "fell", "down", "declin", "drop",
        "crash", "rally", "rise", "surge", "impact", "affect",
        "share price", "stock price", "shares", "market"
    )
    return any(word in text for word in keywords)


def _resolve_yahoo_ticker(prompt: str):
    text = (prompt or "").lower()

    if "ujjivan" in text:
        if re.search(r"\b(bse|bombay)\b", text):
            return "UJJIVANSFB.BO"
        return "UJJIVANSFB.NS"

    if "nifty" in text:
        # Nifty 50 is an NSE index; there is no BSE Nifty 50 index.
        return "^NSEI"
    if "sensex" in text:
        return "^BSESN"
    if "gold" in text:
        return "GC=F"
    if "silver" in text:
        return "SI=F"
    if "usd/inr" in text or "dollar" in text or "rupee" in text:
        return "USDINR=X"
    return None


def _yahoo_quote_and_history(symbol: str) -> str:
    """Prefer Yahoo Finance's latest intraday candle; fall back to its latest daily close."""
    try:
        ticker = yf.Ticker(symbol)
        now_utc = datetime.now(ZoneInfo("UTC"))
        today_ist = datetime.now(ZoneInfo("Asia/Kolkata")).date()

        daily = ticker.history(
            period="1mo",
            interval="1d",
            auto_adjust=False,
            actions=False,
            timeout=20,
        )
        if daily is None or daily.empty:
            daily = None
        else:
            daily = daily.dropna(subset=["Close"])
            if daily.empty:
                daily = None

        intraday = None
        try:
            intraday = ticker.history(
                period="5d",
                interval="5m",
                auto_adjust=False,
                actions=False,
                timeout=20,
            )
            if intraday is not None and not intraday.empty:
                intraday = intraday.dropna(subset=["Close"])
                if intraday.empty:
                    intraday = None
        except Exception as exc:
            logger.warning("Yahoo intraday quote unavailable for %s: %s", symbol, exc)

        price = None
        quote_date = None
        quote_kind = None

        # During an active trading session use the latest intraday candle.
        # Outside NSE/BSE regular hours (including weekends), prefer the completed daily close.
        local_now = datetime.now(ZoneInfo("Asia/Kolkata"))
        market_is_open_window = (
            local_now.weekday() < 5
            and (local_now.hour > 9 or (local_now.hour == 9 and local_now.minute >= 15))
            and (local_now.hour < 15 or (local_now.hour == 15 and local_now.minute < 30))
        )

        if intraday is not None and market_is_open_window:
            latest = intraday.iloc[-1]
            latest_time = intraday.index[-1]
            latest_dt = latest_time.to_pydatetime()
            if latest_dt.tzinfo is None:
                latest_dt = latest_dt.replace(tzinfo=ZoneInfo("UTC"))
            age_hours = (now_utc - latest_dt.astimezone(ZoneInfo("UTC"))).total_seconds() / 3600
            # Accept the latest Yahoo candle from the last 5 calendar days.
            if 0 <= age_hours <= 120:
                price = float(latest["Close"])
                quote_date = latest_dt.astimezone(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M %Z")
                quote_kind = "latest available Yahoo Finance 5-minute candle"

        if price is None and daily is not None:
            latest = daily.iloc[-1]
            latest_time = daily.index[-1]
            latest_date = latest_time.date()
            age_days = (today_ist - latest_date).days
            if age_days <= 5:
                price = float(latest["Close"])
                quote_date = latest_time.strftime("%Y-%m-%d")
                quote_kind = "latest available Yahoo Finance daily close"
            else:
                return (
                    f"Yahoo Finance data for {symbol} is stale: latest daily candle is "
                    f"{latest_date.isoformat()} ({age_days} calendar days old). "
                    "Do not present this as the current price; report that fresh Yahoo Finance data is unavailable."
                )

        if price is None:
            return f"Yahoo Finance returned no fresh price data for {symbol}."

        previous_close = None
        if daily is not None:
            quote_day = quote_date[:10]
            eligible = daily[[idx.strftime("%Y-%m-%d") < quote_day for idx in daily.index]]
            if not eligible.empty:
                previous_close = float(eligible.iloc[-1]["Close"])
            elif len(daily) >= 2:
                previous_close = float(daily.iloc[-2]["Close"])

        change = price - previous_close if previous_close is not None else None
        change_pct = (change / previous_close * 100) if previous_close else None

        return (
            f"Yahoo Finance ticker: {symbol}\n"
            f"Latest available Yahoo Finance price: {price:.4f}\n"
            f"Yahoo Finance quote/trading date: {quote_date}\n"
            f"Quote type: {quote_kind}\n"
            f"Previous daily close: {previous_close if previous_close is not None else 'unavailable'}\n"
            f"Change vs previous daily close: {change if change is not None else 'unavailable'}\n"
            f"Change percent: {change_pct if change_pct is not None else 'unavailable'}\n"
            "IMPORTANT: Use this Yahoo Finance price and its actual timestamp. Never substitute a price from a news snippet."
        )
    except Exception as exc:
        logger.exception("Yahoo Finance price retrieval failed for %s", symbol)
        return f"Yahoo Finance price retrieval failed for {symbol}: {type(exc).__name__}."

def _yahoo_news_for_ticker(symbol: str, prompt: str) -> str:
    """Retrieve news through Yahoo Finance only; no Tavily or other search provider."""
    items = []
    try:
        ticker = yf.Ticker(symbol)
        news = ticker.news or []
        for entry in news[:12]:
            content = entry.get("content") or {}
            title = content.get("title") or entry.get("title") or ""
            summary = content.get("summary") or entry.get("summary") or ""
            pub_date = content.get("pubDate") or entry.get("providerPublishTime") or ""
            provider = content.get("provider") or entry.get("publisher") or "Yahoo Finance"
            if isinstance(provider, dict):
                provider = provider.get("displayName", "Yahoo Finance")
            if title or summary:
                items.append(f"Title: {title}\nPublished: {pub_date}\nPublisher: {provider}\nSummary: {summary}")
    except Exception as exc:
        logger.warning("Yahoo Finance ticker news unavailable for %s: %s", symbol, exc)

    # Yahoo Finance search news broadens coverage to India/global market factors.
    search_terms = [
        prompt,
        "India banking stocks RBI liquidity interest rates foreign institutional investors global markets",
    ]
    Search = getattr(yf, "Search", None)
    if Search:
        for term in search_terms:
            try:
                search_result = Search(term, news_count=8)
                for entry in (getattr(search_result, "news", None) or [])[:8]:
                    title = entry.get("title", "")
                    summary = entry.get("summary", "")
                    pub_date = entry.get("providerPublishTime") or entry.get("pubDate") or ""
                    publisher = entry.get("publisher", "Yahoo Finance")
                    if title or summary:
                        items.append(
                            f"Title: {title}\nPublished: {pub_date}\nPublisher: {publisher}\nSummary: {summary}"
                        )
            except Exception as exc:
                logger.warning("Yahoo Finance news search failed: %s", exc)

    # Deduplicate and bound the context.
    unique = []
    seen = set()
    for item in items:
        key = item.splitlines()[0].strip().lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(item)
    return "\n\n".join(unique[:18]) if unique else "Yahoo Finance returned no recent news items for this query."


def yahoo_research(prompt: str) -> str:
    """Use Yahoo Finance for all prices; use current news research to explain market moves."""
    symbol = _resolve_yahoo_ticker(prompt)
    parts = [
        "PRICE SOURCE POLICY: Yahoo Finance is the source of truth for all prices, price changes and quote dates.",
        f"Current date/time (India): {datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%d %B %Y, %I:%M %p IST')}",
    ]

    if symbol:
        parts.append(_yahoo_quote_and_history(symbol))

    # Keep company leadership lookup where Yahoo Finance provides it.
    if symbol == "UJJIVANSFB.NS" and any(
        term in (prompt or "").lower()
        for term in ("ceo", "md", "managing director", "chief executive")
    ):
        try:
            profile = yf.Ticker(symbol).info or {}
            officers = profile.get("companyOfficers") or []
            officer_lines = []
            for officer in officers[:8]:
                name = officer.get("name")
                title = officer.get("title")
                if name or title:
                    officer_lines.append(f"{title or 'Officer'}: {name or 'Name unavailable'}")
            if officer_lines:
                parts.append("Yahoo Finance company officers:\n" + "\n".join(officer_lines))
        except Exception as exc:
            logger.warning("Yahoo Finance company profile unavailable: %s", exc)

    # News research is retained for reasons and wider market context.
    parts.append("Recent company, Indian-market and global-market research:\n" + _tavily_market_research(prompt, symbol))
    return "\n\n".join(parts)[:22000]


def _market_status_header(prompt: str, market_context: str, include_quote_details: bool = False) -> str:
    """Build a verified, price-free status line unless a false premise needs correcting."""
    symbol = _resolve_yahoo_ticker(prompt)
    if not symbol:
        return "MARKET STATUS: Latest verified data unavailable."

    price_match = re.search(r"Latest available Yahoo Finance price:\s*([0-9]+(?:\.[0-9]+)?)", market_context)
    date_match = re.search(r"Yahoo Finance quote/trading date:\s*([^\n]+)", market_context)
    change_match = re.search(r"Change percent:\s*(-?[0-9]+(?:\.[0-9]+)?)", market_context)

    labels = {
        "^NSEI": "NIFTY 50 (NSE)",
        "^BSESN": "SENSEX (BSE)",
        "USDINR=X": "USD/INR",
        "GC=F": "GOLD (GLOBAL FUTURES)",
        "SI=F": "SILVER (GLOBAL FUTURES)",
        "UJJIVANSFB.NS": "UJJIVAN SFB (NSE)",
        "UJJIVANSFB.BO": "UJJIVAN SFB (BSE)",
    }
    label = labels.get(symbol, symbol)

    if not date_match or not price_match or not change_match:
        return f"{label} — LATEST STATUS UNAVAILABLE"

    quote_date = date_match.group(1).strip()
    price = float(price_match.group(1))
    change_pct = float(change_match.group(1))

    if change_pct > 0.005:
        direction = "HIGHER"
    elif change_pct < -0.005:
        direction = "LOWER"
    else:
        direction = "FLAT"

    status = f"{label} — {direction}\nLatest session: {quote_date}"
    if include_quote_details:
        if symbol in ("GC=F", "SI=F"):
            unit = "USD per troy ounce"
        elif symbol == "USDINR=X":
            unit = "INR per USD"
        else:
            unit = "index points" if symbol in ("^NSEI", "^BSESN") else "INR per share"
        status += f"\nLast close: {price:,.2f} ({unit}) | Change: {change_pct:+.2f}%"
    return status



def _requested_market_direction(prompt: str):
    """Return the direction explicitly assumed or asked about by the user."""
    text = (prompt or "").lower()
    if re.search(r"\\b(up\\s+or\\s+down|down\\s+or\\s+up|rise\\s+or\\s+fall|fall\\s+or\\s+rise|green\\s+or\\s+red|red\\s+or\\s+green)\\b", text):
        return None
    if re.search(r"\b(fall|falling|fell|fallen|down|declin(?:e|ing|ed)?|drop(?:ping|ped)?|crash(?:ing|ed)?)\b", text):
        return "down"
    if re.search(r"\b(ris(?:e|ing)|rose|rising|up|gain(?:ing|ed)?|surge(?:d|ing)?)\b", text):
        return "up"
    return None


def _is_status_only_question(prompt: str) -> bool:
    """Detect direct direction/status questions that do not ask for reasons."""
    text = (prompt or "").lower().strip()
    asks_status = bool(re.search(
        r"\b(is|are|was|were|has|have|did|does|do)\b", text
    )) and bool(re.search(
        r"\b(fall|falling|fell|down|rise|rising|up|gain|gaining|flat|positive|negative|green|red|market status)\b",
        text
    ))
    asks_reason = bool(re.search(
        r"\b(why|reason|cause|factor|driver|because|what made|what caused)\b", text
    ))
    return asks_status and not asks_reason


def _build_intent_aware_market_reply(prompt: str, market_context: str, generated_answer: str = "") -> str:
    """Never explain a move that did not happen; answer status questions without unrelated factors."""
    header = _market_status_header(prompt, market_context)
    if "LATEST STATUS UNAVAILABLE" in header or "Latest verified data unavailable" in header:
        return (
            header + "\n"
            "I can't confirm the market direction from fresh Yahoo Finance data, so I won't guess the reason."
        )

    down_match = re.search(r"Change percent:\s*([+-]?[0-9]+(?:\.[0-9]+)?)", market_context)
    if not down_match:
        return header + "\nLatest market direction could not be verified."

    change_pct = float(down_match.group(1))
    actual_direction = "down" if change_pct < -0.005 else ("up" if change_pct > 0.005 else "flat")
    requested_direction = _requested_market_direction(prompt)

    if _is_status_only_question(prompt):
        if requested_direction == "down":
            if actual_direction == "down":
                return header + "\nYes. It is lower in the latest completed session."
            detailed_header = _market_status_header(prompt, market_context, include_quote_details=True)
            if actual_direction == "up":
                return detailed_header + "\nNo. It did not fall; it closed higher in the latest completed session."
            return detailed_header + "\nNo. It was nearly unchanged in the latest completed session."
        if requested_direction == "up":
            if actual_direction == "up":
                return header + "\nYes. It closed higher in the latest completed session."
            detailed_header = _market_status_header(prompt, market_context, include_quote_details=True)
            if actual_direction == "down":
                return detailed_header + "\nNo. It closed lower in the latest completed session."
            return detailed_header + "\nIt was nearly unchanged in the latest completed session."
        return header

    if requested_direction == "down" and actual_direction != "down":
        detailed_header = _market_status_header(prompt, market_context, include_quote_details=True)
        if actual_direction == "up":
            correction = "It did not fall in the latest completed session; it closed higher."
        else:
            correction = "It was nearly flat in the latest completed session, not meaningfully lower."
        return detailed_header + "\n" + correction + " So there is no fall to explain for that session."

    if requested_direction == "up" and actual_direction != "up":
        detailed_header = _market_status_header(prompt, market_context, include_quote_details=True)
        if actual_direction == "down":
            correction = "It did not rise in the latest completed session; it closed lower."
        else:
            correction = "It was nearly flat in the latest completed session."
        return detailed_header + "\n" + correction + " So there is no rise to explain for that session."

    formatted = _format_stock_reason_answer(generated_answer, prompt, market_context)
    if not formatted:
        return header + "\nVerified news evidence is not strong enough to identify the reasons."
    # Formatter already includes a status heading; retain the intent-checked header only once.
    marker = "\n\nWHY THE MARKET MOVED"
    if marker in formatted:
        formatted = formatted.split(marker, 1)[1]
        return header + marker + formatted
    return header + "\n" + formatted

def _format_stock_reason_answer(answer: str, prompt: str = "", market_context: str = "") -> str:
    """Format status first, then concise evidence-led factors in basic English."""
    text = (answer or "").replace("\r\n", "\n").replace("\\n", "\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    points, strongest, current = [], None, None

    for line in lines:
        line = re.sub(r"[*_`]", "", line).strip()
        if re.match(r"(?i)^(top\s*\d+\s*factors|market status|nifty 50\s*[—-]|sensex\s*[—-])", line):
            continue
        if re.match(r"(?i)^(based on|currently influenced|the following|here are|sources?|references?|citations?)", line):
            continue
        impact = re.match(r"(?i)^(?:biggest impact|strongest impact)\s*:\s*(.*)$", line)
        if impact:
            if current:
                points.append(current)
                current = None
            strongest = impact.group(1).strip()
            continue
        match = re.match(r"^\s*\d+[.)]\s*(.+)$", line)
        if match:
            if current:
                points.append(current)
            current = match.group(1).strip()
        elif current:
            current += " " + line

    if current:
        points.append(current)

    cleaned = []
    for point in points:
        point = re.sub(r"https?://\S+", "", point).strip()
        if re.search(r"(?i)(share price is|stock price is|trading at|quoted at|previous close|volume:|\bhigh:|\blow:)", point):
            continue
        if point:
            cleaned.append(point)

    cleaned = cleaned[:3]
    if not cleaned:
        return ""

    header = _market_status_header(prompt, market_context)
    output = [header, "", "WHY THE MARKET MOVED"]
    output.extend(f"{i}. {point}" for i, point in enumerate(cleaned, 1))
    output.append("BIGGEST IMPACT: " + (
        strongest if strongest else "Not conclusively identifiable from available evidence."
    ))
    return "\n".join(output)

def Gemini(prompt: str) -> str:
    """Generate concise, evidence-led answers using current web research."""
    if not OPENROUTER_API_KEYS:
        return "⚠️ AI unavailable: OpenRouter API key is missing."

    current_dt = datetime.now(ZoneInfo("Asia/Kolkata"))
    current_date = current_dt.strftime("%d %B %Y")
    search_data = yahoo_research(prompt)
    market_question = _is_market_impact_question(prompt)

    system_prompt = f"""
You are USPARK MarketPulse, a rigorous equity-research analyst focused on Indian stocks and global macro events.
SUPPORTED INSTRUMENTS:
- Nifty 50 (NSE index; if user says "BSE Nifty", understand they mean Nifty 50 but label it correctly as NSE).
- BSE Sensex.
- Gold and silver (Yahoo symbols GC=F and SI=F are global futures quoted in USD per troy ounce; do not describe them as Indian retail INR prices).
- Ujjivan Small Finance Bank NSE listing (UJJIVANSFB.NS).
- Ujjivan Small Finance Bank BSE listing (UJJIVANSFB.BO). Select the exchange explicitly named by the user; default to NSE only when no exchange is specified.

Current date/time in India: {current_dt.strftime("%d %B %Y, %I:%M %p IST")}.

MARKET SESSION / AS-OF RULES:
- Determine the current India date and weekday. NSE/BSE equity trading is normally Monday-Friday, 09:15-15:30 IST, excluding exchange holidays.
- If today is Saturday, Sunday or an exchange holiday, say the latest completed session date in the heading/context; never describe a closed-market day as "today's movement".
- For Sunday 1 November 2026, the latest regular NSE/BSE session is Friday 30 October 2026. Use 30 October as the latest completed session, not stale dates from earlier weeks.
- Do not use old stories (for example, 21 October) as fresh catalysts for 30 October unless a new development occurred in the current event window and is explicitly evidenced.
- A market is not moving just because a quote changed. Explain the underlying real-world event and its transmission mechanism.

RESEARCH METHOD:
1. Establish the exact stock, direction and relevant trading sessions using Yahoo Finance data privately.
2. Research the same event window using the supplied independent news results. Prioritise the most recent, date-matched evidence.
3. Separate findings into:
   A. Company-specific catalysts: results vs expectations, guidance, asset quality, slippages, credit cost, margins, deposits, funding costs, management changes, regulatory/exchange disclosures.
   B. Indian market/sector catalysts: Nifty/Sensex and Bank Nifty movement, small-finance-bank peer performance, RBI policy/liquidity, bond yields, INR, crude oil, inflation, FII/DII flows.
   C. Global catalysts: US Fed decisions/expectations, US Treasury yields, dollar strength, global risk-off moves, crude oil, geopolitical events and emerging-market flows.
4. Compare the stock's move with relevant indices and listed peers. If peers and the sector were also weak, explain the sector/macro channel. If the stock underperformed peers, investigate company-specific or stock-specific evidence.
5. Build a short timeline: what happened, when it happened, and whether it preceded or coincided with the stock move.
6. Explain the transmission mechanism in plain language: how the event can affect the bank's earnings, credit risk, funding cost, valuation or investor demand.

EVIDENCE RULES:
- For index/FX/commodity questions, investigate real-world drivers first: central-bank decisions, official economic data, fiscal/policy announcements, geopolitical developments, energy/supply disruptions, trade actions, company earnings and verified institutional flows.
- Match every catalyst to the exact instrument asked about. For Nifty 50, investigate index-weighted constituent earnings/news, sector contributions, RBI/macro policy, FII/DII flows and global spillovers; do not give generic USD/INR explanations unless they materially affected equities.
- Never infer FII inflows from an IPO listing or IPO share-price rise. IPO subscription/listing activity is not proof of foreign portfolio flows.
- Never claim a Fed rate hike is expected, crude is elevated, or institutional flows changed unless current dated research explicitly verifies it.
- For Nifty/Sensex, identify the latest completed Indian trading session and explain that session's actual drivers. Do not reuse a prior week's news as the cause of the latest session.
- For "currently influencing" questions, do not force three items: if fewer than three distinct real-world drivers are supported, return only the supported ones and state that evidence is limited.
- Yahoo Finance/quote feeds may establish only the latest available instrument and session context. NEVER use price candles, technical indicators, index points, percentage moves, volume or quote history as an explanation for why an instrument moved.
- Do not present a company's stock price performance, a market index fall, or futures movement as the underlying cause. These are outcomes/market observations, not causal events.
- For a "top factors influencing" question, each point must identify a real-world event/development and explain its economic transmission channel. If only one or two catalysts are verified, say so instead of padding the list.
- Always state the event date (not merely the article publication date) when available. Reject stale event dates outside the requested/latest-session window unless clearly labelled as background.
- Yahoo Finance is ONLY the private source for quote/ticker/trading-date context. It is NOT a source of causal explanations.
- Use the independent research results for news and events. Do not rely on Yahoo quote movement as proof of a cause.
- Give priority to company/exchange/regulator announcements and reputable financial news. Treat opinion pieces and technical commentary as weaker evidence.
- A factor is CONFIRMED only if a credible dated report, filing or announcement directly supports it. Otherwise label it "Possible" or "Market backdrop".
- Never turn a broad global event into a Ujjivan-specific cause without evidence connecting the channel to Indian banks or the stock's trading period.
- Never claim FII selling, short selling, derivatives positioning, institutional activity or investor reaction unless the supplied evidence supports it.
- Do not treat good quarterly profit as proof that the stock should rise; assess expectations, asset quality, guidance and market reaction.
- Do not repeat stale news as today's trigger. Check both publication date and event date.
- If evidence does not establish a single trigger, say so. Do not fabricate a neat explanation.
- If research results are empty or weak, explicitly state that a confirmed reason is not available rather than filling all points with generic factors.
- Yahoo Finance price, percentage, quote timestamp, high/low, volume and price history must NEVER appear in a stock-fall reason answer.
- Do not include URLs, citations, publisher/source names, bibliography or a Sources section in the final answer.

STOCK-MOVEMENT ANSWER FORMAT:
- NEVER repeat, quote, paraphrase or print the user's question.
- The application independently checks the user's requested direction against Yahoo Finance before displaying your answer.
- Do not create, guess or repeat any price, date, percentage or market direction.
- Only provide factors for the move that actually happened. If the app detects that the user's assumed direction is wrong, it will correct the premise and suppress your factors.
- After the status header, write exactly: WHY THE MARKET MOVED
- Give up to 3 numbered points in very basic, natural English. Each point should be one or two short sentences, maximum 24 words total.
- First explain the strongest factors that match the actual direction. If the index rose, explain what supported the rise and mention major headwinds only if relevant. If it fell, explain what caused the pressure. If flat, explain the balance of positive and negative forces.
- Each point must name a specific, dated event/factor and explain simply how it affects Indian markets. Do not force 3 points if fewer are verified.
- After the points, add exactly one short line: Biggest impact: [single strongest evidence-supported factor].
- If the strongest factor cannot be established, write: **Biggest impact:** Not conclusively identifiable from available evidence.
- Do not add "Based on the provided research", an introduction, conclusion, background paragraph or source list.
- Do not show price, percentage, quote values, high/low or volume in normal answers. Only show the close and percentage when correcting a wrong assumed direction; then include the date and correct unit.
- Keep the entire answer under 90 words.
- Use plain text only. Do not output asterisks, Markdown, HTML tags or literal \\n sequences.

OTHER ANSWERS:
- Simple factual questions (such as current CEO/MD): 1–2 concise lines.
- Other questions: answer directly in short, readable bullets.
""".strip()

    user_content = (
        f"User's exact question:\n{prompt}\n\n"
        f"Recent research results:\n{search_data}\n\n"
        "Answer only the requested market analysis. Do not repeat the question. Use basic English and the status-first format. Explain real-world events, never quote/price movements. Do not display sources or URLs."
    )

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.1,
        "max_tokens": 550 if market_question else 300,
    }

    last_error = "Unknown OpenRouter error"
    for api_key in OPENROUTER_API_KEYS:
        try:
            response = requests.post(
                BASE_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://openrouter.ai/",
                    "X-Title": "USPARK MarketPulse",
                },
                json=payload,
                timeout=(5, 30),
            )

            if response.status_code == 200:
                data = response.json()
                answer = data.get("choices", [{}])[0].get("message", {}).get("content")
                if isinstance(answer, str) and answer.strip():
                    answer = answer.strip()
                    # Reason questions must contain only numbered catalysts, never a quote preamble.
                    prompt_lower = (prompt or "").lower()
                    is_reason_prompt = any(
                        term in prompt_lower
                        for term in (
                            "why", "reason", "fall", "fell", "down", "declin", "drop", "plunge",
                            "factor", "influenc", "impact", "driver", "cause", "what is moving",
                            "what's moving", "market movement", "currently", "today's movement"
                        )
                    )
                    if market_question and is_reason_prompt:
                        answer = _build_intent_aware_market_reply(prompt, search_data, answer)
                    elif market_question and _is_status_only_question(prompt):
                        answer = _build_intent_aware_market_reply(prompt, search_data, answer)
                    # Enforce the no-sources preference even if the model adds a source footer.
                    answer = re.sub(
                        r"(?is)\n*\s*(sources?|references?|citations?)\s*:\s*.*$",
                        "",
                        answer,
                    ).strip()
                    answer = re.sub(r"https?://\S+", "", answer).strip()
                    return answer or "⚠️ I couldn't find enough verified information to answer."
                last_error = "OpenRouter returned an empty answer."
                continue

            last_error = f"OpenRouter HTTP {response.status_code}: {response.text[:500]}"
            logger.error(last_error)
            if response.status_code in (401, 402, 403, 408, 429, 500, 502, 503, 504):
                continue
            break

        except requests.RequestException as exc:
            last_error = f"OpenRouter request failed: {type(exc).__name__}: {exc}"
            logger.exception("OpenRouter request failed")
            continue
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            last_error = f"Could not parse OpenRouter response: {type(exc).__name__}"
            logger.exception("OpenRouter response parsing failed")
            continue

    logger.error("All OpenRouter attempts failed: %s", last_error)
    return "⚠️ I couldn't generate an answer right now. Please try again in a moment."
def AI_Generated_Answer(prompt: str) -> str:
    """Wrapper used by telegram.py; always return a safe string."""
    try:
        response = Gemini(prompt)
        if not isinstance(response, str) or not response.strip():
            return "⚠️ I couldn't generate an answer right now. Please try again."
        return response.strip()
    except Exception:
        logger.exception("Unexpected error while generating AI answer")
        return "⚠️ Something went wrong while generating the answer. Please try again."
