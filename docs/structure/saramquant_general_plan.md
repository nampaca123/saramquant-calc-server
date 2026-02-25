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

## 4. 스케줄러

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

## 5. 퀀트 계산 엔진 상세 (`app/quant/`)

### 디렉토리 구조

```
app/quant/
├── fundamentals/          # 펀더멘털 지표 (7개)
│   ├── valuation.py       #   EPS, BPS, PER, PBR
│   ├── profitability.py   #   ROE, 영업이익률
│   └── stability.py       #   부채비율
├── indicators/            # 기술적 지표 (22개 출력 컬럼)
│   ├── moving_average.py  #   SMA, EMA, WMA
│   ├── momentum.py        #   RSI, MACD, Stochastic
│   ├── volatility.py      #   Bollinger Bands, ATR
│   ├── trend.py           #   ADX(+DI/-DI), Parabolic SAR
│   ├── volume.py          #   OBV, VMA
│   └── risk.py            #   Alpha, Sharpe (Beta는 factor_model에서)
├── factor_model/          # 멀티팩터 리스크 모델 (Barra 방식)
│   ├── exposure.py        #   팩터 노출도 계산 (6 style + industry)
│   ├── normalize.py       #   Winsorize + Z-score 표준화
│   ├── regression.py      #   제약 WLS 횡단면 회귀
│   ├── covariance.py      #   EWM 팩터 공분산, 잔차 분산
│   └── beta.py            #   Factor Beta, OLS Beta, 리스크 분해
├── risk_badge/            # 리스크 뱃지 (5차원 + 종합)
│   ├── badge_types.py     #   Tier/Direction enum, DimensionResult
│   ├── badge_scoring.py   #   공통 유틸 (clamp, sector fallback)
│   ├── dimension_price_heat.py      # 차원 1: 가격 과열도
│   ├── dimension_volatility.py      # 차원 2: 변동성
│   ├── dimension_trend.py           # 차원 3: 추세 강도
│   ├── dimension_company_health.py  # 차원 4: 기업 건전성
│   ├── dimension_valuation.py       # 차원 5: 밸류에이션
│   └── composite_badge.py           # 종합 뱃지 판정
├── portfolio/             # 포트폴리오 분석 (온디맨드 API)
│   ├── hypothetical_returns.py      # 가상 수익률 구축
│   ├── portfolio_risk_score.py      # 포트폴리오 리스크 점수
│   ├── diversification.py           # 분산투자 지표 (HHI 등)
│   ├── risk_contribution.py         # MCAR 기여도
│   └── portfolio_metrics.py         # 팩터 기반 리스크 분해
└── simulation/            # 몬테카를로 시뮬레이션 (온디맨드 API)
    ├── path_generator.py            # 단일 종목 GBM / Bootstrap
    ├── portfolio_path_generator.py  # 포트폴리오 상관 GBM / Bootstrap
    └── monte_carlo.py               # VaR, CVaR, 백분위 통계
```

### 전체 지표 집계 (총 67개)

| 영역 | 지표 수 | 저장 위치 | 계산 시점 |
|------|---------|-----------|-----------|
| 펀더멘털 | 7 | `stock_fundamentals` | 파이프라인 (일일) |
| 기술적 지표 | 22 | `stock_indicators` | 파이프라인 (일일) |
| 팩터 모델 | 6 노출도 + 팩터 수익률 + 공분산 | `factor_exposures`, `factor_returns`, `factor_covariances` | 파이프라인 (일일) |
| 섹터 집계 | 6 | `sector_aggregates` | 파이프라인 (일일) |
| 리스크 뱃지 | 5 차원 점수 + 종합 tier | `risk_badges` | 파이프라인 (일일) |
| 포트폴리오 분석 | 15+ | API 응답 (미저장) | 온디맨드 |
| 시뮬레이션 | 5+ | API 응답 (미저장) | 온디맨드 |

---

### 5.1 펀더멘털 지표 (7개)

서비스: `FundamentalService` → 저장: `stock_fundamentals` 테이블

TTM(Trailing Twelve Months) 기준으로 손익계산서 항목을 합산한 뒤, 최신 종가와 대차대조표 데이터를 조합하여 산출한다.

| # | 카테고리 | 지표 | 컬럼명 | 산출 공식 | 소스 |
|---|---------|------|--------|-----------|------|
| 1 | 밸류에이션 | EPS | `eps` | 당기순이익(TTM) ÷ 발행주식수 | `valuation.py` |
| 2 | 밸류에이션 | BPS | `bps` | 자기자본 ÷ 발행주식수 | `valuation.py` |
| 3 | 밸류에이션 | PER | `per` | 종가 ÷ EPS | `valuation.py` |
| 4 | 밸류에이션 | PBR | `pbr` | 종가 ÷ BPS | `valuation.py` |
| 5 | 수익성 | ROE | `roe` | 당기순이익(TTM) ÷ 자기자본 | `profitability.py` |
| 6 | 수익성 | 영업이익률 | `operating_margin` | 영업이익(TTM) ÷ 매출액(TTM) | `profitability.py` |
| 7 | 안정성 | 부채비율 | `debt_ratio` | 총부채 ÷ 자기자본 | `stability.py` |

**TTM 계산 로직** (`FundamentalService._ttm_income`):
- 최신 보고서가 FY(사업보고서)이면 해당 연간 값 그대로 사용
- 분기보고서이면: FY값 + 올해 분기 누적 − 전년 동기 분기 누적 (= rolling 4분기)
- 대차대조표(자기자본, 총부채)는 최신 스냅샷을 그대로 사용

**이상치 처리**: PER ±1000, PBR 0~200, ROE ±10, 부채비율 0~100, 영업이익률 ±100 범위 외 → `None` 처리

---

### 5.2 기술적 지표 (22개 출력 컬럼)

서비스: `IndicatorService` → 저장: `stock_indicators` 테이블

최소 60일 가격 데이터를 요구하며, 모든 지표는 **최종 거래일의 값 1개**만 DB에 저장된다.

| # | 카테고리 | 지표 | 컬럼명 | 파라미터 | 산출 방식 | 소스 |
|---|---------|------|--------|----------|-----------|------|
| 1 | 이동평균 | SMA | `sma_20` | 기간=20 | 단순 산술평균 | `moving_average.py` |
| 2 | 이동평균 | EMA | `ema_20` | span=20 | 지수가중이동평균 (pandas ewm) | `moving_average.py` |
| 3 | 이동평균 | WMA | `wma_20` | 기간=20 | 선형가중이동평균 (numpy convolve) | `moving_average.py` |
| 4 | 모멘텀 | RSI | `rsi_14` | 기간=14 | EWM 기반 RS = avg_gain/avg_loss | `momentum.py` |
| 5 | 모멘텀 | MACD | `macd` | 12/26 | EMA(12) − EMA(26) | `momentum.py` |
| 6 | 모멘텀 | MACD Signal | `macd_signal` | signal=9 | MACD의 EMA(9) | `momentum.py` |
| 7 | 모멘텀 | MACD Histogram | `macd_hist` | - | MACD − Signal | `momentum.py` |
| 8 | 모멘텀 | Stochastic %K | `stoch_k` | K=14 | 100 × (종가−최저) / (최고−최저) | `momentum.py` |
| 9 | 모멘텀 | Stochastic %D | `stoch_d` | D=3 | %K의 SMA(3) | `momentum.py` |
| 10 | 변동성 | Bollinger Upper | `bb_upper` | 20일/2σ | SMA(20) + 2×표준편차 | `volatility.py` |
| 11 | 변동성 | Bollinger Middle | `bb_middle` | 20일 | SMA(20) | `volatility.py` |
| 12 | 변동성 | Bollinger Lower | `bb_lower` | 20일/2σ | SMA(20) − 2×표준편차 | `volatility.py` |
| 13 | 변동성 | ATR | `atr_14` | 기간=14 | EWM(True Range), TR=max(H−L, |H−PC|, |L−PC|) | `volatility.py` |
| 14 | 추세 | ADX | `adx_14` | 기간=14 | DX의 EWM 평활, DX = |+DI−-DI| / (+DI+-DI) × 100 | `trend.py` |
| 15 | 추세 | +DI | `plus_di` | 기간=14 | EWM(+DM) / ATR × 100 | `trend.py` |
| 16 | 추세 | −DI | `minus_di` | 기간=14 | EWM(−DM) / ATR × 100 | `trend.py` |
| 17 | 추세 | Parabolic SAR | `sar` | AF=0.02~0.2 | 추세 반전 추적 (가속 인자 기반) | `trend.py` |
| 18 | 거래량 | OBV | `obv` | - | Σ(방향 × 거래량), 방향=sign(종가 변화) | `volume.py` |
| 19 | 거래량 | VMA | `vma_20` | 기간=20 | 거래량 SMA(20) | `volume.py` |
| 20 | 리스크 | Beta | `beta` | - | Barra Factor Beta 우선, <90일 시 OLS Beta fallback | `factor_model/beta.py` |
| 21 | 리스크 | Jensen's Alpha | `alpha` | 연환산 | R_stock − (Rf + β × (R_market − Rf)), ×252 | `risk.py` |
| 22 | 리스크 | Sharpe Ratio | `sharpe` | 연환산 | (mean_return − Rf) / σ × √252 | `risk.py` |

> Beta는 `FactorModelService.get_betas()`를 통해 Barra 팩터 베타를 먼저 조회하고, 팩터 수익률 누적 90일 미만이면 `ols_beta(Cov/Var)`로 fallback한다.

---

### 5.3 멀티팩터 리스크 모델 — Barra 방식 (6 스타일 팩터 + 산업 팩터)

서비스: `FactorModelService` → 저장: `factor_exposures`, `factor_returns`, `factor_covariances` 테이블

유효 종목 30개 미만 시 해당 시장 전체 skip.

#### 5.3.1 팩터 노출도 (`exposure.py`)

| # | 스타일 팩터 | 원시 값 산출 | 입력 데이터 |
|---|-----------|-------------|-------------|
| 1 | Size | log(종가 × 발행주식수) | `daily_prices` + `stock_fundamentals` |
| 2 | Value | 1 / PBR | `stock_fundamentals` |
| 3 | Momentum | 12개월 수익률 − 1개월 수익률 | `daily_prices` (252일, 21일) |
| 4 | Volatility | EWM 표준편차 (half-life=42일) | `daily_prices` |
| 5 | Quality | (ROE Z-score + 영업이익률 Z-score) / 2 | `stock_fundamentals` |
| 6 | Leverage | 부채비율 | `stock_fundamentals` |
| - | Industry | 종목 sector 원-핫 인코딩 (N개 열) | `stocks.sector` |

**표준화 파이프라인** (`normalize.py`):
1. MAD-based Winsorization: median ± 3×MAD (MAD × 1.4826 = σ 추정)
2. 시가총액 가중 Z-score: weighted mean/std로 표준화 (가중치 = √시가총액)

#### 5.3.2 횡단면 회귀 (`regression.py`)

Constrained WLS (Weighted Least Squares) — KKT 시스템:

```
[X'WX  C] [f]   [X'Wy]
[C'    0] [λ] = [  0  ]
```

- **y**: 초과수익률 (당일 수익률 − 무위험금리/252)
- **X**: 설계행렬 [market(1) | styles(6) | industries(N)]
- **W**: 시가총액 가중치 (√mcap)
- **C**: 산업 팩터에 대한 라그랑주 제약 (시가총액 가중 합 = 0)
- 결과: 팩터 수익률 벡터 `f`, 잔차(specific returns) = y − Xf

#### 5.3.3 팩터 공분산 (`covariance.py`)

- **팩터 공분산 행렬**: EWM 공분산, half-life=90일 (numpy 직접 구현)
- **잔차 분산**: EWM per-stock specific variance, half-life=42일
- 팩터 수익률 누적 90일 이상부터 갱신 시작

#### 5.3.4 베타 & 리스크 분해 (`beta.py`)

| 메트릭 | 공식 | 용도 |
|--------|------|------|
| Factor Beta | β_i = (X_i' Σ_F X_m) / (X_m' Σ_F X_m) | 주 Beta (≥90일 팩터 이력) |
| OLS Beta | β = Cov(R_i, R_m) / Var(R_m) | Fallback (<90일) |
| Risk Decomposition | Total Var = X_i' Σ_F X_i + σ²_specific | 팩터/잔차 리스크 비중 |

---

### 5.4 리스크 뱃지 (5차원 점수 + 종합 Tier)

서비스: `RiskBadgeService` → 저장: `risk_badges` 테이블

모든 차원은 **0~100 점수** → **STABLE(<40) / CAUTION(40~70) / WARNING(>70)** 3단계 tier로 변환된다.

#### 5.4.1 차원별 상세

| # | 차원 | 입력 지표 | 가중치 | 비교 기준 | 소스 |
|---|------|----------|--------|-----------|------|
| 1 | Price Heat (가격 과열) | RSI, Bollinger %B | RSI 60% + %B 40% | 절대 기준 | `dimension_price_heat.py` |
| 2 | Volatility (변동성) | Beta, volatility_z | Beta 50% + vol_z 50% | 절대 기준 | `dimension_volatility.py` |
| 3 | Trend (추세 강도) | ADX, +DI, −DI | ADX × 방향가중 | 하락=1.0, 상승=0.6 | `dimension_trend.py` |
| 4 | Company Health (기업 건전성) | 부채비율, ROE, 영업이익률 | 부채 40% + ROE 30% + OPM 30% | 섹터 중위수 대비 | `dimension_company_health.py` |
| 5 | Valuation (밸류에이션) | PER, PBR | PER 50% + PBR 50% | 섹터 중위수 대비 | `dimension_valuation.py` |

**Direction 라벨** (차원 1, 2, 3에 부여):
- `OVERHEATED` / `OVERSOLD` (RSI ≥70 / ≤30)
- `UPTREND` / `DOWNTREND` (+DI vs −DI)
- `NEUTRAL`

#### 5.4.2 종합 뱃지 판정 (`composite_badge.py`)

차원을 **Critical** (company_health, valuation)과 **Signal** (price_heat, volatility, trend)로 구분:

| 우선순위 | 조건 | 종합 Tier |
|---------|------|-----------|
| 1 | Critical 차원 중 WARNING 존재 | **WARNING** |
| 2 | Signal WARNING ≥ 2개 | **WARNING** |
| 3 | Signal WARNING 1개 + 다른 차원 CAUTION 이상 | **WARNING** |
| 4 | Signal WARNING 1개 단독 (상승 추세 단독 제외) | **CAUTION** (완화) |
| 5 | Trend WARNING이 UPTREND인 경우 단독 | **CAUTION** (강한 상승추세는 경고 불필요) |
| 6 | 그 외 | 유효 차원 중 최악 tier |

#### 5.4.3 섹터 비교 기준

- 섹터 집계 데이터 우선 사용, 해당 섹터 종목 수 < 5개이면 시장 전체 중위수로 fallback
- `SectorAggregateService` → 저장: `sector_aggregates`

| # | 집계 컬럼 | 산출 | 소스 테이블 |
|---|----------|------|------------|
| 1 | `median_per` | 섹터별 PER 중위수 | `stock_fundamentals` |
| 2 | `median_pbr` | 섹터별 PBR 중위수 | `stock_fundamentals` |
| 3 | `median_roe` | 섹터별 ROE 중위수 | `stock_fundamentals` |
| 4 | `median_operating_margin` | 섹터별 영업이익률 중위수 | `stock_fundamentals` |
| 5 | `median_debt_ratio` | 섹터별 부채비율 중위수 | `stock_fundamentals` |
| 6 | `stock_count` | 섹터별 종목 수 | `stocks` |

---

### 5.5 포트폴리오 분석 (온디맨드 API)

서비스: `PortfolioAnalysisService` → 저장 안 함 (API 응답으로 직접 반환)

사용자 포트폴리오의 보유 종목 + 비중을 기반으로 아래 5가지 분석을 일괄 수행한다.

#### 5.5.1 포트폴리오 리스크 점수 (`portfolio_risk_score.py`)

| 메트릭 | 산출 | 비고 |
|--------|------|------|
| Portfolio Vol | σ_port × √252 (연환산) | 일별 수익률의 std |
| Benchmark Vol | σ_bench × √252 | KOSPI(KR) 또는 S&P500(US) |
| Risk Score | (Portfolio Vol / Benchmark Vol) × 50, max=100 | 벤치마크 대비 상대 변동성 |
| Tier | STABLE(≤40) / CAUTION(40~70) / WARNING(>70) | 리스크 뱃지와 동일 기준 |

최소 20 거래일 데이터 필요, 미달 시 `UNKNOWN`.

#### 5.5.2 분산투자 지표 (`diversification.py`)

| # | 지표 | 산출 | 의미 |
|---|------|------|------|
| 1 | HHI | Σ(w_i²) | 집중도 (0~1, 낮을수록 분산) |
| 2 | Effective N | 1 / HHI | 실효 종목 수 |
| 3 | Max Weight | max(w_i) | 최대 단일 비중 |
| 4 | Diversification Ratio | Σ(w_i × σ_i) / σ_port | >1이면 분산 효과 존재 |
| 5 | Sector Concentration | 섹터별 비중 합산 | 섹터 쏠림 파악 |
| 6 | Sector HHI | Σ(sector_weight²) | 섹터 집중도 |

#### 5.5.3 리스크 기여도 — MCAR (`risk_contribution.py`)

| 메트릭 | 산출 |
|--------|------|
| Portfolio Vol | √(w' Σ w) |
| Marginal Contribution (MCAR) | Σw / σ_port (공분산 행렬 × 비중 / 포트폴리오 변동성) |
| Contribution | w_i × MCAR_i |
| Contribution % | Contribution_i / Σ(Contribution) |

#### 5.5.4 팩터 리스크 분해 (`portfolio_metrics.py`)

DB에 저장된 팩터 모델 데이터를 활용하여 포트폴리오 수준의 리스크를 분해한다.

| 출력 | 설명 |
|------|------|
| Portfolio Beta | 가중 팩터 베타 |
| Factor / Specific Var | X_p' Σ_F X_p + Σ(w² σ²_specific) |
| Factor % | 팩터 리스크 비중 |
| Portfolio Exposure | 팩터별 가중 노출도 |

#### 5.5.5 벤치마크 비교

| 출력 | 설명 |
|------|------|
| Portfolio Return | 가중 누적 수익률 (%) |
| Benchmark Return | KOSPI 또는 S&P500 누적 수익률 (%) |
| Excess Return | Portfolio − Benchmark (%) |
| Benchmark Chart | 일별 누적 수익률 시계열 (portfolio vs benchmark) |

---

### 5.6 몬테카를로 시뮬레이션 (온디맨드 API)

서비스: `SimulationService` (단일 종목), `PortfolioSimulationService` (포트폴리오) → 저장 안 함

#### 5.6.1 경로 생성 방식

| # | 방식 | 적용 대상 | 알고리즘 | 소스 |
|---|------|-----------|----------|------|
| 1 | GBM | 단일 종목 | 기하 브라운 운동, antithetic variates | `path_generator.py` |
| 2 | Bootstrap | 단일 종목 | 과거 수익률 복원추출 | `path_generator.py` |
| 3 | Correlated GBM | 포트폴리오 | 종목 간 상관관계 반영 (Cholesky 분해) | `portfolio_path_generator.py` |
| 4 | Portfolio Bootstrap | 포트폴리오 | 다종목 동시 복원추출 (교차상관 보존) | `portfolio_path_generator.py` |

**GBM 공식**: dS = S(μdt + σdW), μ/σ는 과거 로그수익률에서 추정
**Antithetic Variates**: Z와 −Z를 짝으로 생성하여 분산 감소
**Nearest PD 보정**: 상관행렬이 양정치가 아닌 경우 고유값 보정 후 Cholesky 분해

#### 5.6.2 시뮬레이션 통계 (`monte_carlo.py`)

| # | 메트릭 | 산출 |
|---|--------|------|
| 1 | Expected Return | (평균 최종가 − 초기가) / 초기가 |
| 2 | VaR (Value at Risk) | 수익률 분포의 (1−confidence) 백분위 (기본 95%) |
| 3 | CVaR (Conditional VaR) | VaR 이하 수익률의 평균 (= Expected Shortfall) |
| 4 | Price Percentiles | 최종 가격의 10/25/50/75/90 백분위 |
| 5 | Path Percentiles | 전 시뮬레이션 기간의 일별 10/25/50/75/90 백분위 시계열 |

기본 설정: 10,000 시뮬레이션, 60일 예측, 95% 신뢰구간, 252일 lookback.

---

### 5.7 지표 데이터 흐름 요약

```
┌──────────────────────────────────────────────────────────────────────┐
│                    파이프라인 계산 (일일 저장)                        │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  재무제표(TTM)──▶ [Fundamentals] ──▶ stock_fundamentals (7개 지표)   │
│       │                │                                             │
│       │                ├──▶ [Sector Aggregates] ──▶ sector_aggregates│
│       │                │         (6개 중위수)                        │
│       │                ▼                                             │
│  가격 데이터 ──▶ [Factor Model] ──▶ factor_exposures  (6 스타일)     │
│       │              │         ──▶ factor_returns    (K 팩터)        │
│       │              │         ──▶ factor_covariances (K×K 행렬)     │
│       │              │                                               │
│       │              ├── factor_beta ──┐                             │
│       │              │                 ▼                             │
│       └──────────▶ [Indicators] ──▶ stock_indicators (22개 지표)     │
│                                                                      │
│  위 결과 전부 ──▶ [Risk Badge] ──▶ risk_badges                      │
│                     (5차원 점수 + 종합 tier)                         │
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│                   온디맨드 API 계산 (미저장)                         │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  포트폴리오 보유 ──▶ [Portfolio Analysis]                            │
│       │                ├── Risk Score (벤치마크 대비 변동성)          │
│       │                ├── Diversification (HHI, Effective N 등)     │
│       │                ├── MCAR (종목별 리스크 기여도)               │
│       │                ├── Factor Risk (팩터 리스크 분해)            │
│       │                └── Benchmark Comparison (수익률 비교)        │
│       │                                                              │
│       └──────────▶ [Simulation]                                      │
│                        ├── GBM / Bootstrap 경로 생성                 │
│                        └── VaR, CVaR, 백분위 통계                    │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

