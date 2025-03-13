# Хранение планировщиков задач
strategy_scheduler = None
market_scheduler = None

# Словарь для хранения промежуточных данных сигналов
user_rsi_data = {}
user_sma_data = {}
user_ema_data = {}
user_tpsl_data = {}
user_alligator_data = {}
user_bollinger_data = {}
user_macd_data = {}

# Настройка сигналов
selected_signals = {}
available_signals = ['RSI', 'SMA', 'EMA' , 'Take Profit/Stop Loss', 'Alligator', 'GPT', 'LSTM', 'Bollinger', 'MACD']
tpsl_trigger = False
rsi_trigger = False
sma_trigger = False
ema_trigger = False
alligator_trigger = False
gpt_trigger = False
lstm_trigger = False
bollinger_trigger = False
macd_trigger = False
time = None
auto_market = None
quantity = None
joint = None


# Данные для mls
mls_interval = None

# Данные для RSI
rsi_values = None

# Данные для SMA
fast_sma = None
slow_sma = None

# Данные для EMA
fast_ema = None
slow_ema = None

# Данные для ALLIGATOR
jaw_sma = None
teeth_sma = None
lips_sma = None

# Данные для BOLLINGER
upper_band = None
middle_band = None
lower_band = None

# Данные для MACD
macd = None
macd_line = None
signal_line = None
