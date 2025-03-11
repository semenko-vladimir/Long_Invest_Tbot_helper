from dotenv import load_dotenv
import os
from app.backend.models.database import engine, Base
from app.client.log.logger import setup_logger

logger = setup_logger(__name__)

def configure_database():
    """
    Функция для настройки базы данных.
    
    Загружает переменные окружения BOT_TOKEN, CHAT_ID, TOKEN, SANDBOX_TOKEN,
    проверяет, что они существуют и не пусты.
    
    Returns:
        bool: True, если настройка прошла успешно, иначе False
    """
    try:
        load_dotenv()
        
        # Получение переменных окружения
        BOT_TOKEN = os.getenv('BOT_TOKEN')
        CHAT_ID = os.getenv('CHAT_ID')
        TOKEN = os.getenv('TOKEN')
        SANDBOX_TOKEN = os.getenv('SANDBOX_TOKEN')
        
        # Проверка, что переменные окружения существуют и не пусты
        if (not BOT_TOKEN or BOT_TOKEN.strip() == '' or 
            not CHAT_ID or CHAT_ID.strip() == '' or 
            not TOKEN or TOKEN.strip() == '' or 
            not SANDBOX_TOKEN or SANDBOX_TOKEN.strip() == ''):
            logger.error("Отсутствуют необходимые переменные окружения")
            return False
        
        # Создаем таблицы в базе данных, если они не существуют
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("База данных успешно настроена")
            return True
        except Exception as db_error:
            logger.error(f"Не удалось создать таблицы в базе данных: {str(db_error)}")
            return False
    
    except Exception as e:
        logger.error(f"Ошибка при настройке базы данных: {str(e)}")
        return False
