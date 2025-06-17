from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
import pandas as pd
import numpy as np

app = FastAPI()

# Autoriser les appels depuis n'importe quel frontend
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

@app.get("/api/ngx")
def get_ngx_data():
    url = "https://doclib.ngxgroup.com/REST/api/statistics/equities/?market=&sector=&orderby=&pageSize=300&pageNo=0"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        data = response.json()

        # convertir en DataFrame
        df = pd.DataFrame(data)

        # Remplacer NaN, NaT, inf par None
        df = df.replace({np.nan: None, np.inf: None, -np.inf: None})

        return df.to_dict(orient="records")

    except Exception as e:
        return {"error": "Something went wrong", "details": str(e)}
    from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

@app.get("/ngx", response_class=HTMLResponse)
def show_frontend(request: Request):
    return templates.TemplateResponse("frontend.html", {"request": request})

