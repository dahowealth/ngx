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
            INSERT IGNORE INTO ngx_daily
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

print("NGX daily data loaded into SQL.")
