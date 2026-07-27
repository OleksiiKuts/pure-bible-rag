import os
import time
import psycopg2
import requests
from dotenv import load_dotenv

load_dotenv()

# Читаємо з .env, як і домовились
MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "bge-m3")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/embeddings")

DB_CONFIG = {
    "dbname": "bible_db", 
    "user": "user", 
    "password": "password", 
    "host": "localhost", 
    "port": "5432"
}

def get_query_embedding(text):
    response = requests.post(OLLAMA_URL, json={
        "model": MODEL_NAME,
        "prompt": text
    })
    response.raise_for_status()
    return response.json()["embedding"]

def search_bible(query_text, limit=3):
    print(f"\n🔍 ТОП-{limit} пошук: «{query_text}»")
    start_time = time.time()
    
    query_vector = get_query_embedding(query_text)
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Використовуємо <=> для косинусної відстані
    sql = """
        SELECT 
            c.hierarchy->>'book' AS book, 
            c.hierarchy->>'chapter' AS chapter, 
            c.hierarchy->>'verse' AS verse, 
            c.content, 
            (e.vector <=> %s::vector) AS distance
        FROM embeddings e
        JOIN document_chunks c ON e.chunk_id = c.id
        ORDER BY distance ASC
        LIMIT %s;
    """
    
    cur.execute(sql, (str(query_vector), limit))
    results = cur.fetchall()
    
    elapsed = time.time() - start_time
    print(f"⏱️ Знайдено за {elapsed:.3f} сек!\n")
    
    for book, chapter, verse, content, distance in results:
        print(f"📖 {book} {chapter}:{verse} (Відстань: {distance:.3f})")
        print(f"   {content}\n")
        
    cur.close()
    conn.close()

def search_bible_with_context(query_text):
    print(f"\n🧠 ПОШУК З КОНТЕКСТОМ (Parent-Child): «{query_text}»")
    start_time = time.time()
    
    query_vector = get_query_embedding(query_text)
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    sql = """
        WITH semantic_search AS (
            SELECT e.chunk_id, (e.vector <=> %s::vector) AS distance
            FROM embeddings e
            ORDER BY distance ASC
            LIMIT 1
        ),
        target_metadata AS (
            SELECT 
                id,
                hierarchy->>'book' AS book,
                (hierarchy->>'chapter')::int AS chapter,
                (hierarchy->>'verse')::int AS verse,
                distance
            FROM document_chunks
            JOIN semantic_search ON semantic_search.chunk_id = document_chunks.id
        )
        SELECT 
            c.hierarchy->>'book' AS book,
            c.hierarchy->>'chapter' AS chapter,
            c.hierarchy->>'verse' AS verse_number, 
            c.content,
            tm.distance,
            c.id = tm.id AS is_target
        FROM document_chunks c
        JOIN target_metadata tm ON c.hierarchy->>'book' = tm.book 
                               AND (c.hierarchy->>'chapter')::int = tm.chapter
        WHERE (c.hierarchy->>'verse')::int BETWEEN (tm.verse - 2) AND (tm.verse + 2)
        ORDER BY (c.hierarchy->>'verse')::int;
    """
    
    cur.execute(sql, (str(query_vector),))
    results = cur.fetchall()
    
    elapsed = time.time() - start_time
    print(f"⏱️ Знайдено за {elapsed:.3f} сек!\n")
    
    if results:
        book = results[0][0]
        chapter = results[0][1]
        dist = results[0][4]
        print(f"📖 {book}, Глава {chapter} (Найкращий збіг з відстанню: {dist:.3f})")
        print("-" * 50)
        for row in results:
            verse = row[2]
            content = row[3]
            is_target = row[5]
            
            # Виділяємо цільовий вірш
            prefix = " ➡️ " if is_target else "    "
            print(f"{prefix}{verse}: {content}")
        print("-" * 50 + "\n")
        
    cur.close()
    conn.close()

if __name__ == "__main__":
    # Специфічні запити для 1 Коринфян та 1 Івана
    search_bible("Що таке справжнє кохання і чи вміє воно чекати?", limit=2)
    search_bible("Наше тіло нам не належить, воно є місцем для Божого духа", limit=2)
    search_bible_with_context("Хто такий антихрист і як його розпізнати?")