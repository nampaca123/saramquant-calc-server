from flask import Blueprint

portfolio_bp = Blueprint("portfolio", __name__, url_prefix="/internal/portfolios")

from . import price_lookup, simulation, analysis  # noqa: E402, F401
