# Хранение планировщиков задач
strategy_shedulers = {}
chat_schedulers = {}

# Словарь для хранения промежуточных данных сигналов
user_rsi_data = {}
user_sma_data = {}
user_tpsl_data = {}
user_alligator_data = {}
user_bollinger_data = {}
user_macd_data = {}

# Настройка сигналов
selected_signals = {}
available_signals = ['RSI', 'SMA', 'Take Profit/Stop Loss', 'Alligator', 'GPT', 'LSTM', 'Bollinger', 'MACD']
tpsl_trigger = False
rsi_trigger = False
sma_trigger = False
alligator_trigger = False
gpt_trigger = False
lstm_trigger = False
bollinger_trigger = False
macd_trigger = False
time = None
auto_market = None
quantity = None
joint = None