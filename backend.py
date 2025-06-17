from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
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

@app.get("/")
def root():
    return {"message": "Bienvenue sur l’API temps réel NGX 📈"}

# ---------- NGX API ----------
@app.get("/api/ngx")
def get_ngx_data():
    try:
        url = "https://doclib.ngxgroup.com/REST/api/statistics/equities/?market=&sector=&orderby=&pageSize=300&pageNo=0"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        df = pd.DataFrame(data)
        df = df.replace({np.nan: None, np.inf: None, -np.inf: None})
        return df.to_dict(orient="records")
    except Exception as e:
        return {"error": "NGX API failed", "details": str(e)}

@app.get("/ngx", response_class=HTMLResponse)
def frontend_ngx():
    return """
    <html>
    <head>
        <title>NGX</title>
    </head>
    <body>
        <h1>Données NGX</h1>
        <div id="table"></div>
        <script>
            async function load() {
                const res = await fetch("/api/ngx");
                const data = await res.json();
                let html = "<table border='1'><tr><th>Symbol</th><th>Open</th><th>Close</th></tr>";
                data.slice(0, 10).forEach(row => {
                    html += `<tr><td>${row.Symbol}</td><td>${row.OpeningPrice}</td><td>${row.ClosePrice}</td></tr>`;
                });
                html += "</table>";
                document.getElementById("table").innerHTML = html;
            }
            load();
        </script>
    </body>
    </html>
    """

# ---------- BRVM API ----------
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
        <h1>Données BRVM (scrapées)</h1>
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
