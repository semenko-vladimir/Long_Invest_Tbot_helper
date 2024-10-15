from db.db import get_alligator, get_bollinger, get_ema, get_gpt, get_macd, get_rsi, get_sma, get_t_token, get_tpsl, update_strategy
from telebot import types
from bot.bot import bot
from store.store import available_signals
from apscheduler.schedulers.background import BackgroundScheduler
from config.schedulers_config import configure_scheduler
from store.store import strategy_shedulers, selected_signals, tpsl_trigger, rsi_trigger, sma_trigger, ema_trigger, alligator_trigger, gpt_trigger, lstm_trigger, bollinger_trigger, macd_trigger, time, auto_market, quantity, joint
from strategy.strategy_run import strategy_run


@bot.callback_query_handler(func=lambda call: call.data == 'strategy_set')
def set_signals(call):
    chat_id = call.message.chat.id
    token = get_t_token(chat_id)
    if token is not None:
        # Генерация кнопок для выбора сигналов
        markup = types.InlineKeyboardMarkup(row_width=2)
        buttons = [types.InlineKeyboardButton(signal, callback_data=f'select_{signal.lower()}') for signal in available_signals]
        buttons.append(types.InlineKeyboardButton('Ок', callback_data='ok'))
        buttons.append(types.InlineKeyboardButton('Отмена', callback_data='cancel'))
        markup.add(*buttons)

        bot.send_message(chat_id, "Выберите, какие сигналы подключить к стратегии:", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('select_'))
def select_signal(call):
    global selected_signals, tpsl_trigger, rsi_trigger, sma_trigger, ema_trigger, alligator_trigger, gpt_trigger, lstm_trigger, bollinger_trigger, macd_trigger
    chat_id = call.message.chat.id
    signal = call.data.split('_')[1].upper()

    # Проверяем, не выбран ли сигнал уже
    if selected_signals.get(signal):
        bot.send_message(chat_id, f"Сигнал {signal} уже выбран.")
        return

    # Проверяем, что все поля для сигнала заполнены
    if signal == 'RSI':
        if get_rsi(chat_id)[2:] == [None, None]:  
            bot.send_message(chat_id, "Сигнал RSI не настроен.")
        else:
            selected_signals[signal] = True
            rsi_trigger = True
            bot.send_message(chat_id, f"Сигнал {signal} добавлен.")
    elif signal == 'SMA':
        if get_sma(chat_id)[2:] == [None, None]:
            bot.send_message(chat_id, "Сигнал SMA не настроен.")
        else:
            selected_signals[signal] = True
            sma_trigger = True
            bot.send_message(chat_id, f"Сигнал {signal} добавлен.")
    elif signal == 'EMA':
        if get_ema(chat_id)[2:] == [None, None]:
            bot.send_message(chat_id, "Сигнал EMA не настроен.")
        else:
            selected_signals[signal] = True
            ema_trigger = True
            bot.send_message(chat_id, f"Сигнал {signal} добавлен.")
    elif signal == 'TAKE PROFIT/STOP LOSS':
        if get_tpsl(chat_id)[2:] == [None, None]:
            bot.send_message(chat_id, "Сигнал Take Profit/Stop Loss не настроен.")
        else:
            selected_signals[signal] = True
            tpsl_trigger = True
            bot.send_message(chat_id, f"Сигнал {signal} добавлен.")
    elif signal == 'ALLIGATOR':
        if get_alligator(chat_id)[2:] == [None, None]:
            bot.send_message(chat_id, "Сигнал Alligator не настроен.")
        else:
            selected_signals[signal] = True
            alligator_trigger = True
            bot.send_message(chat_id, f"Сигнал {signal} добавлен.")
    elif signal == 'GPT':
        if get_gpt(chat_id)[2:] == None:
            bot.send_message(chat_id, "Сигнал GPT не настроен.")
        else:
            selected_signals[signal] = True
            gpt_trigger = True
            bot.send_message(chat_id, f"Сигнал {signal} добавлен.")
    elif signal == 'LSTM':
            selected_signals[signal] = True
            lstm_trigger = True
            bot.send_message(chat_id, f"Сигнал {signal} добавлен.")
    elif signal == 'BOLLINGER':
        if get_bollinger(chat_id)[2:] == [None, None]:
            bot.send_message(chat_id, "Сигнал Bollinger не настроен.")
        else:
            selected_signals[signal] = True
            bollinger_trigger = True
            bot.send_message(chat_id, f"Сигнал {signal} добавлен.")
    elif signal == 'MACD':
        if get_macd(chat_id)[2:] == [None, None]:
            bot.send_message(chat_id, "Сигнал MACD не настроен.")
        else:
            selected_signals[signal] = True
            macd_trigger = True
            bot.send_message(chat_id, f"Сигнал {signal} добавлен.")

    # Повторно выводим кнопки для выбора сигналов
    set_signals(call)
        

@bot.callback_query_handler(func=lambda call: call.data == 'ok')
def confirm_selection(call):
    chat_id = call.message.chat.id

    if not selected_signals:
        bot.send_message(chat_id, "Вы не выбрали ни одного сигнала.")
        return

    # Показываем выбор времени
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(types.InlineKeyboardButton('2 минуты', callback_data='time_2'),
               types.InlineKeyboardButton('5 минут', callback_data='time_5'),
               types.InlineKeyboardButton('10 минут', callback_data='time_10'))
    bot.send_message(chat_id, "Выберите время для стратегии:", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('time_'))
def select_time(call):
    global time
    chat_id = call.message.chat.id
    time = int(call.data.split('_')[1])

    # Спрашиваем о включении автоматической торговли
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton('Да', callback_data='auto_yes'),
               types.InlineKeyboardButton('Нет', callback_data='auto_no'))
    bot.send_message(chat_id, "Включить автоматическую торговлю?", reply_markup=markup)


# Обработчик включения автоматической торговли
@bot.callback_query_handler(func=lambda call: call.data.startswith('auto_'))
def set_auto_market(call):
    global selected_signals, tpsl_trigger, rsi_trigger, sma_trigger, ema_trigger, alligator_trigger, gpt_trigger, lstm_trigger, bollinger_trigger, macd_trigger, time, auto_market, quantity, joint
    chat_id = call.message.chat.id
    auto_market = call.data.split('_')[1] == 'yes'

    if auto_market:
        # Спрашиваем у пользователя, сколько бумаг покупать/продавать
        msg = bot.send_message(chat_id, "Введите количество бумаг для покупки/продажи:")
        bot.register_next_step_handler(msg, set_quantity)
    else:
        # Обновляем стратегию с joint-параметром в зависимости от выбора пользователя
        quantity = 0
        ask_for_joint(chat_id)

def set_quantity(message):
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
    # Спрашиваем пользователя, какой логический оператор использовать
    markup = types.InlineKeyboardMarkup()
    and_button = types.InlineKeyboardButton("И", callback_data='joint_and')
    or_button = types.InlineKeyboardButton("ИЛИ", callback_data='joint_or')
    markup.add(and_button, or_button)
    
    bot.send_message(chat_id, "Выберите логический оператор для условий:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ['joint_and', 'joint_or'])
def set_joint(call):
    global selected_signals, joint, tpsl_trigger, rsi_trigger, sma_trigger, ema_trigger, alligator_trigger, gpt_trigger, lstm_trigger, bollinger_trigger, macd_trigger, time, auto_market, quantity

    chat_id = call.message.chat.id
    joint = call.data == 'joint_and'

    # Вызов функции обновления стратегии с учетом joint-параметра
    update_strategy(chat_id, tpsl_trigger, rsi_trigger, sma_trigger, alligator_trigger, gpt_trigger, lstm_trigger, bollinger_trigger, macd_trigger, ema_trigger, time, auto_market, quantity, joint)

    # Завершение текущего планировщика и создание нового
    if chat_id in strategy_shedulers:
        scheduler = strategy_shedulers[chat_id]
        scheduler.shutdown()
        del strategy_shedulers[chat_id]

    scheduler = BackgroundScheduler()
    strategy_shedulers[chat_id] = scheduler
    scheduler.start()

    scheduler.add_job(strategy_run, 'interval', minutes=int(time), args=(chat_id,))

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


# Обработчик кнопки "Отмена"
@bot.callback_query_handler(func=lambda call: call.data == 'cancel')
def cancel_strategy(call):
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
