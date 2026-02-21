import logging
import requests
from app.schema import Maturity
from app.utils import retry_with_backoff

logger = logging.getLogger(__name__)

EXCHANGE_RATE_STAT_CODE = "731Y001"
EXCHANGE_RATE_ITEM_CODE = "0000001"


class EcosClient:
    BASE_URL = "https://ecos.bok.or.kr/api/StatisticSearch"
    PAGE_SIZE = 100
    STAT_CODE = "817Y002"

    ITEM_CODES = {
        Maturity.D91: "010502000",
        Maturity.Y3: "010200000",
        Maturity.Y10: "010210000",
    }

    def __init__(self, api_key: str):
        self._api_key = api_key

    def _fetch_page(
        self,
        item_code: str,
        start_date: str,
        end_date: str,
        start_idx: int,
        end_idx: int,
    ) -> dict:
        return self._fetch_page_with_stat(
            item_code, self.STAT_CODE, start_date, end_date, start_idx, end_idx,
        )

    def fetch_rates(
        self,
        maturity: Maturity,
        start_date: str,
        end_date: str
    ) -> list[dict]:
        if maturity not in self.ITEM_CODES:
            return []

        item_code = self.ITEM_CODES[maturity]
        return self._fetch_all(item_code, self.STAT_CODE, start_date, end_date)

    def fetch_exchange_rates(self, start_date: str, end_date: str) -> list[dict]:
        return self._fetch_all(
            EXCHANGE_RATE_ITEM_CODE, EXCHANGE_RATE_STAT_CODE,
            start_date, end_date,
        )

    def _fetch_all(
        self, item_code: str, stat_code: str, start_date: str, end_date: str
    ) -> list[dict]:
        first = self._fetch_page_with_stat(
            item_code, stat_code, start_date, end_date, 1, 1,
        )
        if not first or "StatisticSearch" not in first:
            logger.warning(f"[ECOS] No data for stat={stat_code} item={item_code}")
            return []

        total = int(first["StatisticSearch"]["list_total_count"])
        rows = []
        for start in range(1, total + 1, self.PAGE_SIZE):
            end = min(start + self.PAGE_SIZE - 1, total)
            page = self._fetch_page_with_stat(
                item_code, stat_code, start_date, end_date, start, end,
            )
            if page and "StatisticSearch" in page:
                rows.extend(page["StatisticSearch"]["row"])
        return rows

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    def _fetch_page_with_stat(
        self,
        item_code: str,
        stat_code: str,
        start_date: str,
        end_date: str,
        start_idx: int,
        end_idx: int,
    ) -> dict:
        url = (
            f"{self.BASE_URL}/{self._api_key}/json/kr/"
            f"{start_idx}/{end_idx}/{stat_code}/D/{start_date}/{end_date}/{item_code}"
        )
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()
