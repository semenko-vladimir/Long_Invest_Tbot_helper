import sys
import os
import threading
import uvicorn
from dotenv import load_dotenv
from pathlib import Path

# Добавление родительской директории в sys.path, чтобы можно было импортировать модули из app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

from app.client.bot.bot import bot
from app.client.config.investor_reminders import configure_investor_reminders
from app.client.config.schedulers_config import configure_schedulers
from app.client.config import ConfigError, get_invest_mode, validate_startup_config
from app.client.config.db_config import configure_database, DatabaseConfigError
from app.client.log.logger import setup_logger
from app.backend.main_api import app as fastapi_app
from app.client.handlers.menu.main_menu import send_main_menu
from app.client.handlers.portfolio.portfolio_handler import get_portfolio_handler
from app.client.handlers.instruments.instruments_handler import instruments_handler
from app.client.handlers.dividends.dividends_handler import dividends_handler
from app.client.handlers.bot.bot_handler import bot_handler
from app.client.handlers.orders.manual_order_handler import manual_order_handler
from app.client.handlers.research.research_handler import research_command_handler, research_text_command_handler
from app.client.handlers.charts.chart_handler import chart_command_handler, position_chart_command_handler
from app.client.handlers.statistics.statistics_handler import statistics_handler
from app.client.handlers.help.help_handler import help_handler
from app.services.user_context import UnknownUserError, UserContextResolver

logger = setup_logger(__name__)
user_context_resolver = UserContextResolver()

class TokenVerificationError(Exception):
    """Исключение, возникающее при ошибке проверки токенов."""
    pass

def verify_tokens():
    """
    Проверяет наличие и валидность необходимых токенов в переменных окружения.
    
    Raises:
        TokenVerificationError: Если отсутствуют необходимые переменные окружения
    """
    try:
        load_dotenv()
        validate_startup_config()
        
        logger.info(f"Все необходимые токены успешно проверены. Режим: {get_invest_mode()}")
    
    except (ConfigError, TokenVerificationError) as e:
        raise TokenVerificationError(str(e)) from e
    except Exception as e:
        error_msg = f"Непредвиденная ошибка при проверке токенов: {str(e)}"
        raise TokenVerificationError(error_msg)


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
        user_context = user_context_resolver.resolve_telegram_chat(chat_id)
        send_main_menu(
            chat_id,
            f'Investor mode is ready for {user_context.display_name}. '
            'Use the menu or type `buy SBER 1` / `sell SBER 1`.',
        )
    except UnknownUserError:
        logger.warning("Unauthorized Telegram /start attempt: chat_id=%s", chat_id)
        bot.send_message(chat_id, "This Telegram chat is not authorized for this local investor assistant.")
    
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /start: {str(e)}")
        bot.send_message(chat_id, "Произошла ошибка при запуске бота. Пожалуйста, попробуйте позже.")


def run_api():
    """
    Запускает FastAPI сервер.
    """
    try:
        api_host = os.getenv("API_HOST", "127.0.0.1")
        api_port = int(os.getenv("API_PORT", "8000"))
        uvicorn.run(fastapi_app, host=api_host, port=api_port)
    
    except Exception as e:
        logger.error(f"Ошибка при запуске API сервера: {str(e)}")


if __name__ == '__main__':
    try:
        # Проверка токенов
        try:
            verify_tokens()
        except TokenVerificationError as e:
            logger.error(f"Ошибка проверки токенов: {str(e)}")
            sys.exit(1)
        
        # Инициализация базы данных
        try:
            configure_database()
        except DatabaseConfigError as e:
            logger.error(f"Не удалось настроить базу данных: {str(e)}")
            sys.exit(1)
        
        # Запуск API в отдельном потоке
        api_thread = threading.Thread(target=run_api, daemon=True)
        api_thread.start()
        logger.info("API сервер запущен на http://localhost:8000")

        # Настройка планировщиков
        configure_schedulers()
        logger.info("Планировщики успешно настроены")
        configure_investor_reminders()
        
        # Запуск бота
        logger.info("Запуск бота...")
        bot.polling()
    
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске приложения: {str(e)}")
        sys.exit(1)
