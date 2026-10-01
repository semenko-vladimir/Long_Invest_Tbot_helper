import io
import logging
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from app.client.log.logger import setup_logger


class LoggerTests(unittest.TestCase):
    def test_console_logging_survives_unwritable_file(self):
        root_handlers = logging.root.handlers[:]
        logger = logging.getLogger("test_logger_file_unavailable")
        stderr = io.StringIO()
        try:
            with patch("app.client.log.logger.os.makedirs"), \
                    patch("app.client.log.logger.logging.FileHandler", side_effect=PermissionError("read-only")), \
                    redirect_stderr(stderr):
                setup_logger(logger.name, log_file="/unwritable/logs.log")
                logger.info("console remains available")
            self.assertEqual(len(logger.handlers), 1)
            self.assertIn("console remains available", stderr.getvalue())
        finally:
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)
                handler.close()
            logging.root.handlers[:] = root_handlers
