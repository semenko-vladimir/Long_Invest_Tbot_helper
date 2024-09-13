import sqlite3

def create_db(name):
    conn = sqlite3.connect(name)
    conn.close()

def delete_database(database_name):
    # Удаляем файл базы данных
    if os.path.exists(database_name):
        os.remove(database_name)

    # Удаляем все файлы с расширением .sqlite в текущем каталоге
    for file_name in os.listdir('.'):
        if file_name.endswith('.sqlite'):
            os.remove(file_name)

    # Удаляем файлы с расширением .db-journal в текущем каталоге
    for file_name in os.listdir('.'):
        if file_name.endswith('.db-journal'):
            os.remove(file_name)

    # Удаляем все файлы с расширением .sqlite-wal в текущем каталоге
    for file_name in os.listdir('.'):
        if file_name.endswith('.sqlite-wal'):
            os.remove(file_name)

    # Удаляем все файлы с расширением .sqlite-shm в текущем каталоге
    for file_name in os.listdir('.'):
        if file_name.endswith('.sqlite-shm'):
            os.remove(file_name)

    # Удаляем все файлы с расширением .sqlite-lock в текущем каталоге
    for file_name in os.listdir('.'):
        if file_name.endswith('.sqlite-lock'):
            os.remove(file_name)

    # Создаем соединение с базой данных (если она существует)
    conn = sqlite3.connect(database_name)
    cursor = conn.cursor()

    # Удаляем все таблицы в базе данных
    cursor.execute('''
        SELECT name FROM sqlite_master WHERE type='table';
    ''')
    tables = [table[0] for table in cursor.fetchall()]

    for table in tables:
        cursor.execute(f'DROP TABLE IF EXISTS {table};')

    # Закрываем соединение с базой данных
    conn.close()

def create_table_users():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY,
            t_token TEXT
        )
    ''')
    conn.commit()
    conn.close()

def create_user(chat_id, t_token):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (chat_id, t_token) VALUES (?, ?)", (chat_id, t_token))
    conn.commit()
    conn.close()
    
def get_t_token(chat_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT t_token FROM users WHERE chat_id = ?", (chat_id,))
    t_token = cursor.fetchone()
    conn.close()
    if t_token is None:
        return None
    else:
        return t_token[0]
    
