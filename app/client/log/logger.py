import logging
import os
from datetime import datetime

def setup_logger(name=__name__, log_file='./app/client/log/logs.log', level=logging.INFO):
    
    """
    Функция для настройки логгера.
    name - имя логгера, по умолчанию - __name__
    log_file - путь до файла, в который будет записываться лог
    level - уровень логирования, по умолчанию - logging.INFO
    """

    # Убираем старые обработчики
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    # Создаем логгер
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.hasHandlers():
        file_handler = None
        try:
            # The source tree may be read-only for the container user.
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
            file_handler.setLevel(level)
        except OSError:
            pass

        # Обработчик для вывода в консоль
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)

        # Форматирование логов
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Применение формата
        if file_handler is not None:
            file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Добавление обработчиков в логгер
        if file_handler is not None:
            logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger


