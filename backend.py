from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import requests
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

app = FastAPI()
load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ROOT
@app.get("/")
def root():
    return {"message": "Welcome to the real-time NGX 📈 and BRVM 📊 API"}

# =========================
# ✅ NGX API (uses OpeningPrice for % change)
# =========================
@app.get("/api/ngx-sql")
def get_ngx_sql_data():
    try:
        query = """
        SELECT
            ticker AS Ticker,
            open_price AS Open,
            close_price AS Close,
            change_pct AS Change_pct,
            volume AS Volume,
            value_traded AS Value_traded,
            trades AS Trades,
            trade_date AS Trade_Date
        FROM ngx_daily
        ORDER BY trade_date DESC, ticker ASC
        """

        df = pd.read_sql(query, con=engine)

        df["Trade_Date"] = pd.to_datetime(df["Trade_Date"]).dt.strftime("%Y-%m-%d")

        df = df.replace({np.nan: "-", np.inf: "-", -np.inf: "-"})

        return df.to_dict(orient="records")

    except Exception as e:
        return {"error": "NGX SQL API failed", "details": str(e)}
@app.get("/api/ngx")
def get_ngx_data():
    url = "https://doclib.ngxgroup.com/REST/api/statistics/equities/?market=&sector=&orderby=&pageSize=300&pageNo=0"
    try:
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

        df = df.replace({np.nan: None, np.inf: None, -np.inf: None})

        df = df.rename(columns={
            "Symbol": "Ticker",
            "OpeningPrice": "Open",
            "HighPrice": "High",
            "LowPrice": "Low",
            "ClosePrice": "Close",
            "Change": "Change_value",
            "ChangePct": "Change_pct",
            "Value": "Value_traded",
            "TradeDate": "Trade_Date"
        })

        df["Trade_Date"] = pd.to_datetime(df["Trade_Date"]).dt.strftime("%Y-%m-%d")

        return df[
            [
                "Ticker",
                "Open",
                "High",
                "Low",
                "Close",
                "Change_value",
                "Change_pct",
                "Volume",
                "Value_traded",
                "Trades",
                "Trade_Date"
            ]
        ].to_dict(orient="records")

    except Exception as e:
        return {"error": "Something went wrong", "details": str(e)}

# ✅ NGX FRONTEND (color-coded %)
@app.get("/ngx", response_class=HTMLResponse)
def frontend_page():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Tableau NGX</title>
        <meta charset="utf-8" />
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            table { border-collapse: collapse; width: 100%; margin-top: 10px; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: center; }
            th { background-color: #f2f2f2; cursor: pointer; }
            th:hover { background-color: #ddd; }
            input[type="text"] { padding: 6px; width: 300px; margin-bottom: 10px; }
            button { padding: 6px 12px; margin-left: 10px; cursor: pointer; }
            .pos { color: green; font-weight: bold; }
            .neg { color: red; font-weight: bold; }
            .flat { color: gray; font-weight: bold; }
        </style>
    </head>
    <body>
        <h1>Real-Time NGX Data</h1>

        <input type="text" id="searchInput" placeholder="🔍 Search here..." />
        <button onclick="downloadCSV()">📥 Télécharger CSV</button>

        <table id="ngxTable" data-sort-dir="asc">
            <thead>
                <tr>
                    <th onclick="sortTable(0)">Ticker</th>
                    <th onclick="sortTable(1)">Open</th>
                    <th onclick="sortTable(2)">Close</th>
                    <th onclick="sortTable(3)">Change (%)</th>
                    <th onclick="sortTable(4)">Volume</th>
                    <th onclick="sortTable(5)">Value Traded</th>
                    <th onclick="sortTable(6)">Transactions</th>
                    <th onclick="sortTable(7)">Date</th>
                </tr>
            </thead>
            <tbody></tbody>
        </table>

        <script>
            let fullData = [];

            async function fetchData() {
                const res = await fetch("/api/ngx-sql");
                const data = await res.json();
                fullData = data;
                renderTable(data);
            }

            function renderTable(data) {
                const tbody = document.querySelector("#ngxTable tbody");
                tbody.innerHTML = "";
                data.forEach(row => {
                    // Format % and choose color class
                    let pctDisplay = "-";
                    let pctClass = "flat";
                    const raw = row.Change_pct;

                    if (raw !== null && raw !== undefined) {
                        const num = parseFloat(raw);
                        if (!isNaN(num)) {
                            pctDisplay = num.toFixed(2) + "%";
                            if (num > 0) pctClass = "pos";
                            else if (num < 0) pctClass = "neg";
                            else pctClass = "flat";
                        }
                    }

                    const tr = document.createElement("tr");
                    tr.innerHTML = `
                    <td>${row.Ticker ?? "-"}</td>
                    <td>${row.Open ?? "-"}</td>
                    <td>${row.Close ?? "-"}</td>
                    <td class="${pctClass}">${pctDisplay}</td>
                    <td>${row.Volume ?? "-"}</td>
                    <td>${row.Value_traded ?? "-"}</td>
                    <td>${row.Trades ?? "-"}</td>
                    <td>${row.Trade_Date ?? "-"}</td>
                `;
                    tbody.appendChild(tr);
                });
            }

            function sortTable(colIndex) {
                const table = document.getElementById("ngxTable");
                let rows = Array.from(table.rows).slice(1);
                if (rows.length === 0) return;

                const direction = table.getAttribute("data-sort-dir") === "asc" ? -1 : 1;

                rows.sort((a, b) => {
                    const get = (row, i) => row.cells[i]?.innerText ?? "";
                    let valA = get(a, colIndex);
                    let valB = get(b, colIndex);

                    // Strip % and commas for numeric compare
                    const clean = (v) => v.replace(/%/g, "").replace(/,/g, "");
                    const numA = parseFloat(clean(valA));
                    const numB = parseFloat(clean(valB));
                    const isNumeric = !isNaN(numA) && !isNaN(numB);

                    if (isNumeric) return (numA - numB) * direction;
                    return valA.localeCompare(valB) * direction;
                });

                rows.forEach(row => table.tBodies[0].appendChild(row));
                table.setAttribute("data-sort-dir", direction === 1 ? "asc" : "desc");
            }

            function filterTable() {
                const query = document.getElementById("searchInput").value.toLowerCase();
                const filtered = fullData.filter(row =>
                    Object.values(row).some(val => String(val ?? "").toLowerCase().includes(query))
                );
                renderTable(filtered);
            }

            function downloadCSV() {
               const header = ["Ticker","Open","Close","Change (%)","Volume","Value Traded","Transactions","Date"];
                
               const rows = fullData.map(row => [row.Ticker,row.Open,row.Close,row.Change_pct,row.Volume,row.Value_traded,row.Trades,row.Trade_Date]);
                
                const csv = [header, ...rows].map(r => r.join(",")).join("\\n");

                const blob = new Blob([csv], { type: "text/csv" });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = "ngx_data.csv";
                a.click();
                window.URL.revokeObjectURL(url);
            }

            document.getElementById("searchInput").addEventListener("input", filterTable);
            fetchData();
            setInterval(fetchData, 60000);
        </script>
    </body>
    </html>
    """

# ---------- BRVM API (Excel) ----------
@app.get("/api/brvm")
def get_brvm_data():
    try:
        path = os.path.join("static", "brvm_actions.xlsx")
        df = pd.read_excel(path)

        df["Trade_Date"] = pd.to_datetime(df["Trade_Date"]).dt.strftime("%Y-%m-%d")

        df = df.replace({np.nan: "-", np.inf: "-", -np.inf: "-"})

        return df.to_dict(orient="records")

    except Exception as e:
        return {"error": "BRVM API failed", "details": str(e)}


# ---------- BRVM SQL API ----------
@app.get("/api/brvm-sql")
def get_brvm_sql_data():
    try:
        query = """
        SELECT
            ticker AS Ticker,
            name AS Name,
            volume AS Volume,
            prev_close AS Prev_Close,
            open_price AS Open,
            close_price AS Close,
            change_pct AS Change_pct,
            trade_date AS Trade_Date
        FROM brvm_daily
        ORDER BY trade_date DESC, ticker ASC
        """

        df = pd.read_sql(query, con=engine)

        df["Trade_Date"] = pd.to_datetime(df["Trade_Date"]).dt.strftime("%Y-%m-%d")

        df = df.replace({np.nan: "-", np.inf: "-", -np.inf: "-"})

        return df.to_dict(orient="records")

    except Exception as e:
        return {"error": "BRVM SQL API failed", "details": str(e)}

@app.get("/brvm", response_class=HTMLResponse)
def frontend_brvm():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Données BRVM</title>
        <style>
            body { font-family: Arial; margin: 20px; }
            table { border-collapse: collapse; width: 100%; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: center; }
            th { background-color: #f2f2f2; cursor: pointer; }
            th:hover { background-color: #ddd; }
            /* color classes */
            .pos { color: green; font-weight: bold; }
            .neg { color: red; font-weight: bold; }
            .flat { color: gray; font-weight: bold; }
        </style>
    </head>
    <body>
        <h1> BRVM (Francophone West Africa Region)</h1>
        <table id="brvmTable" data-sort-dir="asc">
            <thead>
                <tr>
                    <th onclick="sortTable(0)">Ticker</th>
                    <th onclick="sortTable(1)">Name</th>
                    <th onclick="sortTable(2)">Volume</th>
                    <th onclick="sortTable(3)">Open</th>
                    <th onclick="sortTable(4)">Close</th>
                    <th onclick="sortTable(5)">Change (%)</th>
                    <th onclick="sortTable(6)">Date</th>
                </tr>
            </thead>
            <tbody></tbody>
        </table>
        <script>
            async function fetchData() {
                const res = await fetch("/api/brvm-sql");
                const data = await res.json();
                const tbody = document.querySelector("#brvmTable tbody");
                tbody.innerHTML = "";
                data.forEach(row => {
                    // Colorize Variation (%)
                    let varDisplay = row["Change_pct"];
                    let cls = "flat";

                    if (varDisplay !== "-" && varDisplay !== null && varDisplay !== undefined) {
                        // Handle strings like "1.23" or "1,23" or "1.23%"
                        const cleaned = String(varDisplay).replace("%","").replace(",", ".");
                        const num = parseFloat(cleaned);
                        if (!isNaN(num)) {
                            if (num > 0) cls = "pos";
                            else if (num < 0) cls = "neg";
                            else cls = "flat";
                            // ensure it shows with % and two decimals
                            varDisplay = num.toFixed(2) + "%";
                        } else {
                            // leave as-is if not parseable
                            varDisplay = row["Change_pct"];
                            cls = "flat";
                        }
                    }

                    const tr = document.createElement("tr");
                    tr.innerHTML = `
                        <td>${row["Ticker"] || "-"}</td>
                        <td>${row["Name"] || "-"}</td>
                        <td>${row["Volume"] || "-"}</td>
                        <td>${row["Open"] || "-"}</td>
                        <td>${row["Close"] || "-"}</td>
                        <td class="${cls}">${varDisplay ?? "-"}</td>
                        <td>${row["Trade_Date"] || "-"}</td>
                    `;
                    tbody.appendChild(tr);
                });
            }
            function sortTable(colIndex) {
    const table = document.getElementById("brvmTable");
    let rows = Array.from(table.rows).slice(1);
    if (rows.length === 0) return;

    const direction = table.getAttribute("data-sort-dir") === "asc" ? -1 : 1;

    rows.sort((a, b) => {
        const get = (row, i) => row.cells[i]?.innerText ?? "";
        let valA = get(a, colIndex);
        let valB = get(b, colIndex);

        const clean = (v) => v.replace(/%/g, "").replace(/,/g, "");
        const numA = parseFloat(clean(valA));
        const numB = parseFloat(clean(valB));
        const isNumeric = !isNaN(numA) && !isNaN(numB);

        if (isNumeric) return (numA - numB) * direction;
        return valA.localeCompare(valB) * direction;
    });

    rows.forEach(row => table.tBodies[0].appendChild(row));
    table.setAttribute("data-sort-dir", direction === 1 ? "asc" : "desc");
}
            fetchData();
        </script>
    </body>
    </html>
    """

@app.get("/api/market/latest")
def get_market_latest():
    try:
        query = """
        SELECT
            m.exchange_id,
            e.region,
            m.ticker,
            m.company_name,
            m.trade_date,
            m.open_price,
            m.close_price,
            m.change_pct,
            m.volume,
            m.value_traded,
            m.currency
        FROM market_data_daily m
        LEFT JOIN exchanges e ON m.exchange_id = e.exchange_id
        INNER JOIN (
            SELECT exchange_id, MAX(trade_date) AS latest_date
            FROM market_data_daily
            GROUP BY exchange_id
        ) latest
            ON m.exchange_id = latest.exchange_id
            AND m.trade_date = latest.latest_date
        ORDER BY m.exchange_id, m.ticker;
        """
        df = pd.read_sql(query, con=engine)
        df = df.replace({np.nan: "-", np.inf: "-", -np.inf: "-"})
        return df.to_dict(orient="records")
    except Exception as e:
        return {"error": "Market latest API failed", "details": str(e)}


@app.get("/api/market/top-gainers")
def get_market_top_gainers():
    try:
        query = """
        SELECT
            m.exchange_id,
            e.region,
            m.ticker,
            m.company_name,
            m.trade_date,
            m.close_price,
            m.change_pct,
            m.volume,
            m.value_traded,
            m.currency
        FROM market_data_daily m
        LEFT JOIN exchanges e ON m.exchange_id = e.exchange_id
        INNER JOIN (
            SELECT exchange_id, MAX(trade_date) AS latest_date
            FROM market_data_daily
            GROUP BY exchange_id
        ) latest
            ON m.exchange_id = latest.exchange_id
            AND m.trade_date = latest.latest_date
        WHERE m.change_pct IS NOT NULL
        ORDER BY m.change_pct DESC
        LIMIT 20;
        """
        df = pd.read_sql(query, con=engine)
        df = df.replace({np.nan: "-", np.inf: "-", -np.inf: "-"})
        return df.to_dict(orient="records")
    except Exception as e:
        return {"error": "Top gainers API failed", "details": str(e)}


@app.get("/api/market/top-volume")
def get_market_top_volume():
    try:
        query = """
        SELECT
            m.exchange_id,
            e.region,
            m.ticker,
            m.company_name,
            m.trade_date,
            m.close_price,
            m.change_pct,
            m.volume,
            m.value_traded,
            m.currency
        FROM market_data_daily m
        LEFT JOIN exchanges e ON m.exchange_id = e.exchange_id
        INNER JOIN (
            SELECT exchange_id, MAX(trade_date) AS latest_date
            FROM market_data_daily
            GROUP BY exchange_id
        ) latest
            ON m.exchange_id = latest.exchange_id
            AND m.trade_date = latest.latest_date
        WHERE m.volume IS NOT NULL
        ORDER BY m.volume DESC
        LIMIT 20;
        """
        df = pd.read_sql(query, con=engine)
        df = df.replace({np.nan: "-", np.inf: "-", -np.inf: "-"})
        return df.to_dict(orient="records")
    except Exception as e:
        return {"error": "Top volume API failed", "details": str(e)}

@app.get("/market", response_class=HTMLResponse)
def market_dashboard():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>DahoWealth Market Dashboard</title>
        <meta charset="utf-8" />
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            h1 { margin-bottom: 5px; }
            .cards { display: flex; gap: 15px; margin: 20px 0; flex-wrap: wrap; }
            .card { border: 1px solid #ddd; padding: 15px; border-radius: 8px; min-width: 180px; }
            a { text-decoration: none; color: #0b5ed7; font-weight: bold; }
            table { border-collapse: collapse; width: 100%; margin-top: 15px; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: center; }
            th { background-color: #f2f2f2; cursor: pointer; }
            .pos { color: green; font-weight: bold; }
            .neg { color: red; font-weight: bold; }
            .flat { color: gray; font-weight: bold; }
            button { padding: 8px 12px; margin-right: 8px; cursor: pointer; }
        </style>
    </head>
    <body>
        <h1>DahoWealth Market Dashboard</h1>
        <p>Unified market data across U.S., BRVM, and NGX.</p>

        <div class="cards">
            <div class="card"><a href="/brvm">BRVM Market</a></div>
            <div class="card"><a href="/ngx">NGX Nigeria</a></div>
        </div>
    <h3>Global</h3>
    <button onclick="loadData('/api/market/top-gainers')">Global Gainers</button>
    <button onclick="loadData('/api/market/top-volume')">Global Volume</button>
    <button onclick="loadData('/api/market/latest')">Global Latest</button>
    
    <h3>USA</h3>
    <button onclick="loadData('/api/market/1/top-gainers')">USA Gainers</button>
    <button onclick="loadData('/api/market/1/top-volume')">USA Volume</button>
    <button onclick="loadData('/api/market/1/latest')">USA Latest</button>

    <h3>BRVM</h3>
    <button onclick="loadData('/api/market/2/top-gainers')">BRVM Gainers</button>
    <button onclick="loadData('/api/market/2/top-volume')">BRVM Volume</button>
    <button onclick="loadData('/api/market/2/latest')">BRVM Latest</button>
    
    <h3>Nigeria</h3>
    <button onclick="loadData('/api/market/3/top-gainers')">Nigeria Gainers</button>
    <button onclick="loadData('/api/market/3/top-volume')">Nigeria Volume</button>
    <button onclick="loadData('/api/market/3/latest')">Nigeria Latest</button>

        <table id="marketTable">
            <thead>
                <tr>
                    <th>Exchange</th>
                    <th>Ticker</th>
                    <th>Company</th>
                    <th>Date</th>
                    <th>Close</th>
                    <th>Change (%)</th>
                    <th>Volume</th>
                    <th>Value Traded</th>
                    <th>Currency</th>
                </tr>
            </thead>
            <tbody></tbody>
        </table>

        <script>
            async function loadData(endpoint) {
                const res = await fetch(endpoint);
                const data = await res.json();
                const tbody = document.querySelector("#marketTable tbody");
                tbody.innerHTML = "";

                data.forEach(row => {
                    let change = row.change_pct ?? "-";
                    let cls = "flat";

                    if (change !== "-" && change !== null) {
                        const num = parseFloat(change);
                        if (!isNaN(num)) {
                            cls = num > 0 ? "pos" : num < 0 ? "neg" : "flat";
                            change = num.toFixed(2) + "%";
                        }
                    }

                    const tr = document.createElement("tr");
                    tr.innerHTML = `
                        <td>${row.region ?? row.exchange_id ?? "-"}</td>
                        <td>${row.ticker ?? "-"}</td>
                        <td>${row.company_name ?? "-"}</td>
                        <td>${row.trade_date ?? "-"}</td>
                        <td>${row.close_price ?? "-"}</td>
                        <td class="${cls}">${change}</td>
                        <td>${row.volume ?? "-"}</td>
                        <td>${row.value_traded ?? "-"}</td>
                        <td>${row.currency ?? "-"}</td>
                    `;
                    tbody.appendChild(tr);
                });
            }

            loadData('/api/market/top-gainers');
        </script>
    </body>
    </html>
    """
@app.get("/api/market/{exchange_id}/top-gainers")
def exchange_top_gainers(exchange_id: int):
    try:
        query = text("""
        SELECT
            m.exchange_id,
            e.region,
            m.ticker,
            m.company_name,
            m.trade_date,
            m.close_price,
            m.change_pct,
            m.volume,
            m.value_traded,
            m.currency
        FROM market_data_daily m
        LEFT JOIN exchanges e ON m.exchange_id = e.exchange_id
        INNER JOIN (
            SELECT exchange_id, MAX(trade_date) AS latest_date
            FROM market_data_daily
            GROUP BY exchange_id
        ) latest
            ON m.exchange_id = latest.exchange_id
            AND m.trade_date = latest.latest_date
        WHERE m.exchange_id = :exchange_id
        AND m.change_pct IS NOT NULL
        ORDER BY m.change_pct DESC
        LIMIT 20;
        """)

        df = pd.read_sql(query, con=engine, params={"exchange_id": exchange_id})
        df = df.replace({np.nan: "-", np.inf: "-", -np.inf: "-"})
        return df.to_dict(orient="records")

    except Exception as e:
        return {"error": "Exchange top gainers API failed", "details": str(e)}
@app.get("/api/market/{exchange_id}/top-volume")
def exchange_top_volume(exchange_id: int):
    try:
        query = text("""
        SELECT
            m.exchange_id,
            e.region,
            m.ticker,
            m.company_name,
            m.trade_date,
            m.close_price,
            m.change_pct,
            m.volume,
            m.value_traded,
            m.currency
        FROM market_data_daily m
        LEFT JOIN exchanges e ON m.exchange_id = e.exchange_id
        INNER JOIN (
            SELECT exchange_id, MAX(trade_date) AS latest_date
            FROM market_data_daily
            GROUP BY exchange_id
        ) latest
            ON m.exchange_id = latest.exchange_id
            AND m.trade_date = latest.latest_date
        WHERE m.exchange_id = :exchange_id
        AND m.volume IS NOT NULL
        ORDER BY m.volume DESC
        LIMIT 20;
        """)

        df = pd.read_sql(query, con=engine, params={"exchange_id": exchange_id})
        df = df.replace({np.nan: "-", np.inf: "-", -np.inf: "-"})
        return df.to_dict(orient="records")

    except Exception as e:
        return {"error": "Exchange top volume API failed", "details": str(e)}
@app.get("/api/market/{exchange_id}/latest")
def exchange_latest(exchange_id: int):
    try:
        query = text("""
        SELECT
            m.exchange_id,
            e.region,
            m.ticker,
            m.company_name,
            m.trade_date,
            m.open_price,
            m.close_price,
            m.change_pct,
            m.volume,
            m.value_traded,
            m.currency
        FROM market_data_daily m
        LEFT JOIN exchanges e ON m.exchange_id = e.exchange_id
        INNER JOIN (
            SELECT exchange_id, MAX(trade_date) AS latest_date
            FROM market_data_daily
            GROUP BY exchange_id
        ) latest
            ON m.exchange_id = latest.exchange_id
            AND m.trade_date = latest.latest_date
        WHERE m.exchange_id = :exchange_id
        ORDER BY m.ticker;
        """)

        df = pd.read_sql(query, con=engine, params={"exchange_id": exchange_id})
        df = df.replace({np.nan: "-", np.inf: "-", -np.inf: "-"})
        return df.to_dict(orient="records")

    except Exception as e:
        return {"error": "Exchange latest API failed", "details": str(e)}
