import os
import requests
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

engine = create_engine(os.getenv("DATABASE_URL"))

url = "https://doclib.ngxgroup.com/REST/api/statistics/equities/?market=&sector=&orderby=&pageSize=300&pageNo=0"

r = requests.get(url, timeout=10)
r.raise_for_status()

data = r.json()
df = pd.DataFrame(data)

expected = [
    "Symbol", "OpeningPrice", "HighPrice", "LowPrice", "ClosePrice",
    "Change", "Volume", "Value", "Trades", "TradeDate"
]

for col in expected:
    if col not in df.columns:
        df[col] = np.nan

change = pd.to_numeric(df["Change"], errors="coerce")
opening = pd.to_numeric(df["OpeningPrice"], errors="coerce")

with np.errstate(divide="ignore", invalid="ignore"):
    pct = (change / opening) * 100

df["ChangePct"] = np.where(np.isfinite(pct), np.round(pct, 2), np.nan)

df["TradeDate"] = pd.to_datetime(df["TradeDate"]).dt.date
df = df.replace({np.nan: None})

with engine.begin() as conn:
    for _, row in df.iterrows():
        conn.execute(text("""
            INSERT INTO ngx_daily
            (
                ticker,
                open_price,
                high_price,
                low_price,
                close_price,
                change_value,
                change_pct,
                volume,
                value_traded,
                trades,
                trade_date
            )
            VALUES
            (
                :ticker,
                :open_price,
                :high_price,
                :low_price,
                :close_price,
                :change_value,
                :change_pct,
                :volume,
                :value_traded,
                :trades,
                :trade_date
            )
            ON DUPLICATE KEY UPDATE
                open_price = VALUES(open_price),
                high_price = VALUES(high_price),
                low_price = VALUES(low_price),
                close_price = VALUES(close_price),
                change_value = VALUES(change_value),
                change_pct = VALUES(change_pct),
                volume = VALUES(volume),
                value_traded = VALUES(value_traded),
                trades = VALUES(trades);
        """), {
            "ticker": row["Symbol"],
            "open_price": row["OpeningPrice"],
            "high_price": row["HighPrice"],
            "low_price": row["LowPrice"],
            "close_price": row["ClosePrice"],
            "change_value": row["Change"],
            "change_pct": row["ChangePct"],
            "volume": row["Volume"],
            "value_traded": row["Value"],
            "trades": row["Trades"],
            "trade_date": row["TradeDate"]
        })
            
    conn.execute(text("""
            INSERT INTO market_data_daily (
                exchange_id,
                ticker,
                company_name,
                trade_date,
                open_price,
                high_price,
                low_price,
                close_price,
                volume,
                value_traded,
                change_pct,
                currency,
                used_ex_rate
        )
            SELECT
                3,
                ticker,
                ticker,
                trade_date,
                open_price,
                high_price,
                low_price,
                close_price,
                volume,
                value_traded,
                change_pct,
                'NGN',
                1500
            FROM ngx_daily
            ON DUPLICATE KEY UPDATE
                open_price = VALUES(open_price),
                high_price = VALUES(high_price),
                low_price = VALUES(low_price),
                close_price = VALUES(close_price),
                change_pct = VALUES(change_pct),
                volume = VALUES(volume),
                value_traded = VALUES(value_traded),
                used_ex_rate = VALUES(used_ex_rate);
    """))
    conn.execute(text("""
        UPDATE market_data_daily
            SET 
                price_in_usd = close_price / used_ex_rate,
                value_traded_usd = value_traded / used_ex_rate
            WHERE exchange_id = 3
        AND used_ex_rate IS NOT NULL;
    """))

print("NGX daily data loaded into SQL.")
