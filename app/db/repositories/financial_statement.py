from decimal import Decimal

from psycopg2.extensions import connection
from psycopg2.extras import execute_values

from app.schema import FinancialStatement, Market, ReportType


class FinancialStatementRepository:
    def __init__(self, conn: connection):
        self._conn = conn

    def upsert_batch(self, statements: list[FinancialStatement]) -> int:
        if not statements:
            return 0
        query = """
            INSERT INTO financial_statements
                (stock_id, fiscal_year, report_type, revenue, operating_income,
                 net_income, total_assets, total_liabilities, total_equity,
                 shares_outstanding)
            VALUES %s
            ON CONFLICT (stock_id, fiscal_year, report_type) DO UPDATE SET
                revenue = EXCLUDED.revenue,
                operating_income = EXCLUDED.operating_income,
                net_income = EXCLUDED.net_income,
                total_assets = EXCLUDED.total_assets,
                total_liabilities = EXCLUDED.total_liabilities,
                total_equity = EXCLUDED.total_equity,
                shares_outstanding = EXCLUDED.shares_outstanding
        """
        data = [
            (
                s.stock_id, s.fiscal_year, s.report_type.value,
                s.revenue, s.operating_income, s.net_income,
                s.total_assets, s.total_liabilities, s.total_equity,
                s.shares_outstanding,
            )
            for s in statements
        ]
        with self._conn.cursor() as cur:
            execute_values(cur, query, data)
            return cur.rowcount

    def get_ttm_by_stock(self, stock_id: int) -> list[FinancialStatement]:
        query = """
            SELECT stock_id, fiscal_year, report_type,
                   revenue, operating_income, net_income,
                   total_assets, total_liabilities, total_equity,
                   shares_outstanding
            FROM financial_statements
            WHERE stock_id = %s
            ORDER BY fiscal_year DESC,
                     CASE report_type
                         WHEN 'FY' THEN 4 WHEN 'Q3' THEN 3
                         WHEN 'Q2' THEN 2 WHEN 'Q1' THEN 1
                     END DESC
            LIMIT 5
        """
        with self._conn.cursor() as cur:
            cur.execute(query, (stock_id,))
            return [self._row_to_dto(row) for row in cur.fetchall()]

    def get_ttm_by_market(
        self, market: Market
    ) -> dict[int, list[FinancialStatement]]:
        query = """
            SELECT fs.stock_id, fs.fiscal_year, fs.report_type,
                   fs.revenue, fs.operating_income, fs.net_income,
                   fs.total_assets, fs.total_liabilities, fs.total_equity,
                   fs.shares_outstanding
            FROM financial_statements fs
            JOIN stocks s ON s.id = fs.stock_id
            WHERE s.market = %s AND s.is_active = true
              AND fs.fiscal_year >= (
                  SELECT MAX(f2.fiscal_year) - 1
                  FROM financial_statements f2
                  WHERE f2.stock_id = fs.stock_id
              )
            ORDER BY fs.stock_id,
                     fs.fiscal_year DESC,
                     CASE fs.report_type
                         WHEN 'FY' THEN 4 WHEN 'Q3' THEN 3
                         WHEN 'Q2' THEN 2 WHEN 'Q1' THEN 1
                     END DESC
        """
        result: dict[int, list[FinancialStatement]] = {}
        with self._conn.cursor() as cur:
            cur.execute(query, (market.value,))
            for row in cur.fetchall():
                dto = self._row_to_dto(row)
                result.setdefault(dto.stock_id, []).append(dto)

        for stock_id in result:
            result[stock_id] = result[stock_id][:5]

        return result

    @staticmethod
    def _row_to_dto(row: tuple) -> FinancialStatement:
        return FinancialStatement(
            stock_id=row[0],
            fiscal_year=row[1],
            report_type=ReportType(row[2]),
            revenue=row[3],
            operating_income=row[4],
            net_income=row[5],
            total_assets=row[6],
            total_liabilities=row[7],
            total_equity=row[8],
            shares_outstanding=row[9],
        )
