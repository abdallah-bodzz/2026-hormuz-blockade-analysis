"""
data_fetcher.py
---------------
Fetches and stores adjusted close prices for the Hormuz analysis.

Update 2 additions (Jun 14, 2026):
  [U2-1] FETCH_END updated to 2026-06-13 (Update 2 cutoff).
  [U2-2] align_gulf_asset() — reindexes Tadawul (Sun–Thu, UTC+3) series
         to the US trading calendar used by all other assets via forward-fill.
         Called automatically for all assets in GULF_CALENDAR_ASSETS.
  [U2-3] Parquet versioning: original parquet untouched, new file is
         prices_2016_2026_u2.parquet. Both coexist in data/raw/.
  [U2-4] Three new quality_report() caveats: BWET limited history,
         ARAMCO calendar alignment, UNG roll decay.
  [U2-5] quality_report() now includes update_version field.
  [U2-6] fetch_all() handles GULF_CALENDAR_ASSETS alignment after building
         the joint DataFrame and before returning.
  [U2-7] run() updated: default parquet path is _u2; falls back to fetching
         if the _u2 file doesn't exist. Original parquet never touched.

Original design decisions carried forward:
  - auto_adjust=True: adjusted close prices (dividends + splits accounted for).
  - Survivorship bias caveat: XOM/CVX exclude delisted energy peers.
  - Timezone caveat: WTI/DXY 24/5 vs S&P NYSE hours; lag-0 CCF bias remains.
  - Shanghai (000001.SS) excluded: holiday/timezone alignment unreliable.
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

from utils import (
    ACTIVE_TICKERS,
    GULF_CALENDAR_ASSETS,
    LIMITED_HISTORY_ASSETS,
    FETCH_START,
    FETCH_END,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_ROWS         = 20
U2_PARQUET_FNAME = "prices_2016_2026_u2.parquet"
U1_PARQUET_FNAME = "prices_2016_2026.parquet"    # original — never overwritten


# ---------------------------------------------------------------------------
# [U2-2] Gulf asset calendar alignment
# ---------------------------------------------------------------------------

def align_gulf_asset(series: pd.Series,
                     reference_index: pd.DatetimeIndex) -> pd.Series:
    """
    Reindex a Gulf-market series (Tadawul: Sun–Thu, UTC+3) to match the
    US trading calendar used by all other assets.

    Method: forward-fill — the last known price carries forward over
    weekends, US holidays, and any Tadawul-only trading days.
    This is the same approach used for VIX weekend gaps throughout the study.

    Caveats:
      - Same-day comparison with US assets has a structural lag of up to
        ~18 hours (Tadawul close vs NYSE close).
      - Treat ARAMCO as directional / window-level indicator, not
        precise same-day data.
      - The reindex means ARAMCO appears to trade on US holidays — it doesn't.
        Forward-filled values on those days are stale prices, clearly flagged.

    Args:
        series: Raw price series fetched from Tadawul (business days only,
                may include Sun/Mon, exclude Sat/some US holidays).
        reference_index: US-calendar DatetimeIndex from the joint price DataFrame.

    Returns:
        Series reindexed to reference_index, with NaN → forward-filled.
    """
    name = series.name
    aligned = series.reindex(reference_index, method="ffill")
    aligned.name = name
    log.info(
        f"{name} (Gulf): reindexed from {series.notna().sum()} raw rows "
        f"to {aligned.notna().sum()} aligned rows via forward-fill."
    )
    return aligned


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
    [U2-6] After building the joint DataFrame, applies align_gulf_asset()
    to all assets in GULF_CALENDAR_ASSETS.

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
        time.sleep(0.4)   # rate-limit courtesy

    if not frames:
        raise RuntimeError("No data fetched. Check network / yfinance version.")

    prices = pd.concat(frames, axis=1).sort_index()

    # [U2-6] Align Gulf assets to US calendar
    # Build the reference index from the non-Gulf assets first
    reference_index = prices.index
    for gulf_name in GULF_CALENDAR_ASSETS:
        if gulf_name in prices.columns:
            prices[gulf_name] = align_gulf_asset(
                prices[gulf_name], reference_index
            )

    missing = prices.isna().sum()
    if missing.any():
        log.warning(f"Missing values per asset:\n{missing[missing > 0].to_string()}")
    else:
        log.info("Data coverage: complete for all assets.")

    return prices


# ---------------------------------------------------------------------------
# Data quality report
# [U2-4] Three new caveats; [U2-5] update_version field
# ---------------------------------------------------------------------------

def quality_report(prices: pd.DataFrame,
                   update_version: str = "2") -> dict:
    last_date = prices.index[-1]
    cutoff    = pd.Timestamp(FETCH_END)
    stale     = (cutoff - last_date).days > 5

    missing_pct = (prices.isna().mean() * 100).round(2).to_dict()

    caveats = [
        # --- original caveats, unchanged ---
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
        # --- [U2-4] new caveats — Update 2 ---
        "BWET (Breakwave Tanker Shipping ETF): launched May 3, 2023. "
        "Seasonal baseline covers 2024–2025 only (2 years vs 5 for original assets). "
        "Baseline statistics for BWET are marked with a limited-history flag. "
        "AUM is ~$25M; low liquidity makes BWET an analytical signal, not a "
        "real-world trading recommendation at scale.",
        "ARAMCO (2222.SR / Saudi Aramco): trades on Tadawul (Sun–Thu, UTC+3). "
        "Reindexed to US trading calendar via forward-fill — same approach as VIX gaps. "
        "Same-day comparison with US assets has a structural lag of up to ~18 hours. "
        "Treat as directional / window-level indicator, not precise same-day data. "
        "Aramco stock reflects Saudi state policy (production decisions, dividends) "
        "as much as market fundamentals — frame analysis as 'exporter sovereign response'.",
        "UNG (United States Natural Gas Fund): holds near-term nat gas futures. "
        "Returns reflect futures performance, subject to contango roll decay. "
        "Not equivalent to spot natural gas prices. Long-term UNG holders face "
        "structural headwinds from negative roll yield in contango markets.",
    ]

    if stale:
        caveats.append(
            f"WARNING: last data point is {last_date.date()}, "
            f"which is more than 5 days before the intended cutoff "
            f"({FETCH_END}). Some assets may have gaps."
        )

    # Flag any limited-history assets in the loaded data
    for asset, launch_date in LIMITED_HISTORY_ASSETS.items():
        if asset in prices.columns:
            p = prices[asset].dropna()
            if not p.empty:
                caveats.append(
                    f"{asset}: data available from {p.index[0].date()} "
                    f"(expected launch: {launch_date})."
                )

    return {
        "update_version":  update_version,
        "assets_loaded":   list(prices.columns),
        "n_assets":        len(prices.columns),
        "date_range":      (str(prices.index[0].date()), str(last_date.date())),
        "missing_pct":     missing_pct,
        "stale_warning":   stale,
        "caveats":         caveats,
        "analysis_as_of":  "June 13, 2026 -- Update 2 static snapshot.",
        "snapshot_note": (
            "Update 2 static snapshot — data cutoff June 13, 2026. "
            "Iran–Israel ceasefire announced June 21–25, after this cutoff. "
            "Update 3 will cover the resolution chapter."
        ),
    }


# ---------------------------------------------------------------------------
# Save / load — [U2-3] versioned parquet naming
# ---------------------------------------------------------------------------

def save_parquet(df: pd.DataFrame, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_parquet(path, engine="pyarrow")
    log.info(f"Saved: {path}  ({df.shape[0]} rows x {df.shape[1]} cols)")


def load_parquet(path: str) -> pd.DataFrame:
    df = pd.read_parquet(path, engine="pyarrow")
    df.index = pd.to_datetime(df.index)
    return df


def get_parquet_path(data_dir: str, version: str = "u2") -> str:
    """
    Returns the canonical parquet path for a given version.
    version="u1" → prices_2016_2026.parquet (original, read-only)
    version="u2" → prices_2016_2026_u2.parquet (Update 2)
    """
    if version == "u1":
        return os.path.join(data_dir, "raw", U1_PARQUET_FNAME)
    return os.path.join(data_dir, "raw", U2_PARQUET_FNAME)


# ---------------------------------------------------------------------------
# Entry point
# [U2-7] Defaults to _u2 parquet; never overwrites the original
# ---------------------------------------------------------------------------

def run(data_dir: str = "data",
        force_refresh: bool = False,
        version: str = "u2") -> pd.DataFrame:
    """
    Load (or fetch) price data for the specified version.

    version="u2" (default): loads/creates prices_2016_2026_u2.parquet
    version="u1": loads the original prices_2016_2026.parquet (read-only)
    force_refresh=True: re-fetches from yfinance regardless of cache state

    The original parquet (u1) is NEVER overwritten by this function.
    """
    raw_path = get_parquet_path(data_dir, version)

    if version == "u1":
        if not os.path.exists(raw_path):
            raise FileNotFoundError(
                f"Original parquet not found at {raw_path}. "
                "Cannot create it — this is the Update 1 static snapshot."
            )
        log.info(f"Loading Update 1 (original) cache from {raw_path}")
        return load_parquet(raw_path)

    # version == "u2"
    if os.path.exists(raw_path) and not force_refresh:
        log.info(f"Loading Update 2 cache from {raw_path}")
        log.info(
            "NOTE: Update 2 static snapshot — June 13, 2026 cutoff. "
            "Pass force_refresh=True to re-fetch."
        )
        prices = load_parquet(raw_path)

        # Check if any new tickers from ACTIVE_TICKERS are missing from cache
        missing_tickers = {k: v for k, v in ACTIVE_TICKERS.items()
                           if k not in prices.columns}
        if missing_tickers:
            log.info(f"Cache missing tickers: {list(missing_tickers.keys())} -- fetching...")
            frames = []
            for name, symbol in missing_tickers.items():
                df = fetch_ticker(symbol, FETCH_START, FETCH_END)
                if not df.empty:
                    df.columns = [name]
                    frames.append(df)
                time.sleep(0.4)

            if frames:
                new_cols = pd.concat(frames, axis=1)
                # Apply Gulf alignment for any new Gulf assets
                for gulf_name in GULF_CALENDAR_ASSETS:
                    if gulf_name in new_cols.columns:
                        new_cols[gulf_name] = align_gulf_asset(
                            new_cols[gulf_name], prices.index
                        )
                prices = prices.join(new_cols, how="left")
                save_parquet(prices, raw_path)

        return prices

    log.info("Fetching all assets from yfinance (auto_adjust=True)...")
    log.info(f"Tickers: {list(ACTIVE_TICKERS.keys())}")
    prices = fetch_all()
    save_parquet(prices, raw_path)
    return prices


# ---------------------------------------------------------------------------
# Convenience: load both versions side-by-side for comparison
# ---------------------------------------------------------------------------

def load_both_versions(data_dir: str = "data") -> tuple:
    """
    Returns (prices_u1, prices_u2) for side-by-side comparison.
    u1 may have fewer assets (10 original) — document this in notebooks.
    """
    u1_path = get_parquet_path(data_dir, "u1")
    u2_path = get_parquet_path(data_dir, "u2")

    u1 = load_parquet(u1_path) if os.path.exists(u1_path) else None
    u2 = load_parquet(u2_path) if os.path.exists(u2_path) else None

    if u1 is None:
        log.warning("Update 1 parquet not found. Run original notebook first.")
    if u2 is None:
        log.warning("Update 2 parquet not found. Run data_fetcher.run() first.")

    return u1, u2


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    data_dir      = sys.argv[1] if len(sys.argv) > 1 else "data"
    force_refresh = "--refresh" in sys.argv

    prices = run(data_dir, force_refresh=force_refresh)
    report = quality_report(prices)

    print(f"\nUpdate {report['update_version']} — {report['analysis_as_of']}")
    print(f"Assets ({report['n_assets']}): {report['assets_loaded']}")
    print(f"Range:  {report['date_range']}")
    print(f"Stale:  {report['stale_warning']}")
    print("\nCaveats:")
    for c in report["caveats"]:
        print(f"  - {c}")