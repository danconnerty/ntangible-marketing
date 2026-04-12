from dataclasses import asdict
import logging

from app.database import SessionLocal
from app.services.scheduler import SchedulerService


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    db = SessionLocal()
    try:
        result = SchedulerService(db).tick()
        db.commit()
        logging.info("Scheduler tick completed: %s", asdict(result))
    except Exception:
        db.rollback()
        logging.exception("Scheduler tick failed")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
