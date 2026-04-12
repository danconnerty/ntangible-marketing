import json
from pathlib import Path

from app.config import get_settings
from app.content_brain.db_sync import sync_storage_to_db
from app.database import SessionLocal


def main() -> None:
    settings = get_settings()
    storage_root = Path(settings.content_brain_storage_root)
    db = SessionLocal()
    try:
        summary = sync_storage_to_db(db, storage_root=storage_root)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print(
        json.dumps(
            {
                "storage_root": storage_root.as_posix(),
                **summary,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
