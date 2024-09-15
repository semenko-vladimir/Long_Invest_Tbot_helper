import sqlite3

# Функция для создания БД
# TODO: Сделать проверку на существование БД. Дополнить фукнционал созданием всех
# TODO: таблиц.
def create_db(name):
    conn = sqlite3.connect(name)
    conn.close()

# Функция для удаления БД
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


# Функция для создания таблицы users
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

# Функция для создания таблицы tickers
def create_table_tickers():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tickers (
            ticker TEXT PRIMARY KEY,
            user_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users (chat_id)
        )
    ''')
    conn.commit()
    conn.close()

# Функция для создания юзера
def create_user(chat_id, t_token):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (chat_id, t_token) VALUES (?, ?)", (chat_id, t_token))
    conn.commit()
    conn.close()
    

# Функция для получения токена тинькофф инвестиций
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
    
# Функция для добавления нового тикера
def insert_ticker(user_id, ticker):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tickers WHERE user_id = ? AND ticker = ?", (user_id, ticker))
    if cursor.fetchone():
        return "У вас уже есть этот тикер"
    else:
        cursor.execute("INSERT INTO tickers (user_id, ticker) VALUES (?, ?)", (user_id, ticker))
        conn.commit()
        conn.close()
        return "Тикер добавлен"
    
def delete_ticker(user_id, ticker):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tickers WHERE user_id = ? AND ticker = ?", (user_id, ticker))
    conn.commit()
    conn.close()
    
    
def get_all_tickers(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT ticker FROM tickers WHERE user_id = ?", (user_id,))
    tickers = cursor.fetchall()
    conn.close()
    return tickers

def delete_all_tickers(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tickers WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
