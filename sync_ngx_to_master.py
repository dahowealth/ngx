import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

engine = create_engine(os.getenv("DATABASE_URL"))

query = """
INSERT IGNORE INTO market_data_daily (
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
    trades,
    change_pct,
    currency
)
SELECT
    3 AS exchange_id,
    ticker,
    ticker AS company_name,
    trade_date,
    open_price,
    high_price,
    low_price,
    close_price,
    volume,
    value_traded,
    trades,
    change_pct,
    'NGN' AS currency
FROM ngx_daily;
"""

with engine.begin() as conn:
    result = conn.execute(text(query))

print("NGX synced into market_data_daily.")
print("Rows affected:", result.rowcount)
