import sys
import os
import threading
import uvicorn
from telebot import types
from dotenv import load_dotenv
from pathlib import Path

# Добавляем родительскую директорию в sys.path, чтобы можно было импортировать модули из app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

from app.client.bot.bot import bot
from app.client.config.schedulers_config import configure_schedulers
from app.client.config.db_config import configure_database
from app.client.log.logger import setup_logger
from app.backend.api_client import ApiClient
from app.backend.main_api import app as fastapi_app
from app.client.handlers.portfolio.portfolio_handler import get_portfolio_handler
from app.client.handlers.instruments.instruments_handler import instruments_handler
from app.client.handlers.dividends.dividends_handler import dividends_handler
from app.client.handlers.market.market_handler import market_handler
from app.client.handlers.notifications.notification_handler import notification_handler
from app.client.handlers.bot.bot_handler import bot_handler
from app.client.handlers.signals.signals_handler import show_signals_handler
from app.client.handlers.mls.mls_handler import mls_handler
from app.client.handlers.knowledge_base.knowledge_base_handler import knowledge_base_handler
from app.client.handlers.statistics.statistics_handler import statistics_handler

logger = setup_logger(__name__)
api_client = ApiClient()


# Обработчик команды /start
@bot.message_handler(commands=['start'])
def start(message):
    """
    Обработчик команды /start.
    
    Бот отправляет пользователю сообщение с клавиатурой,
    содержащей кнопки для различных функций бота.
    """
    chat_id = message.chat.id
    
    try:
        # Создаем клавиатуру с кнопками
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        portfolio_button = types.KeyboardButton('Получить портфолио')
        tickers_button = types.KeyboardButton('Инструменты')
        notifications_button = types.KeyboardButton('Уведомления')
        strategies_button = types.KeyboardButton('Торговый робот')
        signals_button = types.KeyboardButton('Настройка сигналов')
        market_button = types.KeyboardButton('Состояние рынка')
        dividents_button = types.KeyboardButton('Дивиденды')
        long_strategy_button = types.KeyboardButton('Middle/Long сигналы(Графики)')
        statistics_button = types.KeyboardButton('Статистика')
        knowledge_button = types.KeyboardButton('База знаний')
        
        # Добавляем кнопки на клавиатуру
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
        
        # Отправляем приветственное сообщение с клавиатурой
        bot.send_message(message.chat.id, 'Добро пожаловать!', reply_markup=keyboard)
    
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /start: {str(e)}")
        bot.send_message(chat_id, "Произошла ошибка при запуске бота. Пожалуйста, попробуйте позже.")


def run_api():
    """
    Запускает FastAPI сервер.
    """
    try:
        uvicorn.run(fastapi_app, host="0.0.0.0", port=8000)
    
    except Exception as e:
        logger.error(f"Ошибка при запуске API сервера: {str(e)}")


if __name__ == '__main__':
    try:
        # Инициализация базы данных
        if not configure_database():
            logger.error("Не удалось настроить базу данных. Завершение работы.")
            sys.exit(1)
        
        # Запуск API в отдельном потоке
        api_thread = threading.Thread(target=run_api, daemon=True)
        api_thread.start()
        logger.info("API сервер запущен на http://localhost:8000")

        # Настройка планировщиков
        configure_schedulers()
        logger.info("Планировщики успешно настроены")
        
        # Запуск бота
        logger.info("Запуск бота...")
        bot.polling()
    
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске приложения: {str(e)}")
        sys.exit(1)
