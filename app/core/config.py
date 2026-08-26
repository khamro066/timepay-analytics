import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH)


class Settings:
    timepay_base_url: str = os.getenv("TIMEPAY_BASE_URL", "https://api.app.time-pay.uz")
    timepay_refresh_token: str = os.getenv("TIMEPAY_REFRESH_TOKEN", "")
    refresh_endpoint: str = os.getenv("REFRESH_ENDPOINT", "/api/v1/user/token/refresh/")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./timepay.db")


settings = Settings()
