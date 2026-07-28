from fastapi import FastAPI, HTTPException
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

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Pure Bible RAG API is running"}

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