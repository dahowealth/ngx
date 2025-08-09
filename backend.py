from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import requests
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
import os

app = FastAPI()

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
    return {"message": "Bienvenue sur l’API temps réel NGX 📈 et BRVM 📊"}

# =========================
# ✅ NGX API (updated)
# =========================
@app.get("/api/ngx")
def get_ngx_data():
    url = "https://doclib.ngxgroup.com/REST/api/statistics/equities/?market=&sector=&orderby=&pageSize=300&pageNo=0"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()

        df = pd.DataFrame(data)

        # Ensure expected columns exist (API sometimes shifts fields)
        expected = [
            "Symbol", "OpeningPrice", "HighPrice", "LowPrice", "ClosePrice",
            "PreviousClosingPrice", "Change", "Volume", "Value", "Trades", "TradeDate"
        ]
        for col in expected:
            if col not in df.columns:
                df[col] = np.nan

        # Compute percentage change safely: (Close - PrevClose) / PrevClose * 100
        prev = pd.to_numeric(df["PreviousClosingPrice"], errors="coerce")
        close = pd.to_numeric(df["ClosePrice"], errors="coerce")
        df["ChangePct"] = ((close - prev) / prev * 100).round(2)

        # Clean NaNs/Infs
        df = df.replace({np.nan: None, np.inf: None, -np.inf: None})

        # Return canonical order + new field
        return df[expected + ["ChangePct"]].to_dict(orient="records")
    except Exception as e:
        return {"error": "Something went wrong", "details": str(e)}

# ✅ NGX FRONTEND (updated to display Change %)
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
        </style>
    </head>
    <body>
        <h1>Données NGX en temps réel</h1>

        <input type="text" id="searchInput" placeholder="🔍 Rechercher un symbole ou une valeur..." />
        <button onclick="downloadCSV()">📥 Télécharger CSV</button>

        <table id="ngxTable" data-sort-dir="asc">
            <thead>
                <tr>
                    <th onclick="sortTable(0)">Symbole</th>
                    <th onclick="sortTable(1)">Ouverture</th>
                    <th onclick="sortTable(2)">Plus haut</th>
                    <th onclick="sortTable(3)">Plus bas</th>
                    <th onclick="sortTable(4)">Clôture</th>
                    <th onclick="sortTable(5)">Changement</th>
                    <th onclick="sortTable(6)">Changement (%)</th>
                    <th onclick="sortTable(7)">Volume</th>
                    <th onclick="sortTable(8)">Valeur</th>
                    <th onclick="sortTable(9)">Transactions</th>
                    <th onclick="sortTable(10)">Date</th>
                </tr>
            </thead>
            <tbody></tbody>
        </table>

        <script>
            let fullData = [];

            async function fetchData() {
                const res = await fetch("/api/ngx");
                const data = await res.json();
                fullData = data;
                renderTable(data);
            }

            function renderTable(data) {
                const tbody = document.querySelector("#ngxTable tbody");
                tbody.innerHTML = "";
                data.forEach(row => {
                    const tr = document.createElement("tr");
                    tr.innerHTML = `
                        <td>${row.Symbol ?? "-"}</td>
                        <td>${row.OpeningPrice ?? "-"}</td>
                        <td>${row.HighPrice ?? "-"}</td>
                        <td>${row.LowPrice ?? "-"}</td>
                        <td>${row.ClosePrice ?? "-"}</td>
                        <td>${row.Change ?? "-"}</td>
                        <td>${row.ChangePct ?? "-"}</td>
                        <td>${row.Volume ?? "-"}</td>
                        <td>${row.Value ?? "-"}</td>
                        <td>${row.Trades ?? "-"}</td>
                        <td>${row.TradeDate ?? "-"}</td>
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

                    // Detect numeric by trying to parse after removing commas
                    const numA = parseFloat(valA.replace(/,/g, ""));
                    const numB = parseFloat(valB.replace(/,/g, ""));
                    const isNumeric = !isNaN(numA) && !isNaN(numB);

                    if (isNumeric) {
                        return (numA - numB) * direction;
                    } else {
                        return valA.localeCompare(valB) * direction;
                    }
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
                const header = ["Symbole","Ouverture","Haut","Bas","Clôture","Changement","Changement (%)","Volume","Valeur","Transactions","Date"];
                const rows = fullData.map(row => [
                    row.Symbol, row.OpeningPrice, row.HighPrice, row.LowPrice, row.ClosePrice,
                    row.Change, row.ChangePct, row.Volume, row.Value, row.Trades, row.TradeDate
                ]);
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

# ---------- BRVM API (unchanged) ----------
@app.get("/api/brvm")
def get_brvm_data():
    try:
        path = os.path.join("static", "brvm_actions.xlsx")
        df = pd.read_excel(path)
        df = df.replace({np.nan: "-", np.inf: "-", -np.inf: "-"})
        return df.to_dict(orient="records")
    except Exception as e:
        return {"error": "BRVM API failed", "details": str(e)}

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
            th { background-color: #f2f2f2; }
        </style>
    </head>
    <body>
        <h1>Données BRVM UEMOA (Francophone West Africa Region)</h1>
        <table id="brvmTable">
            <thead>
                <tr>
                    <th>Symbole</th>
                    <th>Nom</th>
                    <th>Volume</th>
                    <th>Ouverture</th>
                    <th>Clôture</th>
                    <th>Variation (%)</th>
                </tr>
            </thead>
            <tbody></tbody>
        </table>
        <script>
            async function fetchData() {
                const res = await fetch("/api/brvm");
                const data = await res.json();
                const tbody = document.querySelector("#brvmTable tbody");
                tbody.innerHTML = "";
                data.forEach(row => {
                    const tr = document.createElement("tr");
                    tr.innerHTML = `
                        <td>${row["Symbole"] || "-"}</td>
                        <td>${row["Nom"] || "-"}</td>
                        <td>${row["Volume"] || "-"}</td>
                        <td>${row["Cours Ouverture (FCFA)"] || "-"}</td>
                        <td>${row["Cours Clôture (FCFA)"] || "-"}</td>
                        <td>${row["Variation (%)"] || "-"}</td>
                    `;
                    tbody.appendChild(tr);
                });
            }
            fetchData();
        </script>
    </body>
    </html>
    """
