from flask import request, jsonify
from app.api.portfolio import portfolio_bp
from app.services.portfolio_analysis_service import PortfolioAnalysisService


@portfolio_bp.route("/risk-score", methods=["POST"])
def risk_score():
    body = request.get_json(silent=True) or {}
    portfolio_id = body.get("portfolio_id")
    if not portfolio_id:
        return jsonify({"error": "portfolio_id required"}), 400
    result = PortfolioAnalysisService.risk_score(int(portfolio_id))
    return jsonify(result)


@portfolio_bp.route("/risk", methods=["POST"])
def risk_decomposition():
    body = request.get_json(silent=True) or {}
    portfolio_id = body.get("portfolio_id")
    if not portfolio_id:
        return jsonify({"error": "portfolio_id required"}), 400
    result = PortfolioAnalysisService.risk_decomposition(int(portfolio_id))
    return jsonify(result)


@portfolio_bp.route("/diversification", methods=["POST"])
def diversification():
    body = request.get_json(silent=True) or {}
    portfolio_id = body.get("portfolio_id")
    if not portfolio_id:
        return jsonify({"error": "portfolio_id required"}), 400
    result = PortfolioAnalysisService.diversification(int(portfolio_id))
    return jsonify(result)
