# SaramQuant 프로젝트 설계서

------

## 1. 프로젝트 개요

### 목적

실시간 주식시장 및 ETF 정보를 수집하고, 전통적인 퀀트 투자 기법과 머신러닝을 통해 분석하여 사용자에게 투자 인사이트를 제공하는 시스템

### 기술 스택

| 레이어    | 기술                 | 역할                       |
| --------- | -------------------- | -------------------------- |
| Frontend  | Next.js              | 대시보드 UI                |
| Gateway   | Spring Boot (Kotlin) | API Gateway, 캐싱, 인증    |
| ML Server | Flask (Python)       | 데이터 수집, 퀀트 분석, ML |
| Database  | PostgreSQL           | 영구 데이터 저장           |
| Cache     | Redis                | 실시간 데이터 캐싱         |

------

## 2. 시스템 아키텍처

### 전체 구조

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           시스템 아키텍처                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│                           [Frontend]                                    │
│                            Next.js                                      │
│                               │                                         │
│                               ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    Spring Boot Gateway                           │   │
│  │                                                                  │   │
│  │   • 프론트엔드 API 제공                                           │   │
│  │   • Flask 서버 프록시                                             │   │
│  │   • Redis 캐싱 관리                                               │   │
│  │   • 인증/인가 (추후)                                              │   │
│  │                                                                  │   │
│  └──────────────────────────────┬──────────────────────────────────┘   │
│                                 │                                       │
│                                 ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      Flask ML Server                             │   │
│  │                                                                  │   │
│  │   [Data Collector]        [Quant Engine]        [ML Engine]     │   │
│  │         │                       │                     │          │   │
│  │         ▼                       ▼                     ▼          │   │
│  │   • 종목 목록 수집         • RSI, MACD          • XGBoost        │   │
│  │   • 일봉/분봉 수집         • 이동평균           • RandomForest   │   │
│  │   • 실시간 시세            • 볼린저밴드         • 학습/추론       │   │
│  │                                                                  │   │
│  └──────────────────────────────┬──────────────────────────────────┘   │
│                                 │                                       │
│              ┌──────────────────┴──────────────────┐                   │
│              ▼                                     ▼                   │
│  ┌──────────────────────┐             ┌──────────────────────┐        │
│  │     PostgreSQL       │             │        Redis         │        │
│  │                      │             │                      │        │
│  │  • 종목 정보         │             │  • 실시간 시세 캐시   │        │
│  │  • 일봉/분봉 데이터   │             │  • 예측 결과 캐시    │        │
│  │  • 예측 결과 히스토리 │             │  • API 토큰 캐시     │        │
│  │  • 모델 메타데이터    │             │                      │        │
│  └──────────────────────┘             └──────────────────────┘        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 역할 분담

| 서버            | 담당 업무                                                    |
| --------------- | ------------------------------------------------------------ |
| **Spring Boot** | API Gateway, 캐싱, 프론트엔드 통신, Flask 프록시             |
| **Flask**       | 외부 API 호출, 데이터 수집/저장, 퀀트 지표 계산, ML 학습/추론 |

------

## 3. 외부 API 전략

### 비용 최적화 원칙

- 무료 API로 가능한 작업은 무료 API 사용
- 실시간 데이터만 유료(또는 계좌 필요) API 사용

### API 선택

### 한국 시장 (KOSPI/KOSDAQ)

| 데이터 종류 | API                  | 비용  | 용도          |
| ----------- | -------------------- | ----- | ------------- |
| 종목 목록   | FinanceDataReader    | 무료  | 초기 세팅     |
| 일봉 (과거) | FinanceDataReader    | 무료  | ML 학습       |
| 일봉 (당일) | 한국투자증권 OpenAPI | 무료* | 일간 업데이트 |
| 분봉        | 한국투자증권 OpenAPI | 무료* | 단기 분석     |
| 실시간 시세 | 한국투자증권 OpenAPI | 무료* | 모니터링      |

- 증권 계좌 개설 필요 (거래 없이 API만 사용 가능)

### 미국 시장 (NASDAQ/S&P500)

| 데이터 종류 | API               | 비용 | 용도          |
| ----------- | ----------------- | ---- | ------------- |
| 종목 목록   | FinanceDataReader | 무료 | 초기 세팅     |
| 일봉 (과거) | yfinance          | 무료 | ML 학습       |
| 일봉 (당일) | yfinance          | 무료 | 일간 업데이트 |
| 분봉        | yfinance          | 무료 | 단기 분석     |
| 실시간 시세 | Finnhub 무료 티어 | 무료 | 모니터링      |

### API 제약사항

| API               | Rate Limit | 데이터 지연 | 비고               |
| ----------------- | ---------- | ----------- | ------------------ |
| FinanceDataReader | 제한 없음  | 1일         | 과거 데이터 전용   |
| yfinance          | 2,000/hour | 15분        | 분봉은 최근 7일만  |
| 한국투자증권      | 초당 20건  | 실시간      | 모의투자 계좌 가능 |
| Finnhub 무료      | 60/minute  | 실시간      | 미국 주식만        |

### 월간 예상 비용

**0원** (모든 API 무료 티어로 구성, 단 한국투자증권 계좌 개설 필요)

------

## 4. 데이터 흐름

### 일간 데이터 수집 흐름

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        일간 데이터 수집 흐름                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  [매일 16:00 KST - 한국 장 마감 후]                                       │
│                                                                         │
│      Flask Scheduler                                                    │
│           │                                                             │
│           ├──▶ FinanceDataReader ──▶ 한국 종목 일봉 수집                 │
│           │                              │                              │
│           │                              ▼                              │
│           │                        PostgreSQL 저장                      │
│           │                                                             │
│           └──▶ 한국투자증권 API ──▶ 당일 분봉 데이터 보완                 │
│                                          │                              │
│                                          ▼                              │
│                                    PostgreSQL 저장                      │
│                                                                         │
│  ─────────────────────────────────────────────────────────────────────  │
│                                                                         │
│  [매일 06:30 KST - 미국 장 마감 후]                                       │
│                                                                         │
│      Flask Scheduler                                                    │
│           │                                                             │
│           └──▶ yfinance ──▶ 미국 종목 일봉/분봉 수집                     │
│                                   │                                     │
│                                   ▼                                     │
│                             PostgreSQL 저장                             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 실시간 조회 흐름

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         실시간 조회 흐름                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  [사용자 요청]                                                           │
│                                                                         │
│      Frontend                                                           │
│         │                                                               │
│         │  GET /api/prices/realtime/005930                             │
│         ▼                                                               │
│      Spring Boot                                                        │
│         │                                                               │
│         ├──▶ Redis 캐시 확인                                            │
│         │         │                                                     │
│         │         ├── HIT ──▶ 즉시 반환                                 │
│         │         │                                                     │
│         │         └── MISS ──┐                                         │
│         │                    ▼                                          │
│         │              Flask 호출                                       │
│         │                    │                                          │
│         │                    ▼                                          │
│         │              한국투자증권 API                                  │
│         │                    │                                          │
│         │                    ▼                                          │
│         │              Redis 저장 (TTL: 10초)                           │
│         │                    │                                          │
│         ◀────────────────────┘                                          │
│         │                                                               │
│         ▼                                                               │
│      Frontend (응답)                                                    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### ML 예측 흐름

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          ML 예측 흐름                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  [매일 17:00 KST - 학습 및 예측]                                         │
│                                                                         │
│      Flask Scheduler                                                    │
│           │                                                             │
│           ├──▶ PostgreSQL에서 학습 데이터 조회                           │
│           │                                                             │
│           ├──▶ 피처 엔지니어링 (기술적 지표 계산)                         │
│           │                                                             │
│           ├──▶ 모델 학습 (XGBoost, RandomForest)                        │
│           │                                                             │
│           ├──▶ 모델 파일 저장 (/models 디렉토리)                         │
│           │                                                             │
│           ├──▶ 내일 예측 결과 생성                                       │
│           │                                                             │
│           └──▶ PostgreSQL + Redis 저장                                  │
│                                                                         │
│  ─────────────────────────────────────────────────────────────────────  │
│                                                                         │
│  [사용자 예측 조회]                                                      │
│                                                                         │
│      Frontend ──▶ Spring Boot ──▶ Redis (캐시) ──▶ 응답                 │
│                                       │                                 │
│                                       └── MISS 시 ──▶ Flask 추론        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

------

## 5. Spring Boot 디렉토리 구조

```
src/main/kotlin/com/obsa/
│
├── domain/                              # 도메인 레이어
│   ├── entity/
│   │   ├── Stock.kt                     # 종목 기본 정보
│   │   ├── DailyPrice.kt                # 일봉 데이터
│   │   ├── MinutePrice.kt               # 분봉 데이터
│   │   ├── MarketIndex.kt               # 시장 지수
│   │   ├── IndexDailyPrice.kt           # 지수 일봉
│   │   ├── PredictionResult.kt          # ML 예측 결과
│   │   └── MlModel.kt                   # 모델 메타데이터
│   │
│   ├── enum/
│   │   ├── Market.kt                    # KR_KOSPI, KR_KOSDAQ, US_NASDAQ, US_SP500
│   │   ├── DataSource.kt                # FDR, YFINANCE, KIS, FINNHUB
│   │   └── IntervalType.kt              # MINUTE_1, MINUTE_5, MINUTE_15, DAILY
│   │
│   └── repository/
│       ├── StockRepository.kt
│       ├── DailyPriceRepository.kt
│       ├── MinutePriceRepository.kt
│       └── PredictionResultRepository.kt
│
├── feature/                             # 기능 레이어 (API 엔드포인트)
│   │
│   ├── stock/                           # 종목 관련 API
│   │   ├── StockController.kt
│   │   ├── StockService.kt
│   │   └── dto/
│   │       ├── StockResponse.kt
│   │       └── StockListResponse.kt
│   │
│   ├── price/                           # 시세 관련 API
│   │   ├── PriceController.kt
│   │   ├── PriceService.kt
│   │   └── dto/
│   │       ├── DailyPriceResponse.kt
│   │       ├── MinutePriceResponse.kt
│   │       └── RealtimePriceResponse.kt
│   │
│   ├── indicator/                       # 기술적 지표 API (Flask 프록시)
│   │   ├── IndicatorController.kt
│   │   ├── IndicatorService.kt
│   │   └── dto/
│   │       └── IndicatorResponse.kt
│   │
│   └── prediction/                      # ML 예측 API (Flask 프록시)
│       ├── PredictionController.kt
│       ├── PredictionService.kt
│       └── dto/
│           └── PredictionResponse.kt
│
├── infra/                               # 인프라 레이어
│   │
│   ├── config/
│   │   ├── DatabaseConfig.kt            # PostgreSQL 설정
│   │   ├── RedisConfig.kt               # Redis 설정
│   │   └── WebClientConfig.kt           # Flask 통신용 WebClient
│   │
│   ├── client/
│   │   └── flask/                       # Flask 서버 클라이언트
│   │       ├── FlaskClient.kt
│   │       └── dto/
│   │           ├── FlaskPriceRequest.kt
│   │           ├── FlaskIndicatorRequest.kt
│   │           └── FlaskPredictionRequest.kt
│   │
│   ├── cache/
│   │   └── RedisCacheService.kt         # Redis 캐시 서비스
│   │
│   └── exception/
│       ├── ApiException.kt
│       ├── ErrorCode.kt
│       └── GlobalExceptionHandler.kt
│
└── SrqtApplication.kt
```

------

## 6. Flask 디렉토리 구조

```
flask_server/
│
├── app/
│   ├── __init__.py                      # Flask 앱 초기화
│   ├── config.py                        # 환경 설정
│   │
│   ├── api/                             # API 엔드포인트
│   │   ├── __init__.py
│   │   ├── prices.py                    # 시세 조회 API
│   │   ├── indicators.py                # 기술적 지표 API
│   │   ├── predictions.py               # ML 예측 API
│   │   └── health.py                    # 헬스 체크
│   │
│   ├── services/                        # 비즈니스 로직
│   │   ├── __init__.py
│   │   ├── price_service.py             # 시세 조회 서비스
│   │   ├── indicator_service.py         # 지표 계산 서비스
│   │   ├── prediction_service.py        # ML 추론 서비스
│   │   └── collection_service.py        # 데이터 수집 서비스
│   │
│   ├── collector/                       # 데이터 수집기
│   │   ├── __init__.py
│   │   ├── base_collector.py            # 추상 베이스 클래스
│   │   ├── fdr_collector.py             # FinanceDataReader 수집기
│   │   ├── yfinance_collector.py        # yfinance 수집기
│   │   ├── kis_collector.py             # 한국투자증권 수집기
│   │   └── finnhub_collector.py         # Finnhub 수집기
│   │
│   ├── quant/                           # 퀀트 엔진
│   │   ├── __init__.py
│   │   ├── indicators/
│   │   │   ├── __init__.py
│   │   │   ├── moving_average.py        # SMA, EMA, WMA
│   │   │   ├── momentum.py              # RSI, MACD, Stochastic
│   │   │   ├── volatility.py            # Bollinger Bands, ATR
│   │   │   └── volume.py                # OBV, VMA
│   │   │
│   │   └── calculator.py                # 지표 통합 계산기
│   │
│   ├── ml/                              # ML 엔진
│   │   ├── __init__.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── base_model.py            # 추상 베이스 클래스
│   │   │   ├── xgboost_model.py
│   │   │   └── random_forest_model.py
│   │   │
│   │   ├── features/
│   │   │   ├── __init__.py
│   │   │   └── feature_engineer.py      # 피처 생성
│   │   │
│   │   ├── trainer.py                   # 모델 학습
│   │   ├── predictor.py                 # 모델 추론
│   │   └── model_manager.py             # 모델 저장/로드/버전 관리
│   │
│   ├── scheduler/                       # 스케줄러
│   │   ├── __init__.py
│   │   ├── scheduler.py                 # APScheduler 설정
│   │   ├── daily_collect_job.py         # 일간 데이터 수집 작업
│   │   ├── minute_collect_job.py        # 분봉 데이터 수집 작업
│   │   └── train_job.py                 # ML 학습 작업
│   │
│   └── utils/
│       ├── __init__.py
│       ├── database.py                  # PostgreSQL 연결 (SQLAlchemy)
│       ├── cache.py                     # Redis 연결
│       └── logger.py                    # 로깅 설정
│
├── models/                              # 학습된 모델 저장
│   ├── xgboost/
│   │   ├── kr_kospi_v20240115.pkl
│   │   ├── kr_kospi_latest.pkl          # 심볼릭 링크
│   │   └── us_nasdaq_latest.pkl
│   │
│   └── random_forest/
│       └── ...
│
├── scripts/                             # CLI 스크립트
│   ├── train.py                         # python scripts/train.py --market KR_KOSPI
│   ├── backtest.py                      # python scripts/backtest.py
│   └── init_data.py                     # python scripts/init_data.py (초기 데이터 수집)
│
├── tests/
│   ├── __init__.py
│   ├── test_collectors.py
│   ├── test_indicators.py
│   └── test_ml.py
│
├── requirements.txt
├── Dockerfile
└── run.py                               # Flask 실행 진입점
```

------

## 7. 데이터베이스 스키마

### ERD 개요

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            ERD 다이어그램                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐       ┌─────────────────┐       ┌─────────────────┐   │
│  │   stocks    │       │  daily_prices   │       │ minute_prices   │   │
│  ├─────────────┤       ├─────────────────┤       ├─────────────────┤   │
│  │ id (PK)     │──┐    │ id (PK)         │       │ id (PK)         │   │
│  │ symbol      │  │    │ stock_id (FK)   │◀──────│ stock_id (FK)   │   │
│  │ name        │  │    │ date            │       │ datetime        │   │
│  │ market      │  └───▶│ open/high/low   │       │ interval_type   │   │
│  │ sector      │       │ close/volume    │       │ open/high/low   │   │
│  │ industry    │       │ adjusted_close  │       │ close/volume    │   │
│  └─────────────┘       └─────────────────┘       └─────────────────┘   │
│         │                                                               │
│         │              ┌─────────────────────┐                         │
│         │              │ prediction_results  │                         │
│         │              ├─────────────────────┤                         │
│         └─────────────▶│ id (PK)             │                         │
│                        │ stock_id (FK)       │                         │
│                        │ prediction_date     │                         │
│                        │ model_name/version  │                         │
│                        │ predicted_direction │                         │
│                        │ confidence          │                         │
│                        │ actual_direction    │                         │
│                        └─────────────────────┘                         │
│                                                                         │
│  ┌─────────────────┐       ┌─────────────────────┐                     │
│  │ market_indices  │       │ index_daily_prices  │                     │
│  ├─────────────────┤       ├─────────────────────┤                     │
│  │ id (PK)         │──────▶│ id (PK)             │                     │
│  │ index_code      │       │ index_id (FK)       │                     │
│  │ name            │       │ date                │                     │
│  │ market          │       │ open/high/low/close │                     │
│  └─────────────────┘       └─────────────────────┘                     │
│                                                                         │
│  ┌─────────────────┐       ┌─────────────────────┐                     │
│  │   ml_models     │       │  collection_logs    │                     │
│  ├─────────────────┤       ├─────────────────────┤                     │
│  │ id (PK)         │       │ id (PK)             │                     │
│  │ model_name      │       │ collection_type     │                     │
│  │ version         │       │ market              │                     │
│  │ market          │       │ status              │                     │
│  │ accuracy/f1     │       │ records_collected   │                     │
│  │ model_path      │       │ error_message       │                     │
│  │ is_active       │       │ started_at          │                     │
│  └─────────────────┘       └─────────────────────┘                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 테이블 상세

### stocks (종목 정보)

| 컬럼       | 타입         | 설명                                     |
| ---------- | ------------ | ---------------------------------------- |
| id         | BIGSERIAL    | PK                                       |
| symbol     | VARCHAR(20)  | 종목 코드 (005930, AAPL)                 |
| name       | VARCHAR(100) | 종목명                                   |
| market     | VARCHAR(20)  | KR_KOSPI, KR_KOSDAQ, US_NASDAQ, US_SP500 |
| sector     | VARCHAR(50)  | 섹터                                     |
| industry   | VARCHAR(50)  | 산업                                     |
| is_active  | BOOLEAN      | 활성 여부                                |
| created_at | TIMESTAMP    | 생성일시                                 |
| updated_at | TIMESTAMP    | 수정일시                                 |

### daily_prices (일봉 데이터)

| 컬럼           | 타입          | 설명                               |
| -------------- | ------------- | ---------------------------------- |
| id             | BIGSERIAL     | PK                                 |
| stock_id       | BIGINT        | FK → [stocks.id](http://stocks.id) |
| date           | DATE          | 거래일                             |
| open           | DECIMAL(15,2) | 시가                               |
| high           | DECIMAL(15,2) | 고가                               |
| low            | DECIMAL(15,2) | 저가                               |
| close          | DECIMAL(15,2) | 종가                               |
| volume         | BIGINT        | 거래량                             |
| adjusted_close | DECIMAL(15,2) | 수정 종가                          |
| data_source    | VARCHAR(30)   | FDR, YFINANCE, KIS                 |
| created_at     | TIMESTAMP     | 수집일시                           |

### minute_prices (분봉 데이터)

| 컬럼          | 타입          | 설명                               |
| ------------- | ------------- | ---------------------------------- |
| id            | BIGSERIAL     | PK                                 |
| stock_id      | BIGINT        | FK → [stocks.id](http://stocks.id) |
| datetime      | TIMESTAMP     | 시간                               |
| interval_type | VARCHAR(10)   | 1m, 5m, 15m                        |
| open          | DECIMAL(15,2) | 시가                               |
| high          | DECIMAL(15,2) | 고가                               |
| low           | DECIMAL(15,2) | 저가                               |
| close         | DECIMAL(15,2) | 종가                               |
| volume        | BIGINT        | 거래량                             |
| data_source   | VARCHAR(30)   | 데이터 출처                        |
| created_at    | TIMESTAMP     | 수집일시                           |

**보관 정책**: 최근 7일만 보관 (스케줄러가 오래된 데이터 삭제)

### prediction_results (ML 예측 결과)

| 컬럼                | 타입          | 설명                               |
| ------------------- | ------------- | ---------------------------------- |
| id                  | BIGSERIAL     | PK                                 |
| stock_id            | BIGINT        | FK → [stocks.id](http://stocks.id) |
| prediction_date     | DATE          | 예측 대상일                        |
| model_name          | VARCHAR(50)   | xgboost, random_forest             |
| model_version       | VARCHAR(20)   | 2024-01-15                         |
| predicted_direction | VARCHAR(10)   | UP, DOWN                           |
| confidence          | DECIMAL(5,4)  | 신뢰도 (0~1)                       |
| predicted_return    | DECIMAL(10,6) | 예측 수익률                        |
| actual_direction    | VARCHAR(10)   | 실제 방향 (다음날 업데이트)        |
| actual_return       | DECIMAL(10,6) | 실제 수익률                        |
| is_correct          | BOOLEAN       | 예측 정확 여부                     |
| created_at          | TIMESTAMP     | 생성일시                           |

### ml_models (모델 메타데이터)

| 컬럼             | 타입         | 설명              |
| ---------------- | ------------ | ----------------- |
| id               | BIGSERIAL    | PK                |
| model_name       | VARCHAR(50)  | 모델명            |
| version          | VARCHAR(20)  | 버전              |
| market           | VARCHAR(20)  | 대상 시장         |
| train_start_date | DATE         | 학습 시작일       |
| train_end_date   | DATE         | 학습 종료일       |
| train_samples    | INT          | 학습 샘플 수      |
| accuracy         | DECIMAL(5,4) | 정확도            |
| precision_score  | DECIMAL(5,4) | 정밀도            |
| recall_score     | DECIMAL(5,4) | 재현율            |
| f1_score         | DECIMAL(5,4) | F1 점수           |
| model_path       | VARCHAR(255) | 모델 파일 경로    |
| is_active        | BOOLEAN      | 현재 사용 중 여부 |
| created_at       | TIMESTAMP    | 생성일시          |

### collection_logs (수집 로그)

| 컬럼              | 타입        | 설명                      |
| ----------------- | ----------- | ------------------------- |
| id                | BIGSERIAL   | PK                        |
| collection_type   | VARCHAR(30) | DAILY, MINUTE, STOCK_LIST |
| market            | VARCHAR(20) | 대상 시장                 |
| data_source       | VARCHAR(30) | 데이터 출처               |
| started_at        | TIMESTAMP   | 시작 시간                 |
| finished_at       | TIMESTAMP   | 종료 시간                 |
| status            | VARCHAR(20) | RUNNING, SUCCESS, FAILED  |
| records_collected | INT         | 수집된 레코드 수          |
| error_message     | TEXT        | 에러 메시지               |
| created_at        | TIMESTAMP   | 생성일시                  |

------

## 8. Redis 캐시 전략

### 키 설계

| 키 패턴                                | TTL    | 설명                     |
| -------------------------------------- | ------ | ------------------------ |
| `price:realtime:{market}:{symbol}`     | 10초   | 실시간 시세              |
| `price:daily:{market}:{symbol}:{date}` | 24시간 | 일봉 데이터              |
| `indicator:{market}:{symbol}:{date}`   | 24시간 | 기술적 지표              |
| `prediction:{market}:{symbol}:{date}`  | 24시간 | ML 예측 결과             |
| `token:kis:access`                     | 23시간 | 한국투자증권 액세스 토큰 |
| `stock:list:{market}`                  | 1시간  | 종목 목록                |

### 예시

```
# 실시간 시세
price:realtime:KR_KOSPI:005930
→ {"price": 71000, "change": 1.5, "volume": 1234567, "timestamp": "..."}

# 기술적 지표
indicator:KR_KOSPI:005930:2024-01-15
→ {"rsi_14": 65.3, "sma_20": 70500, "macd": 150.5, ...}

# ML 예측
prediction:KR_KOSPI:005930:2024-01-15
→ {"direction": "UP", "confidence": 0.73, "model": "xgboost_v20240115"}
```

------

## 9. 스케줄러 일정

### 한국 시장 (KST 기준)

| 시간        | 작업        | 설명                               |
| ----------- | ----------- | ---------------------------------- |
| 08:30       | 장 전 준비  | 전일 미국 데이터 확인, 캐시 워밍업 |
| 09:00~15:30 | 분봉 수집   | 5분마다 실행                       |
| 16:00       | 일봉 수집   | 장 마감 후 전 종목 일봉            |
| 16:30       | 데이터 정리 | 7일 이전 분봉 삭제                 |
| 17:00       | ML 학습     | 새 모델 학습 + 내일 예측           |
| 17:30       | 예측 검증   | 어제 예측 vs 오늘 실제 비교        |

### 미국 시장 (KST 기준)

| 시간        | 작업      | 설명                    |
| ----------- | --------- | ----------------------- |
| 23:30~06:00 | 분봉 수집 | 5분마다 실행 (장 중)    |
| 06:30       | 일봉 수집 | 장 마감 후 전 종목 일봉 |
| 07:00       | ML 학습   | 미국 모델 학습 + 예측   |
| 07:30       | 예측 검증 | 전일 예측 검증          |

------

## 10. API 명세

### Spring Boot Gateway API

### 종목 관련

| Method | Endpoint                       | 설명           |
| ------ | ------------------------------ | -------------- |
| GET    | `/api/stocks`                  | 종목 목록 조회 |
| GET    | `/api/stocks/{symbol}`         | 종목 상세 조회 |
| GET    | `/api/stocks/search?q={query}` | 종목 검색      |

### 시세 관련

| Method | Endpoint                        | 설명        |
| ------ | ------------------------------- | ----------- |
| GET    | `/api/prices/daily/{symbol}`    | 일봉 데이터 |
| GET    | `/api/prices/minute/{symbol}`   | 분봉 데이터 |
| GET    | `/api/prices/realtime/{symbol}` | 실시간 시세 |

### 분석 관련

| Method | Endpoint                            | 설명          |
| ------ | ----------------------------------- | ------------- |
| GET    | `/api/indicators/{symbol}`          | 기술적 지표   |
| GET    | `/api/predictions/{symbol}`         | ML 예측 결과  |
| GET    | `/api/predictions/{symbol}/history` | 예측 히스토리 |

### Flask 내부 API

| Method | Endpoint                        | 설명                        |
| ------ | ------------------------------- | --------------------------- |
| GET    | `/api/prices/realtime/{symbol}` | 실시간 시세 (외부 API 호출) |
| GET    | `/api/indicators/{symbol}`      | 기술적 지표 계산            |
| GET    | `/api/predictions/{symbol}`     | ML 추론                     |
| POST   | `/api/collect/daily`            | 일봉 수집 트리거            |
| POST   | `/api/train`                    | 학습 트리거                 |
| GET    | `/health`                       | 헬스 체크                   |