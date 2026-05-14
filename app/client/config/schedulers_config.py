from dotenv import load_dotenv
import os
from app.client.config import background_schedulers_enabled
from app.client.log.logger import setup_logger

logger = setup_logger(__name__)


def configure_market_scheduler():
    """
    Compatibility no-op for the legacy market scheduler.

    Market notifications are not part of the active investor v1 runtime.
    """
    logger.info("Legacy market scheduling is disabled for investor v1.")


def configure_strategy_scheduler():
    """
    Compatibility no-op for the legacy strategy scheduler.

    Strategy automation is not part of the active investor v1 runtime.
    """
    load_dotenv()
    if os.getenv("ENABLE_STRATEGY_SCHEDULER", "false").strip().lower() in {"1", "true", "yes", "on"}:
        logger.warning(
            "ENABLE_STRATEGY_SCHEDULER is ignored: legacy strategy scheduling is disabled for investor v1."
        )
    else:
        logger.info("Legacy strategy scheduling is disabled for investor v1.")


def configure_schedulers():
    if not background_schedulers_enabled():
        logger.info("Фоновые планировщики отключены для sandbox-first v1")
        return

    configure_market_scheduler()
    configure_strategy_scheduler()
