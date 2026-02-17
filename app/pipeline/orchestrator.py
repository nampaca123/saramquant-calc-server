import logging
from typing import Callable, Any

from app.db import get_connection, DailyPriceRepository
from app.db.repositories.stock import StockRepository
from app.schema import Market
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

PriceMaps = dict[Market, dict[int, list[tuple]]]


class PipelineOrchestrator:
    def __init__(self):
        self._collector = PriceCollectionService()
        self._fund_collector = FundamentalCollectionService()

    # ── public entry points ──

    def run_daily_kr(self) -> None:
        logger.info("[Pipeline] Starting KR daily pipeline")
        self._collector.collect_all("kr")
        self._run_compute_pipeline("kr")
        logger.info("[Pipeline] KR daily pipeline complete")

    def run_daily_us(self) -> None:
        logger.info("[Pipeline] Starting US daily pipeline")
        self._collector.collect_all("us")
        self._run_compute_pipeline("us")
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
        self._collector.collect_all("kr")
        self._collector.collect_all("us")
        self._fund_collector.collect_all("kr")
        self._fund_collector.collect_all("us")
        for region in ("kr", "us"):
            self._run_compute_pipeline(region)
        logger.info("[Pipeline] Full pipeline complete")

    def run_sectors(self) -> None:
        logger.info("[Pipeline] Starting sector collection")
        all_markets = REGION_CONFIG["kr"]["markets"] + REGION_CONFIG["us"]["markets"]
        count = SectorCollector().collect(all_markets)
        logger.info(f"[Pipeline] Sector collection complete: {count} updated")

    # ── compute pipeline ──

    def _run_compute_pipeline(self, region: str) -> None:
        markets = REGION_CONFIG[region]["markets"]
        self._deactivate_no_price_stocks(markets)
        price_maps = self._load_prices(markets)

        fund_ok = self._safe_step("fundamentals", self._compute_fundamentals, region, price_maps)
        factor_ok = self._safe_step("factors", self._compute_factors, region, price_maps) if fund_ok else False
        if factor_ok:
            self._safe_step("indicators", self._compute, region, price_maps)
        if fund_ok:
            self._safe_step("sector_agg", self._compute_sector_aggregates, region)
        self._run_integrity_check(region)

    def _load_prices(self, markets: list[Market]) -> PriceMaps:
        price_maps: PriceMaps = {}
        with get_connection() as conn:
            repo = DailyPriceRepository(conn)
            for market in markets:
                price_maps[market] = repo.get_prices_by_market(market, limit_per_stock=300)
        return price_maps

    def _safe_step(self, name: str, fn: Callable[..., Any], *args: Any) -> bool:
        try:
            fn(*args)
            return True
        except Exception as e:
            logger.error(f"[Pipeline] Step '{name}' failed: {e}", exc_info=True)
            return False

    # ── individual steps ──

    def _deactivate_no_price_stocks(self, markets: list) -> None:
        with get_connection() as conn:
            repo = StockRepository(conn)
            for market in markets:
                count = repo.deactivate_no_price_stocks(market)
                if count:
                    logger.info(f"[Pipeline] Deactivated {count} no-price stocks in {market.value}")
            conn.commit()

    def _compute(self, region: str, price_maps: PriceMaps | None = None) -> None:
        markets = REGION_CONFIG[region]["markets"]
        with get_connection() as conn:
            engine = IndicatorComputeEngine(conn)
            count = engine.run(markets, price_maps)
            logger.info(f"[Pipeline] Computed {count} indicator rows")

    def _compute_fundamentals(self, region: str, price_maps: PriceMaps | None = None) -> None:
        markets = REGION_CONFIG[region]["markets"]
        with get_connection() as conn:
            engine = FundamentalComputeEngine(conn)
            count = engine.run(markets, price_maps)
            logger.info(f"[Pipeline] Computed {count} fundamental rows")

    def _compute_factors(self, region: str, price_maps: PriceMaps | None = None) -> None:
        markets = REGION_CONFIG[region]["markets"]
        with get_connection() as conn:
            engine = FactorComputeEngine(conn)
            count = engine.run(markets, price_maps)
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
