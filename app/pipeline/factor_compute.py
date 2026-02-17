import logging

from psycopg2.extensions import connection

from app.schema import Market
from app.services.factor_model_service import FactorModelService

logger = logging.getLogger(__name__)


class FactorComputeEngine:
    def __init__(self, conn: connection):
        self._service = FactorModelService(conn)
        self._conn = conn

    def run(self, markets: list[Market]) -> int:
        total = 0
        for market in markets:
            result = self._service.run(market)
            if result.get("status") == "ok":
                total += result.get("exposures", 0)
        self._conn.commit()
        return total
