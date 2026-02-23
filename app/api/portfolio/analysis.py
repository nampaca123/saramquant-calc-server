import logging
from flask import request, jsonify
from app.api.portfolio import portfolio_bp
from app.services.portfolio_analysis_service import PortfolioAnalysisService

logger = logging.getLogger(__name__)


def _get_portfolio_id():
    body = request.get_json(silent=True) or {}
    pid = body.get("portfolio_id")
    return int(pid) if pid else None


@portfolio_bp.route("/full-analysis", methods=["POST"])
def full_analysis():
    pid = _get_portfolio_id()
    if not pid:
        return jsonify({"error": "portfolio_id required"}), 400
    try:
        return jsonify(PortfolioAnalysisService.full_analysis(pid))
    except Exception as e:
        logger.exception("full_analysis failed for portfolio %s", pid)
        return jsonify({"error": str(e)}), 200
