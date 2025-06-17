from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import requests
import pandas as pd
import numpy as np
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
# Servir les fichiers statiques (logo, images, etc.)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def root():
    return {"message": "Bienvenue sur l’API temps réel NGX 📈"}

@app.get("/api/ngx")
def get_ngx_data():
    url = "https://doclib.ngxgroup.com/REST/api/statistics/equities/?market=&sector=&orderby=&pageSize=300&pageNo=0"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        df = pd.DataFrame(data)
        df = df.replace({np.nan: None, np.inf: None, -np.inf: None})
        return df.to_dict(orient="records")
    except Exception as e:
        return {"error": "Something went wrong", "details": str(e)}

@app.get("/ngx", response_class=HTMLResponse)
def frontend_page():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Tableau NGX</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; text-align: center; }
            header { margin-bottom: 20px; }
            img { max-height: 100px; }
            .socials a {
                margin: 0 10px;
                text-decoration: none;
                font-weight: bold;
                color: #333;
            }
            table { border-collapse: collapse; width: 100%; margin-top: 20px; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: center; }
            th { background-color: #f2f2f2; cursor: pointer; }
            th:hover { background-color: #ddd; }
            input[type="text"] { padding: 6px; width: 300px; margin-bottom: 10px; }
            button { padding: 6px 12px; margin-left: 10px; cursor: pointer; }
        </style>
    </head>
    <body>
        <header>
            <img src="/static/logo.png" alt="DahoWealth Logo" />
            <div class="socials">
                <a href="https://www.facebook.com/people/Daho-Wealth/61575871481173/" target="_blank">Facebook</a>
                <a href="https://www.tiktok.com/@DahoWealth" target="_blank">TikTok</a>
                <a href="https://www.linkedin.com/in/jpsossavi/" target="_blank">LinkedIn</a>
            </div>
        </header>

        <h1>NGX Nigerian Stock Exchange Market Data</h1>

        <input type="text" id="searchInput" placeholder="🔍 Rechercher un symbole ou une valeur..." />
        <button onclick="downloadCSV()">📥 Télécharger CSV</button>

        <table id="ngxTable">
            <thead>
                <tr>
                    <th onclick="sortTable(0)">Symbole</th>
                    <th onclick="sortTable(1)">Ouverture</th>
                    <th onclick="sortTable(2)">Plus haut</th>
                    <th onclick="sortTable(3)">Plus bas</th>
                    <th onclick="sortTable(4)">Clôture</th>
                    <th onclick="sortTable(5)">Changement</th>
                    <th onclick="sortTable(6)">Volume</th>
                    <th onclick="sortTable(7)">Valeur</th>
                    <th onclick="sortTable(8)">Transactions</th>
                    <th onclick="sortTable(9)">Date</th>
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
                        <td>${row.Symbol || "-"}</td>
                        <td>${row.OpeningPrice || "-"}</td>
                        <td>${row.HighPrice || "-"}</td>
                        <td>${row.LowPrice || "-"}</td>
                        <td>${row.ClosePrice || "-"}</td>
                        <td>${row.Change || "-"}</td>
                        <td>${row.Volume || "-"}</td>
                        <td>${row.Value || "-"}</td>
                        <td>${row.Trades || "-"}</td>
                        <td>${row.TradeDate || "-"}</td>
                    `;
                    tbody.appendChild(tr);
                });
            }

            function sortTable(colIndex) {
                const table = document.getElementById("ngxTable");
                let rows = Array.from(table.rows).slice(1);
                const isNumeric = !isNaN(rows[1].cells[colIndex].innerText.replace(",", ""));
                const direction = table.getAttribute("data-sort-dir") === "asc" ? -1 : 1;
                rows.sort((a, b) => {
                    let valA = a.cells[colIndex].innerText;
                    let valB = b.cells[colIndex].innerText;
                    if (isNumeric) {
                        valA = parseFloat(valA.replace(",", "")) || 0;
                        valB = parseFloat(valB.replace(",", "")) || 0;
                    }
                    return valA > valB ? direction : valA < valB ? -direction : 0;
                });
                rows.forEach(row => table.tBodies[0].appendChild(row));
                table.setAttribute("data-sort-dir", direction === 1 ? "asc" : "desc");
            }

            function filterTable() {
                const query = document.getElementById("searchInput").value.toLowerCase();
                const filtered = fullData.filter(row => {
                    return Object.values(row).some(val =>
                        String(val).toLowerCase().includes(query)
                    );
                });
                renderTable(filtered);
            }

            function downloadCSV() {
                const csv = [
                    ["Symbole", "Ouverture", "Haut", "Bas", "Clôture", "Changement", "Volume", "Valeur", "Transactions", "Date"],
                    ...fullData.map(row => [
                        row.Symbol, row.OpeningPrice, row.HighPrice, row.LowPrice, row.ClosePrice,
                        row.Change, row.Volume, row.Value, row.Trades, row.TradeDate
                    ])
                ].map(e => e.join(",")).join("\\n");

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
