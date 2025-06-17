import os
import requests
import pandas as pd
from bs4 import BeautifulSoup
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# Serve static files like logo.png
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def homepage():
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>DahoWealth NGX & BRVM</title>
        <style>
            body { font-family: Arial, sans-serif; padding: 20px; }
            img { height: 80px; }
            .links { margin-top: 10px; }
            .links a { margin-right: 15px; font-weight: bold; }
            table { border-collapse: collapse; width: 100%; margin-top: 20px; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: center; }
            th { background-color: #f2f2f2; }
        </style>
    </head>
    <body>
        <img src="/static/logo.png" alt="DahoWealth Logo" />
        <div class="links">
            <a href="https://www.facebook.com/people/Daho-Wealth/61575871481173/" target="_blank">Facebook</a>
            <a href="https://www.tiktok.com/@DahoWealth" target="_blank">TikTok</a>
            <a href="https://www.linkedin.com/in/jpsossavi/" target="_blank">LinkedIn</a>
        </div>
        <h1>Bienvenue sur DahoWealth</h1>
        <ul>
            <li><a href="/ngx">Voir l'API NGX 📈</a></li>
            <li><a href="/brvm">Voir les données BRVM 📊</a></li>
        </ul>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/ngx", response_class=JSONResponse)
async def ngx_api():
    return {"message": "Bienvenue sur l’API temps réel NGX 📈"}

@app.get("/brvm", response_class=HTMLResponse)
async def brvm_data():
    url = "https://www.brvm.org/fr/cours-actions/0"
    try:
        resp = requests.get(url, verify=False, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table")
        if not table:
            return HTMLResponse(content="<p>Tableau non trouvé sur le site BRVM.</p>")

        headers = [th.text.strip() for th in table.find_all("th")]
        rows = []
        for tr in table.find_all("tr")[1:]:
            cols = [td.text.strip() for td in tr.find_all("td")]
            if cols:
                rows.append(cols)

        df = pd.DataFrame(rows, columns=headers)
        table_html = df.to_html(index=False, border=1)

        return HTMLResponse(content=f"""
        <html><body>
        <h2>Données BRVM (scrapées)</h2>
        {table_html}
        </body></html>
        """)

    except Exception as e:
        return HTMLResponse(content=f"<p>Erreur lors de la récupération : {str(e)}</p>")
