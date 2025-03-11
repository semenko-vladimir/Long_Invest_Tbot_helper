import sqlite3
import os

class Database:
    '''
        Контекстный менеджер для работы с базой данных.
    '''
    def __init__(self, db_name='database.db'):
        self.db_name = db_name
        self.conn = None
        self.cursor = None

    def __enter__(self):
        self.conn = sqlite3.connect(self.db_name)
        self.cursor = self.conn.cursor()
        return self.cursor

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            print(f"Error occurred: {exc_val}")
        if self.conn:
            self.conn.commit()
            self.conn.close()

# Функция для создания БД
def create_db(name):
    """
    Создает файл базы данных.
    
    :param name: имя файла с расширением .db
    :type name: str
    """
    conn = sqlite3.connect(name)
    conn.close()

# Функция для удаления БД
def delete_database(database_name):
    # Удаляем файл базы данных
    """
    Удаляет базу данных и все связанные файлы, а также удаляет все таблицы из базы данных.

    :param database_name: Имя файла базы данных для удаления.
    :type database_name: str

    Процедура:
    1. Удаляет файл базы данных, если он существует.
    2. Удаляет все файлы с расширениями .sqlite, .db-journal, .sqlite-wal, .sqlite-shm, .sqlite-lock в текущем каталоге.
    3. Создает соединение с базой данных и удаляет все таблицы.
    4. Закрывает соединение с базой данных.
    """

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
    """
    Создает таблицу users, если она не существует.

    :return: None

    Процедура:
    1. Создает соединение с базой данных.
    2. Создает таблицу users, если она не существует.
    3. Закрывает соединение с базой данных.
    """
    with Database() as cursor:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                chat_id INTEGER PRIMARY KEY,
                t_token TEXT,
                sandbox_token TEXT,
                sandbox_trigger BOOLEAN
            )
        ''')


def create_table_config():
    """
    Создает таблицу config, если она не существует.

    :return: None

    Процедура:
    1. Создает соединение с базой данных.
    2. Создает таблицу config, если она не существует.
    3. Закрывает соединение с базой данных.
    """
    with Database() as cursor:
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


def create_table_signal_tpsl():
    """
    Создает таблицу signal_tpsl, если она не существует.

    :return: None

    Процедура:
    1. Создает соединение с базой данных.
    2. Создает таблицу signal_tpsl, если она не существует.
    3. Закрывает соединение с базой данных.
    """
    with Database() as cursor:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signal_tpsl (
                id INTEGER PRIMARY KEY,
                chat_id INTEGER,
                take_profit FLOAT,
                stop_loss FLOAT,
                FOREIGN KEY (chat_id) REFERENCES users (chat_id)
            )
        ''')


def create_table_signal_rsi():
    """
    Создает таблицу signal_rsi, если она не существует.

    :return: None

    Процедура:
    1. Создает соединение с базой данных.
    2. Создает таблицу signal_rsi, если она не существует.
    3. Закрывает соединение с базой данных.
    """
    with Database() as cursor:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signal_rsi (
                id INTEGER PRIMARY KEY,
                chat_id INTEGER,
                period FLOAT,
                hightLevel FLOAT,
                lowLevel FLOAT,
                FOREIGN KEY (chat_id) REFERENCES users (chat_id)
            )
        ''')


def create_table_signal_gpt():
    """
    Создает таблицу signal_gpt, если она не существует.

    :return: None

    Процедура:
    1. Создает соединение с базой данных.
    2. Создает таблицу signal_gpt, если она не существует.
    3. Закрывает соединение с базой данных.
    """
    with Database() as cursor:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signal_gpt (
                id INTEGER PRIMARY KEY,
                chat_id INTEGER,
                text TEXT,
                FOREIGN KEY (chat_id) REFERENCES users (chat_id)
            )
        ''')


def create_table_signal_sma():
    """
    Создает таблицу signal_sma, если она не существует.

    :return: None

    Процедура:
    1. Создает соединение с базой данных.
    2. Создает таблицу signal_sma, если она не существует.
    3. Закрывает соединение с базой данных.
    """

    with Database() as cursor:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signal_sma (
                id INTEGER PRIMARY KEY,
                chat_id INTEGER,
                fastLength INTEGER,
                slowLength INTEGER,
                FOREIGN KEY (chat_id) REFERENCES users (chat_id)
            )
        ''')


def create_table_signal_ema():
    """
    Создает таблицу signal_ema, если она не существует.

    :return: None

    Процедура:
    1. Создает соединение с базой данных.
    2. Создает таблицу signal_ema, если она не существует.
    3. Закрывает соединение с базой данных.
    """

    with Database() as cursor:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signal_ema (
                id INTEGER PRIMARY KEY,
                chat_id INTEGER,
                fastLength INTEGER,
                slowLength INTEGER,
                FOREIGN KEY (chat_id) REFERENCES users (chat_id)
            )
        ''')


def create_table_signal_bollinger():
    """
    Создает таблицу signal_bollinger, если она не существует.

    :return: None

    Процедура:
    1. Создает соединение с базой данных.
    2. Создает таблицу signal_bollinger, если она не существует.
    3. Закрывает соединение с базой данных.
    """
    with Database() as cursor:
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



def create_table_signal_macd():
    """
    Создает таблицу signal_macd, если она не существует.

    :return: None

    Процедура:
    1. Создает соединение с базой данных.
    2. Создает таблицу signal_macd, если она не существует.
    3. Закрывает соединение с базой данных.
    """
    with Database() as cursor:
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



def create_table_strategy():
    """
    Создает таблицу strategy, если она не существует.

    :return: None

    Процедура:
    1. Создает соединение с базой данных.
    2. Создает таблицу strategy, если она не существует.
    3. Закрывает соединение с базой данных.
    """
    with Database() as cursor:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS strategy (
                id INTEGER PRIMARY KEY,
                chat_id INTEGER,
                tpls_trigger BOOLEAN,
                rsi_trigger BOOLEAN,
                sma_trigger BOOLEAN,
                ema_trigger BOOLEAN,
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



def create_table_signal_alligator():
    """
    Создает таблицу signal_alligator, если она не существует.

    :return: None

    Процедура:
    1. Создает соединение с базой данных.
    2. Создает таблицу signal_alligator, если она не существует.
    3. Закрывает соединение с базой данных.
    """
    with Database() as cursor:
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


def create_table_margin():
    """
    Создает таблицу margin, если она не существует.

    :return: None

    Процедура:
    1. Создает соединение с базой данных.
    2. Создает таблицу margin, если она не существует.
    3. Закрывает соединение с базой данных.
    """
    with Database() as cursor:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS margin (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                margin FLOAT,
                ticker TEXT,
                signal TEXT,
                time DATETIME,
                chat_id INTEGER
            )
        ''')


def create_table_buy():
    """
    Создает таблицу buy, если она не существует.

    :return: None

    Процедура:
    1. Создает соединение с базой данных.
    2. Создает таблицу buy, если она не существует.
    3. Закрывает соединение с базой данных.
    """
    with Database() as cursor:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS buy (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                price FLOAT,
                ticker TEXT,
                signal TEXT,
                time DATETIME,
                chat_id INTEGER
            )
        ''')


def create_table_instruments():
    """
    Создает таблицу instruments, если она не существует.

    :return: None

    Процедура:
    1. Создает соединение с базой данных.
    2. Создает таблицу instruments, если она не существует.
    3. Закрывает соединение с базой данных.
    """

    with Database() as cursor:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS instruments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                ticker TEXT,
                figi TEXT,
                FOREIGN KEY (user_id) REFERENCES users (chat_id)
            )
        ''')



def create_table_orders():
    """
    Создает таблицу orders, если она не существует.

    :return: None

    Процедура:
    1. Создает соединение с базой данных.
    2. Создает таблицу orders, если она не существует.
    3. Закрывает соединение с базой данных.
    """

    with Database() as cursor:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER,
                ticker TEXT,
                signal TEXT,
                bm_value FLOAT,
                operation_type TEXT,
                user_id INTEGER
            )
        ''')

def new_margin(margin, ticker, signal, time, chat_id):
    """
    Добавляет новую строку в таблицу margin.

    :param margin: Маржа (float)
    :param ticker: Тикер (str)
    :param signal: Тип сигнала (str)
    :param time: Время наступления сигнала (datetime)
    :param chat_id: id чата, отправившего запрос (int)
    """
    with Database() as cursor:
        cursor.execute("INSERT INTO margin (margin, ticker, signal, time, chat_id) VALUES (?, ?, ?, ?, ?)", (margin, ticker, signal, time, chat_id))


def new_buy(price, ticker, signal, time, chat_id):
    """
    Добавляет новую строку в таблицу buy.

    :param price: Цена покупки (float)
    :param ticker: Тикер (str)
    :param signal: Тип сигнала (str)
    :param time: Время наступления сигнала (datetime)
    :param chat_id: id чата, отправившего запрос (int)
    """
    with Database() as cursor:
        cursor.execute("INSERT INTO buy (price, ticker, signal, time, chat_id) VALUES (?, ?, ?, ?, ?)", (price, ticker, signal, time, chat_id))

def delete_config_table():
    """
    Удаляет таблицу config, если она существует.

    :return: None
    """

    with Database() as cursor:
        cursor.execute('DROP TABLE IF EXISTS config')

def delete_tpsl_table():
    """
    Удаляет таблицу tpsl, если она существует.

    :return: None

    Процедура:
    1. Создает соединение с базой данных.
    2. Удаляет таблицу tpsl, если она существует.
    3. Закрывает соединение с базой данных.
    """
    
    with Database() as cursor:
        cursor.execute('DROP TABLE IF EXISTS tpsl')

def create_user(chat_id, t_token, sandbox_token, sandbox_trigger=0):
    """
    Создает пользователя в таблице users, если он не существует.

    :param chat_id: id чата, который будет использовать бота (int)
    :param t_token: токен для доступа к API Tinkoff Invest (str)
    :param sandbox_token: токен для доступа к песочнице Tinkoff Invest (str)
    :param sandbox_trigger: флаг, показывающий, стоит ли использовать песочницу (int)
    """
    with Database() as cursor:
        cursor.execute("SELECT chat_id FROM users WHERE chat_id = ?", (chat_id,))
        result = cursor.fetchone()

        if result is None:
            cursor.execute(
                "INSERT INTO users (chat_id, t_token, sandbox_token, sandbox_trigger) VALUES (?, ?, ?, ?)",
                (chat_id, t_token, sandbox_token, sandbox_trigger)
            )

def get_sandbox_trigger(chat_id):
    """
    Получает флаг, показывающий, стоит ли использовать песочницу Tinkoff Invest.

    :param chat_id: id чата, который будет использовать бота (int)

    :return: флаг, показывающий, стоит ли использовать песочницу (int)
    """
    with Database() as cursor:
        cursor.execute("SELECT sandbox_trigger FROM users WHERE chat_id = ?", (chat_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        else:
            return row[0]

def get_sandbox_token(chat_id):
    """
    Получает токен песочницы Tinkoff Invest для указанного id чата.

    :param chat_id: id чата, который будет использовать бота (int)

    :return: токен песочницы Tinkoff Invest (str)
    """
    with Database() as cursor:
        cursor.execute("SELECT sandbox_token FROM users WHERE chat_id = ?", (chat_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        else:
            return row[0]


def update_sandbox_trigger(chat_id, sandbox_trigger):
    """
    Обновляет флаг, показывающий, стоит ли использовать песочницу Tinkoff Invest, для указанного id чата.

    :param chat_id: id чата, для которого обновляется флаг (int)
    :param sandbox_trigger: флаг, показывающий, стоит ли использовать песочницу (int)
    """

    with Database() as cursor:
        cursor.execute("UPDATE users SET sandbox_trigger = ? WHERE chat_id = ?", (sandbox_trigger, chat_id))

def get_t_token(chat_id):
    """
    Получает токен тинькофф инвестиций для указанного id чата.

    :param chat_id: id чата, для которого получается токен (int)

    :return: токен тинькофф инвестиций (str)
    """
    with Database() as cursor:
        cursor.execute("SELECT t_token FROM users WHERE chat_id = ?", (chat_id,))
        t_token = cursor.fetchone()
        if t_token is None:
            return None
        else:
            return t_token[0]

# Функция для добавления нового тикера
def insert_instrument(user_id, ticker, figi):
    """
    Добавляет новый тикер для указанного пользователя.

    :param user_id: id чата, для которого добавляется тикер (int)
    :param ticker: тикер (str)
    :param figi: figi (str)

    :return: строка, информирующая, что тикер уже существует, или строка, информирующая, что тикер добавлен (str)
    """
    with Database() as cursor:
        cursor.execute("SELECT * FROM instruments WHERE user_id = ? AND ticker = ?", (user_id, ticker))
        if cursor.fetchone():
            return "У вас уже есть данный инструмент"
        else:
            cursor.execute("INSERT INTO instruments (user_id, ticker, figi) VALUES (?, ?, ?)", (user_id, ticker, figi))
            return f"Инструмент {ticker} добавлен"

def delete_instrument(user_id, ticker):
    """
    Удаляет тикер для указанного пользователя.

    :param user_id: id чата, для которого удаляется тикер (int)
    :param ticker: тикер (str)

    :return: None
    """
    with Database() as cursor:
        cursor.execute("DELETE FROM instruments WHERE user_id = ? AND ticker = ?", (user_id, ticker))

def get_all_tickers(user_id):
    """
    Получает список тикеров, которые добавлены для указанного пользователя.

    :param user_id: id чата, для которого получаются тикеры (int)

    :return: список тикеров (list of tuples, each tuple contains str)
    """
    with Database() as cursor:
        cursor.execute("SELECT ticker FROM instruments WHERE user_id = ?", (user_id,))
        tickers = cursor.fetchall()
    return tickers

def delete_all_instruments(user_id):
    """
    Удаляет все тикеры для указанного пользователя.

    :param user_id: id чата, для которого удаляются тикеры (int)

    :return: None
    """
    with Database() as cursor:
        cursor.execute("DELETE FROM instruments WHERE user_id = ?", (user_id,))


def update_config_collapse(chat_id, collapse_updates_time, collapse_updates, market_updates_time, market_updates):
    """
    Обновляет конфигурацию для указанного чата.

    :param chat_id: id чата, для которого обновляется конфигурация (int)
    :param collapse_updates_time: интервал времени, с которым нужно отправлять уведомления о падениях рынка (int)
    :param collapse_updates: нужно ли отправлять уведомления о падениях рынка (bool)
    :param market_updates_time: интервал времени, с которым нужно отправлять уведомления об обновлениях рынка (int)
    :param market_updates: нужно ли отправлять уведомления об обновлениях рынка (bool)

    :return: None
    """
    with Database() as cursor:
        cursor.execute("SELECT * FROM config WHERE chat_id = ?", (chat_id,))
        row = cursor.fetchone()
        if row is None:
            cursor.execute("INSERT INTO config (chat_id, collapse_updates, collapse_updates_time, market_updates, market_updates_time) VALUES (?, ?, ?, ?, ?)", 
                           (chat_id, collapse_updates, collapse_updates_time, market_updates, market_updates_time))
        else:
            cursor.execute("UPDATE config SET collapse_updates = ?, collapse_updates_time = ?, market_updates = ?, market_updates_time = ? WHERE chat_id = ?", 
                           (collapse_updates, collapse_updates_time, market_updates, market_updates_time, chat_id))

def update_signal_tpsl(chat_id, tp_value, sl_value):
    """
    Обновляет Take Profit и Stop Loss для указанного чата.

    :param chat_id: id чата, для которого обновляются Take Profit и Stop Loss (int)
    :param tp_value: значение Take Profit (int)
    :param sl_value: значение Stop Loss (int)

    :return: None
    """

    with Database() as cursor:
        cursor.execute("SELECT * FROM signal_tpsl WHERE chat_id = ?", (chat_id,))
        row = cursor.fetchone()
        if row is None:
            cursor.execute("INSERT INTO signal_tpsl (chat_id, take_profit, stop_loss) VALUES (?, ?, ?)",
                           (chat_id, tp_value, sl_value))
        else:
            cursor.execute("UPDATE signal_tpsl SET take_profit = ?, stop_loss = ? WHERE chat_id = ?",
                           (tp_value, sl_value, chat_id))

def update_signal_rsi(chat_id, period, highLevel, lowLevel):
    """
    Обновляет настройки сигнала RSI для указанного чата.

    :param chat_id: id чата, для которого обновляются настройки сигнала RSI (int)
    :param period: период для расчета RSI (int)
    :param highLevel: верхний уровень для сигнала перепроданности (float)
    :param lowLevel: нижний уровень для сигнала перекупленности (float)

    :return: None
    """
    with Database() as cursor:
        cursor.execute("SELECT * FROM signal_rsi WHERE chat_id = ?", (chat_id,))
        row = cursor.fetchone()
        if row is None:
            cursor.execute("INSERT INTO signal_rsi (chat_id, period, hightLevel, lowLevel) VALUES (?, ?, ?, ?)",
                           (chat_id, period, highLevel, lowLevel))
        else:
            cursor.execute("UPDATE signal_rsi SET period = ?, hightLevel = ?, lowLevel = ? WHERE chat_id = ?",
                           (period, highLevel, lowLevel, chat_id))


def update_signal_sma(chat_id, fastLength, slowLength):
    """
    Обновляет настройки сигнала SMA для указанного чата.

    :param chat_id: id чата, для которого обновляются настройки сигнала SMA (int)
    :param fastLength: количество точек для расчета быстрого тренда (int)
    :param slowLength: количество точек для расчета медленного тренда (int)

    :return: None
    """
    with Database() as cursor:
        cursor.execute("SELECT * FROM signal_sma WHERE chat_id = ?", (chat_id,))
        row = cursor.fetchone()
        if row is None:
            cursor.execute("INSERT INTO signal_sma (chat_id, fastLength, slowLength) VALUES (?, ?, ?)",
                           (chat_id, fastLength, slowLength))
        else:
            cursor.execute("UPDATE signal_sma SET fastLength = ?, slowLength = ? WHERE chat_id = ?",
                           (fastLength, slowLength, chat_id))

def update_signal_ema(chat_id, fastLength, slowLength):
    """
    Обновляет настройки сигнала EMA для указанного чата.

    :param chat_id: id чата, для которого обновляются настройки сигнала EMA (int)
    :param fastLength: количество точек для расчета быстрого тренда (int)
    :param slowLength: количество точек для расчета медленного тренда (int)

    :return: None
    """
    with Database() as cursor:
        cursor.execute("SELECT * FROM signal_ema WHERE chat_id = ?", (chat_id,))
        row = cursor.fetchone()
        if row is None:
            cursor.execute("INSERT INTO signal_ema (chat_id, fastLength, slowLength) VALUES (?, ?, ?)",
                           (chat_id, fastLength, slowLength))
        else:
            cursor.execute("UPDATE signal_ema SET fastLength = ?, slowLength = ? WHERE chat_id = ?",
                           (fastLength, slowLength, chat_id))

def update_signal_bollinger(chat_id, period, deviation, type_ma):
    """
    Обновляет настройки сигнала полос Боллинджера для указанного чата.

    :param chat_id: id чата, для которого обновляются настройки сигнала полос Боллинджера (int)
    :param period: количество точек для расчета полос Боллинджера (int)
    :param deviation: количество стандартных отклонений для расчета полос Боллинджера (float)
    :param type_ma: тип скользящей средней, используемой в сигнале (str)

    :return: None
    """
    with Database() as cursor:
        cursor.execute("SELECT * FROM signal_bollinger WHERE chat_id = ?", (chat_id,))
        row = cursor.fetchone()
        if row is None:
            cursor.execute("INSERT INTO signal_bollinger (chat_id, period, deviation, type_ma) VALUES (?, ?, ?, ?)",
                           (chat_id, period, deviation, type_ma))
        else:
            cursor.execute("UPDATE signal_bollinger SET period = ?, deviation = ?, type_ma = ? WHERE chat_id = ?",
                           (period, deviation, type_ma, chat_id))

def update_signal_macd(chat_id, fastLength, slowLength, signalLength):
    """
    Обновляет настройки сигнала MACD для указанного чата.

    :param chat_id: id чата, для которого обновляются настройки сигнала MACD (int)
    :param fastLength: количество точек для расчета быстрого MACD (int)
    :param slowLength: количество точек для расчета медленного MACD (int)
    :param signalLength: количество точек для расчета сигнальной линии MACD (int)

    :return: None
    """
    with Database() as cursor:
        cursor.execute("SELECT * FROM signal_macd WHERE chat_id = ?", (chat_id,))
        row = cursor.fetchone()
        if row is None:
            cursor.execute("INSERT INTO signal_macd (chat_id, fastLength, slowLength, signalLength) VALUES (?, ?, ?, ?)",
                           (chat_id, fastLength, slowLength, signalLength))
        else:
            cursor.execute("UPDATE signal_macd SET fastLength = ?, slowLength = ?, signalLength = ? WHERE chat_id = ?",
                           (fastLength, slowLength, signalLength, chat_id))

def update_signal_alligator(chat_id, jaw_period, jaw_shift, teeth_period, teeth_shift, lips_period, lips_shift):
    """
    Обновляет настройки сигнала Аллигатора для указанного чата.

    :param chat_id: id чата, для которого обновляются настройки сигнала Аллигатора (int)
    :param jaw_period: период для расчета Челюсти (int)
    :param jaw_shift: сдвиг Челюсти (int)
    :param teeth_period: период для расчета Зубов (int)
    :param teeth_shift: сдвиг Зубов (int)
    :param lips_period: период для расчета Губ (int)
    :param lips_shift: сдвиг Губ (int)

    :return: None
    """
    
    with Database() as cursor:
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

def update_signal_gpt(chat_id, text):
    """
    Обновляет настройки сигнала GPT для указанного чата.

    :param chat_id: id чата, для которого обновляются настройки сигнала GPT (int)
    :param text: текстовая информация для сигнала GPT (str)

    :return: None
    """

    with Database() as cursor:
        cursor.execute("SELECT * FROM signal_gpt WHERE chat_id = ?", (chat_id,))
        row = cursor.fetchone()
        if row is None:
            cursor.execute("INSERT INTO signal_gpt (chat_id, text) VALUES (?, ?)", (chat_id, text))
        else:
            cursor.execute("UPDATE signal_gpt SET text = ? WHERE chat_id = ?", (text, chat_id))

def update_strategy(chat_id, tpls_trigger, rsi_trigger, sma_trigger, alligator_trigger, gpt_trigger, lstm_trigger, bollinger_trigger, macd_trigger, ema_trigger, time, auto_market, quantity, joint):
    """
    Обновляет настройки стратегии для указанного чата.

    :param chat_id: id чата, для которого обновляются настройки стратегии (int)
    :param tpls_trigger: значение, указывающее, использовать ли TPSL (bool)
    :param rsi_trigger: значение, указывающее, использовать ли RSI (bool)
    :param sma_trigger: значение, указывающее, использовать ли SMA (bool)
    :param alligator_trigger: значение, указывающее, использовать ли Аллигатора (bool)
    :param gpt_trigger: значение, указывающее, использовать ли GPT (bool)
    :param lstm_trigger: значение, указывающее, использовать ли LSTM (bool)
    :param bollinger_trigger: значение, указывающее, использовать ли Bollinger (bool)
    :param macd_trigger: значение, указывающее, использовать ли MACD (bool)
    :param ema_trigger: значение, указывающее, использовать ли EMA (bool)
    :param time: время, начиная с которого запускать стратегию (str)
    :param auto_market: значение, указывающее, использовать ли автоматическую торговлю (bool)
    :param quantity: количество акций, которое будет использоваться для торговли (int)
    :param joint: значение, указывающее, использовать ли объединенный сигнал (bool)

    :return: None
    """
    with Database() as cursor:
        cursor.execute("SELECT * FROM strategy WHERE chat_id = ?", (chat_id,))
        row = cursor.fetchone()
        if row is None:
            cursor.execute('''INSERT INTO strategy (chat_id, tpls_trigger, rsi_trigger, sma_trigger, alligator_trigger, gpt_trigger, lstm_trigger, bollinger_trigger, macd_trigger, ema_trigger, time, auto_market, quantity, joint) 
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                           (chat_id, tpls_trigger, rsi_trigger, sma_trigger, alligator_trigger, gpt_trigger, lstm_trigger, bollinger_trigger, macd_trigger, ema_trigger, time, auto_market, quantity, joint))
        else:
            cursor.execute('''UPDATE strategy 
                              SET tpls_trigger = ?, rsi_trigger = ?, sma_trigger = ?, alligator_trigger = ?, gpt_trigger = ?, lstm_trigger = ?, bollinger_trigger = ?, macd_trigger = ?, ema_trigger = ?, 
                                  time = ?, auto_market = ?, quantity = ?, joint = ? 
                              WHERE chat_id = ?''',
                           (tpls_trigger, rsi_trigger, sma_trigger, alligator_trigger, gpt_trigger, lstm_trigger, bollinger_trigger, macd_trigger, ema_trigger, time, auto_market, quantity, joint, chat_id))

def get_config():
    """Возвращает список настроек, хранящихся в таблице config.

    :return: список настроек
    """
    with Database() as cursor:
        cursor.execute("SELECT * FROM config")
        config = cursor.fetchall()
    return config

def get_tpsl(chat_id):
    """Возвращает список настроек сигнала Take Profit/Stop Loss, хранящихся в таблице signal_tpsl, для указанного чата.

    :param chat_id: id чата
    :return: список настроек сигнала
    """
    with Database() as cursor:
        cursor.execute("SELECT * FROM signal_tpsl WHERE chat_id = ?", (chat_id,))
        tpsl = cursor.fetchall()
    return tpsl

def get_rsi(chat_id):
    """Возвращает список настроек сигнала RSI, хранящихся в таблице signal_rsi, для указанного чата.

    :param chat_id: id чата
    :return: список настроек сигнала
    """
    with Database() as cursor:
        cursor.execute("SELECT * FROM signal_rsi WHERE chat_id = ?", (chat_id,))
        rsi_data = cursor.fetchall()
    return rsi_data

def get_sma(chat_id):
    """Возвращает список настроек сигнала SMA, хранящихся в таблице signal_sma, для указанного чата.

    :param chat_id: id чата
    :return: список настроек сигнала
    """
    with Database() as cursor:
        cursor.execute("SELECT * FROM signal_sma WHERE chat_id = ?", (chat_id,))
        sma_data = cursor.fetchall()
    return sma_data

def get_ema(chat_id):
    """Возвращает список настроек сигнала EMA, хранящихся в таблице signal_ema, для указанного чата.

    :param chat_id: id чата
    :return: список настроек сигнала
    """
    with Database() as cursor:
        cursor.execute("SELECT * FROM signal_ema WHERE chat_id = ?", (chat_id,))
        ema_data = cursor.fetchall()
    return ema_data

def get_alligator(chat_id):
    """Возвращает список настроек сигнала Аллигатора, хранящихся в таблице signal_alligator, для указанного чата.

    :param chat_id: id чата
    :return: список настроек сигнала
    """
    with Database() as cursor:
        cursor.execute("SELECT * FROM signal_alligator WHERE chat_id = ?", (chat_id,))
        alligator_data = cursor.fetchall()
    return alligator_data

def get_gpt(chat_id):
    """
    Возвращает список настроек сигнала GPT, хранящихся в таблице signal_gpt, для указанного чата.

    :param chat_id: id чата
    :return: список настроек сигнала GPT
    """

    with Database() as cursor:
        cursor.execute("SELECT * FROM signal_gpt WHERE chat_id = ?", (chat_id,))
        gpt_data = cursor.fetchall()
    return gpt_data

def get_bollinger(chat_id):
    """
    Возвращает список настроек сигнала полос Боллинджера, хранящихся в таблице signal_bollinger, для указанного чата.

    :param chat_id: id чата
    :return: список настроек сигнала полос Боллинджера
    """
    with Database() as cursor:
        cursor.execute("SELECT * FROM signal_bollinger WHERE chat_id = ?", (chat_id,))
        bollinger_data = cursor.fetchall()
    return bollinger_data

def get_macd(chat_id):
    """
    Возвращает список настроек сигнала MACD, хранящихся в таблице signal_macd, для указанного чата.

    :param chat_id: id чата
    :return: список настроек сигнала MACD
    """
    with Database() as cursor:
        cursor.execute("SELECT * FROM signal_macd WHERE chat_id = ?", (chat_id,))
        macd_data = cursor.fetchall()
    return macd_data

def get_strategy():
    """
    Возвращает список настроек стратегии, хранящихся в таблице strategy.

    :return: список настроек стратегии
    """

    with Database() as cursor:
        cursor.execute("SELECT * FROM strategy")
        strategy_data = cursor.fetchall()
    return strategy_data


def db_get_figi(chat_id, ticker):
    """
    Возвращает FIGI инструмента, хранящийся в таблице instruments, 
    по указанному тикеру и id чата.

    :param chat_id: id чата
    :param ticker: тикер инструмента
    :return: FIGI инструмента
    """

    with Database() as cursor:
        cursor.execute("SELECT figi FROM instruments WHERE ticker = ? AND user_id = ?", (ticker, chat_id))
        figi = cursor.fetchall()
    return figi[0][0]

def get_buy(chat_id):
    """
    Возвращает список покупок, хранящихся в таблице buy, для указанного чата.

    :param chat_id: id чата
    :return: список покупок
    """
    with Database() as cursor:
        cursor.execute("SELECT * FROM buy WHERE chat_id = ?", (chat_id,))
        buy_data = cursor.fetchall()
    return buy_data

def get_margin(chat_id):
    """
    Возвращает список марж, хранящихся в таблице margin, 
    для указанного чата.

    :param chat_id: id чата
    :return: список марж
    """
    
    with Database() as cursor:
        cursor.execute("SELECT * FROM margin WHERE chat_id = ?", (chat_id,))
        margin = cursor.fetchall()
    return margin

def new_order(order_id, ticker, signal, bm_value, operation_type, user_id):
    """
    Создает новый заказ в таблице orders.

    :param order_id: Уникальный идентификатор заказа (int)
    :param ticker: Тикер инструмента (str)
    :param signal: Сигнал для заказа (str)
    :param bm_value: Значение BM для заказа (float)
    :param operation_type: Тип операции (str)
    :param user_id: Идентификатор пользователя, создавшего заказ (int)

    :return: None
    """

    with Database() as cursor:
        cursor.execute('''
            INSERT INTO orders (order_id, ticker, signal, bm_value, operation_type, user_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (order_id, ticker, signal, bm_value, operation_type, user_id))

def delete_order(order_id):
    """
    Удаляет заказ из таблицы orders по указанному идентификатору заказа.

    :param order_id: Уникальный идентификатор заказа для удаления (int)
    
    :return: None
    """

    with Database() as cursor:
        cursor.execute('''
            DELETE FROM orders
            WHERE order_id = ?
        ''', (order_id,))

def get_orders(chat_id):
    """
    Получает список всех заказов, созданных пользователем с указанным идентификатором чата.

    :param chat_id: Идентификатор чата, для которого нужно получить список заказов (int)

    :return: Список заказов, созданных пользователем (list of tuples)
    """

    with Database() as cursor:
        cursor.execute('''
            SELECT * FROM orders
            WHERE user_id = ?
        ''', (chat_id,))
        orders = cursor.fetchall()
    return orders


# create_table_orders()

# from datetime import datetime, timedelta
# import pytz

# moscow_tz = pytz.timezone('Europe/Moscow')

# # Фиктивные данные для 3 дней
# chat_id = 757528922
# tickers = ['GAZP', 'TATN', 'ROSN']
# signals = ['RSI ', 'TPSL ', 'RSI MACD ']

# # Создадим фиктивные данные для покупок
# for i in range(3):  # 3 дня
#     for hour in range(8, 24, 4):  # Разные часы в течение дня
#         # Дата и время с временным сдвигом на i дней
#         time = (datetime.now(moscow_tz) - timedelta(days=i)).replace(hour=hour, minute=0, second=0, microsecond=0)
#         time_str = time.strftime('%d-%m-%Y %H:%M')
        
#         # Добавляем фиктивные покупки
#         price = round(100 + i * 10 + hour * 0.5, 2)  # Примерная цена
#         ticker = tickers[i % len(tickers)]
#         signal = signals[i % len(signals)]
#         new_buy(price, ticker, signal, time_str, chat_id)

# # Создадим фиктивные данные для маржи
# for i in range(3):  # 3 дня
#     for hour in range(10, 22, 3):  # Разные часы в течение дня
#         # Дата и время с временным сдвигом на i дней
#         time = (datetime.now(moscow_tz) - timedelta(days=i)).replace(hour=hour, minute=0, second=0, microsecond=0)
#         time_str = time.strftime('%d-%m-%Y %H:%M')
        
#         # Добавляем фиктивную маржу
#         margin = round((-1)**i * (1 + i + hour * 0.1), 2)  # Пример маржи (положительная и отрицательная)
#         ticker = tickers[i % len(tickers)]
#         signal = signals[i % len(signals)]
#         new_margin(margin, ticker, signal, time_str, chat_id)

# insert_instrument(1231123, "ROSN", "BBG004731354")
# insert_ticker(757528922, "ROSN")
# insert_ticker(757528922, "GAZP")
# insert_ticker(757528922, "TATN")
# insert_ticker(757528922, "KMAZ")
# insert_ticker(757528922, "TCSG")
# insert_ticker(757528922, "AFLT")
# insert_ticker(757528922, "BANE")
# insert_ticker(757528922, "YDEX")
# insert_figi(1231123, "ROSN", "BBG004731354")



# create_table_instruments()
# create_table_figi()

# conn = sqlite3.connect('database.db')
# cursor = conn.cursor()

# # Удаляем все строки из таблицы figi
# cursor.execute("DELETE FROM users")
# conn.commit()

# print("Все строки из таблицы figi были удалены.")

# conn.close()


# create_table_strategy()

# conn = sqlite3.connect('database.db')
# cursor = conn.cursor()
# cursor.execute("DROP TABLE IF EXISTS signal_rsi")
# conn.commit()
# conn.close()

# create_table_signal_rsi()

# create_table_margin()
# create_table_buy()

# new_buy(100, "GAZP", "RSI", "17-10-2024 00:15", 757528922)
# new_margin(-2, "GAZP", "RSI", "17-10-2024 00:15", 757528922)

# create_table_margin()

# conn = sqlite3.connect('database.db')
# cursor = conn.cursor()
# cursor.execute("DELETE FROM buy WHERE id NOT IN (24, 25)")
# conn.commit()
# conn.close()

# conn = sqlite3.connect('database.db')
# cursor = conn.cursor()
# cursor.execute("DELETE FROM users")
# conn.commit()
# conn.close()



# create_user(757528922, 't.Uw4EyMoJpCET932NTtFz4Pw11hGy-zJlVr55AMGJaIVbQIq5YuJoO6EFqxPNm44gvsWIip9BFXo6yyuaUo5gbQ', 't.FQwfYXk8R3DE49SEmTBIwtPOWVmOfVQtpTn-eruGflXC6T4QNrZ_DZZcT-8oTgfZiA622kLbb1oyDAIotxXGdQ', 0)


