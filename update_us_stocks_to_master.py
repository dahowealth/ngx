import os
import time
import numpy as np
import pandas as pd
import yfinance as yf
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))

# Get USA tickers already stored in companies table
with engine.begin() as conn:
    tickers_df = pd.read_sql(text("""
        SELECT ticker, name
        FROM companies
        WHERE exchange_id = 1
        OR currency = 'USD';
    """), conn)

tickers_df["ticker"] = tickers_df["ticker"].astype(str).str.strip()
tickers = tickers_df["ticker"].dropna().unique()

rows = []

for ticker in tickers:
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d")

        if hist.empty:
            continue

        hist = hist.reset_index()
        hist["Date"] = pd.to_datetime(hist["Date"]).dt.date
        hist["Prev_Close"] = hist["Close"].shift(1)
        hist["Change_pct"] = hist["Close"].pct_change() * 100

        company_name = tickers_df.loc[tickers_df["ticker"] == ticker, "name"].iloc[0]

        for _, row in hist.iterrows():
            close_price = float(row["Close"])
            volume = int(row["Volume"]) if not pd.isna(row["Volume"]) else None
            value_traded = close_price * volume if volume is not None else None

            rows.append({
                "exchange_id": 1,
                "ticker": ticker,
                "company_name": company_name,
                "trade_date": row["Date"],
                "open_price": float(row["Open"]),
                "high_price": float(row["High"]),
                "low_price": float(row["Low"]),
                "close_price": close_price,
                "prev_close": None if pd.isna(row["Prev_Close"]) else float(row["Prev_Close"]),
                "change_pct": 0 if pd.isna(row["Change_pct"]) else round(float(row["Change_pct"]), 2),
                "volume": volume,
                "value_traded": value_traded,
                "value_traded_usd": value_traded,
                "currency": "USD",
                "used_ex_rate": 1,
                "price_in_usd": close_price
            })

        print(f"Loaded {ticker}")
        time.sleep(0.2)

    except Exception as e:
        print(f"Skipped {ticker}: {e}")

with engine.begin() as conn:
    for row in rows:
        conn.execute(text("""
            INSERT IGNORE INTO market_data_daily (
                exchange_id, ticker, company_name, trade_date,
                open_price, high_price, low_price, close_price,
                prev_close, change_pct, volume,
                value_traded, value_traded_usd,
                currency, used_ex_rate, price_in_usd
            )
            VALUES (
                :exchange_id, :ticker, :company_name, :trade_date,
                :open_price, :high_price, :low_price, :close_price,
                :prev_close, :change_pct, :volume,
                :value_traded, :value_traded_usd,
                :currency, :used_ex_rate, :price_in_usd
            )
        """), row)

print(f"US stock data synced into market_data_daily. Rows prepared: {len(rows)}")
