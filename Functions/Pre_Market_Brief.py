from datetime import datetime
from zoneinfo import ZoneInfo

from Functions import (
    Gold_Price,
    USD_INR_rate,
    BSE_Sensex,
    NSE_Nifty_50,
    Ujjivan_SFB_NSE,
    Ujjivan_SFB_BSE,
)

IST = ZoneInfo("Asia/Kolkata")


def safe_value(data, key):
    if isinstance(data, dict) and data.get("ok"):
        return data.get(key)
    return None


def get_pre_market_brief():
    generated_at = datetime.now(IST)

    gold = Gold_Price.get_gold_price()
    usd_inr = USD_INR_rate.get_usd_inr()
    sensex = BSE_Sensex.get_bse_sensex()
    nifty = NSE_Nifty_50.get_nse_nifty50()
    ujjivan_nse = Ujjivan_SFB_NSE.get_ujjivan_sfb_nse()
    ujjivan_bse = Ujjivan_SFB_BSE.get_ujjivan_sfb_bse()

    return {
        "title": "Pre-Market Brief",
        "time": "08:45 AM",
        "timezone": "Asia/Kolkata",
        "generated_at": generated_at.isoformat(),

        "gold": {
            "price": safe_value(gold, "price"),
            "change": safe_value(gold, "change_display"),
            "change_percent": safe_value(gold, "change_percent_display"),
            "market_time": safe_value(gold, "market_time"),
        },

        "usd_inr": {
            "rate": safe_value(usd_inr, "price"),
            "change_percent": safe_value(usd_inr, "change_percent_display"),
            "market_time": safe_value(usd_inr, "market_time"),
        },

        "bse_sensex": {
            "price": safe_value(sensex, "price"),
            "change": safe_value(sensex, "change_display"),
            "change_percent": safe_value(
                sensex, "change_percent_display"
            ),
            "market_time": safe_value(sensex, "market_time"),
        },

        "nse_nifty_50": {
            "price": safe_value(nifty, "price"),
            "change": safe_value(nifty, "change_display"),
            "change_percent": safe_value(
                nifty, "change_percent_display"
            ),
            "market_time": safe_value(nifty, "market_time"),
        },

        "ujjivan_sfb_nse": {
            "price": safe_value(ujjivan_nse, "price"),
            "change_percent": safe_value(
                ujjivan_nse, "change_percent"
            ),
            "market_time": safe_value(
                ujjivan_nse, "market_time"
            ),
        },

        "ujjivan_sfb_bse": {
            "price": safe_value(ujjivan_bse, "price"),
            "change_percent": safe_value(
                ujjivan_bse, "change_percent"
            ),
            "market_time": safe_value(
                ujjivan_bse, "market_time"
            ),
        },
    }
    
