import logging
import os
import time

import requests

from app.utils import retry_with_backoff

logger = logging.getLogger(__name__)

_BASE_URL = "https://finnhub.io/api/v1"
_CALLS_PER_MINUTE = 55  # slightly under 60 limit for safety
_MIN_INTERVAL = 60.0 / _CALLS_PER_MINUTE
_TIMEOUT = 10


class FinnhubClient:
    def __init__(self):
        self._token = os.environ.get("FINNHUB_API_KEY", "")
        self._last_call = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < _MIN_INTERVAL:
            time.sleep(_MIN_INTERVAL - elapsed)
        self._last_call = time.monotonic()

    @retry_with_backoff(max_retries=2, base_delay=2.0)
    def fetch_profile(self, symbol: str) -> dict | None:
        self._throttle()
        resp = requests.get(
            f"{_BASE_URL}/stock/profile2",
            params={"symbol": symbol, "token": self._token},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        return data if data else None

    def fetch_sectors_batch(self, symbols: list[str]) -> dict[str, str | None]:
        result: dict[str, str | None] = {}
        for i, symbol in enumerate(symbols, 1):
            profile = self.fetch_profile(symbol)
            if profile:
                industry = profile.get("finnhubIndustry", "")
                result[symbol] = industry if industry else None
            else:
                result[symbol] = None

            if i % 50 == 0:
                logger.info(f"[Finnhub] Progress: {i}/{len(symbols)}")

        return result
