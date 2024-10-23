from db.db import create_db, create_table_buy, create_table_config, create_table_instruments, create_table_margin, create_table_orders, create_table_signal_alligator, create_table_signal_bollinger, create_table_signal_ema, create_table_signal_gpt, create_table_signal_macd, create_table_signal_rsi, create_table_signal_sma, create_table_signal_tpsl, create_table_strategy, create_table_users, create_user
from dotenv import load_dotenv
import os

def configure_database():

    load_dotenv()

    CHAT_ID = os.getenv('CHAT_ID')
    TOKEN = os.getenv('TOKEN')
    SANDBOX_TOKEN = os.getenv('SANDBOX_TOKEN')

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

    create_user(CHAT_ID, TOKEN, SANDBOX_TOKEN, 0)
    print("База данных успешно настроена")