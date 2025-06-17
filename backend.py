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
    return {"message": "Market Data NGX 📈"}

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
            <img src="/static/logo.png" alt="DahoWealth" style="height: 60px;" />
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
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def fetch_brvm_data():
    url = "https://www.brvm.org/fr/cours-actions/0"
    resp = requests.get(url, timeout=10, verify=False)
    soup = BeautifulSoup(resp.text, "html.parser")

    tables = soup.find_all("table")
    target_table = None

    for table in tables:
        headers = [th.text.strip() for th in table.find_all("th")]
        if "Symbole" in headers and "Cours Clôture (FCFA)" in headers:
            target_table = table
            break

    if not target_table:
        return []

    headers = [th.text.strip() for th in target_table.find_all("th")]
    rows = []
    for tr in target_table.find_all("tr")[1:]:
        cells = [td.text.strip() for td in tr.find_all("td")]
        if cells:
            rows.append(dict(zip(headers, cells)))

    return rows

@app.get("/api/brvm")
def get_brvm_data():
    try:
        data = fetch_brvm_data()
        return data
    except Exception as e:
        return {"error": "Could not fetch BRVM data", "details": str(e)}

@app.get("/brvm", response_class=HTMLResponse)
def brvm_frontend():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Données BRVM</title>
        <style>
            body { font-family: Arial; margin: 20px; }
            table { border-collapse: collapse; width: 100%; margin-top: 10px; }
            th, td { border: 1px solid #ccc; padding: 8px; text-align: center; }
            th { background-color: #f4f4f4; }
        </style>
    </head>
    <body>
        <h1>Données BRVM en temps réel</h1>
        <table id="brvmTable">
            <thead></thead>
            <tbody></tbody>
        </table>

        <script>
            async function fetchBRVM() {
                const res = await fetch("/api/brvm");
                const data = await res.json();
                const table = document.getElementById("brvmTable");
                if (!data.length) return;

                const headers = Object.keys(data[0]);
                const thead = "<tr>" + headers.map(h => `<th>${h}</th>`).join("") + "</tr>";
                const tbody = data.map(row => {
                    return "<tr>" + headers.map(h => `<td>${row[h]}</td>`).join("") + "</tr>";
                }).join("");

                table.querySelector("thead").innerHTML = thead;
                table.querySelector("tbody").innerHTML = tbody;
            }

            fetchBRVM();
        </script>
    </body>
    </html>
    """
