from sqlalchemy import Column, DateTime, String

from app.core.database import Base


class ElevatedSession(Base):
    """A sliding step-up-auth window per admin username, for sensitive
    tools (attendance corrections) that require re-entering the password
    even inside an already-valid regular login session. last_activity_at
    is bumped on every authorized use; a lookup older than the inactivity
    window is treated as expired and the row is dropped so it can't be
    resurrected."""

    __tablename__ = "elevated_sessions"

    username = Column(String, primary_key=True)
    last_activity_at = Column(DateTime, nullable=False)
