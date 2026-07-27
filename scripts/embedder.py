import os
import time
import uuid
import psycopg2
import requests
from psycopg2.extras import execute_values
from dotenv import load_dotenv

# Завантажуємо змінні оточення
load_dotenv()

# Читаємо конфігурацію з .env (з фолбеками на випадок відсутності)
MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "bge-m3")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/embeddings")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "500"))

DB_CONFIG = {
    "dbname": "bible_db", 
    "user": "user", 
    "password": "password", 
    "host": "localhost", 
    "port": "5432"
}

def get_embedding(text):
    """Отримує вектор з локального сервера Ollama"""
    response = requests.post(OLLAMA_URL, json={
        "model": MODEL_NAME,
        "prompt": text
    })
    response.raise_for_status()
    return response.json()["embedding"]

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    print("🔌 Підключаємось до бази даних...")
    cur.execute("""
        SELECT id, content FROM document_chunks 
        WHERE id NOT IN (SELECT chunk_id FROM embeddings)
        ORDER BY hierarchy->>'book', (hierarchy->>'chapter')::int, (hierarchy->>'verse')::int
    """)
    records = cur.fetchall()
    total_records = len(records)
    
    if total_records == 0:
        print("✅ Всі фрагменти вже векторизовані!")
        cur.close()
        conn.close()
        return

    print(f"🚀 Починаємо локальну векторизацію (Ollama: {MODEL_NAME}, {total_records} віршів).")
    start_time = time.time()

    processed_count = 0
    batch_data = []

    for row in records:
        chunk_id = row[0]
        text = row[1]
        
        try:
            vector = get_embedding(text)
            batch_data.append((str(uuid.uuid4()), chunk_id, MODEL_NAME, vector))
            processed_count += 1
            
            if len(batch_data) >= BATCH_SIZE:
                execute_values(
                    cur,
                    "INSERT INTO embeddings (id, chunk_id, model_name, vector) VALUES %s",
                    batch_data
                )
                conn.commit()
                elapsed = time.time() - start_time
                print(f"✅ Оброблено і збережено: {processed_count} / {total_records} (Минуло: {elapsed:.1f} сек)")
                batch_data = []
                
        except Exception as e:
            print(f"⚠️ Помилка на вірші {chunk_id}: {e}")

    # Зберігаємо залишки, якщо кількість віршів не кратна BATCH_SIZE
    if batch_data:
        execute_values(
            cur,
            "INSERT INTO embeddings (id, chunk_id, model_name, vector) VALUES %s",
            batch_data
        )
        conn.commit()

    cur.close()
    conn.close()
    
    total_time = time.time() - start_time
    print(f"🎉 Фініш! Біблію успішно векторизовано локально за {total_time:.1f} сек.")

if __name__ == "__main__":
    main()