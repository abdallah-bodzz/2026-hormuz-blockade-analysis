"""
data_fetcher.py
---------------
Fetches and stores adjusted close prices for the Hormuz analysis.

Key design decisions:

  ADJUSTED CLOSE (auto_adjust=True)
    yfinance's auto_adjust=True returns prices adjusted for dividends and
    stock splits. Correct for total-return calculations on equities.
    Futures (WTI, GOLD, VIX, DXY) are unaffected -- no dividends, no splits.

  NEW: DXY (Dollar Index)
    Added DX-Y.NYB to decompose WTI's move into real supply shock vs
    dollar weakness. Oil is priced in USD; a falling dollar inflates the
    nominal oil price. If DXY fell during the shock, some WTI gain is
    currency effect, not pure supply disruption.
    Caveat: DX-Y.NYB is the ICE futures contract. Overnight/weekend gaps
    may differ slightly from spot DXY. Directionally correct.

  NEW: DAX, Nikkei
    Added for international spillover table. Both are liquid and fetch
    cleanly via yfinance. Shanghai (000001.SS) excluded -- timezone and
    holiday handling in yfinance produces unreliable same-day alignment.

  SURVIVORSHIP BIAS CAVEAT
    XOM, CVX: current S&P 500 constituents. Historical baselines exclude
    peers that underperformed and delisted. Inflates energy basket quality.

  TIMEZONE / LEAD-LAG CAVEAT
    WTI trades 24/5 (CME Globex); S&P and equity indices are local-hours only.
    Daily close comparison can produce phantom same-day correlation shifts.
    DXY (ICE futures) also trades nearly 24 hours. Lead-lag analysis uses
    cross-correlation function (CCF), not concurrent correlation, to partially
    address this. Full fix requires intraday data.
"""

import os
import time
import logging
import warnings
from datetime import datetime

import pandas as pd
import numpy as np
import yfinance as yf

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger(__name__)

from utils import ACTIVE_TICKERS

FETCH_START = "2016-01-01"
FETCH_END   = "2026-04-30"
MIN_ROWS    = 20


# ---------------------------------------------------------------------------
# Core fetch
# ---------------------------------------------------------------------------

def fetch_ticker(symbol: str, start: str, end: str,
                 retries: int = 3) -> pd.DataFrame:
    """
    Download adjusted close prices for a single ticker via yfinance.
    Returns empty DataFrame on failure (never raises).
    """
    for attempt in range(1, retries + 1):
        try:
            raw = yf.download(
                symbol,
                start=start,
                end=end,
                auto_adjust=True,
                progress=False,
                threads=False,
            )

            if raw.empty:
                log.warning(f"{symbol}: empty on attempt {attempt}")
                time.sleep(1)
                continue

            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)

            raw.index = pd.to_datetime(raw.index)
            raw.index.name = "date"

            close = raw[["Close"]].rename(columns={"Close": symbol})
            close = close.replace(0, np.nan)
            n_valid = close[symbol].notna().sum()

            if n_valid < MIN_ROWS:
                log.warning(f"{symbol}: only {n_valid} valid rows -- skipping.")
                return pd.DataFrame()

            log.info(
                f"{symbol}: {n_valid} rows "
                f"({close.index[0].date()} to {close.index[-1].date()}) "
                f"[adj close]"
            )
            return close

        except Exception as exc:
            log.warning(f"{symbol}: attempt {attempt} failed -- {exc}")
            time.sleep(2)

    log.error(f"{symbol}: all {retries} attempts failed. Skipping.")
    return pd.DataFrame()


def fetch_all(tickers: dict = None,
              start: str = FETCH_START,
              end: str = FETCH_END) -> pd.DataFrame:
    """
    Fetch all tickers and align on a common trading-day index.
    Returns wide DataFrame: rows = dates, columns = asset names.
    """
    if tickers is None:
        tickers = ACTIVE_TICKERS

    frames = []
    for name, symbol in tickers.items():
        df = fetch_ticker(symbol, start, end)
        if not df.empty:
            df.columns = [name]
            frames.append(df)
        time.sleep(0.4)

    if not frames:
        raise RuntimeError("No data fetched. Check network / yfinance version.")

    prices = pd.concat(frames, axis=1).sort_index()

    missing = prices.isna().sum()
    if missing.any():
        log.warning(f"Missing values per asset:\n{missing[missing > 0].to_string()}")
    else:
        log.info("Data coverage: complete for all assets.")

    return prices


# ---------------------------------------------------------------------------
# Data quality report
# ---------------------------------------------------------------------------

def quality_report(prices: pd.DataFrame) -> dict:
    last_date = prices.index[-1]
    cutoff    = pd.Timestamp(FETCH_END)
    stale     = (cutoff - last_date).days > 5

    missing_pct = (prices.isna().mean() * 100).round(2).to_dict()

    caveats = [
        "Prices are adjusted for dividends and splits (auto_adjust=True).",
        "Survivorship bias: XOM/CVX baselines exclude delisted energy peers.",
        "Timezone mismatch: WTI/DXY daily close leads S&P/equity opens -- "
        "phantom same-day correlations may exist. CCF analysis partially addresses this.",
        "DXY uses ICE futures (DX-Y.NYB). Minor gaps vs spot DXY. Directionally correct.",
        "Beta is estimated on ~39 pre-event trading days -- short window. "
        "During a 30%+ oil shock, beta is likely non-linear; abnormal returns "
        "should be read as directional, not precise.",
        "All figures are nominal. No inflation adjustment applied to "
        "multi-year price comparisons.",
        "Shanghai index excluded: yfinance timezone/holiday handling unreliable "
        "for same-day alignment with US markets.",
    ]

    if stale:
        caveats.append(
            f"WARNING: last data point is {last_date.date()}, "
            f"which is more than 5 days before the intended cutoff "
            f"({FETCH_END}). Some assets may have gaps."
        )

    return {
        "assets_loaded":  list(prices.columns),
        "date_range":     (str(prices.index[0].date()), str(last_date.date())),
        "missing_pct":    missing_pct,
        "stale_warning":  stale,
        "caveats":        caveats,
        "analysis_as_of": "April 30, 2026 -- static snapshot, not live.",
    }


# ---------------------------------------------------------------------------
# Save / load
# ---------------------------------------------------------------------------

def save_parquet(df: pd.DataFrame, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_parquet(path, engine="pyarrow")
    log.info(f"Saved: {path}  ({df.shape[0]} rows x {df.shape[1]} cols)")


def load_parquet(path: str) -> pd.DataFrame:
    df = pd.read_parquet(path, engine="pyarrow")
    df.index = pd.to_datetime(df.index)
    return df


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(data_dir: str = "data",
        force_refresh: bool = False) -> pd.DataFrame:
    raw_path = os.path.join(data_dir, "raw", "prices_2016_2026.parquet")

    if os.path.exists(raw_path) and not force_refresh:
        log.info(f"Loading cached prices from {raw_path}")
        log.info(
            "NOTE: Static snapshot as of April 30, 2026. "
            "Pass force_refresh=True to re-fetch."
        )
        prices = load_parquet(raw_path)
        # If cache predates new tickers, re-fetch missing ones
        missing_tickers = {k: v for k, v in ACTIVE_TICKERS.items()
                           if k not in prices.columns}
        if missing_tickers:
            log.info(f"Cache missing new tickers: {list(missing_tickers.keys())} -- fetching...")
            frames = []
            for name, symbol in missing_tickers.items():
                df = fetch_ticker(symbol, FETCH_START, FETCH_END)
                if not df.empty:
                    df.columns = [name]
                    frames.append(df)
                time.sleep(0.4)
            if frames:
                new_cols = pd.concat(frames, axis=1)
                prices   = prices.join(new_cols, how="left")
                save_parquet(prices, raw_path)
        return prices

    log.info("Fetching adjusted close prices from yfinance (auto_adjust=True)...")
    prices = fetch_all()
    save_parquet(prices, raw_path)
    return prices


if __name__ == "__main__":
    import sys
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "data"
    prices = run(data_dir)
    report = quality_report(prices)
    print(f"\nAssets: {report['assets_loaded']}")
    print(f"Range:  {report['date_range']}")
    print(f"Stale:  {report['stale_warning']}")
    print("\nCaveats:")
    for c in report["caveats"]:
        print(f"  - {c}")