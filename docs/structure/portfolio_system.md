# 포트폴리오 관리 시스템 — 설계 근거 및 전략 해설

## 1. 왜 시장별 분리인가?

### 문제
KOSPI/KOSDAQ(한국)과 NYSE/NASDAQ(미국) 주식을 하나의 포트폴리오에 넣고 **Barra 팩터 모델**로 분석하면, 팩터 공분산 행렬의 차원이 서로 다릅니다. 예를 들어 KOSPI에는 "음식료품" 산업 팩터가 있지만 NYSE에는 없고, 대신 "Technology Hardware"가 있습니다. z-score 표준화도 시장별로 독립적이어서, KOSPI에서의 size z-score = 0.5와 NYSE에서의 0.5는 전혀 다른 의미입니다.

### 해결
사용자당 최대 2개 포트폴리오: **KR 포트폴리오** (KOSPI + KOSDAQ 종목만), **US 포트폴리오** (NYSE + NASDAQ 종목만). 이렇게 하면 각 포트폴리오 내에서는 동일한 팩터 모델을 안전하게 적용할 수 있습니다.

### 통합 대시보드
KR + US를 합산하여 보려면 **수익률 기반 분석**(return-based risk)을 사용합니다. 팩터 모델이 아니라 과거 수익률의 변동성/상관관계를 직접 계산하므로, 이종 시장 간에도 안전합니다. 이때 **USD/KRW 환율 변환**이 필요합니다.

---

## 2. 리스크 스코어: 두 가지 경로

### Path B (기본 경로): 수익률 기반
**Morningstar Portfolio Risk Score (MPRS)**에서 영감을 받은 방식입니다.

1. **가상 과거 수익률 구성**: "현재 비중으로 과거 252일 보유했다면?" → 개별 종목 일별 수익률에 비중을 곱해 합산
2. 포트폴리오 연간화 변동성 계산: `σ_p = std(daily_returns) × √252`
3. 벤치마크 연간화 변동성: KR → KOSPI, US → S&P500
4. **Risk Score = (σ_p / σ_benchmark) × 50**
   - 50 = 벤치마크 수준
   - 0~40: STABLE (보수적)
   - 40~70: CAUTION (중립)
   - 70~100: WARNING (공격적)

**왜 이 방식인가?** Morningstar는 실제로 포트폴리오 변동성을 벤치마크 대비 비율로 환산하여 10단계 점수를 매깁니다. 우리는 이를 3단계(STABLE/CAUTION/WARNING)로 단순화하여 비전문가도 직관적으로 이해할 수 있게 했습니다.

### Path A (Enhancement): 팩터 기반
포트폴리오 내 모든 종목이 동일한 sub-market(예: KOSPI만, NASDAQ만)에 속할 때 적용 가능합니다.

- `σ_p = √(X_p' × Σ_F × X_p + Σ(w_i² × σ²_specific_i))`
- X_p: 포트폴리오 팩터 노출 벡터 (개별 종목 벡터의 가중합)
- Σ_F: 팩터 공분산 행렬

**장점**: 어떤 팩터(size, value, momentum 등)가 변동성에 기여하는지 분해 가능. Path B의 결과와 교차 검증 가능.

---

## 3. Barra 팩터 모델의 포트폴리오 적용

### 기본 수식
포트폴리오의 팩터 노출은 개별 종목 노출의 가중합입니다:

**X_p = Σ(w_i × X_i)**

여기서 w_i는 종목 i의 투자 비중, X_i는 종목 i의 팩터 노출 벡터입니다.

### 포트폴리오 베타
Barra 팩터 베타 공식:

**β_p = (X_p' × Σ_F × X_m) / (X_m' × Σ_F × X_m)**

X_m은 시장 포트폴리오의 팩터 노출 벡터입니다 (market 팩터 = 1, 나머지 = 0).

### 달러 베타 (Dollar Beta)
Paleologo (Advanced Portfolio Management, 10장)의 개념:

**Dollar Beta = β_p × 포트폴리오 총 가치**

포트폴리오가 시장 1% 움직임에 대해 얼마만큼 달러(원) 가치가 변하는지를 나타냅니다.

### 리스크 분해
- **Factor Variance**: X_p' × Σ_F × X_p (시장/스타일/산업 팩터에 의한 리스크)
- **Specific Variance**: Σ(w_i² × σ²_specific_i) (종목 고유 리스크)
- **Total Variance**: Factor + Specific
- **Factor %**: Factor / Total (팩터가 총 리스크에서 차지하는 비중)

---

## 4. MCAR — "어떤 종목이 리스크를 가장 많이 차지하는가?"

**Marginal Contribution to Active Risk (MCAR)**:

- **MCAR_i = (Σ × w)_i / σ_p** (공분산 행렬 × 비중 벡터의 i번째 원소 ÷ 포트폴리오 변동성)
- **Risk Contribution_i = w_i × MCAR_i** (종목 i가 총 리스크에 기여하는 양)
- **Contribution % = RC_i / Σ RC** (비중)

이 정보는 "A 종목이 전체 리스크의 45%를 차지하고 있습니다" 같은 인사이트를 제공합니다.

---

## 5. 분산 분석 (Diversification Metrics)

### HHI (Herfindahl-Hirschman Index)
**HHI = Σ(w_i²)**
- 0에 가까울수록 분산됨
- 종목 5개에 균등 투자 → HHI = 0.2

### Effective N
**N_eff = 1 / HHI**
- 균등 투자 시 종목 수와 같음
- 한 종목 편중 시 → N_eff ≈ 1

### Diversification Ratio
**DR = Σ(w_i × σ_i) / σ_p**
- 항상 ≥ 1 (포트폴리오 효과)
- 높을수록 분산 효과가 크다는 뜻

### 섹터 집중도
각 섹터별 비중의 합계와 섹터 HHI를 계산하여 특정 업종 편중 여부를 판단합니다.

---

## 6. 포트폴리오 몬테카를로 시뮬레이션

### Bootstrap (기본값)
날짜 단위로 전체 종목의 수익률을 통째로 리샘플링합니다.

**왜 Bootstrap이 기본인가?**
- 정규분포 가정 불필요
- 종목 간 상관관계를 날짜 단위 리샘플링으로 **자동 보존**
- KOSPI + KOSDAQ 혼합 포트폴리오에서도 안전하게 작동

### GBM (Cholesky)
기하 브라운 운동 모델에 Cholesky 분해를 적용하여 상관된 난수를 생성합니다.

**절차**:
1. 각 종목의 μ(drift), σ(volatility) 추정
2. 수익률의 상관행렬 계산
3. Cholesky 분해: L × L' = Correlation Matrix
4. 독립 정규 난수 z에 L'를 곱해 상관된 난수 생성
5. 각 종목별 GBM 경로 → 비중 가중합산 → 포트폴리오 가치 경로

상관행렬이 positive definite가 아니면 **nearest positive definite** 보정을 적용합니다.

### 공통 거래일 정렬
다종목 수익률 행렬 구성 시 모든 종목이 데이터를 가진 **공통 거래일**만 사용합니다.
- effective_lookback을 응답에 포함하여 실제 산출 기간을 투명하게 표시
- effective_lookback < MIN_DATA_POINTS(60) → 시뮬레이션 불가

---

## 7. 구매 가격 자동 조회

사용자는 **종목, 날짜, 수량**만 입력합니다. 매입 가격은 시스템이 자동 조회합니다.

### 조회 체인
1. **daily_prices DB** (최근 400일 이내라면 여기에 있음)
2. **PyKRX** (KR) 또는 **Alpaca** (US) — 외부 API on-demand 조회
3. **yfinance** — 위 두 방법 실패 시 폴백
4. **모두 실패** → 사용자에게 수동 입력 요청 (price_source = 'MANUAL')

비거래일인 경우 직전 거래일(최대 5일 전)의 종가를 자동 탐색합니다.

---

## 8. 매입 환율 기록 (Purchase Exchange Rate)

US 포트폴리오 종목의 KRW 기반 손익(PnL)을 정확히 계산하려면, **매수 시점의 환율**이 필요합니다. "3년 전에 VLO를 샀는데 그때 환율이 1,200원이었고 지금 1,400원이면?" — 주가 변동과 환율 변동을 분리하여 보여주려면 매입 환율이 반드시 기록되어야 합니다.

### 설계 원칙: On-demand + Cache

환율 전체를 백필하면 낭비입니다. 사용자가 매수를 등록할 때, **그 날짜의 환율 1건만** 조회하면 됩니다.

### 조회 체인 (historical_price_lookup.py 내장)
1. **exchange_rates DB** — 이미 캐시된 환율이 있으면 즉시 반환
2. **ECOS API** — DB에 없으면 해당 날짜 ± 7일 구간만 조회하여 가장 가까운 환율 획득
3. 조회된 환율을 **DB에 캐시** (다음번엔 DB 히트)
4. ECOS도 실패하면 `fx_rate: null` → Gateway에서 별도 처리

### DB 스키마
`portfolio_holdings` 테이블에 `purchase_fx_rate NUMERIC(12,4)` 컬럼 추가:
- KR 종목: NULL (환율 불필요)
- US 종목: 매수 시점의 USDKRW 환율 기록

### 추가매수 시 가중평균 환율
주가의 `avg_price` 가중평균과 동일한 방식으로 환율도 가중평균합니다:

**new_fx = (old_shares × old_fx + new_shares × new_fx) / total_shares**

### KRW 손익 산출
- 매입 원화 비용: `shares × avg_price × purchase_fx_rate`
- 현재 원화 가치: `shares × current_price × current_fx_rate`
- PnL (KRW): `현재 가치 - 매입 비용`

이 구조로 주가 수익과 환차익을 분리 표시할 수 있습니다:
- 주가 수익 (USD): `shares × (current_price - avg_price)`
- 환차익 (KRW): `shares × avg_price × (current_fx - purchase_fx)`

### 자원 효율성
- ECOS API 호출은 **매수 등록 시 1회**만 발생
- 같은 날짜에 여러 종목을 매수해도, 첫 번째 조회 후 DB에 캐시되어 이후는 DB 히트
- 일별 환율 수집 파이프라인(`ExchangeRateCollector`)은 최근 날짜만 수집하므로 별도 부담 없음

---

## 9. Graceful Degradation

모든 분석 모듈은 3단계 데이터 가용성을 표시합니다:
- **FULL**: 모든 종목의 데이터가 충분
- **PARTIAL**: 일부 종목 데이터 누락 — 해당 종목 제외 후 부분 분석
- **INSUFFICIENT**: 핵심 데이터 부족 — 분석 불가 메시지 표시

팩터 공분산 행렬이 아직 충분히 축적되지 않은 시장의 포트폴리오는 **Path B (수익률 기반)**만 제공하고, "팩터 분석은 충분한 데이터 축적 후 제공됩니다"라고 안내합니다.

---

## 10. 아키텍처 요약

```
Frontend → Gateway (Spring Boot / Kotlin)
              ├── feature/portfolio/ (CRUD, lazy creation, 소유권 검증)
              ├── feature/simulation/ (종목 + 포트폴리오 시뮬레이션)
              └── infra/connection/ (CalcServerClient)
                    ↓
              Calc Server (Python / Flask)
              ├── api/portfolio/ (price-lookup, simulation, analysis endpoints)
              ├── quant/portfolio/ (risk_score, metrics, diversification, mcar)
              ├── quant/simulation/ (bootstrap, GBM, portfolio path generators)
              └── services/ (orchestration, historical price lookup)
                    ↓
              PostgreSQL (user_portfolios, portfolio_holdings, exchange_rates,
                         factor_exposures, factor_covariance, daily_prices, ...)
```

---

## 11. 참고 문헌 & 업계 기준

- **Paleologo, G.** (2021). *Advanced Portfolio Management*. Wiley.
  - 비례 배분 규칙, 리스크 패리티, 평균-분산, 수축된 평균-분산
  - Dollar Beta, Percentage Beta (10장)
  - Barra 팩터 모델 포트폴리오 적용 (8-9장)
- **Barra Risk Model Handbook**: 멀티팩터 리스크 모델, EWM 공분산 추정
- **Morningstar**: Portfolio Risk Score (MPRS), 변동성 기반 단일 리스크 점수
- **PyPortfolioOpt** (Phase 3): Ledoit-Wolf shrinkage, max-Sharpe 최적화
