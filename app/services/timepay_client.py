import requests
from dotenv import set_key

from app.core.config import ENV_PATH, settings

EMPLOYEE_DAILY_STATS_ENDPOINT = "/api/v1/user/employee-daily-stats/"


class TimePayClient:
    """Thin client around the Time Pay HR API.

    Auth: POST {"refresh": ...} to REFRESH_ENDPOINT to get back a fresh
    {"access": ..., "refresh": ...} pair. Time Pay rotates the refresh
    token on every call, so the new one is kept in memory for the rest of
    this run and persisted back to .env so later runs pick it up. The
    access-token itself is sent as a cookie (not an Authorization header)
    on API calls, matching what the browser does.
    """

    def __init__(self) -> None:
        self.session = requests.Session()
        self.access_token: str | None = None
        self.refresh_token: str = settings.timepay_refresh_token

    def get_access_token(self) -> str:
        """Exchanges the current refresh token for a new access/refresh pair."""
        url = f"{settings.timepay_base_url}{settings.refresh_endpoint}"
        response = self.session.post(url, json={"refresh": self.refresh_token})
        response.raise_for_status()
        data = response.json()

        self.access_token = data["access"]
        self.refresh_token = data["refresh"]

        self.session.cookies.set("access-token", self.access_token)
        set_key(str(ENV_PATH), "TIMEPAY_REFRESH_TOKEN", self.refresh_token)

        return self.access_token

    def _post(self, url: str, params: dict | None = None, json_body: dict | None = None) -> dict:
        if self.access_token is None:
            self.get_access_token()

        response = self.session.post(url, params=params, json=json_body)

        if response.status_code == 401:
            self.get_access_token()
            response = self.session.post(url, params=params, json=json_body)

        response.raise_for_status()
        return response.json()

    def fetch_daily_stats(self, date: str) -> list[dict]:
        """Fetches all employee daily-stats rows for a given date (YYYY-MM-DD),
        following pagination until "next" is null."""
        url = f"{settings.timepay_base_url}{EMPLOYEE_DAILY_STATS_ENDPOINT}"
        params = {"offset": 0, "limit": 10}
        body = {
            "date": date,
            "branch_ids": [],
            "department_ids": [],
            "position_ids": [],
            "schedule_ids": [],
            "employee_ids": [],
        }

        results: list[dict] = []

        payload = self._post(url, params=params, json_body=body)
        results.extend(payload.get("results", []))
        next_url = payload.get("next")

        while next_url:
            payload = self._post(next_url, json_body=body)
            results.extend(payload.get("results", []))
            next_url = payload.get("next")

        return results
