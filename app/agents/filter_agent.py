import os
import json
import psycopg2
import requests
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# --- НАЛАШТУВАННЯ ---
MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "bge-m3")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/embeddings")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

DB_CONFIG = {
    "dbname": "bible_db", 
    "user": "user", 
    "password": "password", 
    "host": "localhost", 
    "port": "5432"
}

# --- СТРУКТУРА ВІДПОВІДІ (JSON SCHEMA) ---
class ApprovedVerse(BaseModel):
    reference: str = Field(description="Посилання на уривок (наприклад, 'Буття 3:1-14')")
    text: str = Field(description="Сам текст погодженого уривка з наданого контексту")

class RejectedVerse(BaseModel):
    reference: str = Field(description="Посилання на уривок (наприклад, 'Матвія 7:9-11')")
    text: str = Field(description="Сам текст відхиленого уривка з наданого контексту")
    reason: str = Field(description="Детальна причина, чому цей вірш було відхилено")

class AgentResponse(BaseModel):
    approved_verses: list[ApprovedVerse] = Field(description="Список використаних віршів з їх текстом")
    rejected_verses: list[RejectedVerse] = Field(description="Список відхилених віршів з їх текстом та причиною")

# --- ЛОГІКА ПОШУКУ (Retrieval) ---
def get_query_embedding(text: str) -> list[float]:
    response = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    response.raise_for_status()
    return response.json()["embedding"]

def retrieve_context(query_text: str, limit: int = 5) -> str:
    query_vector = get_query_embedding(query_text)
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    sql = """
        WITH semantic_search AS (
            SELECT chunk_id, (vector <=> %s::vector) AS distance
            FROM embeddings
            ORDER BY distance ASC
            LIMIT %s
        ),
        target_metadata AS (
            SELECT c.id, c.hierarchy->>'book' AS book, (c.hierarchy->>'chapter')::int AS chapter, (c.hierarchy->>'verse')::int AS verse
            FROM document_chunks c
            JOIN semantic_search s ON s.chunk_id = c.id
        )
        SELECT 
            t.book, t.chapter, 
            array_agg(c.hierarchy->>'verse' ORDER BY (c.hierarchy->>'verse')::int) as verses,
            string_agg(c.content, ' ' ORDER BY (c.hierarchy->>'verse')::int) as paragraph
        FROM target_metadata t
        JOIN document_chunks c ON c.hierarchy->>'book' = t.book AND (c.hierarchy->>'chapter')::int = t.chapter
        WHERE (c.hierarchy->>'verse')::int BETWEEN t.verse - 1 AND t.verse + 1
        GROUP BY t.book, t.chapter;
    """
    cur.execute(sql, (str(query_vector), limit))
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    context_blocks = []
    for book, chapter, verses, paragraph in results:
        verse_range = f"{verses[0]}-{verses[-1]}" if len(verses) > 1 else verses[0]
        context_blocks.append(f"[{book} {chapter}:{verse_range}] {paragraph}")
            
    return "\n\n".join(context_blocks)

# --- ЛОГІКА АГЕНТА (Generation) ---
def run_semantic_filter(user_query: str) -> dict:
    context = retrieve_context(user_query)
    
    prompt = f"""
    Ти — суворий біблійний семантичний фільтр. Твоє єдине завдання — проаналізувати запит користувача та надані уривки з Біблії.
    Ти не генеруєш відповідей, не трактуєш текст і не ведеш діалогів. 
    Ти лише ділиш надані уривки на дві категорії:
    1. Погоджені: Ті, що релевантні суті запиту.
    2. Відхилені: Ті, що не стосуються запиту. Коротко поясни причину відхилення.
    
    ЗАПИТ: {user_query}
    
    КОНТЕКСТ:
    {context}
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=AgentResponse,
            temperature=0.1
        )
    )

    return json.loads(response.text)