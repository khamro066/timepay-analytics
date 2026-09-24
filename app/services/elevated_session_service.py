from datetime import datetime, timedelta

from app.core.database import SessionLocal
from app.models.elevated_session import ElevatedSession

DEFAULT_INACTIVITY_MINUTES = 15


def start_elevated_session(username: str) -> None:
    db = SessionLocal()
    try:
        row = db.get(ElevatedSession, username)
        now = datetime.utcnow()
        if row is None:
            row = ElevatedSession(username=username, last_activity_at=now)
            db.add(row)
        else:
            row.last_activity_at = now
        db.commit()
    finally:
        db.close()


def touch_and_check(username: str, inactivity_minutes: int = DEFAULT_INACTIVITY_MINUTES) -> bool:
    """True (and slides the window forward) if `username` has an elevated
    session that hasn't gone quiet for longer than inactivity_minutes.
    False otherwise — and if a session did exist but expired, it's deleted
    so it can't be resurrected by a later call."""
    db = SessionLocal()
    try:
        row = db.get(ElevatedSession, username)
        if row is None:
            return False
        now = datetime.utcnow()
        if now - row.last_activity_at > timedelta(minutes=inactivity_minutes):
            db.delete(row)
            db.commit()
            return False
        row.last_activity_at = now
        db.commit()
        return True
    finally:
        db.close()
