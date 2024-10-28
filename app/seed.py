from config.db_config import configure_database
from db.db import update_signal_alligator, update_signal_bollinger, update_signal_ema, update_signal_macd, update_signal_rsi, update_signal_sma, update_signal_tpsl
from dotenv import load_dotenv
import os

load_dotenv()

CHAT_ID = os.getenv('CHAT_ID')

configure_database()
update_signal_alligator(CHAT_ID, 21, 8, 11, 5, 8, 3)
update_signal_bollinger(CHAT_ID, 20, 2, 'SMA')
update_signal_ema(CHAT_ID, 10, 30)
update_signal_macd(CHAT_ID, 12, 26, 9)
update_signal_rsi(CHAT_ID, 14, 70, 30)
update_signal_sma(CHAT_ID, 10, 30)
update_signal_tpsl(CHAT_ID, 10, 5)