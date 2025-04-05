from app.backend.models.database import engine, Base
from app.client.log.logger import setup_logger

logger = setup_logger(__name__)

class DatabaseConfigError(Exception):
    """Исключение, возникающее при ошибке конфигурации базы данных."""
    pass

def configure_database():
    """
    Функция для настройки базы данных.
    
    Создает таблицы в базе данных, если они не существуют.
    
    Raises:
        DatabaseConfigError: Если произошла ошибка при настройке базы данных
    """
    try:
        # Создаем таблицы в базе данных, если они не существуют
        Base.metadata.create_all(bind=engine)
        logger.info("База данных успешно настроена")
    except Exception as db_error:
        error_msg = f"Не удалось создать таблицы в базе данных: {str(db_error)}"
        logger.error(error_msg)
        raise DatabaseConfigError(error_msg)
