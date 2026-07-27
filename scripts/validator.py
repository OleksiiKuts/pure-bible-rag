import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / 'data' / 'bible_parsed.json'

def validate():
    with open(DB_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    print("Шукаємо залишки приміток (символ '^')...")
    suspicious = [v for v in data if '^' in v['text']]
    
    if not suspicious:
        print("✅ Артефактів '^' не знайдено! База чиста.")
    else:
        print(f"❌ Знайдено {len(suspicious)} проблемних віршів:")
        for v in suspicious[:5]:
            h = v['hierarchy']
            print(f"   {h['book']} {h['chapter']}:{h['verse']} -> {v['text'][:50]}...")
            
    print("\nВибірка для контролю (кожен 999-й вірш з новою ієрархією):")
    for i, v in enumerate(data, 1):
        if i % 999 == 0:
            h = v['hierarchy']
            print(f"{i}. {h['book']} {h['chapter']}:{h['verse']} — {v['text']}")
            
    # Перевірка найостаннішого вірша Біблії
    last_verse = data[-1]
    h = last_verse['hierarchy']
    print(f"\nОстанній вірш бази: {h['book']} {h['chapter']}:{h['verse']} — {last_verse['text']}")

    print("\n--- Перевірка перших віршів вибіркових Псалмів (надписи) ---")
    target_psalms = [19, 38, 57, 76, 95, 114, 133, 150]
    for v in data:
        h = v['hierarchy']
        if h['book'] == 'Псалом' and h['chapter'] in target_psalms and h['verse'] == 1:
            print(f"📖 {h['book']} {h['chapter']}:{h['verse']} — {v['text']}")

if __name__ == "__main__":
    validate()