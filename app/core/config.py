import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    timepay_api_base_url: str = os.getenv("TIMEPAY_API_BASE_URL", "")
    timepay_refresh_token: str = os.getenv("TIMEPAY_REFRESH_TOKEN", "")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./timepay.db")


settings = Settings()
