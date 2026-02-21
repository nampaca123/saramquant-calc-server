from datetime import date
from decimal import Decimal
from dataclasses import dataclass
from psycopg2.extensions import connection
from psycopg2.extras import execute_values


@dataclass
class ExchangeRateRow:
    pair: str
    date: date
    rate: Decimal


class ExchangeRateRepository:
    def __init__(self, conn: connection):
        self._conn = conn

    def upsert_batch(self, rows: list[ExchangeRateRow]) -> int:
        if not rows:
            return 0
        query = """
            INSERT INTO exchange_rates (pair, date, rate)
            VALUES %s
            ON CONFLICT (pair, date) DO UPDATE SET rate = EXCLUDED.rate
        """
        data = [(r.pair, r.date, r.rate) for r in rows]
        with self._conn.cursor() as cur:
            execute_values(cur, query, data)
            return cur.rowcount

    def get_latest_date(self, pair: str) -> date | None:
        query = "SELECT MAX(date) FROM exchange_rates WHERE pair = %s"
        with self._conn.cursor() as cur:
            cur.execute(query, (pair,))
            row = cur.fetchone()
            return row[0] if row and row[0] else None

    def get_rate_on_or_before(self, pair: str, target_date: date) -> Decimal | None:
        query = """
            SELECT rate FROM exchange_rates
            WHERE pair = %s AND date <= %s
            ORDER BY date DESC LIMIT 1
        """
        with self._conn.cursor() as cur:
            cur.execute(query, (pair, target_date))
            row = cur.fetchone()
            return row[0] if row else None

    def upsert_one(self, row: ExchangeRateRow) -> None:
        query = """
            INSERT INTO exchange_rates (pair, date, rate)
            VALUES (%s, %s, %s)
            ON CONFLICT (pair, date) DO UPDATE SET rate = EXCLUDED.rate
        """
        with self._conn.cursor() as cur:
            cur.execute(query, (row.pair, row.date, row.rate))

    def get_latest_rate(self, pair: str) -> Decimal | None:
        query = """
            SELECT rate FROM exchange_rates
            WHERE pair = %s ORDER BY date DESC LIMIT 1
        """
        with self._conn.cursor() as cur:
            cur.execute(query, (pair,))
            row = cur.fetchone()
            return row[0] if row else None
