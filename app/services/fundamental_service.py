from datetime import date

from app.schema import DataCoverage, FinancialStatement, ReportType
from app.quant.fundamentals import (
    eps, bps, per, pbr,
    roe, operating_margin,
    debt_ratio,
)

_Q_ORDER = [ReportType.Q1, ReportType.Q2, ReportType.Q3]


class FundamentalService:
    @staticmethod
    def compute(
        stock_id: int,
        latest_price: float,
        statements: list[FinancialStatement],
    ) -> tuple | None:
        if not statements:
            return None

        latest = statements[0]
        bs_equity = _to_float(latest.total_equity)
        bs_liabilities = _to_float(latest.total_liabilities)
        shares = latest.shares_outstanding

        ttm = FundamentalService._ttm_income(statements)

        if ttm is not None:
            ttm_revenue, ttm_op_income, ttm_net_income = ttm
            eps_val = eps(ttm_net_income, shares) if ttm_net_income is not None else None
            roe_val = roe(ttm_net_income, bs_equity) if ttm_net_income is not None and bs_equity else None
            op_margin_val = (
                operating_margin(ttm_op_income, ttm_revenue)
                if ttm_op_income is not None and ttm_revenue is not None
                else None
            )
            all_present = all(v is not None for v in ttm)
            if eps_val is not None and eps_val < 0:
                coverage = DataCoverage.LOSS
            elif all_present:
                coverage = DataCoverage.FULL
            else:
                coverage = DataCoverage.PARTIAL
        else:
            eps_val = roe_val = op_margin_val = None
            if bs_equity is not None or bs_liabilities is not None:
                coverage = DataCoverage.PARTIAL
            else:
                coverage = DataCoverage.INSUFFICIENT

        bps_val = bps(bs_equity, shares) if bs_equity is not None else None
        per_val = per(latest_price, eps_val) if eps_val is not None else None
        pbr_val = pbr(latest_price, bps_val) if bps_val is not None else None
        debt_val = debt_ratio(bs_liabilities, bs_equity) if bs_equity and bs_liabilities is not None else None

        return (
            stock_id,
            date.today(),
            _round(per_val),
            _round(pbr_val),
            _round(eps_val),
            _round(bps_val),
            _round(roe_val),
            _round(debt_val),
            _round(op_margin_val),
            coverage.value,
        )

    @staticmethod
    def no_fs_row(stock_id: int) -> tuple:
        return (
            stock_id, date.today(),
            None, None, None, None, None, None, None,
            DataCoverage.NO_FS.value,
        )

    @staticmethod
    def _ttm_income(
        statements: list[FinancialStatement],
    ) -> tuple[float | None, float | None, float | None] | None:
        if not statements:
            return None

        if statements[0].report_type == ReportType.FY:
            s = statements[0]
            return _to_float(s.revenue), _to_float(s.operating_income), _to_float(s.net_income)

        fy_stmt: FinancialStatement | None = None
        current_qs: dict[ReportType, FinancialStatement] = {}
        prior_qs: dict[ReportType, FinancialStatement] = {}

        for s in statements:
            if s.report_type == ReportType.FY and fy_stmt is None:
                fy_stmt = s
            elif s.report_type != ReportType.FY:
                if fy_stmt is None:
                    current_qs.setdefault(s.report_type, s)
                elif s.fiscal_year == fy_stmt.fiscal_year:
                    prior_qs.setdefault(s.report_type, s)

        if fy_stmt is None:
            return None

        n = 0
        for qt in _Q_ORDER:
            if qt in current_qs and qt in prior_qs:
                n += 1
            else:
                break
        if n == 0:
            return None

        def _field_ttm(getter):
            fy_val = getter(fy_stmt)
            if fy_val is None:
                return None
            cur = [getter(current_qs[_Q_ORDER[i]]) for i in range(n)]
            pri = [getter(prior_qs[_Q_ORDER[i]]) for i in range(n)]
            if any(v is None for v in cur) or any(v is None for v in pri):
                return None
            return fy_val + sum(cur) - sum(pri)

        result = (
            _field_ttm(lambda s: _to_float(s.revenue)),
            _field_ttm(lambda s: _to_float(s.operating_income)),
            _field_ttm(lambda s: _to_float(s.net_income)),
        )
        if all(v is None for v in result):
            return None
        return result


def _to_float(val) -> float | None:
    if val is None:
        return None
    return float(val)


def _round(val: float | None, digits: int = 4) -> float | None:
    if val is None:
        return None
    return round(val, digits)
