from datetime import date
from decimal import Decimal
from dataclasses import dataclass
from psycopg2.extensions import connection
from psycopg2.extras import execute_values


@dataclass
class HoldingRow:
    id: int
    portfolio_id: int
    stock_id: int
    shares: Decimal
    avg_price: Decimal
    currency: str
    purchased_at: date
    price_source: str


class PortfolioRepository:
    def __init__(self, conn: connection):
        self._conn = conn

    def get_holdings(self, portfolio_id: int) -> list[HoldingRow]:
        query = """
            SELECT id, portfolio_id, stock_id, shares, avg_price,
                   currency, purchased_at, price_source
            FROM portfolio_holdings
            WHERE portfolio_id = %s
            ORDER BY stock_id
        """
        with self._conn.cursor() as cur:
            cur.execute(query, (portfolio_id,))
            return [
                HoldingRow(
                    id=r[0], portfolio_id=r[1], stock_id=r[2],
                    shares=r[3], avg_price=r[4], currency=r[5],
                    purchased_at=r[6], price_source=r[7],
                )
                for r in cur.fetchall()
            ]

    def get_portfolio_market_group(self, portfolio_id: int) -> str | None:
        query = "SELECT market_group FROM user_portfolios WHERE id = %s"
        with self._conn.cursor() as cur:
            cur.execute(query, (portfolio_id,))
            row = cur.fetchone()
            return row[0] if row else None

    def get_holding_stock_ids(self, portfolio_id: int) -> list[int]:
        query = "SELECT stock_id FROM portfolio_holdings WHERE portfolio_id = %s"
        with self._conn.cursor() as cur:
            cur.execute(query, (portfolio_id,))
            return [r[0] for r in cur.fetchall()]
