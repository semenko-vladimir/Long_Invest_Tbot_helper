from db.db import get_t_token
from bot.bot import bot


@bot.callback_query_handler(func=lambda call: call.data == 'base_portfolio')
def base_portfolio_handler(call):
    chat_id = call.message.chat.id
    token = get_t_token(chat_id)
    if token is not None:
        text = [
            f'Раздел "Получить портфолио" представляет собой получение вашего портфолио.\n',
            
            f'\nЗдесь вы можете получить состояние вашего счета и все активные инструменты портфеля.\n',

            f'\nПосле нажатия на кнопку вы получите полную информацию о вашем портфеле, включая:\n',
            
            f'💹 Общую стоимость акций, облигаций, фондов и валют.\n'
            f'📈 Ожидаемую доходность.\n'
            f'📊 Полный список ваших активов с деталями, такими как тикер, тип, количество и текущая цена.\n'
            
            f'\nЭта информация поможет вам лучше понять состояние ваших инвестиций и принимать более обоснованные решения.\n'
        ]



        bot.send_message(chat_id=chat_id, text='\n'.join(text))