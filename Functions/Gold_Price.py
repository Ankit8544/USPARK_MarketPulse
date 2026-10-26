
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
GRAMS_PER_TROY_OUNCE = 31.1034768
GOLD_GRAMS = 10
IMPORT_DUTY_RATE = 0.15  # 15% assumed import duty (BCD + AIDC)
IGST_RATE = 0.03  # 3% IGST, shown separately from import duty


def get_gold_price():
    """Fetch intraday and daily Gold Futures data."""

    symbol = "GC=F"

    try:
        ticker = yf.Ticker(symbol)

        # Intraday candles for market-session alerts
        intraday = ticker.history(
            period="5d",
            interval="5m",
            auto_adjust=False,
            timeout=20
        )

        # Daily candles for previous-close comparison
        daily = ticker.history(
            period="10d",
            interval="1d",
            auto_adjust=False,
            timeout=20
        )

        if intraday.empty or daily.empty:
            return {
                "ok": False,
                "error": "Gold data unavailable"
            }

        intraday = intraday.dropna(subset=["Close"])
        daily = daily.dropna(subset=["Close"])

        if intraday.empty or daily.empty:
            return {
                "ok": False,
                "error": "No valid gold prices available"
            }

        # Latest available intraday candle
        latest = intraday.iloc[-1]
        latest_time = intraday.index[-1]

        # GC=F is quoted in USD per troy ounce. Convert to USD per 10 grams.
        price = float(latest["Close"])
        price_usd_per_10g = price * GOLD_GRAMS / GRAMS_PER_TROY_OUNCE

        # Fetch USD/INR and convert the 10-gram USD price to INR.
        usd_data = get_usd_inr()
        usd_inr_rate = (
            float(usd_data["price"])
            if usd_data.get("ok") and usd_data.get("price") is not None
            else None
        )
        price_inr_per_10g = (
            price_usd_per_10g * usd_inr_rate
            if usd_inr_rate is not None
            else None
        )

        # Find the most recent daily candle before the
        # date of the latest intraday candle.
        intraday_date = latest_time.date()

        previous_rows = daily[
            [idx.date() < intraday_date for idx in daily.index]
        ]

        # Fallback for providers with differing candle dates
        if previous_rows.empty:
            previous = (
                float(daily.iloc[-2]["Close"])
                if len(daily) > 1
                else None
            )
        else:
            previous = float(previous_rows.iloc[-1]["Close"])

        change = (
            price - previous
            if previous is not None
            else None
        )

        change_percent = (
            (change / previous) * 100
            if previous not in (None, 0)
            else None
        )

        # Convert the previous COMEX close using the current USD/INR rate.
        previous_price_inr_per_10g = (
            previous * GOLD_GRAMS / GRAMS_PER_TROY_OUNCE * usd_inr_rate
            if previous is not None and usd_inr_rate is not None
            else None
        )

        # Change in INR per 10 grams, excluding the separate FX-rate effect.
        change_inr_per_10g = (
            price_inr_per_10g - previous_price_inr_per_10g
            if price_inr_per_10g is not None
            and previous_price_inr_per_10g is not None
            else None
        )

        change_inr_percent = (
            (change_inr_per_10g / previous_price_inr_per_10g) * 100
            if previous_price_inr_per_10g not in (None, 0)
            and change_inr_per_10g is not None
            else None
        )

        # Indicative price after import duty (does not include freight/insurance/premium).
        import_duty_inr_per_10g = (
            price_inr_per_10g * IMPORT_DUTY_RATE
            if price_inr_per_10g is not None
            else None
        )
        price_after_import_duty_per_10g = (
            price_inr_per_10g + import_duty_inr_per_10g
            if price_inr_per_10g is not None
            else None
        )

        # Optional landed estimate after 3% IGST on price + import duty.
        igst_inr_per_10g = (
            price_after_import_duty_per_10g * IGST_RATE
            if price_after_import_duty_per_10g is not None
            else None
        )
        price_after_duty_and_igst_per_10g = (
            price_after_import_duty_per_10g + igst_inr_per_10g
            if price_after_import_duty_per_10g is not None
            else None
        )

        def safe_value(value):
            try:
                number = float(value)
                return number if math.isfinite(number) else None
            except (TypeError, ValueError):
                return None

        def signed(value):
            return (
                f"{value:+,.2f}"
                if value is not None
                and math.isfinite(value)
                else None
            )

        # Intraday high/low for the date of the latest candle
        same_date = intraday[
            [idx.date() == intraday_date for idx in intraday.index]
        ]

        intraday_high = safe_value(same_date["High"].max())
        intraday_low = safe_value(same_date["Low"].min())

        volume = safe_value(latest.get("Volume"))

        return {
            "ok": True,
            "name": "Gold Futures",
            "symbol": symbol,
            "currency": "USD",
            "unit": "USD per troy ounce",

            # Original futures quote, retained for compatibility.
            "price": price,

            # Converted prices for 10 grams of gold.
            "price_usd_per_10g": price_usd_per_10g,
            "usd_inr_rate": usd_inr_rate,
            "price_inr_per_10g": price_inr_per_10g,
            "previous_price_inr_per_10g": previous_price_inr_per_10g,
            "change_inr_per_10g": change_inr_per_10g,
            "change_inr_percent": change_inr_percent,
            "import_duty_rate": IMPORT_DUTY_RATE,
            "import_duty_inr_per_10g": import_duty_inr_per_10g,
            "price_after_import_duty_per_10g": price_after_import_duty_per_10g,
            "igst_rate": IGST_RATE,
            "igst_inr_per_10g": igst_inr_per_10g,
            "price_after_duty_and_igst_per_10g": price_after_duty_and_igst_per_10g,
            "price_usd_per_10g_display": f"{price_usd_per_10g:,.2f}",
            "price_inr_per_10g_display": (
                f"{price_inr_per_10g:,.2f}"
                if price_inr_per_10g is not None
                else None
            ),

            # Daily comparison
            "previous_close": previous,
            "change": change,
            "change_percent": change_percent,
            "change_display": signed(change),
            "change_percent_display": signed(change_percent),

            # Latest candle values
            "open": safe_value(latest.get("Open")),

            # Intraday high and low from available 5-minute data
            "high": intraday_high,
            "low": intraday_low,

            "volume": (
                int(volume)
                if volume is not None
                else None
            ),

            # Data timestamps
            "market_time": latest_time.strftime(
                "%Y-%m-%d %H:%M:%S %Z"
            ),
            "fetched_at": datetime.now(IST).strftime(
                "%d-%m-%Y %I:%M:%S %p IST"
            ),

            "interval": "5m",
            "data_type": "Latest available intraday candle",
        }

    except Exception as exc:
        return {
            "ok": False,
            "error": (
                f"Gold data fetch failed: {type(exc).__name__}"
            )
        }
