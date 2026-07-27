import zipfile
from bs4 import BeautifulSoup

epub_path = 'nwt_K.epub'
output_file = 'structure.txt'

print("Скануємо архів і читаємо заголовки файлів (це займе кілька секунд)...")

try:
    with zipfile.ZipFile(epub_path, 'r') as epub:
        # Беремо тільки текстові файли, відкидаємо картинки
        text_files = [f for f in epub.namelist() if f.endswith(('.html', '.xhtml')) and 'images/' not in f]
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for file_path in text_files:
                # Читаємо файл прямо з архіву
                content = epub.read(file_path)
                
                # Парсимо через BeautifulSoup, щоб дістати <title>
                soup = BeautifulSoup(content, 'lxml')
                title_tag = soup.find('title')
                title = title_tag.text.strip() if title_tag else "Без заголовка"
                
                # Записуємо у форматі: шлях_до_файлу ---> Справжня назва
                f.write(f"{file_path}  --->  {title}\n")
                
    print(f"\nГотово! Всю структуру записано у файл {output_file}.")
        
except Exception as e:
    print(f"Помилка: {e}")