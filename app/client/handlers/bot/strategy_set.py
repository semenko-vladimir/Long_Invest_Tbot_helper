from telebot import types
from app.client.api.signals_client import SignalsApiClient
from app.client.api.strategy_client import StrategyApiClient
from app.client.bot.bot import bot
from apscheduler.schedulers.background import BackgroundScheduler
from app.client.strategy.strategy_run import strategy_run
from app.client.store.store import strategy_scheduler

strategy_client = StrategyApiClient()
signals_client = SignalsApiClient()

# Временные хранилища для данных
available_signals = ['RSI', 'SMA', 'EMA', 'TAKE PROFIT/STOP LOSS', 'ALLIGATOR', 'GPT', 'LSTM', 'BOLLINGER', 'MACD']
selected_signals = {}
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


@bot.callback_query_handler(func=lambda call: call.data == 'strategy_set')
def set_signals(call):
    """
    Обработчик для настройки стратегии.
    
    Отображает меню с доступными сигналами для выбора.
    """
    chat_id = call.message.chat.id
    
    # Генерация кнопок для выбора сигналов
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [types.InlineKeyboardButton(signal, callback_data=f'select_{signal.lower()}') for signal in available_signals]
    buttons.append(types.InlineKeyboardButton('Ок', callback_data='ok'))
    buttons.append(types.InlineKeyboardButton('Отмена', callback_data='cancel'))
    
    for button in buttons:
        markup.add(button)
    
    bot.send_message(chat_id, "Выберите, какие сигналы подключить к стратегии:", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('select_'))
def select_signal(call):
    """
    Обработчик для выбора сигнала.
    
    Добавляет выбранный сигнал в список выбранных сигналов.
    """
    global selected_signals, tpsl_trigger, rsi_trigger, sma_trigger, ema_trigger, alligator_trigger, gpt_trigger, lstm_trigger, bollinger_trigger, macd_trigger
    chat_id = call.message.chat.id
    signal = call.data.split('_')[1].upper()

    # Проверяем, не выбран ли сигнал уже
    if selected_signals.get(signal):
        bot.send_message(chat_id, f"Сигнал {signal} уже выбран.")
        return

    # Проверяем, что все поля для сигнала заполнены
    try:
        if signal == 'RSI':
            current_settings = signals_client.get_signal_rsi()
            if current_settings:
                selected_signals[signal] = True
                rsi_trigger = True
                bot.send_message(chat_id, f"Сигнал {signal} добавлен.")
            else:
                bot.send_message(chat_id, "Сигнал RSI не настроен.")
        
        elif signal == 'SMA':
            current_settings = signals_client.get_signal_sma()
            if current_settings:
                selected_signals[signal] = True
                sma_trigger = True
                bot.send_message(chat_id, f"Сигнал {signal} добавлен.")
            else:
                bot.send_message(chat_id, "Сигнал SMA не настроен.")
        
        elif signal == 'EMA':
            current_settings = signals_client.get_signal_ema()
            if current_settings:
                selected_signals[signal] = True
                ema_trigger = True
                bot.send_message(chat_id, f"Сигнал {signal} добавлен.")
            else:
                bot.send_message(chat_id, "Сигнал EMA не настроен.")
        
        elif signal == 'TAKE PROFIT/STOP LOSS':
            current_settings = signals_client.get_signal_tpsl()
            if current_settings:
                selected_signals[signal] = True
                tpsl_trigger = True
                bot.send_message(chat_id, f"Сигнал {signal} добавлен.")
            else:
                bot.send_message(chat_id, "Сигнал Take Profit/Stop Loss не настроен.")
        
        elif signal == 'ALLIGATOR':
            current_settings = signals_client.get_signal_alligator()
            if current_settings:
                selected_signals[signal] = True
                alligator_trigger = True
                bot.send_message(chat_id, f"Сигнал {signal} добавлен.")
            else:
                bot.send_message(chat_id, "Сигнал Alligator не настроен.")
        
        elif signal == 'GPT':
            current_settings = signals_client.get_signal_gpt()
            if current_settings:
                selected_signals[signal] = True
                gpt_trigger = True
                bot.send_message(chat_id, f"Сигнал {signal} добавлен.")
            else:
                bot.send_message(chat_id, "Сигнал GPT не настроен.")
        
        elif signal == 'LSTM':
            selected_signals[signal] = True
            lstm_trigger = True
            bot.send_message(chat_id, f"Сигнал {signal} добавлен.")
        
        elif signal == 'BOLLINGER':
            current_settings = signals_client.get_signal_bollinger()
            if current_settings:
                selected_signals[signal] = True
                bollinger_trigger = True
                bot.send_message(chat_id, f"Сигнал {signal} добавлен.")
            else:
                bot.send_message(chat_id, "Сигнал Bollinger не настроен.")
        
        elif signal == 'MACD':
            current_settings = signals_client.get_signal_macd()
            if current_settings:
                selected_signals[signal] = True
                macd_trigger = True
                bot.send_message(chat_id, f"Сигнал {signal} добавлен.")
            else:
                bot.send_message(chat_id, "Сигнал MACD не настроен.")
    
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при проверке настроек сигнала {signal}: {str(e)}")

    # Повторно выводим кнопки для выбора сигналов
    set_signals(call)


@bot.callback_query_handler(func=lambda call: call.data == 'ok')
def confirm_selection(call):
    """
    Обработчик для подтверждения выбора сигналов.
    
    Переходит к выбору времени для стратегии.
    """
    chat_id = call.message.chat.id

    if not selected_signals:
        bot.send_message(chat_id, "Вы не выбрали ни одного сигнала.")
        return

    # Показываем выбор времени
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(
        types.InlineKeyboardButton('2 минуты', callback_data='time_2'),
        types.InlineKeyboardButton('5 минут', callback_data='time_5'),
        types.InlineKeyboardButton('10 минут', callback_data='time_10')
    )
    bot.send_message(chat_id, "Выберите время для стратегии:", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('time_'))
def select_time(call):
    """
    Обработчик для выбора времени стратегии.
    
    Сохраняет выбранное время и переходит к выбору автоматической торговли.
    """
    global time
    chat_id = call.message.chat.id
    time = int(call.data.split('_')[1])

    # Спрашиваем о включении автоматической торговли
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton('Да', callback_data='auto_yes'),
        types.InlineKeyboardButton('Нет', callback_data='auto_no')
    )
    bot.send_message(chat_id, "Включить автоматическую торговлю?", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('auto_'))
def set_auto_market(call):
    """
    Обработчик для выбора автоматической торговли.
    
    Сохраняет выбор автоматической торговли и переходит к выбору количества бумаг.
    """
    global auto_market
    chat_id = call.message.chat.id
    auto_market = call.data.split('_')[1] == 'yes'

    if auto_market:
        # Спрашиваем у пользователя, сколько бумаг покупать/продавать
        msg = bot.send_message(chat_id, "Введите количество бумаг для покупки/продажи:")
        bot.register_next_step_handler(msg, set_quantity)
    else:
        # Обновляем стратегию с joint-параметром в зависимости от выбора пользователя
        global quantity
        quantity = 0
        ask_for_joint(chat_id)


def set_quantity(message):
    """
    Обработчик для получения количества бумаг.
    
    Сохраняет количество бумаг и переходит к выбору логического оператора.
    """
    global quantity
    chat_id = message.chat.id

    # Проверка на ввод числа
    try:
        quantity = int(message.text)
    except ValueError:
        msg = bot.send_message(chat_id, "Пожалуйста, введите корректное количество (целое число):")
        bot.register_next_step_handler(msg, set_quantity)
        return

    # Обновляем стратегию с учетом joint-параметра
    ask_for_joint(chat_id)


def ask_for_joint(chat_id):
    """
    Функция для запроса логического оператора.
    
    Отображает меню с выбором логического оператора.
    """
    # Спрашиваем пользователя, какой логический оператор использовать
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("И", callback_data='joint_and'),
        types.InlineKeyboardButton("ИЛИ", callback_data='joint_or')
    )
    
    bot.send_message(chat_id, "Выберите логический оператор для условий:", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data in ['joint_and', 'joint_or'])
def set_joint(call):
    """
    Обработчик для выбора логического оператора.
    
    Сохраняет выбор логического оператора и обновляет настройки стратегии.
    """
    global selected_signals, joint, tpsl_trigger, rsi_trigger, sma_trigger, ema_trigger, alligator_trigger, gpt_trigger, lstm_trigger, bollinger_trigger, macd_trigger, time, auto_market, quantity

    chat_id = call.message.chat.id
    joint = call.data == 'joint_and'

    try:
        # Обновляем настройки стратегии через API-клиент
        strategy_client.update_strategy_signals(
            tpsl_trigger,
            rsi_trigger,
            sma_trigger,
            alligator_trigger,
            gpt_trigger,
            lstm_trigger,
            bollinger_trigger,
            macd_trigger,
            ema_trigger,
            joint
        )
        
        strategy_client.update_strategy_settings(
            f"{time}",
            auto_market,
            quantity
        )

        # Завершение текущего планировщика и создание нового
        global strategy_scheduler
        if strategy_scheduler:
            strategy_scheduler.shutdown()

        strategy_scheduler = BackgroundScheduler()
        strategy_scheduler.start()

        # Получаем chat_id из переменных окружения для отправки уведомлений
        from dotenv import load_dotenv
        import os
        load_dotenv()
        env_chat_id = os.getenv('CHAT_ID')
        
        # Используем chat_id из переменных окружения, если доступен, иначе используем текущий chat_id
        strategy_scheduler.add_job(strategy_run, 'interval', minutes=int(time))

        # Сброс переменных стратегии
        selected_signals = {}
        tpsl_trigger = False
        rsi_trigger = False
        sma_trigger = False
        alligator_trigger = False
        gpt_trigger = False
        lstm_trigger = False
        bollinger_trigger = False
        macd_trigger = False
        ema_trigger = False
        time = None
        auto_market = None
        quantity = None
        joint = None

        bot.send_message(chat_id, "Стратегия обновлена.")
    
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при обновлении стратегии: {str(e)}")


@bot.callback_query_handler(func=lambda call: call.data == 'cancel')
def cancel_strategy(call):
    """
    Обработчик для отмены выбора стратегии.
    
    Сбрасывает все параметры стратегии.
    """
    global selected_signals, tpsl_trigger, rsi_trigger, sma_trigger, ema_trigger, alligator_trigger, gpt_trigger, lstm_trigger, bollinger_trigger, macd_trigger, time, auto_market, quantity, joint
    chat_id = call.message.chat.id

    # Сброс всех параметров
    selected_signals.clear()
    tpsl_trigger = False
    rsi_trigger = False
    sma_trigger = False
    alligator_trigger = False
    gpt_trigger = False
    lstm_trigger = False
    bollinger_trigger = False
    macd_trigger = False
    ema_trigger = False
    time = None
    auto_market = None
    quantity = None
    joint = None

    bot.send_message(chat_id, "Выбор стратегии отменен.")
