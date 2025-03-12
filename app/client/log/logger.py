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
        # Создаем папки, если их нет
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

        try:
            # Обработчик для записи в файл
            file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
            file_handler.setLevel(level)
        except Exception as e:
            print(f"Ошибка при создании FileHandler: {e}")

        # Обработчик для вывода в консоль
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)

        # Форматирование логов
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Применение формата
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Добавление обработчиков в логгер
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger


