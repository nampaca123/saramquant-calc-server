import logging

from psycopg2.extensions import connection

from app.db import DailyPriceRepository
from app.db.repositories.financial_statement import FinancialStatementRepository
from app.db.repositories.fundamental import FundamentalRepository
from app.schema import Market
from app.services.fundamental_service import FundamentalService

logger = logging.getLogger(__name__)


class FundamentalComputeEngine:
    def __init__(self, conn: connection):
        self._conn = conn
        self._fs_repo = FinancialStatementRepository(conn)
        self._fund_repo = FundamentalRepository(conn)
        self._price_repo = DailyPriceRepository(conn)

    def run(self, markets: list[Market]) -> int:
        all_rows: list[tuple] = []

        for market in markets:
            rows = self._process_market(market)
            all_rows.extend(rows)

        deleted = self._fund_repo.delete_by_markets(markets)
        logger.info(f"[FundCompute] Deleted {deleted} old fundamental rows")

        inserted = self._fund_repo.insert_batch(all_rows)
        self._conn.commit()
        logger.info(f"[FundCompute] Inserted {inserted} fundamental rows")
        return inserted

    def _process_market(self, market: Market) -> list[tuple]:
        fs_map = self._fs_repo.get_ttm_by_market(market)
        if not fs_map:
            logger.warning(f"[FundCompute] No financial data for {market.value}")
            return []

        price_map = self._price_repo.get_prices_by_market(market, limit_per_stock=1)

        rows: list[tuple] = []
        for i, (stock_id, statements) in enumerate(fs_map.items(), 1):
            prices = price_map.get(stock_id)
            if not prices:
                continue

            latest_close = float(prices[0][4])
            result = FundamentalService.compute(stock_id, latest_close, statements)
            if result:
                rows.append(result)

            if i % 500 == 0:
                logger.info(f"[FundCompute] {market.value}: {i}/{len(fs_map)} stocks")

        logger.info(
            f"[FundCompute] {market.value}: {len(rows)}/{len(fs_map)} stocks computed"
        )
        return rows
