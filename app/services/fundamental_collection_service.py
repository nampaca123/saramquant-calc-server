import logging

from app.collectors.kr_financial_statement import KrFinancialStatementCollector
from app.collectors.us_financial_statement import UsFinancialStatementCollector

logger = logging.getLogger(__name__)


class FundamentalCollectionService:
    def collect_all(self, region: str) -> dict[str, int]:
        if region == "kr":
            return self._collect_kr()
        elif region == "us":
            return self._collect_us()
        return {}

    def _collect_kr(self) -> dict[str, int]:
        collector = KrFinancialStatementCollector()
        results = collector.collect_all()
        logger.info(f"[FundCollection] KR complete: {results}")
        return results

    def _collect_us(self) -> dict[str, int]:
        collector = UsFinancialStatementCollector()
        results = collector.collect_all()
        logger.info(f"[FundCollection] US complete: {results}")
        return results
