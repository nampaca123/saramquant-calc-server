"""
데이터 소스 통합 테스트 스크립트
각 API가 DB 스키마에 필요한 데이터를 제공하는지 검증

테스트 대상:
1. FinanceDataReader (FDR) - 한국/미국 종목목록, 일봉
2. yfinance - 미국 일봉/분봉
3. 한국투자증권 REST API - 한국 실시간/분봉/일봉
4. Finnhub - 미국 실시간

DB 스키마 (검증 대상):
- stocks: symbol, name, market, sector, industry
- daily_prices: date, open, high, low, close, volume, adjusted_close
- minute_prices: datetime, interval_type, open, high, low, close, volume
"""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

load_dotenv()


def section(title: str) -> None:
    print(f"\n{'='*70}\n {title}\n{'='*70}")


def subsection(title: str) -> None:
    print(f"\n--- {title} ---")


def show_columns(df: pd.DataFrame | dict, source: str) -> None:
    if isinstance(df, pd.DataFrame):
        print(f"\n[{source}] Columns: {list(df.columns)}")
        if hasattr(df, 'index') and df.index.name:
            print(f"[{source}] Index: {df.index.name}")
    else:
        print(f"\n[{source}] Keys: {list(df.keys())}")


def mapping_check(field: str, available: bool, source_field: str = None) -> str:
    icon = "✅" if available else "❌"
    src = f" <- {source_field}" if source_field else ""
    return f"  {icon} {field}{src}"


def save_sample(data, filename: str) -> None:
    path = OUTPUT_DIR / filename
    if isinstance(data, pd.DataFrame):
        data.to_csv(path, index=True, encoding="utf-8-sig")
    else:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    print(f"  💾 Saved: {path}")


# =============================================================================
# 1. FinanceDataReader 테스트
# =============================================================================
def test_fdr():
    section("1. FinanceDataReader (FDR) 테스트")
    import FinanceDataReader as fdr

    results = {"success": [], "failed": []}

    # 1-1. 한국 종목 목록 (KRX) - 403 에러 예상
    subsection("1-1. KRX 종목 목록")
    try:
        df = fdr.StockListing("KRX")
        print(f"  종목 수: {len(df)}")
        show_columns(df, "KRX")
        print("\n  stocks 테이블 매핑:")
        print(mapping_check("symbol", "Code" in df.columns, "Code"))
        print(mapping_check("name", "Name" in df.columns, "Name"))
        print(mapping_check("market", "Market" in df.columns, "Market"))
        print(mapping_check("sector", "Sector" in df.columns, "Sector"))
        print(mapping_check("industry", "Industry" in df.columns, "Industry"))
        save_sample(df.head(20), "fdr_krx_stocks.csv")
        results["success"].append("KRX 종목 목록")
    except Exception as e:
        print(f"  ❌ 실패: {e}")
        results["failed"].append(f"KRX 종목 목록: {e}")

    # 1-2. 미국 S&P500 종목 목록
    subsection("1-2. S&P500 종목 목록")
    try:
        df = fdr.StockListing("S&P500")
        print(f"  종목 수: {len(df)}")
        show_columns(df, "S&P500")
        print("\n  stocks 테이블 매핑:")
        print(mapping_check("symbol", "Symbol" in df.columns, "Symbol"))
        print(mapping_check("name", "Name" in df.columns, "Name"))
        print(mapping_check("market", False, "하드코딩 필요 (US_SP500)"))
        print(mapping_check("sector", "Sector" in df.columns, "Sector"))
        print(mapping_check("industry", "Industry" in df.columns, "Industry"))
        save_sample(df.head(20), "fdr_sp500_stocks.csv")
        results["success"].append("S&P500 종목 목록")
    except Exception as e:
        print(f"  ❌ 실패: {e}")
        results["failed"].append(f"S&P500 종목 목록: {e}")

    # 1-3. NASDAQ 종목 목록
    subsection("1-3. NASDAQ 종목 목록")
    try:
        df = fdr.StockListing("NASDAQ")
        print(f"  종목 수: {len(df)}")
        show_columns(df, "NASDAQ")
        save_sample(df.head(20), "fdr_nasdaq_stocks.csv")
        results["success"].append("NASDAQ 종목 목록")
    except Exception as e:
        print(f"  ❌ 실패: {e}")
        results["failed"].append(f"NASDAQ 종목 목록: {e}")

    # 1-4. 한국 주식 일봉 (삼성전자)
    subsection("1-4. 한국 주식 일봉 (005930 삼성전자)")
    try:
        df = fdr.DataReader("005930", "2025-01-01")
        print(f"  데이터 수: {len(df)}")
        show_columns(df, "KR Daily")
        print("\n  daily_prices 테이블 매핑:")
        print(mapping_check("date", True, "index"))
        print(mapping_check("open", "Open" in df.columns, "Open"))
        print(mapping_check("high", "High" in df.columns, "High"))
        print(mapping_check("low", "Low" in df.columns, "Low"))
        print(mapping_check("close", "Close" in df.columns, "Close"))
        print(mapping_check("volume", "Volume" in df.columns, "Volume"))
        print(mapping_check("adjusted_close", "Adj Close" in df.columns, "Adj Close"))
        print(f"\n  샘플 데이터:\n{df.tail(3)}")
        save_sample(df.tail(20), "fdr_kr_daily.csv")
        results["success"].append("한국 주식 일봉")
    except Exception as e:
        print(f"  ❌ 실패: {e}")
        results["failed"].append(f"한국 주식 일봉: {e}")

    # 1-5. 미국 주식 일봉 (AAPL)
    subsection("1-5. 미국 주식 일봉 (AAPL)")
    try:
        df = fdr.DataReader("AAPL", "2025-01-01")
        print(f"  데이터 수: {len(df)}")
        show_columns(df, "US Daily")
        print(f"\n  샘플 데이터:\n{df.tail(3)}")
        save_sample(df.tail(20), "fdr_us_daily.csv")
        results["success"].append("미국 주식 일봉")
    except Exception as e:
        print(f"  ❌ 실패: {e}")
        results["failed"].append(f"미국 주식 일봉: {e}")

    # 1-6. 시장 지수 (KOSPI, S&P500)
    subsection("1-6. 시장 지수")
    try:
        df_kospi = fdr.DataReader("KS11", "2025-01-01")
        print(f"  KOSPI 지수 데이터 수: {len(df_kospi)}")
        df_sp500 = fdr.DataReader("US500", "2025-01-01")
        print(f"  S&P500 지수 데이터 수: {len(df_sp500)}")
        save_sample(df_kospi.tail(10), "fdr_index_kospi.csv")
        save_sample(df_sp500.tail(10), "fdr_index_sp500.csv")
        results["success"].append("시장 지수")
    except Exception as e:
        print(f"  ❌ 실패: {e}")
        results["failed"].append(f"시장 지수: {e}")

    return results


# =============================================================================
# 2. yfinance 테스트
# =============================================================================
def test_yfinance():
    section("2. yfinance 테스트")
    import yfinance as yf

    results = {"success": [], "failed": []}

    # 2-1. 종목 정보 (AAPL)
    subsection("2-1. 종목 기본 정보 (AAPL)")
    try:
        ticker = yf.Ticker("AAPL")
        info = ticker.info
        print(f"  반환된 필드 수: {len(info)}")
        print("\n  stocks 테이블 매핑:")
        print(mapping_check("symbol", "symbol" in info, "symbol"))
        print(mapping_check("name", "shortName" in info or "longName" in info, "shortName/longName"))
        print(mapping_check("sector", "sector" in info, "sector"))
        print(mapping_check("industry", "industry" in info, "industry"))
        print(f"\n  주요 정보:")
        for key in ["symbol", "shortName", "sector", "industry", "marketCap", "currency"]:
            print(f"    {key}: {info.get(key, 'N/A')}")
        save_sample(info, "yf_aapl_info.json")
        results["success"].append("종목 기본 정보")
    except Exception as e:
        print(f"  ❌ 실패: {e}")
        results["failed"].append(f"종목 기본 정보: {e}")

    # 2-2. 일봉 데이터
    subsection("2-2. 일봉 데이터 (AAPL)")
    try:
        df = ticker.history(period="1mo", interval="1d")
        print(f"  데이터 수: {len(df)}")
        show_columns(df, "yf Daily")
        print("\n  daily_prices 테이블 매핑:")
        print(mapping_check("date", True, "index"))
        print(mapping_check("open", "Open" in df.columns, "Open"))
        print(mapping_check("high", "High" in df.columns, "High"))
        print(mapping_check("low", "Low" in df.columns, "Low"))
        print(mapping_check("close", "Close" in df.columns, "Close"))
        print(mapping_check("volume", "Volume" in df.columns, "Volume"))
        # yfinance의 Close가 이미 adjusted close
        print(mapping_check("adjusted_close", True, "Close (이미 수정주가)"))
        print(f"\n  샘플 데이터:\n{df.tail(3)}")
        save_sample(df.tail(20), "yf_daily.csv")
        results["success"].append("일봉 데이터")
    except Exception as e:
        print(f"  ❌ 실패: {e}")
        results["failed"].append(f"일봉 데이터: {e}")

    # 2-3. 분봉 데이터 (5분봉)
    subsection("2-3. 분봉 데이터 (5분봉, AAPL)")
    try:
        df = ticker.history(period="5d", interval="5m")
        print(f"  데이터 수: {len(df)}")
        show_columns(df, "yf 5min")
        print("\n  minute_prices 테이블 매핑:")
        print(mapping_check("datetime", True, "index"))
        print(mapping_check("interval_type", True, "하드코딩 (5m)"))
        print(mapping_check("open", "Open" in df.columns, "Open"))
        print(mapping_check("high", "High" in df.columns, "High"))
        print(mapping_check("low", "Low" in df.columns, "Low"))
        print(mapping_check("close", "Close" in df.columns, "Close"))
        print(mapping_check("volume", "Volume" in df.columns, "Volume"))
        print(f"\n  샘플 데이터:\n{df.tail(3)}")
        save_sample(df.tail(50), "yf_5min.csv")
        results["success"].append("분봉 데이터 (5m)")
    except Exception as e:
        print(f"  ❌ 실패: {e}")
        results["failed"].append(f"분봉 데이터: {e}")

    # 2-4. 1분봉 데이터
    subsection("2-4. 1분봉 데이터 (AAPL)")
    try:
        df = ticker.history(period="1d", interval="1m")
        print(f"  데이터 수: {len(df)}")
        print(f"  (주의: 1분봉은 최근 7일만 제공)")
        save_sample(df.tail(50), "yf_1min.csv")
        results["success"].append("분봉 데이터 (1m)")
    except Exception as e:
        print(f"  ❌ 실패: {e}")
        results["failed"].append(f"1분봉 데이터: {e}")

    # 2-5. 한국 주식 테스트 (삼성전자)
    subsection("2-5. 한국 주식 (005930.KS 삼성전자)")
    try:
        kr_ticker = yf.Ticker("005930.KS")
        df = kr_ticker.history(period="1mo", interval="1d")
        print(f"  데이터 수: {len(df)}")
        if len(df) > 0:
            print(f"\n  샘플 데이터:\n{df.tail(3)}")
            save_sample(df.tail(20), "yf_kr_daily.csv")
            results["success"].append("한국 주식 (yfinance)")
        else:
            print("  ⚠️ 데이터 없음")
            results["failed"].append("한국 주식: 데이터 없음")
    except Exception as e:
        print(f"  ❌ 실패: {e}")
        results["failed"].append(f"한국 주식: {e}")

    return results


# =============================================================================
# 3. 한국투자증권 REST API 테스트
# =============================================================================
def test_kis():
    section("3. 한국투자증권 REST API 테스트")

    app_key = os.getenv("KIS_APP_KEY")
    app_secret = os.getenv("KIS_APP_SECRET")

    if not app_key or not app_secret:
        print("  ❌ KIS_APP_KEY, KIS_APP_SECRET 환경변수가 필요합니다")
        return {"success": [], "failed": ["환경변수 없음"]}

    results = {"success": [], "failed": []}
    base_url = "https://openapivts.koreainvestment.com:29443"  # 모의투자

    # 3-1. 접근토큰 발급
    subsection("3-1. 접근토큰 발급")
    try:
        token_url = f"{base_url}/oauth2/tokenP"
        token_body = {
            "grant_type": "client_credentials",
            "appkey": app_key,
            "appsecret": app_secret
        }
        res = requests.post(token_url, json=token_body)
        token_data = res.json()

        if "access_token" in token_data:
            access_token = token_data["access_token"]
            print(f"  ✅ 토큰 발급 성공")
            print(f"  토큰 타입: {token_data.get('token_type')}")
            print(f"  만료 시간: {token_data.get('expires_in')}초")
            results["success"].append("토큰 발급")
        else:
            print(f"  ❌ 토큰 발급 실패: {token_data}")
            results["failed"].append(f"토큰 발급: {token_data}")
            return results
    except Exception as e:
        print(f"  ❌ 실패: {e}")
        results["failed"].append(f"토큰 발급: {e}")
        return results

    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {access_token}",
        "appkey": app_key,
        "appsecret": app_secret,
    }

    # 3-2. 주식 현재가 조회 (삼성전자)
    subsection("3-2. 주식 현재가 조회 (005930 삼성전자)")
    try:
        url = f"{base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",  # 주식
            "FID_INPUT_ISCD": "005930"  # 삼성전자
        }
        headers["tr_id"] = "FHKST01010100"

        res = requests.get(url, headers=headers, params=params)
        data = res.json()

        if data.get("rt_cd") == "0":
            output = data.get("output", {})
            print(f"  ✅ 조회 성공")
            print(f"\n  반환 필드 수: {len(output)}")
            print(f"\n  주요 정보:")
            field_map = {
                "stck_prpr": "현재가",
                "stck_oprc": "시가",
                "stck_hgpr": "고가",
                "stck_lwpr": "저가",
                "acml_vol": "누적거래량",
                "prdy_vrss": "전일대비",
                "prdy_ctrt": "전일대비율",
            }
            for key, name in field_map.items():
                print(f"    {name}: {output.get(key, 'N/A')}")

            print("\n  실시간 시세 매핑:")
            print(mapping_check("price", "stck_prpr" in output, "stck_prpr"))
            print(mapping_check("open", "stck_oprc" in output, "stck_oprc"))
            print(mapping_check("high", "stck_hgpr" in output, "stck_hgpr"))
            print(mapping_check("low", "stck_lwpr" in output, "stck_lwpr"))
            print(mapping_check("volume", "acml_vol" in output, "acml_vol"))
            print(mapping_check("change", "prdy_vrss" in output, "prdy_vrss"))
            print(mapping_check("change_rate", "prdy_ctrt" in output, "prdy_ctrt"))

            save_sample(output, "kis_realtime.json")
            results["success"].append("현재가 조회")
        else:
            print(f"  ❌ 조회 실패: {data.get('msg1')}")
            results["failed"].append(f"현재가 조회: {data.get('msg1')}")
    except Exception as e:
        print(f"  ❌ 실패: {e}")
        results["failed"].append(f"현재가 조회: {e}")

    # 3-3. 일봉 데이터 조회
    subsection("3-3. 일봉 데이터 조회 (005930)")
    try:
        url = f"{base_url}/uapi/domestic-stock/v1/quotations/inquire-daily-price"
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": "005930",
            "FID_PERIOD_DIV_CODE": "D",  # 일봉
            "FID_ORG_ADJ_PRC": "0"  # 수정주가
        }
        headers["tr_id"] = "FHKST01010400"

        res = requests.get(url, headers=headers, params=params)
        data = res.json()

        if data.get("rt_cd") == "0":
            output = data.get("output", [])
            print(f"  ✅ 조회 성공")
            print(f"  데이터 수: {len(output)}")

            if output:
                sample = output[0]
                print(f"\n  첫 번째 레코드 필드: {list(sample.keys())}")
                print("\n  daily_prices 테이블 매핑:")
                print(mapping_check("date", "stck_bsop_date" in sample, "stck_bsop_date"))
                print(mapping_check("open", "stck_oprc" in sample, "stck_oprc"))
                print(mapping_check("high", "stck_hgpr" in sample, "stck_hgpr"))
                print(mapping_check("low", "stck_lwpr" in sample, "stck_lwpr"))
                print(mapping_check("close", "stck_clpr" in sample, "stck_clpr"))
                print(mapping_check("volume", "acml_vol" in sample, "acml_vol"))

                print(f"\n  샘플 데이터 (최근 3일):")
                for item in output[:3]:
                    print(f"    {item.get('stck_bsop_date')}: 종가 {item.get('stck_clpr')}, 거래량 {item.get('acml_vol')}")

                save_sample(output[:20], "kis_daily.json")
                results["success"].append("일봉 데이터")
        else:
            print(f"  ❌ 조회 실패: {data.get('msg1')}")
            results["failed"].append(f"일봉 데이터: {data.get('msg1')}")
    except Exception as e:
        print(f"  ❌ 실패: {e}")
        results["failed"].append(f"일봉 데이터: {e}")

    # 3-4. 분봉 데이터 조회
    subsection("3-4. 분봉 데이터 조회 (005930)")
    try:
        url = f"{base_url}/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": "005930",
            "FID_INPUT_HOUR_1": "153000",  # 조회 시작 시간 (장 마감)
            "FID_PW_DATA_INCU_YN": "Y"  # 과거 데이터 포함
        }
        headers["tr_id"] = "FHKST03010200"

        res = requests.get(url, headers=headers, params=params)
        data = res.json()

        if data.get("rt_cd") == "0":
            output2 = data.get("output2", [])
            print(f"  ✅ 조회 성공")
            print(f"  데이터 수: {len(output2)}")

            if output2:
                sample = output2[0]
                print(f"\n  첫 번째 레코드 필드: {list(sample.keys())}")
                print("\n  minute_prices 테이블 매핑:")
                print(mapping_check("datetime", "stck_cntg_hour" in sample, "stck_bsop_date + stck_cntg_hour"))
                print(mapping_check("open", "stck_oprc" in sample, "stck_oprc"))
                print(mapping_check("high", "stck_hgpr" in sample, "stck_hgpr"))
                print(mapping_check("low", "stck_lwpr" in sample, "stck_lwpr"))
                print(mapping_check("close", "stck_prpr" in sample, "stck_prpr"))
                print(mapping_check("volume", "cntg_vol" in sample, "cntg_vol"))

                save_sample(output2[:30], "kis_minute.json")
                results["success"].append("분봉 데이터")
        else:
            print(f"  ❌ 조회 실패: {data.get('msg1')}")
            results["failed"].append(f"분봉 데이터: {data.get('msg1')}")
    except Exception as e:
        print(f"  ❌ 실패: {e}")
        results["failed"].append(f"분봉 데이터: {e}")

    return results


# =============================================================================
# 4. Finnhub 테스트
# =============================================================================
def test_finnhub():
    section("4. Finnhub 테스트")

    # Finnhub 무료 API 키 (테스트용 - 실제 사용시 발급 필요)
    # 무료 키 발급: https://finnhub.io/register
    api_key = os.getenv("FINNHUB_API_KEY", "")

    results = {"success": [], "failed": []}

    if not api_key:
        print("  ⚠️ FINNHUB_API_KEY 환경변수 없음 - 공개 API로 테스트")
        # 일부 API는 키 없이도 사용 가능

    base_url = "https://finnhub.io/api/v1"

    # 4-1. 현재가 조회 (Quote)
    subsection("4-1. 실시간 시세 (AAPL)")
    try:
        url = f"{base_url}/quote"
        params = {"symbol": "AAPL", "token": api_key} if api_key else {"symbol": "AAPL"}
        res = requests.get(url, params=params)
        data = res.json()

        if "c" in data:  # c = current price
            print(f"  ✅ 조회 성공")
            print(f"\n  반환 필드: {list(data.keys())}")
            field_map = {
                "c": "현재가",
                "d": "변동",
                "dp": "변동률(%)",
                "h": "고가",
                "l": "저가",
                "o": "시가",
                "pc": "전일종가",
                "t": "타임스탬프"
            }
            print(f"\n  데이터:")
            for key, name in field_map.items():
                val = data.get(key, "N/A")
                if key == "t" and val != "N/A":
                    val = datetime.fromtimestamp(val).strftime("%Y-%m-%d %H:%M:%S")
                print(f"    {name}: {val}")

            print("\n  실시간 시세 매핑:")
            print(mapping_check("price", "c" in data, "c"))
            print(mapping_check("open", "o" in data, "o"))
            print(mapping_check("high", "h" in data, "h"))
            print(mapping_check("low", "l" in data, "l"))
            print(mapping_check("change", "d" in data, "d"))
            print(mapping_check("change_rate", "dp" in data, "dp"))
            print(mapping_check("volume", False, "❌ 제공 안 됨"))

            save_sample(data, "finnhub_quote.json")
            results["success"].append("실시간 시세")
        else:
            print(f"  ❌ 조회 실패: {data}")
            results["failed"].append(f"실시간 시세: {data}")
    except Exception as e:
        print(f"  ❌ 실패: {e}")
        results["failed"].append(f"실시간 시세: {e}")

    # 4-2. 회사 정보
    subsection("4-2. 회사 프로필 (AAPL)")
    try:
        url = f"{base_url}/stock/profile2"
        params = {"symbol": "AAPL", "token": api_key} if api_key else {"symbol": "AAPL"}
        res = requests.get(url, params=params)
        data = res.json()

        if "name" in data:
            print(f"  ✅ 조회 성공")
            print(f"\n  반환 필드: {list(data.keys())}")
            print(f"\n  stocks 테이블 매핑:")
            print(mapping_check("symbol", "ticker" in data, "ticker"))
            print(mapping_check("name", "name" in data, "name"))
            print(mapping_check("sector", "finnhubIndustry" in data, "finnhubIndustry"))
            print(mapping_check("industry", "finnhubIndustry" in data, "finnhubIndustry"))

            print(f"\n  주요 정보:")
            for key in ["ticker", "name", "finnhubIndustry", "exchange", "marketCapitalization"]:
                print(f"    {key}: {data.get(key, 'N/A')}")

            save_sample(data, "finnhub_profile.json")
            results["success"].append("회사 프로필")
        else:
            print(f"  ❌ 조회 실패 (API 키 필요할 수 있음): {data}")
            results["failed"].append(f"회사 프로필: {data}")
    except Exception as e:
        print(f"  ❌ 실패: {e}")
        results["failed"].append(f"회사 프로필: {e}")

    # 4-3. 캔들스틱 데이터 (일봉)
    subsection("4-3. 캔들스틱 데이터 (AAPL 일봉)")
    try:
        url = f"{base_url}/stock/candle"
        end_time = int(datetime.now().timestamp())
        start_time = int((datetime.now() - timedelta(days=30)).timestamp())
        params = {
            "symbol": "AAPL",
            "resolution": "D",  # D=일봉, 1=1분, 5=5분, 15=15분, 30=30분, 60=60분
            "from": start_time,
            "to": end_time
        }
        if api_key:
            params["token"] = api_key

        res = requests.get(url, params=params)
        data = res.json()

        if data.get("s") == "ok":
            print(f"  ✅ 조회 성공")
            print(f"  데이터 수: {len(data.get('c', []))}")
            print(f"\n  반환 필드: {list(data.keys())}")
            print("\n  daily_prices 테이블 매핑:")
            print(mapping_check("date", "t" in data, "t (타임스탬프)"))
            print(mapping_check("open", "o" in data, "o"))
            print(mapping_check("high", "h" in data, "h"))
            print(mapping_check("low", "l" in data, "l"))
            print(mapping_check("close", "c" in data, "c"))
            print(mapping_check("volume", "v" in data, "v"))

            # 샘플 데이터 변환
            if data.get("t"):
                sample_df = pd.DataFrame({
                    "date": [datetime.fromtimestamp(t).strftime("%Y-%m-%d") for t in data["t"][-5:]],
                    "open": data["o"][-5:],
                    "high": data["h"][-5:],
                    "low": data["l"][-5:],
                    "close": data["c"][-5:],
                    "volume": data["v"][-5:]
                })
                print(f"\n  샘플 데이터:\n{sample_df}")

            save_sample(data, "finnhub_candle.json")
            results["success"].append("캔들스틱 데이터")
        else:
            print(f"  ❌ 조회 실패: {data}")
            results["failed"].append(f"캔들스틱 데이터: {data}")
    except Exception as e:
        print(f"  ❌ 실패: {e}")
        results["failed"].append(f"캔들스틱 데이터: {e}")

    return results


# =============================================================================
# 메인 실행 & 결과 요약
# =============================================================================
def print_summary(all_results: dict):
    section("📊 테스트 결과 요약")

    print("\n[DB 스키마별 데이터 소스 매핑]\n")

    print("┌─────────────────┬────────────────────────────────────────────────┐")
    print("│ DB 테이블/필드   │ 데이터 소스                                    │")
    print("├─────────────────┼────────────────────────────────────────────────┤")

    # stocks 테이블
    print("│ stocks          │                                                │")
    print("│  - symbol       │ FDR(Code/Symbol), yfinance, KIS, Finnhub      │")
    print("│  - name         │ FDR(Name), yfinance(shortName), Finnhub       │")
    print("│  - market       │ FDR(Market-KR만), 하드코딩 필요                │")
    print("│  - sector       │ FDR(S&P500만), yfinance, Finnhub              │")
    print("│  - industry     │ FDR(S&P500만), yfinance, Finnhub              │")
    print("├─────────────────┼────────────────────────────────────────────────┤")

    # daily_prices 테이블
    print("│ daily_prices    │                                                │")
    print("│  - date         │ FDR(index), yfinance(index), KIS, Finnhub     │")
    print("│  - OHLCV        │ FDR, yfinance, KIS, Finnhub 모두 제공          │")
    print("│  - adj_close    │ FDR(US만), yfinance(기본값), KIS/Finnhub(X)   │")
    print("├─────────────────┼────────────────────────────────────────────────┤")

    # minute_prices 테이블
    print("│ minute_prices   │                                                │")
    print("│  - datetime     │ yfinance, KIS 제공                             │")
    print("│  - OHLCV        │ yfinance, KIS 제공                             │")
    print("│  - 제한사항     │ yfinance: 최근 7일만 / KIS: 당일만             │")
    print("├─────────────────┼────────────────────────────────────────────────┤")

    # 실시간 시세
    print("│ 실시간 시세      │                                                │")
    print("│  - 한국         │ KIS (실시간)                                   │")
    print("│  - 미국         │ Finnhub (실시간), yfinance (15분 지연)         │")
    print("└─────────────────┴────────────────────────────────────────────────┘")

    print("\n[데이터 소스별 테스트 결과]\n")
    for source, result in all_results.items():
        print(f"  {source}:")
        if result["success"]:
            print(f"    ✅ 성공: {', '.join(result['success'])}")
        if result["failed"]:
            print(f"    ❌ 실패: {', '.join(result['failed'])}")
        print()


def main():
    print("\n" + "="*70)
    print(" 데이터 소스 통합 테스트".center(70))
    print(f" 실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}".center(70))
    print("="*70)

    all_results = {}

    # 1. FDR 테스트
    all_results["FinanceDataReader"] = test_fdr()

    # 2. yfinance 테스트
    all_results["yfinance"] = test_yfinance()

    # 3. 한국투자증권 테스트
    all_results["한국투자증권"] = test_kis()

    # 4. Finnhub 테스트
    all_results["Finnhub"] = test_finnhub()

    # 결과 요약
    print_summary(all_results)

    # 결과 저장
    save_sample(all_results, "test_summary.json")

    print(f"\n📁 모든 출력 파일: {OUTPUT_DIR}")
    print("✅ 테스트 완료!")


if __name__ == "__main__":
    main()
