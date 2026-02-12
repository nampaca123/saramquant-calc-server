import logging

from app.db import get_connection
from app.services import PriceCollectionService
from app.services.price_collection_service import REGION_CONFIG
from app.services.fundamental_collection_service import FundamentalCollectionService
from app.pipeline.indicator_compute import IndicatorComputeEngine
from app.pipeline.fundamental_compute import FundamentalComputeEngine

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    def __init__(self):
        self._collector = PriceCollectionService()
        self._fund_collector = FundamentalCollectionService()

    def run_kr(self) -> None:
        logger.info("[Pipeline] Starting KR pipeline")
        self._collector.collect_all("kr")
        self._fund_collector.collect_all("kr")
        self._compute("kr")
        self._compute_fundamentals("kr")
        logger.info("[Pipeline] KR pipeline complete")

    def run_us(self) -> None:
        logger.info("[Pipeline] Starting US pipeline")
        self._collector.collect_all("us")
        self._fund_collector.collect_all("us")
        self._compute("us")
        self._compute_fundamentals("us")
        logger.info("[Pipeline] US pipeline complete")

    def run_all(self) -> None:
        self.run_kr()
        self.run_us()

    def _compute(self, region: str) -> None:
        markets = REGION_CONFIG[region]["markets"]
        with get_connection() as conn:
            engine = IndicatorComputeEngine(conn)
            count = engine.run(markets)
            logger.info(f"[Pipeline] Computed {count} indicator rows")

    def _compute_fundamentals(self, region: str) -> None:
        markets = REGION_CONFIG[region]["markets"]
        with get_connection() as conn:
            engine = FundamentalComputeEngine(conn)
            count = engine.run(markets)
            logger.info(f"[Pipeline] Computed {count} fundamental rows")
