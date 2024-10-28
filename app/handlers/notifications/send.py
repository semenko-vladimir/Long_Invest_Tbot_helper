from utils.methods import get_price_change_in_current_interval

def send_price_change_notification(figi, start_time, end_time, candle_interval, bot, chat_id, name, type_of, ticker, collapse=False):
    price_change, price_change_percent, max_price, min_price, close_price = get_price_change_in_current_interval(figi, start_time, end_time, candle_interval)
    
    message = f'Название: {name}\nТип: {type_of}\nТикер: {ticker}\nИзменение цены: {round(price_change_percent, 2)}% \nЦена закрытия: {close_price} \nМаксимальная цена: {max_price} \nМинимальная цена: {min_price}'
    
    if collapse and price_change_percent < -0.001:
        bot.send_message(chat_id, message)
    elif not collapse:
        bot.send_message(chat_id, message)
