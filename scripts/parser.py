import zipfile
import json
import re
from bs4 import BeautifulSoup, NavigableString
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
EPUB_PATH = BASE_DIR / 'data' / 'nwt_K.epub'
OUTPUT_PATH = BASE_DIR / 'data' / 'bible_parsed.json'

def process_epub():
    all_verses = []
    print("Виконуємо точне налаштування (обробка надписів Псалмів та зачистка артефактів навігації)...\n")
    
    with zipfile.ZipFile(EPUB_PATH, 'r') as epub:
        namelist = epub.namelist()
        
        for book_idx in range(1001061105, 1001061171):
            prefix = f"OEBPS/{book_idx}"
            book_files = [f for f in namelist if f.startswith(prefix) and f.endswith('.xhtml') and '-extracted' not in f]
            
            def sort_key(filename):
                match = re.search(r'split(\d+)', filename)
                return int(match.group(1)) if match else 1
                
            book_files.sort(key=sort_key)
            
            book_name = None
            
            # Змінні стану перенесено сюди, але вони скидаються в кінці кожного файлу
            current_chapter = None
            current_verse = None
            current_text = []
            
            for file_path in book_files:
                content = epub.read(file_path)
                soup = BeautifulSoup(content, 'xml')
                
                if not book_name:
                    title_tag = soup.find('title')
                    if title_tag:
                        book_name = re.sub(r'\s+\d+$', '', title_tag.text.strip())
                    else:
                        book_name = f"Книга_{book_idx}"
                        
                # --- ХІРУРГІЧНА СТЕРИЛІЗАЦІЯ ---
                
                # 1. Заголовки (щоб технічні слова "Псалом 6" не дублювалися в тексті)
                for header in soup.find_all(['header', 'h1', 'h2']):
                    header.decompose()
                
                # 2. Точне видалення навігації (виправлено баг з класами xml-парсера)
                for tag in soup.find_all(['p', 'div']):
                    classes = tag.get('class', '')
                    if isinstance(classes, list):
                        classes = ' '.join(classes)
                    if 'navigation' in classes or 'biblebookname' in classes:
                        tag.decompose()
                        
                # 3. Примітки внизу файлу
                for bottom_notes in soup.find_all('div', class_=re.compile(r'groupFootnote|groupExt')):
                    bottom_notes.decompose()
                for aside in soup.find_all('aside'):
                    aside.decompose()
                    
                # 4. Посилання на примітки всередині тексту
                for a in soup.find_all('a', {'epub:type': 'noteref'}):
                    a.decompose()
                for span in soup.find_all('span', id=lambda x: x and x.startswith('footnotesource')):
                    span.decompose()
                    
                # 5. Номери сторінок та віршів
                for span in soup.find_all('span', class_=['pageNum', 'w_ch']):
                    span.decompose()
                for sup in soup.find_all('sup'):
                    if sup.parent and sup.parent.name == 'strong' and sup.text.strip().isdigit():
                        sup.parent.decompose()

                # --- ЕКСТРАКЦІЯ ТЕКСТУ З БУФЕРОМ ДЛЯ ПСАЛМІВ ---
                
                # Буфер збирає текст (напр., музичні вказівки), який іде ДО першого вірша у файлі
                pre_verse_buffer = []
                
                for node in soup.body.descendants:
                    if node.name == 'span' and node.has_attr('id'):
                        match = re.match(r'chapter(\d+)_verse(\d+)', node['id'])
                        if match:
                            # Зберігаємо попередній вірш
                            if current_verse is not None and current_text:
                                text = "".join(current_text).strip()
                                text = re.sub(r'\s+', ' ', text).replace(' ', ' ')
                                if text:
                                    all_verses.append({
                                        "hierarchy": {
                                            "book": book_name,
                                            "chapter": int(current_chapter),
                                            "verse": int(current_verse)
                                        },
                                        "text": text
                                    })
                            
                            current_chapter = match.group(1)
                            current_verse = match.group(2)
                            current_text = []
                            
                            # Якщо це ПЕРШИЙ вірш, і перед ним був текст (вказівки до Псалма)
                            # додаємо цей текст на самий початок
                            if pre_verse_buffer:
                                current_text.extend(pre_verse_buffer)
                                pre_verse_buffer = []
                                
                    elif isinstance(node, NavigableString):
                        text_str = str(node)
                        if current_verse is not None:
                            current_text.append(text_str)
                        else:
                            # Якщо вірш ще не почався, складаємо текст у буфер очікування
                            pre_verse_buffer.append(text_str)
                            
                # Файл закінчився: ЗБЕРІГАЄМО останній вірш і закриваємо його.
                # Це блокує перетікання в наступний розділ.
                if current_verse is not None and current_text:
                    text = "".join(current_text).strip()
                    text = re.sub(r'\s+', ' ', text).replace(' ', ' ')
                    if text:
                        all_verses.append({
                            "hierarchy": {
                                "book": book_name,
                                "chapter": int(current_chapter),
                                "verse": int(current_verse)
                            },
                            "text": text
                        })
                
                # Жорстке скидання стану перед переходом до нового файлу/глави
                current_verse = None
                current_text = []
            
            print(f"✔ Опрацьовано: {book_name}")

    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(all_verses, f, ensure_ascii=False, indent=2)
        
    print(f"\nСИСТЕМА ЧИСТА! Збережено {len(all_verses)} віршів у {OUTPUT_PATH}")

if __name__ == "__main__":
    process_epub()