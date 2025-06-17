from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import requests
import pandas as pd
from bs4 import BeautifulSoup
import os

app = FastAPI()

# CORS config
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

@app.get("/api/brvm")
def get_brvm_data():
    url = "https://www.brvm.org/fr/cours-actions/0"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
    }

    try:
        response = requests.get(url, headers=headers, verify=False, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")

        table = soup.find("table")
        if not table:
            return {"data": [], "error": "Aucune table trouvée."}

        headers_row = [th.text.strip() for th in table.find_all("th")]
        rows = []
        for tr in table.find_all("tr")[1:]:
            cols = [td.text.strip() for td in tr.find_all("td")]
            if len(cols) == len(headers_row):
                rows.append(dict(zip(headers_row, cols)))

        return {"data": rows[:30]}  # retourne juste 30 lignes
    except Exception as e:
        return {"error": str(e)}

@app.get("/brvm", response_class=HTMLResponse)
def brvm_page():
    return """
    <html>
    <head>
        <title>Données BRVM</title>
        <style>
            body { font-family: Arial, sans-serif; padding: 20px; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: center; }
            th { background-color: #f4f4f4; }
        </style>
    </head>
    <body>
        <h2>Données BRVM (scrapées)</h2>
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
            async function loadData() {
                const res = await fetch('/api/brvm');
                const json = await res.json();
                const tbody = document.querySelector("#brvmTable tbody");
                tbody.innerHTML = "";

                if (json.data) {
                    json.data.forEach(row => {
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
                } else {
                    tbody.innerHTML = "<tr><td colspan='6'>Erreur de chargement</td></tr>";
                }
            }
            loadData();
        </script>
    </body>
    </html>
    """
