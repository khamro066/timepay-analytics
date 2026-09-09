import requests

from app.core.config import settings
from app.services.app_config_service import get_config, set_config

EMPLOYEE_DAILY_STATS_ENDPOINT = "/api/v1/user/employee-daily-stats/"
REFRESH_TOKEN_CONFIG_KEY = "timepay_refresh_token"


class TimePayClient:
    """Thin client around the Time Pay HR API.

    Auth: POST {"refresh": ...} to REFRESH_ENDPOINT to get back a fresh
    {"access": ..., "refresh": ...} pair. Time Pay rotates the refresh
    token on every call, so the new one is kept in memory for the rest of
    this run and persisted to the app_config table so later runs — including
    a separate Render cron job container, which shares the database but not
    a local disk — pick it up. TIMEPAY_REFRESH_TOKEN in the environment is
    only used to seed app_config the very first time (i.e. when no row for
    REFRESH_TOKEN_CONFIG_KEY exists yet).

    The access-token is sent as an `Authorization: Bearer` header on API
    calls. The "access-token" cookie visible in the browser turned out to
    be for the site's own pages, not this API: a cookie-only request to
    employee-daily-stats came back 401 with `WWW-Authenticate: Bearer
    realm="api"` and body {"detail": "Authentication credentials were
    not provided."}; switching to a Bearer header returned 200.
    """

    def __init__(self) -> None:
        self.session = requests.Session()
        self.access_token: str | None = None
        self.refresh_token: str = get_config(REFRESH_TOKEN_CONFIG_KEY) or settings.timepay_refresh_token

    def get_access_token(self) -> str:
        """Exchanges the current refresh token for a new access/refresh pair."""
        url = f"{settings.timepay_base_url}{settings.refresh_endpoint}"
        response = self.session.post(url, json={"refresh": self.refresh_token})
        response.raise_for_status()
        data = response.json()

        self.access_token = data["access"]
        self.refresh_token = data["refresh"]

        set_config(REFRESH_TOKEN_CONFIG_KEY, self.refresh_token)

        return self.access_token

    def _post(self, url: str, params: dict | None = None, json_body: dict | None = None) -> dict:
        if self.access_token is None:
            self.get_access_token()

        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = self.session.post(url, params=params, json=json_body, headers=headers)

        if response.status_code == 401:
            self.get_access_token()
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = self.session.post(url, params=params, json=json_body, headers=headers)

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
