import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH)


def _resolve_database_url() -> str:
    """Anchors a relative sqlite DATABASE_URL to BASE_DIR, so the DB file
    resolves to the same path regardless of the server's working directory.
    Absolute paths and non-sqlite URLs (e.g. a future postgres:// one) are
    left untouched.
    """
    raw = os.getenv("DATABASE_URL", "sqlite:///./timepay.db")
    prefix = "sqlite:///"
    if raw.startswith(prefix):
        rel_path = raw[len(prefix) :]
        if not Path(rel_path).is_absolute():
            abs_path = (BASE_DIR / rel_path).resolve()
            return f"{prefix}{abs_path.as_posix()}"
    return raw


class Settings:
    timepay_base_url: str = os.getenv("TIMEPAY_BASE_URL", "https://api.app.time-pay.uz")
    timepay_refresh_token: str = os.getenv("TIMEPAY_REFRESH_TOKEN", "")
    refresh_endpoint: str = os.getenv("REFRESH_ENDPOINT", "/api/v1/user/token/refresh/")
    database_url: str = _resolve_database_url()

    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))


settings = Settings()
