import json
import psycopg2
from psycopg2.extras import execute_values
from pathlib import Path
import uuid

# Налаштування підключення (використовуємо дані з docker-compose.yml)
DB_CONFIG = {
    "dbname": "bible_db",
    "user": "user",
    "password": "password",
    "host": "localhost",
    "port": "5432"
}

BASE_DIR = Path(__file__).resolve().parent.parent
JSON_PATH = BASE_DIR / 'data' / 'bible_parsed.json'

def init_db():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # 1. Вмикаємо розширення для векторів
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    
    # 2. Створюємо структуру
    cur.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id UUID PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            metadata JSONB
        );
        
        CREATE TABLE IF NOT EXISTS document_chunks (
            id UUID PRIMARY KEY,
            document_id UUID REFERENCES documents(id),
            content TEXT,
            hierarchy JSONB
        );
        
        CREATE TABLE IF NOT EXISTS embeddings (
            id UUID PRIMARY KEY,
            chunk_id UUID REFERENCES document_chunks(id),
            model_name VARCHAR(100),
            vector VECTOR(1536) -- Розмірність для OpenAI text-embedding-3-small
        );
    """)
    conn.commit()
    return conn, cur

def load_data(conn, cur):
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    # Реєструємо документ "Переклад нового світу"
    doc_id = uuid.uuid4()
    cur.execute("INSERT INTO documents (id, title) VALUES (%s, %s)", 
                (str(doc_id), "Переклад нового світу (nwt-K)"))
    
    # Підготовуємо дані для вставки
    chunks_to_insert = []
    for v in data:
        chunks_to_insert.append((
            str(uuid.uuid4()),
            str(doc_id),
            v['text'],
            json.dumps(v['hierarchy'])
        ))
    
    # Масова вставка
    execute_values(cur, """
        INSERT INTO document_chunks (id, document_id, content, hierarchy) 
        VALUES %s
    """, chunks_to_insert)
    
    conn.commit()
    print(f"✅ Базу даних успішно ініціалізовано. Завантажено {len(chunks_to_insert)} фрагментів.")

if __name__ == "__main__":
    conn, cur = init_db()
    load_data(conn, cur)
    cur.close()
    conn.close()