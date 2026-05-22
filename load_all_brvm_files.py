import os
import glob
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))

folder = "/Users/jpsossavi/Documents/BRVM_daily"
files = glob.glob(os.path.join(folder, "*.xlsx")) + glob.glob(os.path.join(folder, "*.csv"))
print("Files found:", len(files))
for f in files:
    print(f)

with engine.begin() as conn:
    for file in files:
        print("Loading:", file)

        if file.endswith(".csv"):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
        df["Trade_Date"] = pd.to_datetime(df["Trade_Date"]).dt.date

        for _, row in df.iterrows():
            conn.execute(text("""
                INSERT IGNORE INTO brvm_daily
                (ticker, name, volume, prev_close, open_price, close_price, change_pct, trade_date)
                VALUES
                (:ticker, :name, :volume, :prev_close, :open_price, :close_price, :change_pct, :trade_date)
            """), {
                "ticker": row["Ticker"],
                "name": row["Name"],
                "volume": row["Volume"],
                "prev_close": row["Prev_Close"],
                "open_price": row["Open"],
                "close_price": row["Close"],
                "change_pct": row["Change_pct"],
                "trade_date": row["Trade_Date"]
            })

    conn.execute(text("""
        INSERT IGNORE INTO market_data_daily (
            exchange_id, ticker, company_name, trade_date,
            open_price, close_price, volume, prev_close,
            change_pct, currency
        )
        SELECT
            2, ticker, name, trade_date,
            open_price, close_price, volume, prev_close,
            change_pct, 'XOF'
        FROM brvm_daily;
    """))

    conn.execute(text("""
        UPDATE market_data_daily
        SET value_traded = close_price * volume
        WHERE exchange_id = 2
        AND value_traded IS NULL
        AND close_price IS NOT NULL
        AND volume IS NOT NULL;
    """))

print("All BRVM files loaded and synced.")
