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
            t_token TEXT,
            sandbox_token TEXT,
            sandbox_trigger BOOLEAN
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
def create_table_signal_tpsl():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS signal_tpsl (
            id INTEGER PRIMARY KEY,
            chat_id INTEGER,
            take_profit FLOAT,
            stop_loss FLOAT,
            FOREIGN KEY (chat_id) REFERENCES users (chat_id)
        )
    ''')
    conn.commit()
    conn.close()

def create_table_signal_rsi():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS signal_rsi (
            id INTEGER PRIMARY KEY,
            chat_id INTEGER,
            period FLOAT,
            higthLevel FLOAT,
            lowLevel FLOAT,
            FOREIGN KEY (chat_id) REFERENCES users (chat_id)
        )
    ''')
    conn.commit()
    conn.close()

def create_table_signal_gpt():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS signal_gpt (
            id INTEGER PRIMARY KEY,
            chat_id INTEGER,
            text TEXT,
            FOREIGN KEY (chat_id) REFERENCES users (chat_id)
        )
    ''')
    conn.commit()
    conn.close()

def create_table_signal_sma():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS signal_sma (
            id INTEGER PRIMARY KEY,
            chat_id INTEGER,
            fastLength INTEGER,
            slowLength INTEGER,
            FOREIGN KEY (chat_id) REFERENCES users (chat_id)
        )
    ''')
    conn.commit()
    conn.close()

def create_table_signal_bollinger():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS signal_bollinger (
            id INTEGER PRIMARY KEY,
            chat_id INTEGER,
            period INTEGER,
            deviation FLOAT,
            type_ma TEXT,
            FOREIGN KEY (chat_id) REFERENCES users (chat_id)
        )
    ''')
    conn.commit()
    conn.close()


def create_table_signal_macd():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS signal_macd (
            id INTEGER PRIMARY KEY,
            chat_id INTEGER,
            fastLength INTEGER,
            slowLength INTEGER,
            signalLength INTEGER,
            FOREIGN KEY (chat_id) REFERENCES users (chat_id)
        )
    ''')
    conn.commit()
    conn.close()


def create_table_strategy():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS strategy (
            id INTEGER PRIMARY KEY,
            chat_id INTEGER,
                   
            tpls_trigger BOOLEAN,
            rsi_trigger BOOLEAN,
            sma_trigger BOOLEAN,
            alligator_trigger BOOLEAN,
            gpt_trigger BOOLEAN,
            lstm_trigger BOOLEAN,
            bollinger_trigger BOOLEAN,
            macd_trigger BOOLEAN,
                   
            time TIMESTAMP,
            auto_market BOOLEAN,
                   
            quantity INTEGER,
            joint BOOLEAN,
                   
            FOREIGN KEY (chat_id) REFERENCES users (chat_id)
        )
    ''')
    conn.commit()
    conn.close()


def create_table_signal_alligator():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS signal_alligator (
            id INTEGER PRIMARY KEY,
            chat_id INTEGER,
            jaw_period INTEGER,
            jaw_shift INTEGER,
            teeth_period INTEGER,
            teeth_shift INTEGER,
            lips_period INTEGER,
            lips_shift INTEGER,
            FOREIGN KEY (chat_id) REFERENCES users (chat_id)
        )
    ''')
    conn.commit()
    conn.close()


def create_table_margin():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS margin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            margin FLOAT,
            ticker TEXT,
            signals TEXT
        )
    ''')
    conn.commit()
    conn.close()

def create_table_buy():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS buy (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            price FLOAT,
            ticker TEXT,
            signals TEXT
        )
    ''')
    conn.commit()
    conn.close()

def new_margin(margin, ticker, signals):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO margin (margin, ticker, signals) VALUES (?, ?, ?)", (margin, ticker, signals))
    conn.commit()
    conn.close()

def new_buy(price, ticker, signals):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO buy (price, ticker, signals) VALUES (?, ?, ?)", (price, ticker, signals))
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
def create_user(chat_id, t_token, sandbox_token, sandbox_trigger=0):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (chat_id, t_token, sandbox_token, sandbox_trigger) VALUES (?, ?, ?, ?)",
                   (chat_id, t_token, sandbox_token, sandbox_trigger))
    conn.commit()
    conn.close()

def get_sandbox_trigger(chat_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT sandbox_trigger FROM users WHERE chat_id = ?", (chat_id,))
    row = cursor.fetchone()
    if row is None:
        return None
    else:
        return row[0]
    
def get_sandbox_token(chat_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT sandbox_token FROM users WHERE chat_id = ?", (chat_id,))
    row = cursor.fetchone()
    if row is None:
        return None
    else:
        return row[0]

def update_sandbox_trigger(chat_id, sandbox_trigger):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET sandbox_trigger = ? WHERE chat_id = ?", (sandbox_trigger, chat_id))
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

def update_signal_tpsl(chat_id, tp_value, sl_value):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM signal_tpsl WHERE chat_id = ?", (chat_id,))
    row = cursor.fetchone()
    if row is None:
        cursor.execute("INSERT INTO signal_tpsl (chat_id, take_profit, stop_loss) VALUES (?, ?, ?)",
                       (chat_id, tp_value, sl_value))
    else:
        cursor.execute("UPDATE signal_tpsl SET take_profit = ?, stop_loss = ? WHERE chat_id = ?",
                       (tp_value, sl_value, chat_id))
    conn.commit()
    conn.close()

def update_signal_rsi(chat_id, period, highLevel, lowLevel):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM signal_rsi WHERE chat_id = ?", (chat_id,))
    row = cursor.fetchone()
    if row is None:
        cursor.execute("INSERT INTO signal_rsi (chat_id, period, higthLevel, lowLevel) VALUES (?, ?, ?, ?)",
                       (chat_id, period, highLevel, lowLevel))
    else:
        cursor.execute("UPDATE signal_rsi SET period = ?, higthLevel = ?, lowLevel = ? WHERE chat_id = ?",
                       (period, highLevel, lowLevel, chat_id))
    conn.commit()
    conn.close()

def update_signal_sma(chat_id, fastLength, slowLength):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM signal_sma WHERE chat_id = ?", (chat_id,))
    row = cursor.fetchone()
    if row is None:
        cursor.execute("INSERT INTO signal_sma (chat_id, fastLength, slowLength) VALUES (?, ?, ?)",
                       (chat_id, fastLength, slowLength))
    else:
        cursor.execute("UPDATE signal_sma SET fastLength = ?, slowLength = ? WHERE chat_id = ?",
                       (fastLength, slowLength, chat_id))
    conn.commit()
    conn.close()

def update_signal_bollinger(chat_id, period, deviation, type_ma):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM signal_bollinger WHERE chat_id = ?", (chat_id,))
    row = cursor.fetchone()
    if row is None:
        cursor.execute("INSERT INTO signal_bollinger (chat_id, period, deviation, type_ma) VALUES (?, ?, ?, ?)",
                        (chat_id, period, deviation, type_ma))
    else:
        cursor.execute("UPDATE signal_bollinger SET period = ?, deviation = ?, type_ma = ? WHERE chat_id = ?",
                        (period, deviation, type_ma, chat_id))
    conn.commit()
    conn.close()


def update_signal_macd(chat_id, fastLength, slowLength, signalLength):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM signal_macd WHERE chat_id = ?", (chat_id,))
    row = cursor.fetchone()
    if row is None:
        cursor.execute("INSERT INTO signal_macd (chat_id, fastLength, slowLength, signalLength) VALUES (?, ?, ?, ?)",
                        (chat_id, fastLength, slowLength, signalLength))
    else:
        cursor.execute("UPDATE signal_macd SET fastLength = ?, slowLength = ?, signalLength = ? WHERE chat_id = ?",
                        (fastLength, slowLength, signalLength, chat_id))
    conn.commit()
    conn.close()


def update_signal_alligator(chat_id, jaw_period, jaw_shift, teeth_period, teeth_shift, lips_period, lips_shift):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM signal_alligator WHERE chat_id = ?", (chat_id,))
    row = cursor.fetchone()
    if row is None:
        cursor.execute('''INSERT INTO signal_alligator 
                          (chat_id, jaw_period, jaw_shift, teeth_period, teeth_shift, lips_period, lips_shift) 
                          VALUES (?, ?, ?, ?, ?, ?, ?)''',
                       (chat_id, jaw_period, jaw_shift, teeth_period, teeth_shift, lips_period, lips_shift))
    else:
        cursor.execute('''UPDATE signal_alligator 
                          SET jaw_period = ?, jaw_shift = ?, teeth_period = ?, teeth_shift = ?, lips_period = ?, lips_shift = ? 
                          WHERE chat_id = ?''',
                       (jaw_period, jaw_shift, teeth_period, teeth_shift, lips_period, lips_shift, chat_id))
    conn.commit()
    conn.close()

def update_signal_gpt(chat_id, text):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM signal_gpt WHERE chat_id = ?", (chat_id,))
    row = cursor.fetchone()
    if row is None:
        cursor.execute("INSERT INTO signal_gpt (chat_id, text) VALUES (?, ?)",
                       (chat_id, text))
    else:
        cursor.execute("UPDATE signal_gpt SET text = ? WHERE chat_id = ?",
                       (text, chat_id))
    conn.commit()
    conn.close()


def update_strategy(chat_id, tpls_trigger, rsi_trigger, sma_trigger, alligator_trigger, gpt_trigger, lstm_trigger, bollinger_trigger, macd_trigger, time, auto_market, quantity, joint):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM strategy WHERE chat_id = ?", (chat_id,))
    row = cursor.fetchone()
    if row is None:
        cursor.execute("INSERT INTO strategy (chat_id, tpls_trigger, rsi_trigger, sma_trigger, alligator_trigger, gpt_trigger, lstm_trigger, bollinger_trigger, macd_trigger, time, auto_market, quantity, joint) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       (chat_id, tpls_trigger, rsi_trigger, sma_trigger, alligator_trigger, gpt_trigger, lstm_trigger, bollinger_trigger, macd_trigger, time, auto_market, quantity, joint))
    else:
        cursor.execute("UPDATE strategy SET tpls_trigger = ?, rsi_trigger = ?, sma_trigger = ?, alligator_trigger = ?, gpt_trigger = ?, lstm_trigger = ?, bollinger_trigger = ?, macd_trigger = ?, time = ?, auto_market = ?, quantity = ?, joint = ? WHERE chat_id = ?",
                       (tpls_trigger, rsi_trigger, sma_trigger, alligator_trigger, gpt_trigger, lstm_trigger, bollinger_trigger, macd_trigger, time, auto_market, quantity, joint, chat_id))
    conn.commit()
    conn.close()


def get_config():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM config")
    config = cursor.fetchall()
    conn.close()
    return config


def get_tpsl(chat_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM signal_tpsl WHERE chat_id = ?", (chat_id,))
    tpsl = cursor.fetchall()
    conn.close()
    return tpsl

def get_rsi(chat_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM signal_rsi WHERE chat_id = ?", (chat_id,))
    rsi_data = cursor.fetchall()
    conn.close()
    return rsi_data

def get_sma(chat_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM signal_sma WHERE chat_id = ?", (chat_id,))
    sma_data = cursor.fetchall()
    conn.close()
    return sma_data

def get_alligator(chat_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM signal_alligator WHERE chat_id = ?", (chat_id,))
    alligator_data = cursor.fetchall()
    conn.close()
    return alligator_data

def get_gpt(chat_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM signal_gpt WHERE chat_id = ?", (chat_id,))
    gpt_data = cursor.fetchall()
    conn.close()
    return gpt_data

def get_bollinger(chat_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM signal_bollinger WHERE chat_id = ?", (chat_id,))
    bollinger_data = cursor.fetchall()
    conn.close()
    return bollinger_data

def get_macd(chat_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM signal_macd WHERE chat_id = ?", (chat_id,))
    macd_data = cursor.fetchall()
    conn.close()
    return macd_data

def get_strategy():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM strategy")
    strategy_data = cursor.fetchall()
    conn.close()
    return strategy_data


#create_table_strategy()

# conn = sqlite3.connect('database.db')
# cursor = conn.cursor()
# cursor.execute("DROP TABLE IF EXISTS strategy")
# conn.commit()
# conn.close()




