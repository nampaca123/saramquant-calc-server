import logging
from flask import request, jsonify
from app.api.portfolio import portfolio_bp

logger = logging.getLogger(__name__)


@portfolio_bp.route("/<int:portfolio_id>/simulation", methods=["POST"])
def portfolio_simulation(portfolio_id: int):
    from app.services.portfolio_simulation_service import PortfolioSimulationService

    try:
        params = {
            "days": int(request.args.get("days", 60)),
            "num_simulations": int(request.args.get("simulations", 10000)),
            "confidence": float(request.args.get("confidence", 0.95)),
            "lookback": int(request.args.get("lookback", 252)),
            "method": request.args.get("method", "bootstrap"),
        }
        result = PortfolioSimulationService.run(portfolio_id=portfolio_id, **params)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception("portfolio simulation failed for %s", portfolio_id)
        return jsonify({"error": str(e)}), 200
