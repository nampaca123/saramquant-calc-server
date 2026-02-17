import logging

from app.db import get_connection
from app.db.repositories.stock import StockRepository
from app.services import PriceCollectionService
from app.services.price_collection_service import REGION_CONFIG
from app.services.fundamental_collection_service import FundamentalCollectionService
from app.collectors import SectorCollector
from app.pipeline.indicator_compute import IndicatorComputeEngine
from app.pipeline.fundamental_compute import FundamentalComputeEngine
from app.pipeline.factor_compute import FactorComputeEngine
from app.pipeline.sector_aggregate_compute import SectorAggregateComputeEngine
from app.pipeline.integrity_check import IntegrityCheckEngine

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    def __init__(self):
        self._collector = PriceCollectionService()
        self._fund_collector = FundamentalCollectionService()

    def run_daily_kr(self) -> None:
        logger.info("[Pipeline] Starting KR daily pipeline")
        self._collector.collect_all("kr")
        self._deactivate_no_price_stocks(REGION_CONFIG["kr"]["markets"])
        self._compute_fundamentals("kr")          # 1. fundamentals first (factor model needs them)
        self._compute_factors("kr")                # 2. factor model (produces exposures + covariance)
        self._compute("kr")                        # 3. indicators (uses factor betas from step 2)
        self._compute_sector_aggregates("kr")
        self._run_integrity_check("kr")
        logger.info("[Pipeline] KR daily pipeline complete")

    def run_daily_us(self) -> None:
        logger.info("[Pipeline] Starting US daily pipeline")
        self._collector.collect_all("us")
        self._deactivate_no_price_stocks(REGION_CONFIG["us"]["markets"])
        self._compute_fundamentals("us")           # 1. fundamentals first
        self._compute_factors("us")                # 2. factor model
        self._compute("us")                        # 3. indicators (uses factor betas)
        self._compute_sector_aggregates("us")
        self._run_integrity_check("us")
        logger.info("[Pipeline] US daily pipeline complete")

    def run_daily_all(self) -> None:
        self.run_daily_kr()
        self.run_daily_us()

    def run_collect_fs_kr(self) -> None:
        logger.info("[Pipeline] Collecting KR financial statements")
        self._fund_collector.collect_all("kr")
        self._compute_fundamentals("kr")
        logger.info("[Pipeline] KR financial statement pipeline complete")

    def run_collect_fs_us(self) -> None:
        logger.info("[Pipeline] Collecting US financial statements")
        self._fund_collector.collect_all("us")
        self._compute_fundamentals("us")
        logger.info("[Pipeline] US financial statement pipeline complete")

    def run_full(self) -> None:
        logger.info("[Pipeline] Starting full pipeline")
        self.run_daily_kr()
        self.run_daily_us()
        self.run_collect_fs_kr()
        self.run_collect_fs_us()
        self._compute_fundamentals_all()
        logger.info("[Pipeline] Full pipeline complete")

    def _deactivate_no_price_stocks(self, markets: list) -> None:
        with get_connection() as conn:
            repo = StockRepository(conn)
            for market in markets:
                count = repo.deactivate_no_price_stocks(market)
                if count:
                    logger.info(f"[Pipeline] Deactivated {count} no-price stocks in {market.value}")
            conn.commit()

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

    def _compute_factors(self, region: str) -> None:
        markets = REGION_CONFIG[region]["markets"]
        with get_connection() as conn:
            engine = FactorComputeEngine(conn)
            count = engine.run(markets)
            logger.info(f"[Pipeline] Computed {count} factor exposure rows")

    def _compute_sector_aggregates(self, region: str) -> None:
        markets = REGION_CONFIG[region]["markets"]
        with get_connection() as conn:
            engine = SectorAggregateComputeEngine(conn)
            count = engine.run(markets)
            logger.info(f"[Pipeline] Computed {count} sector aggregate rows")

    def _run_integrity_check(self, region: str) -> None:
        markets = REGION_CONFIG[region]["markets"]
        with get_connection() as conn:
            engine = IntegrityCheckEngine(conn)
            engine.run(markets)

    def run_sectors(self) -> None:
        logger.info("[Pipeline] Starting sector collection")
        all_markets = REGION_CONFIG["kr"]["markets"] + REGION_CONFIG["us"]["markets"]
        count = SectorCollector().collect(all_markets)
        logger.info(f"[Pipeline] Sector collection complete: {count} updated")

    def _compute_fundamentals_all(self) -> None:
        for region in ("kr", "us"):
            markets = REGION_CONFIG[region]["markets"]
            with get_connection() as conn:
                engine = FundamentalComputeEngine(conn)
                count = engine.run(markets)
                logger.info(f"[Pipeline] Re-computed {count} fundamental rows ({region})")
