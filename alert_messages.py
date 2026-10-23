from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def _num(value, signed=False):
    if value is None:
        return "N/A"
    try:
        return f"{float(value):+,.2f}" if signed else f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return "N/A"


def _instrument(label, data, unit):
    if not data or not data.get("ok"):
        return f"• {label}: unavailable"
    return (f"• {label}: {_num(data.get('price'))} {unit}"
            f" | Change: {_num(data.get('change'), True)}"
            f" ({_num(data.get('change_percent'), True)}%)")


def _stamp(lines):
    lines.extend(["", "🕒 Generated: " + datetime.now(IST).strftime("%d-%m-%Y %I:%M:%S %p IST")])
    return "\n".join(lines)


def _base(data):
    return (data["gold"], data["usd_inr"], data["sensex"], data["nifty"], data["ujjivan_nse"], data["ujjivan_bse"])


def build_pre_market_message(data):
    gold, usd, sensex, nifty, nse, bse = _base(data)
    return _stamp(["🌅 PRE-MARKET BRIEF", _instrument("Gold Futures", gold, "USD/oz"),
        _instrument("USD/INR", usd, "INR"), _instrument("BSE Sensex", sensex, "points"),
        _instrument("NSE Nifty 50", nifty, "points"), _instrument("Ujjivan SFB NSE", nse, "INR/share"),
        _instrument("Ujjivan SFB BSE", bse, "INR/share"), "🗓️ Previous-session comparison uses latest provider data."])


def build_market_open_message(data):
    gold, usd, sensex, nifty, nse, bse = _base(data)
    lines = ["📈 MARKET OPENING ALERT", _instrument("BSE Sensex", sensex, "points"),
        _instrument("NSE Nifty 50", nifty, "points"), _instrument("Ujjivan SFB NSE", nse, "INR/share"),
        _instrument("Ujjivan SFB BSE", bse, "INR/share"), _instrument("Gold Futures", gold, "USD/oz"),
        _instrument("USD/INR", usd, "INR")]
    for label, item in (("Ujjivan NSE", nse), ("Ujjivan BSE", bse)):
        if item.get("ok") and item.get("open") is not None and item.get("previous_close") not in (None, 0):
            gap = (item["open"] - item["previous_close"]) / item["previous_close"] * 100
            status = "GAP UP" if gap > 0 else "GAP DOWN" if gap < 0 else "FLAT"
            lines.append(f"📉 {label} opening gap: {status} ({gap:+.2f}%)")
    return _stamp(lines)


def build_mid_morning_message(data):
    gold, usd, sensex, nifty, nse, bse = _base(data)
    return _stamp(["☀️ MID-MORNING MARKET UPDATE", _instrument("Gold Futures", gold, "USD/oz"),
        _instrument("USD/INR", usd, "INR"), _instrument("BSE Sensex", sensex, "points"),
        _instrument("NSE Nifty 50", nifty, "points"), _instrument("Ujjivan SFB NSE", nse, "INR/share"),
        _instrument("Ujjivan SFB BSE", bse, "INR/share"),
        f"📍 NSE high/low: {_num(nse.get('high'))} / {_num(nse.get('low'))}" if nse.get("ok") else "📍 NSE high/low: unavailable",
        f"📊 NSE volume: {nse.get('volume', 'N/A')}"])


def build_afternoon_message(data):
    gold, usd, sensex, nifty, nse, bse = _base(data)
    return _stamp(["📊 AFTERNOON MARKET PULSE", _instrument("Gold Futures", gold, "USD/oz"),
        _instrument("USD/INR", usd, "INR"), _instrument("BSE Sensex", sensex, "points"),
        _instrument("NSE Nifty 50", nifty, "points"), _instrument("Ujjivan SFB NSE", nse, "INR/share"),
        _instrument("Ujjivan SFB BSE", bse, "INR/share"),
        f"📍 Ujjivan NSE high/low: {_num(nse.get('high'))} / {_num(nse.get('low'))}" if nse.get("ok") else "📍 Ujjivan NSE high/low: unavailable",
        f"📊 Ujjivan NSE volume: {nse.get('volume', 'N/A')}",
        "📉 Intraday movement is based on the latest available provider candles."])


def build_closing_soon_message(data):
    _, _, sensex, nifty, nse, bse = _base(data)
    return _stamp(["🔔 MARKET CLOSING SOON", _instrument("BSE Sensex", sensex, "points"),
        _instrument("NSE Nifty 50", nifty, "points"), _instrument("Ujjivan SFB NSE", nse, "INR/share"),
        _instrument("Ujjivan SFB BSE", bse, "INR/share"),
        f"📍 Ujjivan NSE high/low: {_num(nse.get('high'))} / {_num(nse.get('low'))}" if nse.get("ok") else "📍 Ujjivan NSE high/low: unavailable",
        f"📊 Ujjivan NSE volume: {nse.get('volume', 'N/A')}", "⏳ Scheduled five minutes before the usual equity-market close."])


def build_closing_report_message(data):
    gold, usd, sensex, nifty, nse, bse = _base(data)
    tracked = (sensex, nifty, nse, bse)
    positive = all(x.get("ok") and (x.get("change") or 0) > 0 for x in tracked)
    summary = "All tracked equity instruments positive" if positive else "Mixed/negative or incomplete data; see changes above"
    ohlc = (f"O {_num(nse.get('open'))} | H {_num(nse.get('high'))} | L {_num(nse.get('low'))} | Latest {_num(nse.get('price'))}"
            if nse.get("ok") else "unavailable")
    return _stamp(["🏁 DAILY MARKET CLOSING REPORT", _instrument("BSE Sensex", sensex, "points"),
        _instrument("NSE Nifty 50", nifty, "points"), _instrument("Ujjivan SFB NSE", nse, "INR/share"),
        _instrument("Ujjivan SFB BSE", bse, "INR/share"), _instrument("Gold Futures", gold, "USD/oz"),
        _instrument("USD/INR", usd, "INR"), "📈 Ujjivan NSE OHLC: " + ohlc,
        f"📊 Ujjivan NSE volume: {nse.get('volume', 'N/A')}", "🧾 Daily summary: " + summary,
        "ℹ️ Provider values may not be official closing ticks."])

