from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from app.agents.filter_agent import run_semantic_filter

app = FastAPI(
    title="Pure Bible RAG API",
    description="Open Source мікросервіс для точного пошуку по Біблії",
    version="0.1.0"
)

class SearchRequest(BaseModel):
    query: str

class SearchResponse(BaseModel):
    approved_verses: list[dict]
    rejected_verses: list[dict]

@app.get("/", response_class=HTMLResponse)
def read_root():
    try:
        with open("app/static/index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>Файл інтерфейсу не знайдено</h1>"

@app.post("/api/v1/search", response_model=SearchResponse)
def search_bible(request: SearchRequest):
    try:
        result = run_semantic_filter(request.query)
        return SearchResponse(
            approved_verses=result.get("approved_verses", []),
            rejected_verses=result.get("rejected_verses", [])
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))