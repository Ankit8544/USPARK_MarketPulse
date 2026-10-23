
import math
from datetime import datetime
from zoneinfo import ZoneInfo

import yfinance as yf


IST = ZoneInfo("Asia/Kolkata")


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

        price = float(latest["Close"])

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

            # Latest available 5-minute candle close
            "price": price,

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
