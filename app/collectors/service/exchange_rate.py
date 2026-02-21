import os
import logging
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from app.db import get_connection
from app.db.repositories.exchange_rate import ExchangeRateRepository, ExchangeRateRow
from app.collectors.clients import EcosClient

logger = logging.getLogger(__name__)

PAIR = "USDKRW"


class ExchangeRateCollector:
    def __init__(self):
        self._ecos = EcosClient(os.getenv("ECOS_API_KEY", ""))

    def collect(self) -> int:
        start_date = self._get_start_date()
        end_date = date.today().strftime("%Y%m%d")
        start_str = start_date.strftime("%Y%m%d") if start_date else "20200101"

        rows = self._ecos.fetch_exchange_rates(start_str, end_date)
        if not rows:
            logger.info("[ExchangeRate] No new rows from ECOS")
            return 0

        records = self._transform(rows)
        return self._save(records)

    def _get_start_date(self) -> date | None:
        with get_connection() as conn:
            repo = ExchangeRateRepository(conn)
            latest = repo.get_latest_date(PAIR)
        if latest:
            return latest + timedelta(days=1)
        return None

    def _transform(self, rows: list[dict]) -> list[ExchangeRateRow]:
        records = []
        for row in rows:
            try:
                t = row["TIME"]
                d = date(int(t[:4]), int(t[4:6]), int(t[6:8]))
                rate = Decimal(row["DATA_VALUE"].replace(",", ""))
                records.append(ExchangeRateRow(pair=PAIR, date=d, rate=rate))
            except (KeyError, InvalidOperation, ValueError) as e:
                logger.warning(f"[ExchangeRate] Skip invalid row: {e}")
        return records

    def _save(self, records: list[ExchangeRateRow]) -> int:
        if not records:
            return 0
        with get_connection() as conn:
            repo = ExchangeRateRepository(conn)
            count = repo.upsert_batch(records)
            conn.commit()
        logger.info(f"[ExchangeRate] Saved {count} rows")
        return count
