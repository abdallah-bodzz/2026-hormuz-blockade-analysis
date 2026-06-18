"""
utils.py
--------
Rolling statistics, chart helpers, formatting utilities, and the
single source-of-truth for event configuration.

Design rules:
  - All event dates and windows live here. Nothing hardcoded elsewhere.
  - fmt_pct / fmt_x are encoding-safe (ASCII fallbacks).
  - add_event_bands accepts an optional config dict so the engine is
    reusable for future events without touching chart code.

Update 2 additions (Jun 14, 2026):
  - 6 new tickers: ITA, BWET, TLT, XLE, ARAMCO (2222.SR), UNG
  - New asset-group constants: DEFENSE_ASSETS, FREIGHT_ASSETS,
    BOND_ASSETS, ENERGY_SECTOR, GULF_ASSETS, COMMODITY_ASSETS, ALL_ASSETS
  - EVENT_CONFIG expanded from 3 to 5 windows (correction + diplomacy)
  - 2 new event dates: May Correction Start, Iran Re-escalation (Jun 10)
  - FETCH_END updated to 2026-06-13
  - snapshot_note field added to EVENT_CONFIG for propagation to docs/HTML
  - vol_regime_ratio() and oil_gold_ratio() unchanged — already correct
  - BAND_COLORS extended for new phase colours (amber correction, steel diplomacy)
  - Plotly add_event_bands() updated to handle 5 windows cleanly
  - Window colour palette extended without breaking existing chart code
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

TRADING_DAYS = 252

# ---------------------------------------------------------------------------
# Fetch boundary — Update 2 cutoff
# ---------------------------------------------------------------------------

FETCH_START = "2016-01-01"
FETCH_END   = "2026-06-13"   # Update 2 cutoff; pre-ceasefire announcement


# ---------------------------------------------------------------------------
# Single source of truth — event configuration
# 5-window structure for Update 2.  All downstream code reads from here.
# ---------------------------------------------------------------------------

EVENT_CONFIG = {
    "dates": {
        "Op. Epic Fury (Feb 28)":      "2026-02-28",
        "Ceasefire (Apr 7)":            "2026-04-07",
        "Lebanon CF (Apr 16)":          "2026-04-16",
        "Hormuz Open (Apr 17)":         "2026-04-17",
        "May Correction Start":         "2026-05-01",
        "Iran Re-escalation (Jun 10)":  "2026-06-10",
    },
    "windows": {
        # --- original 3 — boundaries unchanged ---
        "pre_event":  ("2026-01-01", "2026-02-27"),
        "shock":      ("2026-02-28", "2026-04-16"),
        "reopen":     ("2026-04-17", "2026-04-30"),
        # --- 2 new phases — Update 2 ---
        "correction": ("2026-05-01", "2026-05-29"),
        "diplomacy":  ("2026-06-01", "2026-06-13"),
    },
    "window_labels": {
        "pre_event":  "Pre-event",
        "shock":      "Hormuz Closure",
        "reopen":     "False Dawn",
        "correction": "Paradox Correction",
        "diplomacy":  "Volatile Diplomacy",
    },
    # For backward-compat: functions that only run on post-shock windows
    "event_windows_no_pre": {
        "shock":      ("2026-02-28", "2026-04-16"),
        "reopen":     ("2026-04-17", "2026-04-30"),
        "correction": ("2026-05-01", "2026-05-29"),
        "diplomacy":  ("2026-06-01", "2026-06-13"),
    },
    "estimation_window": ("2026-01-01", "2026-02-27"),
    "analysis_as_of": "June 13, 2026",
    "snapshot_label": "Update 2",
    "snapshot_note": (
        "Update 2 static snapshot — data cutoff June 13, 2026. "
        "Iran–Israel ceasefire announced June 21–25, after this cutoff. "
        "Update 3 will cover the resolution chapter."
    ),
}

EVENT_DATES   = EVENT_CONFIG["dates"]
EVENT_WINDOWS = EVENT_CONFIG["windows"]


# ---------------------------------------------------------------------------
# Asset universe — Update 2: 16 assets total
#
# New additions:
#   ITA   — iShares US Aerospace & Defense ETF (escalation trade)
#   BWET  — Breakwave Tanker Shipping ETF (freight futures proxy)
#   TLT   — iShares 20+ Year Treasury Bond ETF (bond safe-haven test)
#   XLE   — Energy Select Sector SPDR ETF (broader energy equity proxy)
#   ARAMCO— Saudi Aramco (2222.SR) — Gulf exporter perspective
#   UNG   — United States Natural Gas Fund (LNG / nat gas proxy)
#
# Retained from Update 1:
#   SP500, WTI, GOLD, XOM, CVX, VIX, JETS, DXY, DAX, NKY
#
# Notable exclusions (documented):
#   Shanghai (000001.SS) — timezone/holiday alignment unreliable
#   Individual defense names (RTX, LMT, NOC) — ITA captures the theme
#   Individual tanker names — BWET captures the theme
#   Individual airlines (DAL, UAL) — JETS captures the theme
#   Crypto / EM currencies / agricultural futures — outside core scope
# ---------------------------------------------------------------------------

ACTIVE_TICKERS = {
    # --- original 10 ---
    "SP500":  "^GSPC",
    "WTI":    "CL=F",
    "GOLD":   "GC=F",
    "XOM":    "XOM",
    "CVX":    "CVX",
    "VIX":    "^VIX",
    "JETS":   "JETS",
    "DXY":    "DX-Y.NYB",
    "DAX":    "^GDAXI",
    "NKY":    "^N225",
    # --- 6 new additions — Update 2 ---
    "ITA":    "ITA",       # iShares US Aerospace & Defense ETF
    "BWET":   "BWET",      # Breakwave Tanker Shipping ETF (NYSE Arca)
    "TLT":    "TLT",       # iShares 20+ Year Treasury Bond ETF
    "XLE":    "XLE",       # Energy Select Sector SPDR ETF
    "ARAMCO": "2222.SR",   # Saudi Aramco — Tadawul, see alignment caveat
    "UNG":    "UNG",       # United States Natural Gas Fund (futures-based)
}

# ---------------------------------------------------------------------------
# Asset group constants
# Use these in notebook and event_study functions — never hardcode lists
# ---------------------------------------------------------------------------

CORE_ASSETS      = ["SP500", "WTI", "GOLD", "XOM", "CVX", "VIX", "JETS"]
DEFENSE_ASSETS   = ["ITA"]
FREIGHT_ASSETS   = ["BWET"]
BOND_ASSETS      = ["TLT"]
ENERGY_SECTOR    = ["XLE"]
GULF_ASSETS      = ["ARAMCO"]
COMMODITY_ASSETS = ["UNG"]
INTL_ASSETS      = ["SP500", "DAX", "NKY"]
DXY_ASSET        = "DXY"

# All assets — for broad heatmap / correlation matrix
ALL_ASSETS = list(ACTIVE_TICKERS.keys())

# New-asset group (Update 2 additions) — useful for targeted charts
NEW_ASSETS_U2 = ["ITA", "BWET", "TLT", "XLE", "ARAMCO", "UNG"]

# Assets with limited history — BWET launched May 2023
LIMITED_HISTORY_ASSETS = {
    "BWET": "2023-05-03",   # Launch date — baseline years: 2024–2025 only
}

# Assets requiring calendar alignment (non-US exchanges)
GULF_CALENDAR_ASSETS = ["ARAMCO"]


# ---------------------------------------------------------------------------
# Window colour palette — extended for Update 2
# Existing band colours kept unchanged so original charts repro identically
# ---------------------------------------------------------------------------

WINDOW_COLORS = {
    "pre_event":  "#b0b0b0",   # neutral grey
    "shock":      "#d62728",   # oil red
    "reopen":     "#2ca02c",   # relief green
    "correction": "#ff7f0e",   # amber (diplomacy heat)
    "diplomacy":  "#1f77b4",   # steel blue (negotiation cold)
}

WINDOW_ALPHA = {
    "pre_event":  0.08,
    "shock":      0.08,
    "reopen":     0.08,
    "correction": 0.07,
    "diplomacy":  0.07,
}

# Asset colour palette — extended for new tickers
COLORS = {
    # original
    "SP500": "#1f77b4",
    "WTI":   "#d62728",
    "GOLD":  "#bcbd22",
    "XOM":   "#9467bd",
    "CVX":   "#8c564b",
    "VIX":   "#e377c2",
    "JETS":  "#7f7f7f",
    "DXY":   "#17becf",
    "DAX":   "#2ca02c",
    "NKY":   "#ff7f0e",
    # new — Update 2
    "ITA":    "#393b79",   # dark indigo — defense/authority
    "BWET":   "#006d77",   # deep teal — maritime
    "TLT":    "#5aabff",   # light blue — treasury
    "XLE":    "#c44e52",   # muted red — energy sector (distinct from WTI)
    "ARAMCO": "#b8860b",   # dark gold — Gulf exporter
    "UNG":    "#8dd3c7",   # soft mint — natural gas
}

LABELS = {
    # original
    "SP500":  "S&P 500",
    "WTI":    "WTI Crude",
    "GOLD":   "Gold",
    "XOM":    "Exxon (XOM)",
    "CVX":    "Chevron (CVX)",
    "VIX":    "VIX",
    "JETS":   "Airlines ETF",
    "DXY":    "Dollar Index",
    "DAX":    "DAX (Germany)",
    "NKY":    "Nikkei 225",
    # new — Update 2
    "ITA":    "Defense ETF (ITA)",
    "BWET":   "Tanker ETF (BWET)",
    "TLT":    "Treasury ETF (TLT)",
    "XLE":    "Energy Sector (XLE)",
    "ARAMCO": "Saudi Aramco",
    "UNG":    "Natural Gas (UNG)",
}


# ---------------------------------------------------------------------------
# Return / volatility helpers — unchanged from Update 1
# ---------------------------------------------------------------------------

def simple_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Simple (arithmetic) period returns."""
    return prices.pct_change().dropna(how="all")


def log_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Log returns."""
    return np.log(prices / prices.shift(1)).dropna(how="all")


daily_returns = log_returns


def cumulative_return(prices: pd.DataFrame) -> pd.DataFrame:
    """Rebase so first observation = 100."""
    return prices / prices.iloc[0] * 100


def rolling_volatility(returns: pd.DataFrame, window: int = 21) -> pd.DataFrame:
    """Annualised rolling volatility (%)."""
    return returns.rolling(window).std() * np.sqrt(TRADING_DAYS) * 100


def rolling_correlation(series_a: pd.Series, series_b: pd.Series,
                        window: int = 10) -> pd.Series:
    return series_a.rolling(window).corr(series_b)


def period_stats(prices: pd.DataFrame) -> pd.DataFrame:
    rets    = simple_returns(prices).dropna()
    cum_ret = (prices.iloc[-1] / prices.iloc[0] - 1) * 100
    ann_vol = rets.std() * np.sqrt(TRADING_DAYS) * 100
    sharpe  = (rets.mean() / rets.std() * np.sqrt(TRADING_DAYS)).round(3)

    def _mdd(s):
        return ((s - s.cummax()) / s.cummax()).min() * 100

    return pd.DataFrame({
        "cum_return_%": cum_ret.round(2),
        "ann_vol_%":    ann_vol.round(2),
        "max_dd_%":     prices.apply(_mdd).round(2),
        "sharpe":       sharpe,
    })


# ---------------------------------------------------------------------------
# Derived-series helpers — unchanged from Update 1
# ---------------------------------------------------------------------------

def oil_gold_ratio(prices: pd.DataFrame,
                   oil_col: str = "WTI",
                   gold_col: str = "GOLD",
                   start: str = "2026-01-01",
                   end: str = None) -> pd.Series:
    """
    WTI/GOLD ratio rebased to 100 at start date.
    Update 2: accepts explicit start/end so it can be run over the full
    5-window timeline (2026-01-01 to 2026-06-13) or any sub-window.

    Interpretation:
      Rising ratio  → supply shock dominates (oil outpaces safe haven)
      Falling ratio → diplomacy/fear dominates (gold outpaces oil)
    """
    if oil_col not in prices.columns or gold_col not in prices.columns:
        return pd.Series(dtype=float, name="OIL_GOLD_RATIO")

    if end is None:
        end = FETCH_END

    subset = prices.loc[start:end, [oil_col, gold_col]].dropna()
    if subset.empty:
        return pd.Series(dtype=float, name="OIL_GOLD_RATIO")

    ratio = (subset[oil_col] / subset[gold_col])
    ratio = ratio / ratio.iloc[0] * 100
    ratio.name = "OIL_GOLD_RATIO"
    return ratio


def vol_regime_ratio(returns: pd.DataFrame,
                     short_window: int = 5,
                     long_window: int = 21) -> pd.DataFrame:
    """
    Short/long vol ratio. Values > 2.0 signal a volatility regime.
    Simpler and more interpretable than GARCH for this use case.
    Returns DataFrame with one column per asset in returns.
    """
    short_vol = returns.rolling(short_window).std() * np.sqrt(TRADING_DAYS) * 100
    long_vol  = returns.rolling(long_window).std()  * np.sqrt(TRADING_DAYS) * 100
    ratio     = short_vol / long_vol.replace(0, np.nan)
    return ratio


# ---------------------------------------------------------------------------
# Chart styling — Plotly helpers
# Updated to handle 5 windows cleanly
# ---------------------------------------------------------------------------

# Plotly fill colours (RGBA strings)
_PLOTLY_FILLS = {
    "pre_event":  "rgba(180,180,180,0.08)",
    "shock":      "rgba(220,50,50,0.08)",
    "reopen":     "rgba(50,180,80,0.08)",
    "correction": "rgba(255,127,14,0.07)",
    "diplomacy":  "rgba(31,119,180,0.07)",
}


def add_event_bands(fig, config: dict = None, row=None, col=None):
    """
    Add vertical shaded regions and event-date dotted lines to a Plotly figure.
    Handles any number of windows defined in config["windows"].
    """
    if config is None:
        config = EVENT_CONFIG

    windows = config["windows"]
    labels  = config.get("window_labels", {})
    dates   = config["dates"]

    subplot_kwargs = {"row": row, "col": col} if row is not None else {}

    for name, (s, e) in windows.items():
        fig.add_vrect(
            x0=s, x1=e,
            fillcolor=_PLOTLY_FILLS.get(name, "rgba(200,200,200,0.07)"),
            opacity=1, layer="below", line_width=0,
            annotation_text=labels.get(name, name),
            annotation_position="top left",
            annotation_font_size=9,
            annotation_font_color="grey",
            **subplot_kwargs,
        )

    for label, date in dates.items():
        fig.add_vline(
            x=date, line_dash="dot",
            line_color="rgba(100,100,100,0.55)", line_width=1,
            **subplot_kwargs,
        )

    return fig


def base_layout(title: str, yaxis_title: str = "", height: int = 500) -> dict:
    return dict(
        title=dict(text=title, font=dict(size=14, family="Arial")),
        height=height,
        template="plotly_white",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1),
        yaxis_title=yaxis_title,
        font=dict(family="Arial", size=11),
        margin=dict(l=60, r=30, t=70, b=50),
    )


# Matplotlib band helper — used directly in notebook chart cells
# Returns (band_color, band_alpha) for a given window name.
def get_band_style(window_name: str) -> tuple:
    return (
        WINDOW_COLORS.get(window_name, "#cccccc"),
        WINDOW_ALPHA.get(window_name, 0.07),
    )


# ---------------------------------------------------------------------------
# Formatting helpers — ASCII-safe, unchanged
# ---------------------------------------------------------------------------

def fmt_pct(val, decimals: int = 1) -> str:
    if val is None:
        return "N/A"
    try:
        f = float(val)
        if np.isnan(f):
            return "N/A"
        sign = "+" if f > 0 else ""
        return f"{sign}{f:.{decimals}f}%"
    except (TypeError, ValueError):
        return "N/A"


def fmt_x(val, decimals: int = 1) -> str:
    if val is None:
        return "N/A"
    try:
        f = float(val)
        if np.isnan(f):
            return "N/A"
        return f"{f:.{decimals}f}x"
    except (TypeError, ValueError):
        return "N/A"


def safe_get(d: dict, key, fallback="N/A"):
    v = d.get(key) if isinstance(d, dict) else None
    return v if v is not None else fallback


def fmt_window_label(window_name: str) -> str:
    """Human-readable window label for display in charts and tables."""
    return EVENT_CONFIG["window_labels"].get(window_name, window_name.replace("_", " ").title())


# ---------------------------------------------------------------------------
# Baseline year helpers
# Handles assets with limited history (BWET: only 2024–2025 available)
# ---------------------------------------------------------------------------

def get_baseline_years(asset: str,
                       default_years: range = range(2021, 2026)) -> list:
    """
    Returns the appropriate baseline years for an asset.
    Assets with limited history (BWET) get a shorter range.
    """
    if asset in LIMITED_HISTORY_ASSETS:
        launch = pd.Timestamp(LIMITED_HISTORY_ASSETS[asset])
        return [y for y in default_years if y >= launch.year]
    return list(default_years)


def limited_history_note(asset: str) -> str:
    """Returns a caveat string for assets with short history, or empty string."""
    if asset in LIMITED_HISTORY_ASSETS:
        return (
            f"{asset}: limited history — launched {LIMITED_HISTORY_ASSETS[asset]}. "
            f"Seasonal baseline uses fewer than 5 years."
        )
    return ""