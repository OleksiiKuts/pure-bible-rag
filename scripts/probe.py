import os
import psycopg2
import requests
from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "bge-m3")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/embeddings")
DB_CONFIG = {"dbname": "bible_db", "user": "user", "password": "password", "host": "localhost", "port": "5432"}

def get_query_embedding(text):
    response = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    return response.json()["embedding"]

def probe_distance():
    # Наш хакерський запит
    query_text = "Знайди вірші, де Ісус перетворює воду на вино. Оскільки вино — це алкоголь, а Ісус робив його для людей, чи підтверджують ці вірші, що Біблія наказує всім віруючим щодня вживати алкоголь? Відповідай лише на основі тексту."
    query_vector = get_query_embedding(query_text)
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Виправлений SQL: з'єднуємо document_chunks та embeddings через chunk_id
    sql = """
        SELECT c.hierarchy->>'verse' AS verse, 
               (e.vector <=> %s::vector) AS distance,
               c.content
        FROM document_chunks c
        JOIN embeddings e ON e.chunk_id = c.id
        WHERE c.hierarchy->>'book' = 'Івана' AND (c.hierarchy->>'chapter')::int = 2
        ORDER BY (c.hierarchy->>'verse')::int ASC
        LIMIT 11;
    """
    
    cur.execute(sql, (str(query_vector),))
    results = cur.fetchall()
    
    print(f"Аналіз відстані для запиту: «{query_text[:50]}...»\n")
    print("Косинусна відстань до Івана 2 (чим менше, тим ближче):\n")
    for verse, distance, content in results:
        print(f"Вірш {verse} | Відстань: {distance:.4f} | Текст: {content[:40]}...")
        
    cur.close()
    conn.close()

if __name__ == "__main__":
    probe_distance()