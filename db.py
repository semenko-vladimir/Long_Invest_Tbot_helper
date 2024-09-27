import sqlite3
import os

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

# Функция для создания таблицы config
def create_table_config():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS config (
            id INTEGER PRIMARY KEY,
            chat_id INTEGER,
            collapse_updates BOOLEAN,
            collapse_updates_time TIMESTAMP,
            market_updates BOOLEAN,
            market_updates_time TIMESTAMP,
            FOREIGN KEY (chat_id) REFERENCES users (chat_id)
        )
    ''')
    conn.commit()
    conn.close()

# Функция для создания таблицы tpsl
def create_table_tpsl():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tpsl (
            id INTEGER PRIMARY KEY,
            chat_id INTEGER,
            trigger BOOLEAN,
            time TIMESTAMP,
            auto_market BOOLEAN,
            take_profit FLOAT,
            stop_loss FLOAT,
            FOREIGN KEY (chat_id) REFERENCES users (chat_id)
        )
    ''')
    conn.commit()
    conn.close()

def create_table_strategy_rsi():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS strategy_rsi (
            id INTEGER PRIMARY KEY,
            chat_id INTEGER,
            trigger BOOLEAN,
            time TIMESTAMP,
            auto_market BOOLEAN,
            period FLOAT,
            higthLevel FLOAT,
            lowLevel FLOAT,
            FOREIGN KEY (chat_id) REFERENCES users (chat_id)
        )
    ''')
    conn.commit()
    conn.close()

def create_table_strategy_sma():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS strategy_sma (
            id INTEGER PRIMARY KEY,
            chat_id INTEGER,
            trigger BOOLEAN,
            time TIMESTAMP,
            auto_market BOOLEAN,
            fastLength INTEGER,
            slowLength INTEGER,
            FOREIGN KEY (chat_id) REFERENCES users (chat_id)
        )
    ''')
    conn.commit()
    conn.close()



def delete_config_table():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS config')
    conn.commit()
    conn.close()

def delete_tpsl_table():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS tpsl')
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

def update_config_collapse(chat_id, collapse_updates_time, collapse_updates, market_updates_time, market_updates):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM config WHERE chat_id = ?", (chat_id,))
    row = cursor.fetchone()
    if row is None:
        cursor.execute("INSERT INTO config (chat_id, collapse_updates, collapse_updates_time, market_updates, market_updates_time) VALUES (?, ?, ?, ?, ?)", 
                       (chat_id, collapse_updates, collapse_updates_time, market_updates, market_updates_time))
    else:
        cursor.execute("UPDATE config SET collapse_updates = ?, collapse_updates_time = ?, market_updates = ?, market_updates_time = ? WHERE chat_id = ?", 
                       (collapse_updates, collapse_updates_time, market_updates, market_updates_time, chat_id))
    conn.commit()
    conn.close()

def update_tpsl(chat_id, tp_value, sl_value, time_value, auto_market, trigger):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tpsl WHERE chat_id = ?", (chat_id,))
    row = cursor.fetchone()
    if row is None:
        cursor.execute("INSERT INTO tpsl (chat_id, take_profit, stop_loss, time, auto_market, trigger) VALUES (?, ?, ?, ?, ?, ?)",
                       (chat_id, tp_value, sl_value, time_value, auto_market, trigger))
    else:
        cursor.execute("UPDATE tpsl SET take_profit = ?, stop_loss = ?, time = ?, auto_market = ?, trigger = ? WHERE chat_id = ?",
                       (tp_value, sl_value, time_value, auto_market, trigger, chat_id))
    conn.commit()
    conn.close()

def update_strategy_rsi(chat_id, trigger, time_value, auto_market, period, highLevel, lowLevel):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM strategy_rsi WHERE chat_id = ?", (chat_id,))
    row = cursor.fetchone()
    if row is None:
        cursor.execute("INSERT INTO strategy_rsi (chat_id, trigger, time, auto_market, period, higthLevel, lowLevel) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (chat_id, trigger, time_value, auto_market, period, highLevel, lowLevel))
    else:
        cursor.execute("UPDATE strategy_rsi SET trigger = ?, time = ?, auto_market = ?, period = ?, higthLevel = ?, lowLevel = ? WHERE chat_id = ?",
                       (trigger, time_value, auto_market, period, highLevel, lowLevel, chat_id))
    conn.commit()
    conn.close()

def update_strategy_sma(chat_id, trigger, time_value, auto_market, fastLength, slowLength):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM strategy_sma WHERE chat_id = ?", (chat_id,))
    row = cursor.fetchone()
    if row is None:
        cursor.execute("INSERT INTO strategy_sma (chat_id, trigger, time, auto_market, fastLength, slowLength) VALUES (?, ?, ?, ?, ?, ?)",
                       (chat_id, trigger, time_value, auto_market, fastLength, slowLength))
    else:
        cursor.execute("UPDATE strategy_sma SET trigger = ?, time = ?, auto_market = ?, fastLength = ?, slowLength = ? WHERE chat_id = ?",
                       (trigger, time_value, auto_market, fastLength, slowLength, chat_id))
    conn.commit()
    conn.close()

def get_config():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM config")
    config = cursor.fetchall()
    conn.close()
    return config


def get_tpsl():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tpsl")
    tpsl = cursor.fetchall()
    conn.close()
    return tpsl

def get_rsi():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM strategy_rsi")
    rsi_data = cursor.fetchall()
    conn.close()
    return rsi_data

def get_sma():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM strategy_sma")
    rsi_data = cursor.fetchall()
    conn.close()
    return rsi_data


