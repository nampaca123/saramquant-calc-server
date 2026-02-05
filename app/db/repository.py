from datetime import date
from psycopg2.extensions import connection
from psycopg2.extras import execute_values
from app.schema.data_sources import StockInfo, DailyPrice, Market


class StockRepository:
    def __init__(self, conn: connection):
        self._conn = conn

    def upsert_batch(self, stocks: list[StockInfo]) -> int:
        if not stocks:
            return 0
        query = """
            INSERT INTO stocks (symbol, name, market)
            VALUES %s
            ON CONFLICT (symbol, market)
            DO UPDATE SET name = EXCLUDED.name, updated_at = now()
        """
        data = [(s.symbol, s.name, s.market.value) for s in stocks]
        with self._conn.cursor() as cur:
            execute_values(cur, query, data)
            return cur.rowcount

    def get_active_stocks(
        self, market: Market | None = None
    ) -> list[tuple[int, str, Market]]:
        if market:
            query = """
                SELECT id, symbol, market FROM stocks
                WHERE is_active = true AND market = %s
            """
            params: tuple = (market.value,)
        else:
            query = "SELECT id, symbol, market FROM stocks WHERE is_active = true"
            params = ()

        with self._conn.cursor() as cur:
            cur.execute(query, params)
            return [(row[0], row[1], Market(row[2])) for row in cur.fetchall()]

    def deactivate_unlisted(self, market: Market, active_symbols: set[str]) -> int:
        if not active_symbols:
            return 0
        query = """
            UPDATE stocks SET is_active = false, updated_at = now()
            WHERE market = %s AND symbol != ALL(%s) AND is_active = true
        """
        with self._conn.cursor() as cur:
            cur.execute(query, (market.value, list(active_symbols)))
            return cur.rowcount


class DailyPriceRepository:
    def __init__(self, conn: connection):
        self._conn = conn

    def upsert_batch(self, stock_id: int, prices: list[DailyPrice]) -> int:
        if not prices:
            return 0
        query = """
            INSERT INTO daily_prices (stock_id, date, open, high, low, close, volume)
            VALUES %s
            ON CONFLICT (stock_id, date) DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume
        """
        data = [
            (stock_id, p.date, p.open, p.high, p.low, p.close, p.volume)
            for p in prices
        ]
        with self._conn.cursor() as cur:
            execute_values(cur, query, data)
            return cur.rowcount

    def get_latest_date(self, stock_id: int) -> date | None:
        query = "SELECT MAX(date) FROM daily_prices WHERE stock_id = %s"
        with self._conn.cursor() as cur:
            cur.execute(query, (stock_id,))
            result = cur.fetchone()
            return result[0] if result and result[0] else None