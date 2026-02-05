"""
Korea Investment & Securities (한국투자증권) REST API response types.

Base URL (모의투자): https://openapivts.koreainvestment.com:29443
Base URL (실전투자): https://openapi.koreainvestment.com:9443

Tested endpoints:
- POST /oauth2/tokenP: Access token issuance
- GET /uapi/domestic-stock/v1/quotations/inquire-price (tr_id: FHKST01010100): Realtime quote
- GET /uapi/domestic-stock/v1/quotations/inquire-daily-price (tr_id: FHKST01010400): Daily OHLCV
- GET /uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice (tr_id: FHKST03010200): Minute OHLCV

Notes:
- All numeric values returned as strings
- Rate limit: 20 requests/second
- Token expires in 86400 seconds (24 hours)
"""
from typing import TypedDict


class KisTokenResponse(TypedDict):
    access_token: str
    token_type: str  # "Bearer"
    expires_in: int  # 86400


class KisRealtimeQuote(TypedDict, total=False):
    """
    80 fields available. Subset defined below.
    All values are strings.
    """
    # Price
    stck_prpr: str      # current price
    stck_oprc: str      # open
    stck_hgpr: str      # high
    stck_lwpr: str      # low
    stck_sdpr: str      # previous close

    # Volume
    acml_vol: str       # accumulated volume
    acml_tr_pbmn: str   # accumulated trade amount

    # Change
    prdy_vrss: str      # change from previous day
    prdy_vrss_sign: str # 1:limit up, 2:up, 3:unchanged, 4:down, 5:limit down
    prdy_ctrt: str      # change rate (%)

    # Limits
    stck_mxpr: str      # upper limit price
    stck_llam: str      # lower limit price

    # Fundamentals
    per: str            # PER
    pbr: str            # PBR
    eps: str            # EPS
    bps: str            # BPS

    # 52-week
    w52_hgpr: str       # 52-week high
    w52_lwpr: str       # 52-week low
    w52_hgpr_date: str  # 52-week high date (YYYYMMDD)
    w52_lwpr_date: str  # 52-week low date (YYYYMMDD)

    # Foreign
    hts_frgn_ehrt: str  # foreign holding ratio (%)
    frgn_ntby_qty: str  # foreign net buy quantity

    # Classification
    bstp_kor_isnm: str       # sector name (Korean)
    rprs_mrkt_kor_name: str  # market name (Korean)

    # Stock info
    stck_shrn_iscd: str  # short stock code
    cpfn: str            # capital (억원)
    lstn_stcn: str       # listed shares


class KisDailyPrice(TypedDict):
    """Daily OHLCV from inquire-daily-price endpoint."""
    stck_bsop_date: str  # trade date (YYYYMMDD)
    stck_oprc: str       # open
    stck_hgpr: str       # high
    stck_lwpr: str       # low
    stck_clpr: str       # close
    acml_vol: str        # volume
    prdy_vrss: str       # change
    prdy_vrss_sign: str  # change sign
    prdy_ctrt: str       # change rate (%)
    hts_frgn_ehrt: str   # foreign holding ratio
    frgn_ntby_qty: str   # foreign net buy
    flng_cls_code: str   # suspension code
    acml_prtt_rate: str  # accumulated turnover rate


class KisMinutePrice(TypedDict):
    """
    Minute OHLCV from inquire-time-itemchartprice endpoint.
    Returns in output2 array.
    """
    stck_bsop_date: str  # trade date (YYYYMMDD)
    stck_cntg_hour: str  # trade time (HHMMSS)
    stck_prpr: str       # close (current price)
    stck_oprc: str       # open
    stck_hgpr: str       # high
    stck_lwpr: str       # low
    cntg_vol: str        # volume for this candle
    acml_vol: str        # accumulated volume
    acml_tr_pbmn: str    # accumulated trade amount
