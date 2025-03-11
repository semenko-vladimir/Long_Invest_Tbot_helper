from db.db import create_db, create_table_buy, create_table_config, create_table_instruments, create_table_margin, create_table_orders, create_table_signal_alligator, create_table_signal_bollinger, create_table_signal_ema, create_table_signal_gpt, create_table_signal_macd, create_table_signal_rsi, create_table_signal_sma, create_table_signal_tpsl, create_table_strategy, create_table_users, create_user
from dotenv import load_dotenv
import os

def configure_database():

    """
    Функция для настройки БД

    Данная фунция загружает переменные окружения CHAT_ID, TOKEN, SANDBOX_TOKEN,
    проверяет, что они существуют и не пусты, создает все необходимые таблицы,
    создает пользователя.

    :return: False, если переменные окружения не существуют или пусты
    """
    
    load_dotenv()

    # Получение переменных окружения
    CHAT_ID = os.getenv('CHAT_ID')
    TOKEN = os.getenv('TOKEN')
    SANDBOX_TOKEN = os.getenv('SANDBOX_TOKEN')

    # Проверка, что переменные окружения существуют и не пусты
    if not CHAT_ID or CHAT_ID.strip() == '' or CHAT_ID is None or not TOKEN or TOKEN.strip() == '' or TOKEN is None or not SANDBOX_TOKEN or SANDBOX_TOKEN.strip() == '' or SANDBOX_TOKEN is None:
        return False

    # Создание всех необходимых таблиц
    create_db("database.db")
    create_table_users()
    create_table_config()
    create_table_signal_tpsl()
    create_table_signal_rsi()
    create_table_signal_gpt()
    create_table_signal_sma()
    create_table_signal_ema()
    create_table_signal_bollinger()
    create_table_signal_macd()
    create_table_signal_alligator()
    create_table_strategy()
    create_table_margin()
    create_table_buy()
    create_table_instruments()
    create_table_orders()

    # Создание пользователя
    create_user(CHAT_ID, TOKEN, SANDBOX_TOKEN, 0)
    print("База данных успешно настроена")
    return True