import json
import logging
import os
import zipfile

import requests

from app.utils import retry_with_backoff

logger = logging.getLogger(__name__)

USER_AGENT = "SaramQuant knnam12@outlook.com"

BULK_FACTS_URL = "https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip"
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"


class EdgarClient:
    def __init__(self):
        self._headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"}

    def download_bulk_facts(self, data_dir: str) -> str:
        dest = os.path.join(data_dir, "companyfacts")
        zip_path = os.path.join(data_dir, "companyfacts.zip")

        if os.path.isdir(dest) and os.listdir(dest):
            logger.info(f"[EDGAR] Bulk data already exists at {dest}, skipping download")
            return dest

        os.makedirs(data_dir, exist_ok=True)
        logger.info("[EDGAR] Downloading companyfacts.zip (this may take several minutes)...")

        resp = requests.get(BULK_FACTS_URL, headers=self._headers, stream=True, timeout=600)
        resp.raise_for_status()

        with open(zip_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)

        logger.info("[EDGAR] Extracting companyfacts.zip...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(data_dir)

        if os.path.exists(zip_path):
            os.remove(zip_path)

        logger.info(f"[EDGAR] Bulk data extracted to {dest}")
        return dest

    def parse_company_facts(self, data_dir: str, cik: int) -> dict | None:
        path = os.path.join(data_dir, "companyfacts", f"CIK{cik:010d}.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    def fetch_company_tickers(self) -> dict[str, int]:
        resp = requests.get(TICKERS_URL, headers=self._headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        mapping: dict[str, int] = {}
        for entry in data.values():
            ticker = entry.get("ticker", "")
            cik = entry.get("cik_str")
            if ticker and cik:
                mapping[ticker.upper()] = int(cik)

        logger.info(f"[EDGAR] Loaded {len(mapping)} ticker-to-CIK mappings")
        return mapping
