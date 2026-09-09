from datetime import datetime

from app.core.database import SessionLocal
from app.models.app_config import AppConfig


def get_config(key: str) -> str | None:
    db = SessionLocal()
    try:
        row = db.get(AppConfig, key)
        return row.value if row else None
    finally:
        db.close()


def set_config(key: str, value: str) -> None:
    db = SessionLocal()
    try:
        row = db.get(AppConfig, key)
        if row is None:
            row = AppConfig(key=key, value=value)
            db.add(row)
        else:
            row.value = value
            row.updated_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()
