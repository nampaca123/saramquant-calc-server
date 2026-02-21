# SaramQuant Calc Server - Directory Structure

```
saramquant-calc-server/
├── run.py
├── requirements.txt
├── db_table.sql
├── Dockerfile
│
├── app/
│   ├── api/
│   │   ├── quant/
│   │   │   └── simulation.py           # 몬테카를로 시뮬레이션 API
│   │   └── portfolio/
│   │       ├── analysis.py             # 리스크 점수, 리스크 분해, 분산도
│   │       ├── simulation.py           # 포트폴리오 시뮬레이션
│   │       └── price_lookup.py         # 특정 날짜 종가/환율 조회
│   │
│   ├── collectors/
│   │   ├── __init__.py
│   │   ├── clients/
│   │   │   ├── alpaca.py
│   │   │   ├── dart.py
│   │   │   ├── ecos.py
│   │   │   ├── finnhub.py
│   │   │   ├── fred.py
│   │   │   ├── nasdaq_screener.py
│   │   │   ├── pykrx.py
│   │   │   └── yfinance.py
│   │   ├── service/
│   │   │   ├── benchmark_price.py
│   │   │   ├── kr_daily_price.py
│   │   │   ├── kr_financial_statement.py
│   │   │   ├── risk_free_rate.py
│   │   │   ├── sector_classification.py
│   │   │   ├── us_daily_price.py
│   │   │   └── us_stock_list.py
│   │   └── pipeline.py
│   │
│   ├── quant/
│   │   ├── indicator/
│   │   │   ├── technical.py
│   │   │   ├── fundamental.py
│   │   │   ├── factor_model.py
│   │   │   └── sector_aggregate.py
│   │   ├── risk_badge/
│   │   │   ├── badge_engine.py
│   │   │   ├── dimension_engines/
│   │   │   │   ├── price_heat.py
│   │   │   │   ├── volatility.py
│   │   │   │   ├── trend.py
│   │   │   │   ├── company_health.py
│   │   │   │   └── valuation.py
│   │   │   └── summary.py
│   │   └── portfolio/
│   │       ├── risk_score.py
│   │       ├── risk_decomposition.py
│   │       └── diversification.py
│   │
│   ├── services/
│   │   ├── indicator_compute_service.py
│   │   ├── fundamental_compute_service.py
│   │   ├── factor_compute_service.py
│   │   ├── sector_aggregate_compute_service.py
│   │   └── risk_badge_compute_service.py
│   │
│   ├── pipeline.py
│   │
│   ├── models/
│   │   ├── enums/
│   │   │   ├── benchmark.py
│   │   │   ├── country.py
│   │   │   ├── data_coverage.py
│   │   │   ├── data_source.py
│   │   │   ├── market.py
│   │   │   ├── maturity.py
│   │   │   └── report_type.py
│   │
│   └── utils/
│       ├── quant/
│       │   └── market_reference_data.py
│       └── system/
│           ├── errors.py
│           ├── logging_config.py
│           └── retry.py
│
├── docs/
│   └── structure/
│       ├── fundamental-pipeline-story.md
│       ├── indicator-optimization-story.md
│       ├── multi-factor-risk-model-story.md
│       ├── risk_badge_system.md
│       ├── sector_classification.md
│       ├── saramquant_directory_structure.md
│       ├── saramquant_general_plan.md
│       ├── issues-2026-02-16.md
│       ├── test-kr-workflow-initial-2026-02-16.md
│       └── test-us-workflow-initial-2026-02-16.md
│
└── tests/
    └── data_source_test/
        └── test_all_sources.py
```
