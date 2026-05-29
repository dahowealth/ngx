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
            m.price_in_usd,
            m.change_pct,
            m.volume,
            m.value_traded,
            m.value_traded_usd,
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
            m.price_in_usd,
            m.change_pct,
            m.volume,
            m.value_traded,
            m.value_traded_usd,
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
            m.price_in_usd,
            m.change_pct,
            m.volume,
            m.value_traded,
            m.value_traded_usd,
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
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 24px; background:#0f172a; color:#e5e7eb; }
            h1 { margin-bottom: 5px; }
            p { color:#cbd5e1; }
            button { padding: 12px 18px; margin: 5px; cursor: pointer; border:1px solid #334155; border-radius:10px; font-weight:bold; background: #111827;color: #e5e7eb; transition: all 0.2s ease; }
            button:hover {
                transform: translateY(-2px);
                box-shadow: 0 0 12px rgba(59,130,246,0.35);
            }
            .tab { background:#1e293b; color:#e5e7eb; }
            .active { background:#16a34a; color:white; }
            .grid { display:grid; grid-template-columns: repeat(2, 1fr); gap:20px; margin-top:20px; margin-bottom:40px; }
            .card { background:linear-gradient(180deg, #111827 0%, #0b1220 100%); border:1px solid #334155; padding:20px; border-radius:14px; box-shadow:0 6px 20px rgba(0,0,0,.25); overflow: hidden; }
            .brand { color:#94a3b8; font-size:12px; margin-top:6px; text-align:right; }
            table { border-collapse: collapse; width: 100%; margin-top: 25px; background:#111827; }
            th, td { border: 1px solid #334155; padding: 8px; }
            th { background:#1e293b; cursor:pointer; }
            td.text, th.text { text-align:left; }
            td.num, th.num { text-align:right; }
            .pos { color:#22c55e; font-weight:bold; }
            .neg { color:#ef4444; font-weight:bold; }
            .flat { color:#94a3b8; font-weight:bold; }
            .card {
            transition: transform 0.2s ease, box-shadow 0.2s ease;
    }

            .card:hover {
                transform: translateY(-3px);
                box-shadow: 0 0 25px rgba(59,130,246,0.25);
    }

            thead {
                position: sticky;
                top: 0;
                z-index: 10;
    }

            th {
                user-select: none;
    }
        </style>
    </head>
    <body>
        <h1 style="font-size:42px; margin-bottom:8px;">
            DahoWealth Market Dashboard
        </h1> 
        <div style="margin-top:12px; margin-bottom:24px; color:#94a3b8;">
            Real-time multi-market intelligence platform covering U.S., BRVM, and Nigerian equities.
        </div>
        

        <button class="tab active" onclick="loadExchange(0, this)">Global</button>
        <button class="tab" onclick="loadExchange(1, this)">USA</button>
        <button class="tab" onclick="loadExchange(2, this)">BRVM</button>
        <button class="tab" onclick="loadExchange(3, this)">Nigeria</button>

        <div class="grid">
            <div class="card"><h3>Top 5 Gainers</h3><canvas id="gainersChart"></canvas><div class="brand">By DahoWealth</div></div>
            <div class="card"><h3>Top 5 Losers</h3><canvas id="losersChart"></canvas><div class="brand">By DahoWealth</div></div>
            <div class="card"><h3>Top 5 Volume</h3><canvas id="volumeChart"></canvas><div class="brand">By DahoWealth</div></div>
            <div class="card"><h3>Top 5 Value Traded</h3><canvas id="valueChart"></canvas><div class="brand">By DahoWealth</div></div>
        </div>

        <h2>Latest Market Table</h2>
        <div style="display:flex; gap:12px; margin:18px 0; flex-wrap:wrap;">
        <input 
            id="searchInput"
            type="text"
            placeholder="Search ticker or company..."
            onkeyup="applyFilters()"
            style="
                padding:12px;
                border-radius:10px;
                border:1px solid #334155;
                background:#0f172a;
                color:#e5e7eb;
                min-width:260px;
            "
        >
    
        <select 
            id="sortFilter"
            onchange="applyFilters()"
            style="
                padding:12px;
                border-radius:10px;
                border:1px solid #334155;
                background:#0f172a;
                color:#e5e7eb;
            "
        >
            <option value="default">Default</option>
            <option value="gainers">Top Gainers</option>
            <option value="losers">Top Losers</option>
            <option value="volume">Highest Volume</option>
            <option value="value">Highest Value Traded</option>
        </select>
    </div>
    
    <table id="marketTable" data-sort-dir="asc">
            <thead>
                <tr>
                    <th class="text" onclick="sortMarketTable(0)">Exchange</th>
                    <th class="text" onclick="sortMarketTable(1)">Ticker</th>
                    <th class="text" onclick="sortMarketTable(2)">Company</th>
                    <th class="text" onclick="sortMarketTable(3)">Date</th>
                    <th class="num"  onclick="sortMarketTable(4)">Close</th>
                    <th class="num" onclick="sortMarketTable(5)">Close USD</th>
                    <th class="num"  onclick="sortMarketTable(6)">Change (%)</th>
                    <th class="num"  onclick="sortMarketTable(7)">Volume</th>
                    <th class="num"  onclick="sortMarketTable(8)">Value Traded</th>
                    <th class="num" onclick="sortMarketTable(9)">Value Traded USD</th>
                    <th class="text" onclick="sortMarketTable(10)">Currency</th>
                </tr>
            </thead>
            <tbody></tbody>
        </table>

        <script>
            let charts = {};
            let currentMarketData = [];

            function fmtNum(x, decimals=0) {
                if (x === null || x === undefined || x === "-") return "-";
                const n = Number(x);
                if (isNaN(n)) return x;
                return n.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
            }

            function makeChart(canvasId, labels, values, label, color) {
                if (charts[canvasId]) charts[canvasId].destroy();

                charts[canvasId] = new Chart(document.getElementById(canvasId), {
                type: "bar",
                data: {
                    labels: labels,
                    datasets: [{label: label,data: values,backgroundColor: color,borderColor: color,borderWidth: 1}]
        },
                options: {
                    responsive: true,
                    plugins: { legend: { labels: { color:"#e5e7eb" } } },
                    scales: {
                        x: { ticks: { color:"#cbd5e1" }, grid: { color:"#1f2937" } },
                        y: { ticks: { color:"#cbd5e1" }, grid: { color:"#1f2937" } }
                    }
                }
            });
        }

            async function getJSON(url) {
                const res = await fetch(url);
                return await res.json();
            }

            async function loadExchange(exchangeId, btn) {
                document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
                if (btn) btn.classList.add("active");

                const base = exchangeId === 0 ? "/api/market" : `/api/market/${exchangeId}`;

                const gainers = await getJSON(`${base}/top-gainers`);
                const losers = exchangeId === 0 ? [] : await getJSON(`${base}/top-losers`);
                const volume = await getJSON(`${base}/top-volume`);
                const value = exchangeId === 0 ? [] : await getJSON(`${base}/top-value`);
                const latest = await getJSON(`${base}/latest`);

                makeChart("gainersChart", gainers.slice(0,5).map(r=>r.ticker), gainers.slice(0,5).map(r=>Number(r.change_pct)), "Change %", "#22c55e");

                makeChart("losersChart", losers.slice(0,5).map(r=>r.ticker), losers.slice(0,5).map(r=>Number(r.change_pct)), "Change %", "#ef4444");

                makeChart("volumeChart", volume.slice(0,5).map(r=>r.ticker), volume.slice(0,5).map(r=>Number(r.volume)), "Volume", "#3b82f6");

                makeChart("valueChart", value.slice(0,5).map(r=>r.ticker), value.slice(0,5).map(r=>Number(r.value_traded_usd ?? r.value_traded)), "Value Traded USD", "#f59e0b");

                currentMarketData = latest;
                renderTable(currentMarketData);
            }

            function applyFilters() {
                const search = document.getElementById("searchInput").value.toLowerCase();
                const sort = document.getElementById("sortFilter").value;
            
                let filtered = currentMarketData.filter(row => {
                    const ticker = String(row.ticker ?? "").toLowerCase();
                    const company = String(row.company_name ?? "").toLowerCase();
                    return ticker.includes(search) || company.includes(search);
                });
            
                if (sort === "gainers") {
                    filtered.sort((a, b) => Number(b.change_pct ?? -999999) - Number(a.change_pct ?? -999999));
                }
            
                if (sort === "losers") {
                    filtered.sort((a, b) => Number(a.change_pct ?? 999999) - Number(b.change_pct ?? 999999));
                }
            
                if (sort === "volume") {
                    filtered.sort((a, b) => Number(b.volume ?? 0) - Number(a.volume ?? 0));
                }
            
                if (sort === "value") {
                    filtered.sort((a, b) => Number(b.value_traded_usd ?? b.value_traded ?? 0) - Number(a.value_traded_usd ?? a.value_traded ?? 0));
                }
            
                renderTable(filtered);
            }

            function renderTable(data) {
                const tbody = document.querySelector("#marketTable tbody");
                tbody.innerHTML = "";

                data.forEach(row => {
                    let change = row.change_pct ?? "-";
                    let cls = "flat";
                    const num = parseFloat(change);
                    if (!isNaN(num)) {
                        cls = num > 0 ? "pos" : num < 0 ? "neg" : "flat";
                        change = num.toFixed(2) + "%";
                    }

                    const tr = document.createElement("tr");
                    tr.innerHTML = `
                        <td class="text">${row.region ?? row.exchange_id ?? "-"}</td>
                        <td class="text">
                            <a href="/stock/${row.ticker}" style="color:#38bdf8; font-weight:bold; text-decoration:none;">
                                ${row.ticker ?? "-"}
                            </a>
                        </td>
                        <td class="text">${row.company_name ?? "-"}</td>
                        <td class="text">${row.trade_date ?? "-"}</td>
                        <td class="num">${fmtNum(row.close_price, 2)}</td>
                        <td class="num">${fmtNum(row.price_in_usd, 4)}</td>
                        <td class="num ${cls}">${change}</td>
                        <td class="num">${fmtNum(row.volume, 0)}</td>
                        <td class="num">${fmtNum(row.value_traded, 2)}</td>
                        <td class="num">${fmtNum(row.value_traded_usd, 2)}</td>
                        <td class="text">${row.currency ?? "-"}</td>
                    `;
                    tbody.appendChild(tr);
                });
            }
            function sortMarketTable(colIndex) {
                const table = document.getElementById("marketTable");
                let rows = Array.from(table.tBodies[0].rows);
                const currentDir = table.getAttribute("data-sort-dir") || "asc";
                const direction = currentDir === "asc" ? 1 : -1;

                rows.sort((a, b) => {
                    let valA = a.cells[colIndex].innerText.replace(/,/g, "").replace("%", "");
                    let valB = b.cells[colIndex].innerText.replace(/,/g, "").replace("%", "");

                    const numA = parseFloat(valA);
                    const numB = parseFloat(valB);

                    if (!isNaN(numA) && !isNaN(numB)) {
                        return (numA - numB) * direction;
        }

                    return valA.localeCompare(valB) * direction;
    });

                rows.forEach(row => table.tBodies[0].appendChild(row));
                table.setAttribute("data-sort-dir", currentDir === "asc" ? "desc" : "asc");
}
            loadExchange(0, document.querySelector(".tab"));
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
            m.price_in_usd,
            m.change_pct,
            m.volume,
            m.value_traded,
            m.value_traded_usd,
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
            m.price_in_usd,
            m.change_pct,
            m.volume,
            m.value_traded,
            m.value_traded_usd,
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
            m.price_in_usd,
            m.change_pct,
            m.volume,
            m.value_traded,
            m.value_traded_usd,
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

@app.get("/api/market/{exchange_id}/top-losers")
def exchange_top_losers(exchange_id: int):
    try:
        query = text("""
        SELECT m.exchange_id, e.region, m.ticker, m.company_name, m.trade_date,
               m.close_price, m.price_in_usd, m.change_pct, m.volume, m.value_traded, m.value_traded_usd, m.currency
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
        ORDER BY m.change_pct ASC
        LIMIT 5;
        """)
        df = pd.read_sql(query, con=engine, params={"exchange_id": exchange_id})
        df = df.replace({np.nan: "-", np.inf: "-", -np.inf: "-"})
        return df.to_dict(orient="records")
    except Exception as e:
        return {"error": "Exchange top losers API failed", "details": str(e)}


@app.get("/api/market/{exchange_id}/top-value")
def exchange_top_value(exchange_id: int):
    try:
        query = text("""
        SELECT m.exchange_id, e.region, m.ticker, m.company_name, m.trade_date,
               m.close_price, m.price_in_usd, m.change_pct, m.volume,
               m.value_traded, m.value_traded_usd, m.currency
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
        AND m.value_traded IS NOT NULL
        ORDER BY m.value_traded_usd DESC
        LIMIT 5;
        """)
        df = pd.read_sql(query, con=engine, params={"exchange_id": exchange_id})
        df = df.replace({np.nan: "-", np.inf: "-", -np.inf: "-"})
        return df.to_dict(orient="records")
    except Exception as e:
        return {"error": "Exchange top value API failed", "details": str(e)}


@app.get("/api/stock/{ticker}")
def get_stock(ticker: str):
    try:
        query = text("""
        SELECT
            exchange_id,
            ticker,
            company_name,
            trade_date,
            open_price,
            high_price,
            low_price,
            close_price,
            price_in_usd,
            change_pct,
            volume,
            value_traded,
            value_traded_usd,
            currency
        FROM market_data_daily
        WHERE ticker = :ticker
        ORDER BY trade_date DESC
        LIMIT 90;
        """)

        df = pd.read_sql(query, con=engine, params={"ticker": ticker.upper()})
        df = df.replace({np.nan: "-", np.inf: "-", -np.inf: "-"})
        return df.to_dict(orient="records")
    except Exception as e:
        return {"error": "Stock API failed", "details": str(e)}

@app.get("/stock/{ticker}", response_class=HTMLResponse)
def stock_page(ticker: str):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>DahoWealth - {ticker.upper()}</title>
        <meta charset="utf-8" />
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            body {{ margin:0; padding:24px; background:#0f172a; color:#e5e7eb; font-family:Arial, sans-serif; }}
            a {{ color:#38bdf8; text-decoration:none; }}
            .card {{ background:linear-gradient(180deg,#111827,#0b1220); border:1px solid #334155; padding:20px; border-radius:16px; margin-top:20px; }}
            .grid {{ display:grid; grid-template-columns: repeat(2, 1fr); gap:20px; }}
            .metric {{ font-size:28px; font-weight:bold; }}
            .muted {{ color:#94a3b8; }}
            .pos {{ color:#22c55e; }}
            .neg {{ color:#ef4444; }}
            table {{ border-collapse:collapse; width:100%; margin-top:20px; background:#111827; }}
            th, td {{ border:1px solid #334155; padding:8px; }}
            th {{ background:#1e293b; }}
            .text {{ text-align:left; }}
            .num {{ text-align:right; }}
        </style>
    </head>
    <body>
        <a href="/market">← Back to Market Dashboard</a>

        <h1>{ticker.upper()} Stock Detail</h1>
        <p class="muted">Historical market data powered by DahoWealth.</p>

        <div class="grid">
            <div class="card">
                <h3>Latest Price</h3>
                <div id="latestPrice" class="metric">Loading...</div>
                <div id="latestCurrency" class="muted"></div>
            </div>

            <div class="card">
                <h3>Latest Change</h3>
                <div id="latestChange" class="metric">Loading...</div>
                <div class="muted">Daily percentage change</div>
            </div>
        </div>

        <div class="grid">
            <div class="card">
                <h3>Price History</h3>
                <canvas id="priceChart"></canvas>
                <div class="muted" style="text-align:right;">By DahoWealth</div>
            </div>

            <div class="card">
                <h3>Volume History</h3>
                <canvas id="volumeChart"></canvas>
                <div class="muted" style="text-align:right;">By DahoWealth</div>
            </div>
        </div>

        <div class="card">
            <h3>Historical Data</h3>
            <table>
                <thead>
                    <tr>
                        <th class="text">Date</th>
                        <th class="num">Open</th>
                        <th class="num">High</th>
                        <th class="num">Low</th>
                        <th class="num">Close</th>
                        <th class="num">Close USD</th>
                        <th class="num">Change %</th>
                        <th class="num">Volume</th>
                    </tr>
                </thead>
                <tbody id="stockTable"></tbody>
            </table>
        </div>

        <script>
            const ticker = "{ticker.upper()}";
            let charts = {{}};

            function fmtNum(x, decimals=2) {{
                if (x === null || x === undefined || x === "-") return "-";
                const n = Number(x);
                if (isNaN(n)) return x;
                return n.toLocaleString(undefined, {{
                    minimumFractionDigits: decimals,
                    maximumFractionDigits: decimals
                }});
            }}

            async function loadStock() {{
                const res = await fetch(`/api/stock/${{ticker}}`);
                const data = await res.json();

                if (!Array.isArray(data) || data.length === 0) {{
                    document.body.innerHTML += "<h2>No data found for this ticker.</h2>";
                    return;
                }}

                const latest = data[0];

                document.getElementById("latestPrice").innerText = fmtNum(latest.close_price, 2);
                document.getElementById("latestCurrency").innerText = latest.currency ?? "";

                const change = Number(latest.change_pct);
                const changeEl = document.getElementById("latestChange");
                changeEl.innerText = isNaN(change) ? "-" : change.toFixed(2) + "%";
                changeEl.className = "metric " + (change > 0 ? "pos" : change < 0 ? "neg" : "");

                const ordered = [...data].reverse();
                const labels = ordered.map(r => r.trade_date);
                const prices = ordered.map(r => Number(r.price_in_usd ?? r.close_price));
                const volumes = ordered.map(r => Number(r.volume));

                new Chart(document.getElementById("priceChart"), {{
                    type: "line",
                    data: {{
                        labels: labels,
                        datasets: [{{
                            label: "Price USD",
                            data: prices,
                            borderColor: "#22c55e",
                            backgroundColor: "rgba(34,197,94,0.15)",
                            tension: 0.3,
                            fill: true
                        }}]
                    }},
                    options: {{
                        plugins: {{ legend: {{ labels: {{ color:"#e5e7eb" }} }} }},
                        scales: {{
                            x: {{ ticks: {{ color:"#cbd5e1", maxTicksLimit: 12}}, grid: {{ color:"#1f2937" }} }},
                            y: {{ ticks: {{ color:"#cbd5e1" }}, grid: {{ color:"#1f2937" }} }}
                        }}
                    }}
                }});

                new Chart(document.getElementById("volumeChart"), {{
                    type: "bar",
                    data: {{
                        labels: labels,
                        datasets: [{{
                            label: "Volume",
                            data: volumes,
                            backgroundColor: "#3b82f6"
                        }}]
                    }},
                    options: {{
                        plugins: {{ legend: {{ labels: {{ color:"#e5e7eb" }} }} }},
                        scales: {{
                            x: {{ ticks: {{ color:"#cbd5e1", maxTicksLimit: 12}}, grid: {{ color:"#1f2937" }} }},
                            y: {{ ticks: {{ color:"#cbd5e1" }}, grid: {{ color:"#1f2937" }} }}
                        }}
                    }}
                }});

                const tbody = document.getElementById("stockTable");
                tbody.innerHTML = "";

                data.forEach(row => {{
                    const tr = document.createElement("tr");
                    tr.innerHTML = `
                        <td class="text">${{row.trade_date ?? "-"}}</td>
                        <td class="num">${{fmtNum(row.open_price, 2)}}</td>
                        <td class="num">${{fmtNum(row.high_price, 2)}}</td>
                        <td class="num">${{fmtNum(row.low_price, 2)}}</td>
                        <td class="num">${{fmtNum(row.close_price, 2)}}</td>
                        <td class="num">${{fmtNum(row.price_in_usd, 4)}}</td>
                        <td class="num">${{fmtNum(row.change_pct, 2)}}%</td>
                        <td class="num">${{fmtNum(row.volume, 0)}}</td>
                    `;
                    tbody.appendChild(tr);
                }});
            }}

            loadStock();
        </script>
    </body>
    </html>
    """
    @app.get("/api/economy/summary")
    def economy_summary():
    query = text("""
        SELECT
            MIN(week_start) AS first_week,
            MAX(week_start) AS latest_week,
            COUNT(*) AS total_rows,
            COUNT(DISTINCT city_id) AS total_cities,
            COUNT(DISTINCT product_id) AS total_products
        FROM Benin_inflation.food_prices;
    """)
    with engine.connect() as conn:
        row = conn.execute(query).mappings().first()
        return dict(row)


@app.get("/api/economy/latest-prices")
def economy_latest_prices():
    query = text("""
        SELECT
            f.week_start,
            f.week_end,
            c.city_name,
            p.product_name,
            f.price,
            f.variation
        FROM Benin_inflation.food_prices f
        JOIN Benin_inflation.cities c ON f.city_id = c.city_id
        JOIN Benin_inflation.products p ON f.product_id = p.product_id
        WHERE f.week_start = (
            SELECT MAX(week_start)
            FROM Benin_inflation.food_prices
        )
        ORDER BY c.city_name, p.product_name;
    """)
    with engine.connect() as conn:
        return [dict(r) for r in conn.execute(query).mappings().all()]


@app.get("/api/economy/top-increases")
def economy_top_increases():
    query = text("""
        SELECT
            f.week_start,
            c.city_name,
            p.product_name,
            f.price,
            f.variation
        FROM Benin_inflation.food_prices f
        JOIN Benin_inflation.cities c ON f.city_id = c.city_id
        JOIN Benin_inflation.products p ON f.product_id = p.product_id
        WHERE f.week_start = (
            SELECT MAX(week_start)
            FROM Benin_inflation.food_prices
        )
        ORDER BY f.variation DESC
        LIMIT 20;
    """)
    with engine.connect() as conn:
        return [dict(r) for r in conn.execute(query).mappings().all()]

@app.get("/economy", response_class=HTMLResponse)
def economy_page():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Daho Wealth Economy Dashboard</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            body {
                background:#020617;
                color:#e5e7eb;
                font-family: Arial, sans-serif;
                padding:30px;
            }
            .card {
                background:#0f172a;
                border:1px solid #1e293b;
                border-radius:16px;
                padding:20px;
                margin:12px;
                box-shadow:0 8px 20px rgba(0,0,0,.25);
            }
            .grid {
                display:grid;
                grid-template-columns:repeat(auto-fit,minmax(220px,1fr));
                gap:16px;
                margin-bottom:30px;
            }
            table {
                width:100%;
                border-collapse:collapse;
                margin-top:20px;
                background:#0f172a;
            }
            th, td {
                padding:10px;
                border-bottom:1px solid #1e293b;
            }
            th {
                color:#38bdf8;
                text-align:left;
            }
            .pos { color:#22c55e; font-weight:bold; }
            .neg { color:#ef4444; font-weight:bold; }
        </style>
    </head>
    <body>
        <h1>🌍 Daho Wealth Economy Dashboard</h1>
        <p style="color:#94a3b8;">Benin food price and inflation intelligence powered by Daho Wealth data infrastructure.</p>

        <div class="grid">
            <div class="card"><h3>First Week</h3><div id="firstWeek">-</div></div>
            <div class="card"><h3>Latest Week</h3><div id="latestWeek">-</div></div>
            <div class="card"><h3>Cities</h3><div id="cities">-</div></div>
            <div class="card"><h3>Products</h3><div id="products">-</div></div>
            <div class="card"><h3>Total Records</h3><div id="rows">-</div></div>
        </div>

        <div class="card">
            <h2>Top Weekly Price Increases</h2>
            <table id="increaseTable">
                <thead>
                    <tr>
                        <th>Week</th>
                        <th>City</th>
                        <th>Product</th>
                        <th>Price</th>
                        <th>Variation %</th>
                    </tr>
                </thead>
                <tbody></tbody>
            </table>
        </div>

        <div class="card">
            <h2>Latest Prices</h2>
            <table id="latestTable">
                <thead>
                    <tr>
                        <th>Week</th>
                        <th>City</th>
                        <th>Product</th>
                        <th>Price</th>
                        <th>Variation %</th>
                    </tr>
                </thead>
                <tbody></tbody>
            </table>
        </div>

        <script>
            async function getJSON(url) {
                const res = await fetch(url);
                return await res.json();
            }

            function fmt(x) {
                if (x === null || x === undefined) return "-";
                const n = Number(x);
                if (isNaN(n)) return x;
                return n.toLocaleString();
            }

            async function loadEconomy() {
                const summary = await getJSON("/api/economy/summary");
                document.getElementById("firstWeek").innerText = summary.first_week;
                document.getElementById("latestWeek").innerText = summary.latest_week;
                document.getElementById("cities").innerText = summary.total_cities;
                document.getElementById("products").innerText = summary.total_products;
                document.getElementById("rows").innerText = fmt(summary.total_rows);

                const increases = await getJSON("/api/economy/top-increases");
                const incBody = document.querySelector("#increaseTable tbody");
                incBody.innerHTML = "";
                increases.forEach(r => {
                    incBody.innerHTML += `
                        <tr>
                            <td>${r.week_start}</td>
                            <td>${r.city_name}</td>
                            <td>${r.product_name}</td>
                            <td>${fmt(r.price)}</td>
                            <td class="${Number(r.variation) >= 0 ? 'pos' : 'neg'}">${r.variation}</td>
                        </tr>
                    `;
                });

                const latest = await getJSON("/api/economy/latest-prices");
                const latestBody = document.querySelector("#latestTable tbody");
                latestBody.innerHTML = "";
                latest.forEach(r => {
                    latestBody.innerHTML += `
                        <tr>
                            <td>${r.week_start}</td>
                            <td>${r.city_name}</td>
                            <td>${r.product_name}</td>
                            <td>${fmt(r.price)}</td>
                            <td class="${Number(r.variation) >= 0 ? 'pos' : 'neg'}">${r.variation}</td>
                        </tr>
                    `;
                });
            }

            loadEconomy();
        </script>
    </body>
    </html>
    """
