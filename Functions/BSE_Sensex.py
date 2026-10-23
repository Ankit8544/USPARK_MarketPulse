
import math
from datetime import datetime
from zoneinfo import ZoneInfo

import yfinance as yf


IST = ZoneInfo("Asia/Kolkata")


def get_bse_sensex():
    """Fetch intraday and daily BSE Sensex data."""

    symbol = "^BSESN"

    try:
        ticker = yf.Ticker(symbol)

        # Intraday data for scheduled Telegram alerts
        intraday = ticker.history(
            period="5d",
            interval="5m",
            auto_adjust=False,
            timeout=20
        )

        # Daily data for previous-close comparison
        daily = ticker.history(
            period="10d",
            interval="1d",
            auto_adjust=False,
            timeout=20
        )

        if intraday.empty or daily.empty:
            return {
                "ok": False,
                "error": "BSE Sensex data unavailable"
            }

        intraday = intraday.dropna(subset=["Close"])
        daily = daily.dropna(subset=["Close"])

        if intraday.empty or daily.empty:
            return {
                "ok": False,
                "error": "No valid Sensex values available"
            }

        latest = intraday.iloc[-1]
        latest_time = intraday.index[-1]
        latest_date = latest_time.date()

        price = float(latest["Close"])

        # Previous daily close before the latest intraday date
        previous_rows = daily[
            [idx.date() < latest_date for idx in daily.index]
        ]

        if not previous_rows.empty:
            previous_close = float(
                previous_rows.iloc[-1]["Close"]
            )
        else:
            previous_close = (
                float(daily.iloc[-2]["Close"])
                if len(daily) >= 2
                else None
            )

        change = (
            price - previous_close
            if previous_close is not None
            else None
        )

        change_percent = (
            (change / previous_close) * 100
            if previous_close not in (None, 0)
            else None
        )

        def safe_value(value):
            try:
                number = float(value)
                return number if math.isfinite(number) else None
            except (TypeError, ValueError):
                return None

        def format_change(value):
            if value is None or not math.isfinite(value):
                return None

            return f"{value:+,.2f}"

        # High and low from available candles for this date
        same_date = intraday[
            [idx.date() == latest_date for idx in intraday.index]
        ]

        day_high = safe_value(same_date["High"].max())
        day_low = safe_value(same_date["Low"].min())

        # Index volume is generally unavailable from yfinance
        volume = safe_value(latest.get("Volume"))

        return {
            "ok": True,
            "name": "BSE Sensex",
            "symbol": symbol,
            "currency": "INR",
            "unit": "index points",

            # Latest available intraday candle close
            "price": price,

            # Previous daily close and daily change
            "previous_close": previous_close,
            "change": change,
            "change_percent": change_percent,

            # Signed display values
            "change_display": format_change(change),
            "change_percent_display": format_change(
                change_percent
            ),

            # Latest candle's opening price
            "open": safe_value(latest.get("Open")),

            # High and low from available intraday candles
            "high": day_high,
            "low": day_low,

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
                f"BSE Sensex data fetch failed: "
                f"{type(exc).__name__}"
            )
        }
