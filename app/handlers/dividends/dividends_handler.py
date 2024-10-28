from db.db import db_get_figi, get_all_tickers, get_t_token
from bot.bot import bot
from utils.methods import get_dividends_data


@bot.message_handler(func=lambda message: message.text == 'Дивиденды')
def dividends_handler(message):
    chat_id = message.chat.id
    token = get_t_token(chat_id)

    if token:
        msg = bot.send_message(chat_id, "Введите период окончания (в днях):")
        bot.register_next_step_handler(msg, handle_dividends_period, token)
    else:
        bot.send_message(chat_id, "Токен не найден. Пожалуйста, авторизуйтесь.")


def handle_dividends_period(message, token):
    chat_id = message.chat.id

    try:
        period = int(message.text)
        tickers = get_all_tickers(chat_id)

        if not tickers:
            bot.send_message(chat_id, "У вас нет активных тикеров.")
            return

        dividends_text = generate_dividends_report(chat_id, token, period, tickers)
        bot.send_message(chat_id, dividends_text)

    except ValueError:
        msg = bot.send_message(chat_id, "Некорректный ввод. Введите числовое значение для периода:")
        bot.register_next_step_handler(msg, handle_dividends_period, token)


def generate_dividends_report(chat_id, token, period, tickers):
    report_text = 'Дивиденды:\n'

    for ticker in tickers:
        figi = db_get_figi(chat_id, ticker[0])
        dividend_data = get_dividends_data(token, period, figi)

        if dividend_data:
            report_text += format_dividend_data(ticker[0], dividend_data)

    if report_text == 'Дивиденды:\n':
        return 'Дивиденды за выбранный период не найдены'
    
    return report_text


def format_dividend_data(ticker, data):
    return (
        f'\nТикер: {ticker}\n'
        f'Величина дивидента на 1 ценную бумагу (включая валюту): {data["dividend_net"]} руб.\n'
        f'Дата фактических выплат: {data["payment_date"]}\n'
        f'Дата объявления дивидендов: {data["declared_date"]}\n'
        f'Последний день (включительно) покупки для получения выплаты: {data["last_buy_date"]}\n'
        f'Дата фиксации реестра: {data["record_date"]}\n'
        f'Величина доходности: {data["yield_value"]}%\n'
    )
