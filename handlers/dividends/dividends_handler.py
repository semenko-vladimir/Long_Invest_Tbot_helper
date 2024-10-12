from db import db_get_figi, get_all_tickers, get_t_token
from bot import bot
from helpers import get_dividends_data

@bot.message_handler(func=lambda message: message.text == 'Дивиденды')
def dividends_handler(message):
    chat_id = message.chat.id
    token = get_t_token(chat_id)

    if token is not None:
        msg = bot.send_message(chat_id, "Введите период окончания (в днях):")
        bot.register_next_step_handler(msg, process_dividends_period, token)


def process_dividends_period(message, token):
    chat_id = message.chat.id

    try:
        period = int(message.text)
        tickers = get_all_tickers(chat_id)

        if not tickers:
            bot.send_message(chat_id, "У вас нет активных тикеров")
        else:
            text = 'Дивиденды:\n'
            for ticker in tickers:
                figi = db_get_figi(chat_id, ticker[0])
                data = get_dividends_data(token, period, figi)

                if data is not None:

                    text += (
                        f'\nТикер: {ticker[0]}\n'
                        f'Величина дивидента на 1 ценную бумагу (включая валюту): {data["dividend_net"]}\n'
                        f'Дата фактических выплат: {data["payment_date"]}\n'
                        f'Дата объявления дивидендов: {data["declared_date"]}\n'
                        f'Последний день (включительно) покупки для получения выплаты: {data["last_buy_date"]}\n'
                        f'Дата фиксации реестра: {data["record_date"]}\n'
                        f'Величина доходности: {data["yield_value"]}\n'
                    )

            if text == 'Дивиденды:\n':
                text = 'Дивиденды за выбранный период не найдены'

            bot.send_message(chat_id, text)

    except ValueError:
        msg = bot.send_message(chat_id, "Некорректный ввод. Введите числовое значение для периода:")
        bot.register_next_step_handler(msg, process_dividends_period, token)