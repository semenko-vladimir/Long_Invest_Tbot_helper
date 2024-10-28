from db.db import get_t_token
from bot.bot import bot


@bot.callback_query_handler(func=lambda call: call.data == 'base_dividends')
def base_dividends_handler(call):
    chat_id = call.message.chat.id
    token = get_t_token(chat_id)
    if token is not None:
        text = [
            f'Раздел "Дивиденды" позволяет вам получить информацию о дивидендах по вашим инструментам.\n',
                       
            f'\nВы можете выбрать временной промежуток.\n',

            f'\nПри получении информации о дивидендах вам будет предоставлена следующая информация:\n'
            f'🔹 Тикер инструмента\n'
            f'🔹 Величина дивиденда за 1 ценную бумагу в рублях\n'
            f'🔹 Дата фактических выплат\n'
            f'🔹 Дата объявления дивидендов\n'
            f'🔹 Последний день (включительно) покупки для получения выплаты\n'
            f'🔹 Дата фиксации реестра\n'
            f'🔹 Величина доходности в %\n'

        ]



        bot.send_message(chat_id=chat_id, text='\n'.join(text))