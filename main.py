from bot.bot import bot
from telebot import types
from config.db_config import configure_database
from config.schedulers_config import configure_schedulers
from db.db import get_t_token
from handlers.portfolio.portfolio_handler import get_portfolio_handler
from handlers.instruments.instruments_handler import instruments_handler
from handlers.dividends.dividends_handler import dividends_handler
from handlers.market.market_handler import market_handler
from handlers.notifications.notification_handler import notification_handler
from handlers.bot.bot_handler import bot_handler
from handlers.signals.signals_handler import show_signals_handler
from handlers.mls.mls_handler import mls_handler
from handlers.knowledge_base.knowledge_base_handler import knowledge_base_handler
from handlers.statistics.statistics_handler import statistics_handler
from log.logger import setup_logger

logger = setup_logger(__name__)


# Обработчик команды /start
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    print(chat_id)
    token = get_t_token(chat_id)
    if token is None:
        bot.send_message(message.chat.id, 'Вы не зарегистрированы в системе')
    else:
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        portfolio_button = types.KeyboardButton('Получить портфолио')
        tickers_button = types.KeyboardButton('Инструменты')
        notifications_button = types.KeyboardButton('Уведомления')
        strategies_button = types.KeyboardButton('Торговый робот')
        signals_button = types.KeyboardButton('Настройка сигналов')
        market_button = types.KeyboardButton('Состояние рынка')
        dividents_button = types.KeyboardButton('Дивиденды')
        long_strategy_button = types.KeyboardButton('Middle/Long сигналы')
        statistics_button = types.KeyboardButton('Статистика')
        knowledge_button = types.KeyboardButton('База знаний')


        keyboard.row(portfolio_button)

        keyboard.row(tickers_button)

        keyboard.row(notifications_button)

        keyboard.row(market_button)

        keyboard.row(signals_button)

        keyboard.row(strategies_button)

        keyboard.row(dividents_button)

        keyboard.row(long_strategy_button)

        keyboard.row(knowledge_button)

        keyboard.row(statistics_button)
        
        bot.send_message(message.chat.id, 'Добро пожаловать!', reply_markup=keyboard)

if __name__ == '__main__':
    # Настройка конфигуратора планировщика
    configure_schedulers()
    configure_database()
    print("Конфигуратор успешно настроен")
    # Запускаем бота
    bot.polling()
