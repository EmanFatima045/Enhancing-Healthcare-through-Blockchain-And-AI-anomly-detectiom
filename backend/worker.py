"""Long-running durable outbox worker for blockchain and notification jobs."""

import logging
import signal
import time

from dotenv import load_dotenv

load_dotenv()

from .app.core.config import settings
from .app.core.database import SessionLocal, initialize_database
from .app.services.outbox import process_jobs

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("healerplus.worker")
running = True


def stop_worker(*_args):
    global running
    running = False


def main() -> None:
    settings.validate()
    initialize_database()
    signal.signal(signal.SIGTERM, stop_worker)
    signal.signal(signal.SIGINT, stop_worker)
    logger.info("HealerPlus outbox worker started; polling every %.1fs", settings.OUTBOX_POLL_SECONDS)
    while running:
        try:
            with SessionLocal() as db:
                result = process_jobs(db)
            if result["processed"] or result["failed"]:
                logger.info("outbox cycle: %s", result)
        except Exception:
            logger.exception("outbox cycle failed; retrying")
        time.sleep(settings.OUTBOX_POLL_SECONDS)
    logger.info("HealerPlus outbox worker stopped")


if __name__ == "__main__":
    main()
