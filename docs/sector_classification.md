# Sector Classification

## Data Sources

### KR (KOSPI / KOSDAQ)
- **Source**: KRX via pykrx `get_market_sector`
- **Sector count**: 22~24 sectors (varies by exchange)
- Examples: 음식료품, 전기전자, 의약품, 운수장비, 유통업, 서비스업, 건설업, 금융업, ...

### US (NYSE / NASDAQ)
- **Primary source**: NASDAQ Screener API (`api.nasdaq.com/api/screener/stocks`)
- **Fallback source**: Finnhub API (`/stock/profile2` → `finnhubIndustry`)
- **Sector count**: ~12 sectors (NASDAQ Screener), ~50+ industries (Finnhub, more granular)

NASDAQ Screener sectors:
- Technology, Health Care, Consumer Discretionary, Industrials, Finance
- Consumer Staples, Energy, Real Estate, Utilities, Basic Materials
- Telecommunications, Miscellaneous

Finnhub industry examples:
- Technology, Pharmaceuticals & Biotechnology, Media, Real Estate
- Hotels & Leisure, Automobiles & Parts, Banks, Insurance, etc.

## Sector Value Policy

| `sector` value | Meaning | Quant analysis |
|---|---|---|
| Valid string (e.g. 'Technology') | Normal common stock | **Included** |
| `'N/A'` | Finnhub identified as non-equity (SPAC, shell, etc.) | **Excluded** |
| `NULL` | Unclassified (both APIs failed) | **Excluded** |

## Collection Flow

1. Stock list collected from KIS master files
2. KR sectors: pykrx sector map lookup
3. US sectors (primary): NASDAQ Screener bulk fetch
4. US sectors (fallback): Finnhub individual profile lookup for remaining NULL sectors
   - `finnhubIndustry = 'N/A'` → stored as `sector = 'N/A'` (non-equity marker)
   - Valid industry → stored as sector
   - No response → remains NULL

## Cross-Source Mapping

Finnhub sectors are more granular than NASDAQ Screener sectors. No normalization is applied —
the actual API value is stored as-is. Factor model industry dummies use whatever sector string
is in the database, so NASDAQ Screener and Finnhub sectors coexist as separate categories.

This means a Finnhub-sourced 'Pharmaceuticals & Biotechnology' and a Screener-sourced
'Health Care' are treated as different industries in the factor model. This is acceptable
because the cross-sectional regression naturally handles varying granularity.
