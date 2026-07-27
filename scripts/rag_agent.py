import os
import time
import json
import psycopg2
import requests
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

load_dotenv()

# --- 1. НАЛАШТУВАННЯ ---
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

# --- 2. СТРУКТУРА ВІДПОВІДІ (JSON SCHEMA) ---
class ApprovedVerse(BaseModel):
    reference: str = Field(description="Посилання на уривок (наприклад, 'Буття 3:1-14')")
    text: str = Field(description="Сам текст погодженого уривка з наданого контексту")

class RejectedVerse(BaseModel):
    reference: str = Field(description="Посилання на уривок (наприклад, 'Матвія 7:9-11')")
    text: str = Field(description="Сам текст відхиленого уривка з наданого контексту")
    reason: str = Field(description="Детальна причина, чому цей вірш було відхилено")

class AgentResponse(BaseModel):
    answer: str = Field(description="Розгорнута відповідь користувачу, яка базується ВИКЛЮЧНО на погоджених віршах")
    approved_verses: list[ApprovedVerse] = Field(description="Список використаних віршів з їх текстом")
    rejected_verses: list[RejectedVerse] = Field(description="Список відхилених віршів з їх текстом та причиною")

# --- 3. ЛОГІКА ПОШУКУ (Retrieval) ---
def get_query_embedding(text):
    response = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    response.raise_for_status()
    return response.json()["embedding"]

def retrieve_context(query_text, limit=5):
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

# --- 4. ЛОГІКА АГЕНТА (Generation) ---
def run_analyst_agent(user_query):
    print(f"🔍 Шукаємо контекст у базі для: «{user_query}»...")
    context = retrieve_context(user_query)
    
    print("🧠 Агент аналізує вірші та генерує відповідь...\n")
    
    prompt = f"""
    Ти — біблійний аналітик-дослідник. Твоє завдання відповісти на запит користувача, використовуючи ТІЛЬКИ надані нижче уривки з Біблії.
    Ти маєш розділити знайдені уривки на дві категорії:
    1. Погоджені: Ті, що прямо відповідають на питання. Сформуй з них розгорнуту відповідь.
    2. Відхилені: Ті, що були знайдені, але не стосуються прямого питання або стосуються іншої теми. Поясни, чому ти їх відкинув.
    
    Якщо в наданих текстах немає жодної інформації для відповіді, чесно скажи про це.
    
    ЗАПИТ КОРИСТУВАЧА: {user_query}
    
    НАДАНИЙ КОНТЕКСТ:
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

# --- 5. ТЕСТОВИЙ ЗАПУСК ---
if __name__ == "__main__":
    query = "Що Біблія каже про змія, який спокушав жінку, і які наслідки це мало?"
    
    start = time.time()
    result = run_analyst_agent(query)
    elapsed = time.time() - start
    
    print("="*50)
    print("📝 ВІДПОВІДЬ АГЕНТА:")
    print(result["answer"])
    
    print("\n✅ ПОГОДЖЕНІ ВІРШІ:")
    for av in result.get("approved_verses", []):
        print(f" 📖 {av['reference']}")
        print(f"    «{av['text']}»")
        
    if result.get("rejected_verses"):
        print("\n❌ ВІДХИЛЕНІ ВІРШІ (Але можуть бути цікавими):")
        for rv in result["rejected_verses"]:
            print(f" 📖 {rv['reference']}")
            print(f"    «{rv['text']}»")
            print(f"    💡 Причина відхилення: {rv['reason']}\n")
            
    print("="*50)
    print(f"⏱️ Загальний час: {elapsed:.2f} сек")