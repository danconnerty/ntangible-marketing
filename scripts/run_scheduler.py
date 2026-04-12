import logging
import sys

from app.database import SessionLocal
from app.services.scheduler import run_scheduler_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)

if __name__ == "__main__":
    logging.getLogger(__name__).info("Starting scheduler loop (polling every 15s)")
    run_scheduler_loop(SessionLocal)
