import logging
import os

def setup_logger(name=__name__, log_file='./log/log.txt', level=logging.INFO):

    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    logger = logging.getLogger(name)
    logger.setLevel(level)


    if not logger.hasHandlers():

        os.makedirs(os.path.dirname(log_file), exist_ok=True)

        try:
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(level)
        except Exception as e:
            print(f"Ошибка при создании FileHandler: {e}")

        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)

        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(funcName)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger
