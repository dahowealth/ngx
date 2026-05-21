import os
import yfinance as yf
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))

def get_rate(pair, fallback):
    try:
        rate = yf.Ticker(pair).fast_info["last_price"]
        return float(rate) if rate else fallback
    except Exception:
        return fallback

usd_xof = get_rate("USDXOF=X", 557.70)
usd_ngn = get_rate("USDNGN=X", 1500.00)

with engine.begin() as conn:
    # USD stocks
    conn.execute(text("""
        UPDATE market_data_daily
        SET used_ex_rate = 1,
            price_in_usd = close_price,
            value_traded_usd = value_traded
        WHERE currency = 'USD';
    """))

    # BRVM XOF stocks
    conn.execute(text("""
        UPDATE market_data_daily
        SET used_ex_rate = :usd_xof,
            price_in_usd = close_price / :usd_xof,
            value_traded_usd = value_traded / :usd_xof
        WHERE currency = 'XOF';
    """), {"usd_xof": usd_xof})

    # NGX NGN stocks
    conn.execute(text("""
        UPDATE market_data_daily
        SET used_ex_rate = :usd_ngn,
            price_in_usd = close_price / :usd_ngn,
            value_traded_usd = value_traded / :usd_ngn
        WHERE currency = 'NGN';
    """), {"usd_ngn": usd_ngn})

print("Currency conversion updated.")
print("USD/XOF:", usd_xof)
print("USD/NGN:", usd_ngn)
