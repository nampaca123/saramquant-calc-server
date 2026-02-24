# SaramQuant Calc Server 설계서

## 1. 프로젝트 개요

### 목적

주식 데이터를 수집하고, 퀀트 기법과 머신러닝을 통해 분석하여 투자 인사이트를 제공하는 시스템

### 기술 스택

| 레이어 | 기술 | 역할 |
|--------|------|------|
| Frontend | Next.js | 대시보드 UI |
| Gateway | Spring Boot (Kotlin) | API Gateway, 캐싱 |
| Calc Server | Flask (Python) | 데이터 수집, 퀀트 분석, 리스크 뱃지 파이프라인 |
| US FS Collector | Nest.js (TypeScript) | US 재무제표 수집 마이크로서비스 (Railway US East) |
| Database | Supabase (PostgreSQL) | 데이터 저장 |
| Cache | Redis | API 응답 캐싱 |

### 마이크로서비스 구조

```
┌──────────────────┐   HTTP POST /collect   ┌─────────────────────────────────┐
│  Calc Server       │ ────────────────────▶  │  saramquant-usa-fstatements-    │
│  (한국 리전)     │   GET /status/:jobId   │  collector (US East, Railway)   │
│                  │ ◀──── polling ────────  │                                │
└────────┬─────────┘                        └────────────┬────────────────────┘
         │                                               │
         │           ┌──────────────┐                    │
         └──────────▶│  Supabase DB │◀───────────────────┘
                     │  (공유)       │
                     └──────────────┘
```

Calc Server가 US 재무제표 수집을 트리거하면, US East에 배포된 마이크로서비스가 SEC EDGAR에서 벌크 데이터를 다운로드·파싱·DB 적재까지 처리한다.
Calc Server는 jobId로 상태를 폴링하여 완료를 확인한다.

---

## 2. 데이터 소스

### 종목 목록 (KIS 종목정보파일)

KIS에서 제공하는 마스터 파일. 인증 불필요, 매일 자동 업데이트.

| 시장 | URL |
|------|-----|
| KOSPI | `https://new.real.download.dws.co.kr/common/master/kospi_code.mst.zip` |
| KOSDAQ | `https://new.real.download.dws.co.kr/common/master/kosdaq_code.mst.zip` |
| NYSE | `https://new.real.download.dws.co.kr/common/master/nysmst.cod.zip` |
| NASDAQ | `https://new.real.download.dws.co.kr/common/master/nasmst.cod.zip` |

### 일봉 OHLCV

| 시장 | 클라이언트 | 비고 |
|------|-----------|------|
| 한국 | pykrx (`PykrxClient`) | 날짜 단위로 시장 전 종목 OHLCV 일괄 조회, 거래량=0 행 제외 |
| 미국 | Alpaca (`AlpacaClient`) | NYSE+NASDAQ 통합 수집, 50종목 배치, IEX 데이터 피드 |

**공통:** 증분 수집 — DB에 저장된 마지막 날짜 다음 날부터 오늘까지만 수집한다. 최초 수집 시에는 과거 **400일** 치를 수집한다.

**KR 세부:** pykrx `get_market_ohlcv(date_str, market=KOSPI/KOSDAQ)`를 날짜별로 호출. 0.5초 스로틀 적용.

**US 세부:** NYSE+NASDAQ 활성 종목 전체를 하나의 `stock_map`으로 합쳐 Alpaca에 일괄 요청. 50종목씩 배치 분할 후 순차 호출. 200 calls/min 스로틀 적용.

### 벤치마크 지수

| 벤치마크 | 클라이언트 | 식별자 |
|----------|-----------|--------|
| KOSPI | pykrx | `1001` |
| KOSDAQ | pykrx | `2001` |
| S&P500 | yfinance | `^GSPC` |
| NASDAQ | yfinance | `^IXIC` |

### 무위험 이자율

#### 한국 - ECOS (한국은행 경제통계시스템)

| 만기 | 통계코드 | 항목코드 |
|------|----------|----------|
| 91D | 817Y002 | 010502000 |
| 3Y | 817Y002 | 010200000 |
| 10Y | 817Y002 | 010210000 |

- API URL: `https://ecos.bok.or.kr/api/StatisticSearch`
- 환경변수: `ECOS_API_KEY`

#### 미국 - FRED (Federal Reserve Economic Data)

| 만기 | Series ID |
|------|-----------|
| 91D | DTB3 |
| 1Y | DGS1 |
| 3Y | DGS3 |
| 10Y | DGS10 |

- API URL: `https://api.stlouisfed.org/fred/series/observations`
- 환경변수: `FRED_API_KEY`

### 섹터 분류

| 시장 | 1차 소스 | 2차 소스 (fallback) | 비고 |
|------|----------|-------------------|------|
| 한국 | pykrx (`PykrxClient`) | - | KRX 업종 인덱스 구성종목으로 매핑 |
| 미국 | NASDAQ Screener API | Finnhub API | 1차 후 NULL 잔여분에 한해 개별 profile 조회 |

**공통:** 섹터 수집은 증분 방식 — `sector IS NULL`인 종목만 대상으로 한다. 이미 섹터가 설정된 종목은 갱신하지 않는다.

**KR 세부:**
- pykrx `get_index_portfolio_deposit_file()`로 업종 인덱스별 구성종목을 순회하여 `{symbol: 업종명}` 맵 생성
- SKIP_INDICES에 등록된 인덱스(시장 전체·섹터 복합 등)는 제외
- 우선주(symbol 끝자리 5/7/9) → 보통주(끝자리 0) 심볼로 변환해 섹터 재매핑 시도

**US 세부:**
- NASDAQ Screener: `nasdaq`, `nyse` 두 거래소를 `ThreadPoolExecutor(max_workers=2)`로 병렬 요청
  - URL: `https://api.nasdaq.com/api/screener/stocks` (params: `tableonly=true, limit=25000, exchange={nasdaq|nyse}, download=true`)
- Finnhub: NASDAQ Screener 후에도 NULL인 종목만 대상으로 개별 `/stock/profile2` 호출
  - `finnhubIndustry` 필드를 sector로 사용
  - rate limit: 55 req/min (코드 설정 기준), 환경변수: `FINNHUB_API_KEY`

**`sector` 값 정책:** 유효 문자열 = 퀀트 대상, `'N/A'` = 비보통주(SPAC 등) 제외, `NULL` = 미분류 제외

### 재무제표

| 시장 | 수집 방식 | 비고 |
|------|----------|------|
| 한국 | DART API (`DartClient`) | `ThreadPoolExecutor(max_workers=10)` 병렬 배치 수집 |
| 미국 | 마이크로서비스 위임 | SEC EDGAR companyfacts.zip 벌크 다운로드, US East에서 처리 |

**KR 수집 세부:**
- DART `fetch_corp_codes()`로 symbol → dart_corp_code 매핑 (DB 미보유 시 자동 sync)
- `shares_outstanding`은 DART가 아닌 pykrx `get_market_cap_by_ticker()`에서 별도 취득
- CFS(연결재무제표) 우선, 미존재 시 OFS(개별재무제표) fallback
- 기본 수집 범위: 직전 2개 회계연도 × 4개 보고서 유형(FY, Q1, Q2, Q3)

**US 수집 세부:**
- 폴링 간격: 30초, 최대 대기: 30분(1800초)
- 폴링 응답에서 `phase`, `parsed/total` 진행 상황 로깅
- 환경변수: `USA_FS_COLLECTOR_URL`, `USA_FS_COLLECTOR_AUTH_KEY`

---

## 3. 파이프라인 아키텍처

KR과 US를 독립된 파이프라인으로 분리하여, 각 시장의 장 마감 시점에 맞춰 실행한다.

```
python -m app.pipeline kr         # KR 일일 (수집 + 지표 + 펀더멘털 + 리스크뱃지)
python -m app.pipeline us         # US 일일 (수집 + 지표 + 펀더멘털 + 리스크뱃지)
python -m app.pipeline kr-initial # KR 초기화 (수집 + 재무제표 + 전체 계산)
python -m app.pipeline us-initial # US 초기화 (수집 + 재무제표 + 전체 계산)
python -m app.pipeline kr-fs      # KR 재무제표 수집 + 펀더멘털 재계산
python -m app.pipeline us-fs      # US 재무제표 수집 + 펀더멘털 재계산 (마이크로서비스 트리거)
```

### 파이프라인 흐름

```
┌─────────────────────────────────────────────────────────────┐
│              KR 파이프라인 (18:00 KST, Mon-Fri)             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [Collect]                                                  │
│      ├──▶ KIS mst ZIP → stocks 갱신 (KOSPI, KOSDAQ)        │
│      │    (type_code=ST 보통주만, is_skippable 스팩 등 제외) │
│      ├──▶ pykrx 업종 인덱스 → sector=NULL 종목만 증분 갱신  │
│      │    (우선주 5/7/9 → 보통주 0 fallback 매핑 포함)      │
│      │    (실패해도 파이프라인 계속 진행)                   │
│      ├──▶ pykrx → daily_prices 증분 저장 (날짜별 전 종목)  │
│      │    (거래량=0 행 제외, 최초 수집 시 400일치)          │
│      ├──▶ pykrx → benchmark_daily_prices 증분 저장         │
│      ├──▶ ECOS API → risk_free_rates 증분 저장 (91D, 3Y, 10Y)│
│      └──▶ ECOS API → exchange_rates 증분 저장 (USDKRW)     │
│                                                             │
│  [Progressive Deactivate] (단일 트랜잭션)                   │
│      ├──▶ 재상장 종목 is_active=true 복원                  │
│      ├──▶ 가격 없는 종목 is_active=false                   │
│      ├──▶ 섹터 없는 종목 is_active=false                   │
│      └──▶ 재무제표 없는 종목 is_active=false               │
│           ※ 활성 종목 10% 미만 시 rollback 후 이후 전체 중단│
│                                                             │
│  [Load price_maps] DB에서 최대 300일 일봉 선로드 (공유)     │
│                                                             │
│  [Compute Fundamentals] ──── 실패 시 이후 전체 중단        │
│      ├──▶ TTM 재무제표 → PER, PBR, EPS, BPS, ROE 등 계산   │
│      └──▶ 재무제표 없는 종목은 NO_FS 행으로 삽입           │
│                                                             │
│  [Compute Factors] ★ 멀티팩터 리스크 모델                   │
│      │    (Fundamentals 실패 시 skip)                       │
│      ├──▶ 팩터 노출도 계산 + 시가총액 가중 Z-score 표준화  │
│      ├──▶ 시가총액 가중 WLS 횡단면 회귀 → 팩터 수익률 저장 │
│      └──▶ 누적 90일+ 시 EWM 팩터 공분산 행렬 갱신          │
│                                                             │
│  [Compute Indicators] (Factors 실패 시 skip)               │
│      ├──▶ 팩터 베타 (or OLS fallback) + 알파 + 샤프        │
│      └──▶ 이동평균, RSI, MACD 등 23개 지표                 │
│                                                             │
│  [Sector Aggregates] (Fundamentals 성공 시)                 │
│      └──▶ 섹터별 중위수 PER, PBR, ROE 등 → sector_aggregates│
│                                                             │
│  [Compute Risk Badges] (Fundamentals 성공 시)               │
│      └──▶ 5개 차원 점수 + 종합 tier → risk_badges          │
│                                                             │
│  [Integrity Check] 데이터 품질 보고 (읽기 전용)             │
│      └──▶ sector_null + sector_na > 20% 시 경고            │
│                                                             │
│  [Audit Log] 파이프라인 실행 결과 기록                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              US 파이프라인 (09:00 KST, Tue-Sat)             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [Collect]                                                  │
│      ├──▶ KIS cod ZIP → stocks 갱신 (NYSE, NASDAQ)         │
│      │    (type_code=2 보통주만, is_valid_us_symbol 필터)   │
│      ├──▶ NASDAQ Screener(nasdaq/nyse 병렬) → sector=NULL  │
│      │    종목만 증분 갱신, Finnhub fallback (여전히 NULL인  │
│      │    종목에 한해 개별 호출), (실패해도 계속 진행)       │
│      ├──▶ Alpaca IEX → daily_prices 증분 저장              │
│      │    (NYSE+NASDAQ 통합, 50종목 배치, 최초 수집 시 400일)│
│      ├──▶ yfinance → benchmark_daily_prices 증분 저장      │
│      └──▶ FRED API → risk_free_rates 증분 저장 (91D,1Y,3Y,10Y)│
│                                                             │
│  [Progressive Deactivate] (단일 트랜잭션)                   │
│      ├──▶ 재상장 종목 is_active=true 복원                  │
│      ├──▶ 가격 없는 종목 is_active=false                   │
│      ├──▶ 섹터 없는 종목 is_active=false                   │
│      └──▶ 재무제표 없는 종목 is_active=false               │
│           ※ 활성 종목 10% 미만 시 rollback 후 이후 전체 중단│
│                                                             │
│  [Load price_maps] DB에서 최대 300일 일봉 선로드 (공유)     │
│                                                             │
│  [Compute Fundamentals] ──── 실패 시 이후 전체 중단        │
│      ├──▶ TTM 재무제표 → PER, PBR, EPS, BPS, ROE 등 계산   │
│      └──▶ 재무제표 없는 종목은 NO_FS 행으로 삽입           │
│                                                             │
│  [Compute Factors] ★ 멀티팩터 리스크 모델                   │
│      │    (Fundamentals 실패 시 skip)                       │
│      ├──▶ 팩터 노출도 계산 + 시가총액 가중 Z-score 표준화  │
│      ├──▶ 시가총액 가중 WLS 횡단면 회귀 → 팩터 수익률 저장 │
│      └──▶ 누적 90일+ 시 EWM 팩터 공분산 행렬 갱신          │
│                                                             │
│  [Compute Indicators] (Factors 실패 시 skip)               │
│      ├──▶ 팩터 베타 (or OLS fallback) + 알파 + 샤프        │
│      └──▶ 이동평균, RSI, MACD 등 23개 지표                 │
│                                                             │
│  [Sector Aggregates] (Fundamentals 성공 시)                 │
│      └──▶ 섹터별 중위수 PER, PBR, ROE 등 → sector_aggregates│
│                                                             │
│  [Compute Risk Badges] (Fundamentals 성공 시)               │
│      └──▶ 5개 차원 점수 + 종합 tier → risk_badges          │
│                                                             │
│  [Integrity Check] 데이터 품질 보고 (읽기 전용)             │
│      └──▶ sector_null + sector_na > 20% 시 경고            │
│                                                             │
│  [Audit Log] 파이프라인 실행 결과 기록                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              재무제표 수집 (분기별 별도 실행)                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [KR] DART API 다중배치 수집 (ThreadPoolExecutor, 10 workers)│
│      ├──▶ DART corp_code 동기화 (없으면 자동 sync 먼저 실행)│
│      ├──▶ pykrx get_market_cap_by_ticker → shares_outstanding│
│      ├──▶ DART multi_financial_statement 병렬 fetch         │
│      │    CFS(연결재무제표) 우선, 없으면 OFS(개별) fallback │
│      └──▶ financial_statements 저장 → 펀더멘털 재계산       │
│                                                             │
│  [US] Calc Server → POST /collect → 마이크로서비스 트리거   │
│       마이크로서비스: EDGAR ZIP 다운로드 → 파싱 → DB 저장  │
│       Calc Server ← GET /status/:jobId 폴링               │
│       (30초 간격, 최대 30분 대기)                          │
│       완료 후 → 펀더멘털 재계산                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 지표 계산 목록

| 카테고리 | 지표 | 컬럼명 |
|----------|------|--------|
| 이동평균 | SMA(20), EMA(20), WMA(20) | sma_20, ema_20, wma_20 |
| 모멘텀 | RSI(14), MACD, Stochastic | rsi_14, macd/macd_signal/macd_hist, stoch_k/stoch_d |
| 변동성 | Bollinger Bands, ATR(14), ADX(14) | bb_upper/bb_middle/bb_lower, atr_14, adx_14/plus_di/minus_di |
| 거래량 | OBV, VMA(20) | obv, vma_20 |
| 추세 | Parabolic SAR | sar |
| 리스크 | Beta, Jensen's Alpha, Sharpe Ratio | beta, alpha, sharpe |

> Beta는 Barra 멀티팩터 베타를 우선 사용하며, 팩터 수익률 90일 미만 시 OLS 베타로 fallback한다. Alpha와 Sharpe는 선택된 Beta 값을 기반으로 계산된다.

### 펀더멘털 지표 목록

| 카테고리 | 지표 | 컬럼명 |
|----------|------|--------|
| 밸류에이션 | PER, PBR, EPS, BPS | per, pbr, eps, bps |
| 수익성 | ROE, 영업이익률 | roe, operating_margin |
| 안정성 | 부채비율 | debt_ratio |

### 멀티팩터 리스크 모델 (Barra 방식)

| 팩터 | 산출 방식 | 출처 |
|------|-----------|------|
| Market | 절편 (intercept = 1) | - |
| Size | log(종가 × 발행주식수) | daily_prices + stock_fundamentals |
| Value | 1 / PBR | stock_fundamentals |
| Momentum | 12개월 수익률 − 최근 1개월 수익률 | daily_prices |
| Volatility | EWM 표준편차 (half-life=42일) | daily_prices |
| Quality | (ROE Z-score + 영업이익률 Z-score) / 2 | stock_fundamentals |
| Leverage | 부채비율 | stock_fundamentals |
| Industry | 종목 sector 원-핫 인코딩 | stocks.sector |

- 스타일 팩터는 Winsorization 후 시가총액 가중 Z-score 표준화
- 횡단면 WLS 회귀 (시가총액 가중, 라그랑주 산업 제약)
- EWM 공분산 (half-life=90일, numpy 직접 구현)
- 팩터 수익률 90일 미만 시 OLS 베타 fallback
- 유효 종목 30개 미만 시 해당 시장 팩터 계산 전체 skip

---

## 4. 데이터베이스 스키마

### ERD

```
┌────────────────┐    ┌─────────────────┐
│   stocks       │    │  daily_prices   │
├────────────────┤    ├─────────────────┤
│ id (PK)        │─┐  │ id (PK)         │
│ symbol         │ │  │ stock_id (FK)   │
│ name           │ ├─▶│ date            │
│ market         │ │  │ open            │
│ is_active      │ │  │ high            │
│ dart_corp_code │ │  │ low             │
│ sector         │ │  │ close           │
│ created_at     │ │  │ volume          │
│ updated_at     │ │  │ created_at      │
└────────────────┘ │  └─────────────────┘
                   │
                   │  ┌─────────────────────┐
                   │  │  stock_indicators   │
                   │  ├─────────────────────┤
                   ├─▶│ stock_id (PK, FK)   │
                   │  │ date (PK)           │
                   │  │ sma_20 .. sharpe    │
                   │  │ created_at          │
                   │  └─────────────────────┘
                   │
                   │  ┌───────────────────────────┐
                   │  │   financial_statements    │
                   │  ├───────────────────────────┤
                   ├─▶│ id (PK)                   │
                   │  │ stock_id (FK)             │
                   │  │ fiscal_year               │
                   │  │ report_type               │
                   │  │ revenue .. shares_out      │
                   │  │ created_at                │
                   │  └───────────────────────────┘
                   │
                   │  ┌───────────────────────────┐
                   │  │   stock_fundamentals      │
                   │  ├───────────────────────────┤
                   ├─▶│ stock_id (PK, FK)         │
                   │  │ date (PK)                 │
                   │  │ per .. operating_margin    │
                   │  │ created_at                │
                   │  └───────────────────────────┘
                   │
                   │  ┌─────────────────────┐
                   │  │    predictions      │
                   │  ├─────────────────────┤
                   └─▶│ id (PK)             │
                      │ stock_id (FK)       │
                      │ date                │
                      │ direction           │
                      │ confidence          │
                      │ actual_direction    │
                      │ is_correct          │
                      │ created_at          │
                      └─────────────────────┘

                   │
                   │  ┌───────────────────────────┐
                   │  │   factor_exposures        │
                   │  ├───────────────────────────┤
                   ├─▶│ stock_id (PK, FK)         │
                   │  │ date (PK)                 │
                   │  │ size_z .. leverage_z       │
                   │  └───────────────────────────┘
                   │
                   │  ┌───────────────────────────┐
                   │  │   factor_returns          │
                   │  ├───────────────────────────┤
                   │  │ market (PK)               │
                   │  │ date (PK)                 │
                   │  │ market_ret .. industry_*   │
                   │  └───────────────────────────┘
                   │
                   │  ┌───────────────────────────┐
                   │  │   factor_covariance       │
                   │  ├───────────────────────────┤
                   │  │ market (PK)               │
                   │  │ date (PK)                 │
                   │  │ matrix (JSONB)            │
                   │  │ factor_names (TEXT[])      │
                   │  └───────────────────────────┘

┌───────────────────────────┐
│   sector_aggregates       │
├───────────────────────────┤
│ market (PK)               │
│ sector (PK)               │
│ date (PK)                 │
│ stock_count               │
│ median_per .. median_*    │
└───────────────────────────┘

┌───────────────────────────┐   ┌───────────────────────────┐
│     risk_badges           │   │  benchmark_daily_prices   │
├───────────────────────────┤   ├───────────────────────────┤
│ stock_id (PK, FK)         │   │ id (PK)                   │
│ market                    │   │ benchmark                 │
│ date                      │   │ date                      │
│ summary_tier              │   │ close                     │
│ dimensions (JSONB)        │   │ created_at                │
│ updated_at                │   └───────────────────────────┘
└───────────────────────────┘
                                ┌───────────────────────────┐
                                │    risk_free_rates        │
                                ├───────────────────────────┤
                                │ id (PK)                   │
                                │ country                   │
                                │ maturity                  │
                                │ date                      │
                                │ rate                      │
                                │ created_at                │
                                └───────────────────────────┘

                                ┌───────────────────────────┐
                                │    exchange_rates         │
                                ├───────────────────────────┤
                                │ id (PK)                   │
                                │ pair (e.g. KRW/USD)       │
                                │ date                      │
                                │ rate                      │
                                └───────────────────────────┘
```

### 테이블 상세

#### stocks

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | BIGSERIAL | PK |
| symbol | VARCHAR(20) | 종목 코드 |
| name | TEXT | 종목명 |
| market | market_type | KR_KOSPI, KR_KOSDAQ, US_NYSE, US_NASDAQ |
| is_active | BOOLEAN | 활성 여부 |
| dart_corp_code | VARCHAR(8) | DART 고유번호 (KR만 사용) |
| sector | VARCHAR(100) | 섹터 분류 (KR: pykrx 업종, US: NASDAQ Screener) |
| created_at | TIMESTAMPTZ | 생성일시 |
| updated_at | TIMESTAMPTZ | 수정일시 |

#### daily_prices

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | BIGSERIAL | PK |
| stock_id | BIGINT | FK → stocks.id |
| date | DATE | 거래일 |
| open | NUMERIC(15,2) | 시가 |
| high | NUMERIC(15,2) | 고가 |
| low | NUMERIC(15,2) | 저가 |
| close | NUMERIC(15,2) | 종가 |
| volume | BIGINT | 거래량 |
| created_at | TIMESTAMPTZ | 수집일시 |

#### stock_indicators

| 컬럼 | 타입 | 설명 |
|------|------|------|
| stock_id | BIGINT | PK (복합), FK → stocks.id |
| date | DATE | PK (복합), 기준 거래일 |
| sma_20 | NUMERIC(15,4) | SMA 20일 |
| ema_20 | NUMERIC(15,4) | EMA 20일 |
| wma_20 | NUMERIC(15,4) | WMA 20일 |
| rsi_14 | NUMERIC(8,4) | RSI 14일 |
| macd | NUMERIC(15,4) | MACD 라인 |
| macd_signal | NUMERIC(15,4) | MACD 시그널 |
| macd_hist | NUMERIC(15,4) | MACD 히스토그램 |
| stoch_k | NUMERIC(8,4) | 스토캐스틱 %K |
| stoch_d | NUMERIC(8,4) | 스토캐스틱 %D |
| bb_upper | NUMERIC(15,4) | 볼린저 상단 |
| bb_middle | NUMERIC(15,4) | 볼린저 중앙 |
| bb_lower | NUMERIC(15,4) | 볼린저 하단 |
| atr_14 | NUMERIC(15,4) | ATR 14일 |
| adx_14 | NUMERIC(8,4) | ADX 14일 |
| plus_di | NUMERIC(8,4) | +DI |
| minus_di | NUMERIC(8,4) | -DI |
| obv | BIGINT | OBV |
| vma_20 | BIGINT | 거래량 이동평균 20일 |
| sar | NUMERIC(15,4) | Parabolic SAR |
| beta | NUMERIC(8,4) | 베타 (vs 벤치마크) |
| alpha | NUMERIC(8,4) | 젠센의 알파 |
| sharpe | NUMERIC(8,4) | 샤프 비율 |
| created_at | TIMESTAMPTZ | 생성일시 |

#### financial_statements

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | BIGSERIAL | PK |
| stock_id | BIGINT | FK → stocks.id |
| fiscal_year | INT | 회계연도 |
| report_type | report_type | ANNUAL, Q1, Q2, Q3 |
| revenue | NUMERIC(20,2) | 매출액 |
| operating_income | NUMERIC(20,2) | 영업이익 |
| net_income | NUMERIC(20,2) | 순이익 |
| total_assets | NUMERIC(20,2) | 총자산 |
| total_liabilities | NUMERIC(20,2) | 총부채 |
| total_equity | NUMERIC(20,2) | 총자본 |
| shares_outstanding | BIGINT | 발행주식수 |
| created_at | TIMESTAMPTZ | 수집일시 |

#### stock_fundamentals

| 컬럼 | 타입 | 설명 |
|------|------|------|
| stock_id | BIGINT | PK (복합), FK → stocks.id |
| date | DATE | PK (복합), 기준일 |
| per | NUMERIC(12,4) | PER |
| pbr | NUMERIC(12,4) | PBR |
| eps | NUMERIC(15,4) | EPS |
| bps | NUMERIC(15,4) | BPS |
| roe | NUMERIC(10,4) | ROE |
| debt_ratio | NUMERIC(10,4) | 부채비율 |
| operating_margin | NUMERIC(10,4) | 영업이익률 |
| data_coverage | data_coverage_type | FULL, PARTIAL, LOSS, NO_FS, INSUFFICIENT |
| created_at | TIMESTAMPTZ | 생성일시 |

#### risk_badges

| 컬럼 | 타입 | 설명 |
|------|------|------|
| stock_id | BIGINT | PK, FK → stocks.id |
| market | market_type | KR_KOSPI, KR_KOSDAQ, US_NYSE, US_NASDAQ |
| date | DATE | 기준일 |
| summary_tier | VARCHAR(10) | 종합 리스크 등급 (LOW/MID/HIGH 등) |
| dimensions | JSONB | 5개 차원 점수 (price_heat, volatility, trend, company_health, valuation) |
| updated_at | TIMESTAMPTZ | 최종 갱신일시 |

#### benchmark_daily_prices

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | BIGSERIAL | PK |
| benchmark | benchmark_type | KR_KOSPI, KR_KOSDAQ, US_SP500, US_NASDAQ |
| date | DATE | 거래일 |
| close | NUMERIC(15,2) | 종가 |
| created_at | TIMESTAMPTZ | 생성일시 |

#### risk_free_rates

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | BIGSERIAL | PK |
| country | country_type | KR, US |
| maturity | maturity_type | 91D, 1Y, 3Y, 10Y |
| date | DATE | 기준일 |
| rate | NUMERIC(6,4) | 금리 (%) |
| created_at | TIMESTAMPTZ | 생성일시 |

#### exchange_rates

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | BIGSERIAL | PK |
| pair | VARCHAR(7) | 통화쌍 (e.g. KRW/USD) |
| date | DATE | 기준일 |
| rate | NUMERIC(12,4) | 환율 |

#### factor_exposures

| 컬럼 | 타입 | 설명 |
|------|------|------|
| stock_id | BIGINT | PK (복합), FK → stocks.id |
| date | DATE | PK (복합), 기준일 |
| size_z | NUMERIC(8,4) | Size 팩터 Z-score |
| value_z | NUMERIC(8,4) | Value 팩터 Z-score |
| momentum_z | NUMERIC(8,4) | Momentum 팩터 Z-score |
| volatility_z | NUMERIC(8,4) | Volatility 팩터 Z-score |
| quality_z | NUMERIC(8,4) | Quality 팩터 Z-score |
| leverage_z | NUMERIC(8,4) | Leverage 팩터 Z-score |

#### factor_returns

| 컬럼 | 타입 | 설명 |
|------|------|------|
| market | market_type | PK (복합), 시장 |
| date | DATE | PK (복합), 기준일 |
| factor_name | TEXT | PK (복합), 팩터명 |
| return_value | NUMERIC(10,6) | 팩터 수익률 |

#### factor_covariance

| 컬럼 | 타입 | 설명 |
|------|------|------|
| market | market_type | PK (복합), 시장 |
| date | DATE | PK (복합), 기준일 |
| matrix | JSONB | 팩터 공분산 행렬 (K×K) |
| factor_names | TEXT[] | 팩터명 순서 배열 |

#### sector_aggregates

| 컬럼 | 타입 | 설명 |
|------|------|------|
| market | market_type | PK (복합), 시장 |
| sector | VARCHAR(100) | PK (복합), 섹터명 |
| date | DATE | PK (복합), 기준일 |
| stock_count | INT | 해당 섹터 종목 수 |
| median_per | NUMERIC(12,4) | PER 중위수 |
| median_pbr | NUMERIC(12,4) | PBR 중위수 |
| median_roe | NUMERIC(10,4) | ROE 중위수 |
| median_operating_margin | NUMERIC(10,4) | 영업이익률 중위수 |
| median_debt_ratio | NUMERIC(10,4) | 부채비율 중위수 |

---

## 5. 스케줄러

### 파이프라인 스케줄

| 시간 (KST) | 명령어 | 요일 | 설명 |
|------------|--------|------|------|
| 18:00 | `python -m app.pipeline kr` | Mon-Fri | KR 수집 + 지표 + 펀더멘털 + 리스크뱃지 |
| 09:00 | `python -m app.pipeline us` | Tue-Sat | US 수집 + 지표 + 펀더멘털 + 리스크뱃지 |

### KR 파이프라인 (18:00 KST)

| 순서 | 단계 | 작업 | 설명 |
|------|------|------|------|
| 1 | Collect | 종목 목록 갱신 | KIS mst ZIP 파일 (KOSPI, KOSDAQ), 보통주(ST)만 취득 |
| 2 | Collect | KR 섹터 수집 | pykrx 업종 인덱스 매핑, sector=NULL 종목만 증분 갱신 (우선주 fallback 포함, 실패해도 진행) |
| 3 | Collect | KR 일봉 수집 | pykrx 날짜별 전 종목 일괄 조회, 증분 저장 (거래량=0 제외, 최초 400일) |
| 4 | Collect | KR 벤치마크 수집 | pykrx로 KOSPI/KOSDAQ 지수 |
| 5 | Collect | KR 무위험금리 수집 | ECOS API (91D, 3Y, 10Y) |
| 6 | Collect | 환율 수집 | ECOS API → exchange_rates (USDKRW) |
| 7 | Deactivate | Progressive 비활성화 | 재상장 복원 → 가격/섹터/재무제표 없는 종목 비활성화 (단일 트랜잭션, safety: 10% 미만 시 rollback 후 중단) |
| 8 | Load | price_maps 선로드 | 최대 300일 일봉을 DB에서 미리 로드 (이후 단계 공유) |
| 9 | Compute | KR 펀더멘털 계산 | TTM 기준 PER, PBR, ROE 등 → stock_fundamentals (실패 시 이후 전체 중단) |
| 10 | Compute | KR 팩터 모델 | 노출도 → WLS 회귀 → 공분산 → factor_* 테이블 (Fundamentals 실패 시 skip) |
| 11 | Compute | KR 지표 계산 | 팩터 베타 + 23개 지표 → stock_indicators (Factors 실패 시 skip) |
| 12 | Compute | KR 섹터 집계 | 섹터별 중위수 PER, PBR 등 → sector_aggregates (Fundamentals 성공 시) |
| 13 | Compute | KR 리스크뱃지 | 5개 차원 점수 + 종합 tier → risk_badges (Fundamentals 성공 시) |
| 14 | Check | 무결성 보고 | 데이터 품질 로그, sector 제외율 20% 초과 시 경고 |
| 15 | Log | Audit 기록 | 각 단계 성공/실패 및 소요시간 → audit_logs |

### US 파이프라인 (09:00 KST)

| 순서 | 단계 | 작업 | 설명 |
|------|------|------|------|
| 1 | Collect | 종목 목록 갱신 | KIS cod ZIP 파일 (NYSE, NASDAQ), type_code=2 보통주만 취득 |
| 2 | Collect | US 섹터 수집 | NASDAQ Screener(nasdaq/nyse 병렬) + Finnhub fallback, sector=NULL 종목만 증분 갱신 (실패해도 진행) |
| 3 | Collect | US 일봉 수집 | Alpaca IEX, NYSE+NASDAQ 통합 50종목 배치, 증분 저장 (최초 400일) |
| 4 | Collect | US 벤치마크 수집 | yfinance로 S&P500/NASDAQ 지수 |
| 5 | Collect | US 무위험금리 수집 | FRED API (91D, 1Y, 3Y, 10Y) |
| 6 | Deactivate | Progressive 비활성화 | 재상장 복원 → 가격/섹터/재무제표 없는 종목 비활성화 (단일 트랜잭션, safety: 10% 미만 시 rollback 후 중단) |
| 7 | Load | price_maps 선로드 | 최대 300일 일봉을 DB에서 미리 로드 (이후 단계 공유) |
| 8 | Compute | US 펀더멘털 계산 | TTM 기준 PER, PBR, ROE 등 → stock_fundamentals (실패 시 이후 전체 중단) |
| 9 | Compute | US 팩터 모델 | 노출도 → WLS 회귀 → 공분산 → factor_* 테이블 (Fundamentals 실패 시 skip) |
| 10 | Compute | US 지표 계산 | 팩터 베타 + 23개 지표 → stock_indicators (Factors 실패 시 skip) |
| 11 | Compute | US 섹터 집계 | 섹터별 중위수 PER, PBR 등 → sector_aggregates (Fundamentals 성공 시) |
| 12 | Compute | US 리스크뱃지 | 5개 차원 점수 + 종합 tier → risk_badges (Fundamentals 성공 시) |
| 13 | Check | 무결성 보고 | 데이터 품질 로그, sector 제외율 20% 초과 시 경고 |
| 14 | Log | Audit 기록 | 각 단계 성공/실패 및 소요시간 → audit_logs |

### 초기화 / 재무제표 수집 (별도 실행)

| 명령어 | 설명 |
|--------|------|
| `python -m app.pipeline kr-initial` | KR 초기화: 수집 + DART 재무제표 + 전체 계산 |
| `python -m app.pipeline us-initial` | US 초기화: 수집 + EDGAR 재무제표 + 전체 계산 |
| `python -m app.pipeline kr-fs` | KR 재무제표 수집 (DART API) + 펀더멘털 재계산 |
| `python -m app.pipeline us-fs` | US 재무제표 수집 (마이크로서비스 위임) + 펀더멘털 재계산 |

### 스케줄 시간 근거

- KR: 장 마감 15:30 KST → 데이터 확정 ~17:00 → 18:00 실행 → 다음 장 09:00까지 15시간 여유
- US: 장 마감 16:00 EST = 06:00 KST → 데이터 확정 ~08:00 KST → 09:00 실행 → 다음 장 23:30 KST까지 14.5시간 여유

### 재무제표 수집 스케줄 (분기)

공시 법정 기한 + 5~7일 여유를 두어 지각 제출 종목까지 커버한다.

| 날짜 (KST) | 명령어 | 대상 분기 | 근거 |
|-------------|--------|-----------|------|
| 4/7 03:00 | `kr-fs`, `us-fs` | Q4/연간 | KR 사업보고서 3/31 마감, US 10-K ~3/1 마감 |
| 5/22 03:00 | `kr-fs`, `us-fs` | Q1 | KR 분기보고서 5/15 마감, US 10-Q ~5/10 마감 |
| 8/21 03:00 | `kr-fs`, `us-fs` | Q2/반기 | KR 반기보고서 8/14 마감, US 10-Q ~8/9 마감 |
| 11/21 03:00 | `kr-fs`, `us-fs` | Q3 | KR 분기보고서 11/14 마감, US 10-Q ~11/9 마감 |

### 스케줄러 구현 (`app/scheduler.py`)

APScheduler `BackgroundScheduler`로 모든 스케줄을 Python 코드에 선언.

- 일일 파이프라인 2건: KR 18:00 Mon-Fri, US 09:00 Tue-Sat
- 분기 재무제표 8건: 4개 날짜 × KR/US, 각각 개별 job으로 등록 (cartesian product 방지)
- 파이프라인은 `PipelineOrchestrator` 메서드를 스레드 내에서 직접 호출 (subprocess 미사용)

### Railway 배포

단일 서비스로 운영. `gunicorn.conf.py`의 `on_starting` 훅에서 `init_scheduler()`를 호출하므로, gunicorn master 프로세스 기동 시 BackgroundScheduler가 함께 시작된다.

| 서비스 | Start Command | 포트 |
|--------|---------------|------|
| Web + Scheduler | `gunicorn -c gunicorn.conf.py "app:create_app()"` | 8080 |

---

## 6. API 명세

### Gateway API (Spring Boot, Kotlin)

**인증 / 사용자**
| Method | Path | 설명 |
|--------|------|------|
| GET | `/login/oauth2/code/{provider}` | OAuth 콜백 (Google, Kakao) |
| POST | `/api/auth/signup` | Manual 회원가입 (email + password) |
| POST | `/api/auth/login` | Manual 로그인 (email + password) |
| POST | `/api/auth/refresh` | Access Token 재발급 |
| POST | `/api/auth/logout` | 로그아웃 (현재 세션) |
| POST | `/api/auth/logout-all` | 전체 세션 로그아웃 |
| GET | `/api/users/me` | 내 프로필 |
| PATCH | `/api/users/me` | 프로필 수정 |

**대시보드 (Screener 통합)**
| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/dashboard/stocks?market=&tier=&sector=&sort=&page=&size=` | 종목 카드 목록 |
| GET | `/api/dashboard/sectors?market=` | 섹터 필터용 목록 |

**종목 상세**
| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/stocks/{symbol}?market=&lang=` | 종목 리포트 |
| GET | `/api/stocks/{symbol}/prices?market=&period=` | OHLCV 시계열 |
| GET | `/api/stocks/{symbol}/benchmark?market=&period=` | 벤치마크 비교 |
| GET | `/api/stocks/{symbol}/ai-analysis?market=&preset=&lang=` | 캐시된 AI 분석 |

**AI 전략 분석**
| Method | Path | 설명 |
|--------|------|------|
| POST | `/api/ai/stock-analysis` | LLM 종목 분석 트리거 |
| POST | `/api/ai/portfolio-analysis` | LLM 포트폴리오 진단 트리거 |
| GET | `/api/ai/usage` | AI 사용량 조회 |

**포트폴리오**
| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/portfolios` | 포트폴리오 목록 |
| GET | `/api/portfolios/{id}` | 포트폴리오 상세 |
| POST | `/api/portfolios/{id}/buy` | 매수 |
| POST | `/api/portfolios/{id}/sell/{holdingId}` | 매도 |

**시뮬레이션 / 포트폴리오 분석**
| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/stocks/{symbol}/simulation` | 종목 몬테카를로 시뮬레이션 |
| POST | `/api/portfolios/{id}/simulation` | 포트폴리오 몬테카를로 시뮬레이션 |
| POST | `/api/portfolios/{id}/risk-score` | 리스크 점수 |
| POST | `/api/portfolios/{id}/risk` | 리스크 분해 |
| POST | `/api/portfolios/{id}/diversification` | 분산 효과 |

### Calc Server Internal API (Flask, Python)

| Method | Path | 설명 |
|--------|------|------|
| POST | `/internal/portfolios/risk-score` | 가중평균 리스크 스코어 |
| POST | `/internal/portfolios/risk` | 공분산 리스크 분해 (MCAR) |
| POST | `/internal/portfolios/diversification` | HHI, Effective N, 분산효과 비율 |
| POST | `/internal/portfolios/price-lookup` | 날짜별 종가 + 환율 |
| POST | `/internal/portfolios/<portfolio_id>/simulation` | 포트폴리오 몬테카를로 시뮬레이션 |
| GET | `/internal/stocks/<symbol>/simulation` | 종목 몬테카를로 시뮬레이션 (GBM/Bootstrap) |

> 시뮬레이션 공통 쿼리 파라미터: `days`, `simulations`, `confidence`, `lookback`, `method`
> 종목 시뮬레이션 추가 파라미터: `market` (KR_KOSPI, KR_KOSDAQ, US_NYSE, US_NASDAQ)

데이터 수집과 지표/리스크뱃지 일괄 계산은 API가 아닌 CLI 파이프라인으로 처리:

```bash
python -m app.pipeline kr|us|kr-initial|us-initial|kr-fs|us-fs
```

### US Financial Statements Collector (Nest.js, 마이크로서비스)

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/usa-financial-statements/collect` | 수집 작업 트리거 → `{ jobId }` 반환 |
| GET | `/usa-financial-statements/status/:jobId` | 작업 상태 조회 |
| GET | `/usa-financial-statements/health` | 헬스 체크 |

---

## 7. Redis 캐시

| 키 패턴 | TTL | 설명 |
|---------|-----|------|
| `stock:list:{market}` | 1시간 | 종목 목록 |
| `price:daily:{symbol}:{date}` | 24시간 | 일봉 데이터 |
| `indicator:{symbol}:{date}` | 24시간 | 기술적 지표 |
| `prediction:{symbol}:{date}` | 24시간 | ML 예측 결과 |
