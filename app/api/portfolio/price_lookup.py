from flask import request, jsonify
from app.api.portfolio import portfolio_bp
from app.services.historical_price_lookup import HistoricalPriceLookup
from datetime import date

_lookup = HistoricalPriceLookup()


@portfolio_bp.route("/price-lookup", methods=["POST"])
def price_lookup():
    body = request.get_json(silent=True) or {}
    stock_id = body.get("stock_id")
    date_str = body.get("date")

    if not stock_id or not date_str:
        return jsonify({"error": "stock_id and date are required"}), 400

    try:
        target_date = date.fromisoformat(date_str)
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400

    result = _lookup.lookup(int(stock_id), target_date)
    if result is None:
        return jsonify({"found": False, "message": "Price not available"}), 200

    resp = {
        "found": True,
        "close": float(result["close"]),
        "date": result["date"].isoformat(),
        "source": result["source"],
    }
    if "fx_rate" in result:
        resp["fx_rate"] = result["fx_rate"]

    return jsonify(resp)
