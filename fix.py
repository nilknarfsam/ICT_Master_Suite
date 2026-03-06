with open('models.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('sqlite3.connect(DB_PATH, timeout=', 'conectar_banco(timeout=')

with open('models.py', 'w', encoding='utf-8') as f:
    f.write(text)
