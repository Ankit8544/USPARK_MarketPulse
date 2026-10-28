import math
from datetime import datetime
from zoneinfo import ZoneInfo

import yfinance as yf

try:
    # Works when this file and USD_INR_rate.py are in the same directory.
    from USD_INR_rate import get_usd_inr
except ImportError:
    # Works when these modules are inside a Functions package.
    from Functions.USD_INR_rate import get_usd_inr


IST = ZoneInfo("Asia/Kolkata")
SYMBOL = "GC=F"  # COMEX Gold Futures, Yahoo Finance
GRAMS_PER_TROY_OUNCE = 31.1034768
GOLD_GRAMS = 10
IMPORT_DUTY_RATE = 0.15
IGST_RATE = 0.03


def _number(value):
    """Return a finite float, or None when Yahoo provides no usable value."""
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _signed(value):
    return f"{value:+,.2f}" if value is not None else None


def get_gold_price():
    """Get Yahoo Finance COMEX gold quote and convert its price/change to INR per 10g."""
    try:
        ticker = yf.Ticker(SYMBOL)

        # Yahoo quote fields provide the quote's own change and change percentage.
        # Do not independently derive change from a previous daily close.
        info = ticker.info or {}

        price_usd_per_oz = _number(
            info.get("regularMarketPrice")
            or info.get("currentPrice")
            or info.get("previousClose")
        )
        change_usd_per_oz = _number(info.get("regularMarketChange"))
        change_percent = _number(info.get("regularMarketChangePercent"))
        previous_close_usd_per_oz = _number(info.get("regularMarketPreviousClose") or info.get("previousClose"))

        # History is used only as a fallback for the latest available price and
        # for high/low/time metadata, not to invent the quote's change fields.
        intraday = ticker.history(
            period="5d", interval="5m", auto_adjust=False, timeout=20
        )
        if intraday is not None and not intraday.empty:
            intraday = intraday.dropna(subset=["Close"])

        latest = intraday.iloc[-1] if intraday is not None and not intraday.empty else None
        latest_time = intraday.index[-1] if latest is not None else None

        if price_usd_per_oz is None and latest is not None:
            price_usd_per_oz = _number(latest.get("Close"))

        if price_usd_per_oz is None:
            return {"ok": False, "error": "Yahoo Finance gold price unavailable"}

        # Convert USD/oz to USD/gram first, then multiply by 10 for USD/10g.
        price_usd_per_gram = price_usd_per_oz / GRAMS_PER_TROY_OUNCE
        price_usd_per_10g = price_usd_per_gram * GOLD_GRAMS

        # Apply the exact same unit conversion to Yahoo's quote change.
        change_usd_per_gram = (
            change_usd_per_oz / GRAMS_PER_TROY_OUNCE
            if change_usd_per_oz is not None else None
        )
        change_usd_per_10g = (
            change_usd_per_gram * GOLD_GRAMS
            if change_usd_per_gram is not None else None
        )

        # Fetch USD/INR and convert only after USD per-gram/per-10g values exist.
        usd_data = get_usd_inr()
        usd_inr_rate = (
            _number(usd_data.get("price"))
            if isinstance(usd_data, dict) and usd_data.get("ok") else None
        )
        price_inr_per_gram = (
            price_usd_per_gram * usd_inr_rate if usd_inr_rate is not None else None
        )
        price_inr_per_10g = (
            price_usd_per_10g * usd_inr_rate if usd_inr_rate is not None else None
        )
        change_inr_per_gram = (
            change_usd_per_gram * usd_inr_rate
            if change_usd_per_gram is not None and usd_inr_rate is not None else None
        )
        change_inr_per_10g = (
            change_usd_per_10g * usd_inr_rate
            if change_usd_per_10g is not None and usd_inr_rate is not None else None
        )

        # A unit/currency conversion does not change the quoted percentage.
        change_inr_percent = change_percent

        # Indicative estimate after import duty; IGST is applied to price + duty.
        import_duty_inr_per_10g = (
            price_inr_per_10g * IMPORT_DUTY_RATE
            if price_inr_per_10g is not None else None
        )
        price_after_import_duty_per_10g = (
            price_inr_per_10g + import_duty_inr_per_10g
            if price_inr_per_10g is not None else None
        )
        igst_inr_per_10g = (
            price_after_import_duty_per_10g * IGST_RATE
            if price_after_import_duty_per_10g is not None else None
        )
        price_after_duty_and_igst_per_10g = (
            price_after_import_duty_per_10g + igst_inr_per_10g
            if price_after_import_duty_per_10g is not None else None
        )

        intraday_high = intraday_low = volume = open_price = None
        if latest is not None:
            same_date = intraday[[idx.date() == latest_time.date() for idx in intraday.index]]
            intraday_high = _number(same_date["High"].max())
            intraday_low = _number(same_date["Low"].min())
            volume_value = _number(latest.get("Volume"))
            volume = int(volume_value) if volume_value is not None else None
            open_price = _number(latest.get("Open"))

        return {
            "ok": True,
            "name": "COMEX Gold Futures",
            "symbol": SYMBOL,
            "currency": "USD",
            "unit": "USD per troy ounce",
            "price": price_usd_per_oz,
            "price_usd_per_gram": price_usd_per_gram,
            "price_usd_per_10g": price_usd_per_10g,
            "change_usd_per_gram": change_usd_per_gram,
            "change_usd_per_10g": change_usd_per_10g,
            "change_percent": change_percent,
            "usd_inr_rate": usd_inr_rate,
            "price_inr_per_gram": price_inr_per_gram,
            "price_inr_per_10g": price_inr_per_10g,
            "change_inr_per_gram": change_inr_per_gram,
            "change_inr_per_10g": change_inr_per_10g,
            "change_inr_percent": change_inr_percent,
            "import_duty_rate": IMPORT_DUTY_RATE,
            "import_duty_inr_per_10g": import_duty_inr_per_10g,
            "price_after_import_duty_per_10g": price_after_import_duty_per_10g,
            "igst_rate": IGST_RATE,
            "igst_inr_per_10g": igst_inr_per_10g,
            "price_after_duty_and_igst_per_10g": price_after_duty_and_igst_per_10g,
            "price_usd_per_10g_display": f"{price_usd_per_10g:,.2f}",
            "price_inr_per_10g_display": f"{price_inr_per_10g:,.2f}" if price_inr_per_10g is not None else None,
            # Compatibility fields: these now reflect Yahoo's quote change, not a daily-close calculation.
            "previous_close": previous_close_usd_per_oz,
            "change": change_usd_per_oz,
            "change_display": _signed(change_usd_per_oz),
            "change_percent_display": _signed(change_percent),
            "open": open_price,
            "high": intraday_high,
            "low": intraday_low,
            "volume": volume,
            "market_time": (
                latest_time.strftime("%Y-%m-%d %H:%M:%S %Z")
                if latest_time is not None else info.get("regularMarketTime")
            ),
            "fetched_at": datetime.now(IST).strftime("%d-%m-%Y %I:%M:%S %p IST"),
            "interval": "Yahoo Finance quote; 5m history for metadata",
            "data_type": "Yahoo Finance COMEX gold quote",
        }

    except Exception as exc:
        return {
            "ok": False,
            "error": f"Gold data fetch failed: {type(exc).__name__}: {exc}",
        }
