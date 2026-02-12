from dataclasses import dataclass
from decimal import Decimal

from app.schema.enums import ReportType


@dataclass
class FinancialStatement:
    stock_id: int
    fiscal_year: int
    report_type: ReportType
    revenue: Decimal | None
    operating_income: Decimal | None
    net_income: Decimal | None
    total_assets: Decimal | None
    total_liabilities: Decimal | None
    total_equity: Decimal | None
    shares_outstanding: int | None
