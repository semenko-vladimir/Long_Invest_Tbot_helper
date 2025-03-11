import math
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from keras.api.models import Sequential
from keras.api.layers import Dense, LSTM
import matplotlib.pyplot as plt
from tinkoff.invest import Client, CandleInterval
from datetime import datetime, timedelta
from app.client.log.logger import setup_logger
from app.client.utils.helpers import create_df
from dotenv import load_dotenv
import os

plt.style.use('fivethirtyeight')
logger = setup_logger(__name__)

# Загрузка данных через Tinkoff Invest API с разбивкой на меньшие интервалы
def load_stock_data_tinkoff(token, figi, start_date, end_date):
    """
    Загружает исторические данные по инструменту с FIGI = figi с разбивкой 
    на меньшие интервалы (не более 1 года) с помощью Tinkoff Invest API.

    start_date и end_date - даты начала и конца периода, 
    соответственно, в формате 'YYYY-MM-DD'.

    Возвращает pandas.DataFrame, индексированный датами, 
    со столбцами date и close.
    """
    with Client(token) as client:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        delta = timedelta(days=365)  # Один год для дневных свечей

        data = []
        while start < end:
            to_date = min(start + delta, end)
            candles = client.market_data.get_candles(
                figi=figi,
                from_=start,
                to=to_date,
                interval=CandleInterval.CANDLE_INTERVAL_DAY
            )
            for candle in candles.candles:
                data.append({
                    'date': candle.time,
                    'close': candle.close.units + candle.close.nano * 1e-9,
                })
            start = to_date

        df = pd.DataFrame(data)
        df.set_index('date', inplace=True)
        return df

# Обучение модели LSTM
def train_lstm_model(df):
    # Подготовка данных для обучения модели
    """
    Обучает модель LSTM на данных из pandas.DataFrame df.

    df должен иметь индекс даты и столбец 'close' с ценами закрытия.

    Возвращает обученную модель LSTM и scaler, используемый для масштабирования данных.
    """
    
    data = df.filter(['close'])
    dataset = data.values
    training_data_len = math.ceil(len(dataset) * 0.8)

    scaler = MinMaxScaler(feature_range=(0,1))
    scaled_data = scaler.fit_transform(dataset)

    train_data = scaled_data[0:training_data_len, :]

    x_train = []
    y_train = []

    for i in range(60, len(train_data)):
        x_train.append(train_data[i-60:i, 0])
        y_train.append(train_data[i, 0])

    x_train, y_train = np.array(x_train), np.array(y_train)
    x_train = np.reshape(x_train, (x_train.shape[0], x_train.shape[1], 1))

    # Создание и обучение модели LSTM
    model = Sequential()
    model.add(LSTM(50, return_sequences=True, input_shape=(x_train.shape[1], 1)))
    model.add(LSTM(50, return_sequences=False))
    model.add(Dense(25))
    model.add(Dense(1))

    model.compile(optimizer='adam', loss='mean_squared_error')
    model.fit(x_train, y_train, batch_size=1, epochs=1)

    # Визуализация результатов обучения
    train = data[:training_data_len]
    valid = data[training_data_len:]

    # Подготовка данных для тестирования модели
    test_data = scaled_data[training_data_len - 60:, :]
    x_test = []
    y_test = dataset[training_data_len:, :]

    for i in range(60, len(test_data)):
        x_test.append(test_data[i-60:i, 0])

    x_test = np.array(x_test)
    x_test = np.reshape(x_test, (x_test.shape[0], x_test.shape[1], 1))

    # Предсказание
    predictions = model.predict(x_test)
    predictions = scaler.inverse_transform(predictions)

    # Оценка модели
    rmse = np.sqrt(np.mean(((predictions - y_test)**2)))
    logger.info(f"RMSE: {rmse}")

    # Визуализация результатов
    # valid['Predictions'] = predictions
    # plt.figure(figsize=(16,8))
    # plt.title('Model')
    # plt.xlabel('Date', fontsize=18)
    # plt.ylabel('Close Price RUB', fontsize=18)
    # plt.plot(train['close'])
    # plt.plot(valid[['close', 'Predictions']])
    # plt.legend(['Train', 'Val', 'Predictions'], loc='lower right')
    # plt.show()

    return model, scaler

# Функция для вычисления стратегии LSTM
def calculate_lstm_strategy(candles, figi, profit):

    """
    Функция для вычисления стратегии LSTM (Long Short-Term Memory).

    :param candles: исторические данные ( HistoricCandle ) для расчета стратегии
    :param figi: FIGI инструмента
    :param profit: прибыль для определения момента для продажи

    :return: 'buy', 'sell' или 'hold', в зависимости от стратегии
    """
    load_dotenv()

    token = os.getenv('TOKEN')

    df = load_stock_data_tinkoff(token, figi, '2020-01-01', '2024-01-01')

    # Проверка данных
    print(df.head())

    # Обучение модели
    model, scaler = train_lstm_model(df)

    # Предобработка данных
    df = create_df(candles.candles)  # Предполагается, что create_df возвращает DataFrame с колонкой 'close'
    data = df.filter(['close']).values
    scaled_data = scaler.transform(data)

    # Проверка длины scaled_data
    num_data_points = len(scaled_data)

    # Если данных недостаточно для построения временной последовательности, возвращаем hold
    if num_data_points < 2:
        return "hold"

    # Используем последние 60 точек данных или меньше, если их недостаточно
    x_test = []
    last_data_points = scaled_data[-60:] if num_data_points >= 60 else scaled_data
    x_test.append(last_data_points)

    x_test = np.array(x_test)
    x_test = np.reshape(x_test, (x_test.shape[0], x_test.shape[1], 1))

    # Предсказание
    predictions = model.predict(x_test)
    predictions = scaler.inverse_transform(predictions)

    # Генерация сигналов
    last_price = predictions[-1][0]
    current_price = df['close'].values[-1]

    if last_price > current_price:
        return "buy"
    elif last_price < current_price and profit > 0:
        return "sell"
    else:
        return "hold"


