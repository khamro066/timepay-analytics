from datetime import datetime

from sqlalchemy import Column, DateTime, String

from app.core.database import Base


class AppConfig(Base):
    """A simple key-value store for small pieces of app state that need to
    persist in the database rather than a local file — e.g. the rotating
    Time Pay refresh token, which must be visible to every process talking
    to the same database (local dev, the Render cron job) rather than
    living on one machine's disk."""

    __tablename__ = "app_config"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
