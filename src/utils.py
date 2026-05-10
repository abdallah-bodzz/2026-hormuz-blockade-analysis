"""
utils.py
--------
Rolling statistics, chart helpers, formatting utilities, and the
single source-of-truth for event configuration.

Design rules:
  - All event dates and windows live here. Nothing hardcoded elsewhere.
  - fmt_pct / fmt_x are encoding-safe (ASCII fallbacks for em-dash, times).
  - add_event_bands accepts an optional config dict so the engine is
    reusable for future events without touching chart code.

New additions:
  - DXY ticker added to ACTIVE_TICKERS (dollar index for oil decomposition)
  - DAX, Nikkei added for international spillover table
  - vol_regime_ratio() helper for 5d/21d vol regime detection
  - oil_gold_ratio() derived series helper
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

TRADING_DAYS = 252


# ---------------------------------------------------------------------------
# Single source of truth — event configuration
# ---------------------------------------------------------------------------

EVENT_CONFIG = {
    "dates": {
        "Op. Epic Fury (Feb 28)": "2026-02-28",
        "Ceasefire (Apr 7)":      "2026-04-07",
        "Lebanon CF (Apr 16)":    "2026-04-16",
        "Hormuz Open (Apr 17)":   "2026-04-17",
    },
    "windows": {
        "pre_event": ("2026-01-01", "2026-02-27"),
        "shock":     ("2026-02-28", "2026-04-16"),
        "reopen":    ("2026-04-17", "2026-04-30"),
    },
    "window_labels": {
        "pre_event": "Pre-event",
        "shock":     "Hormuz Closure",
        "reopen":    "Reopening",
    },
    "estimation_window": ("2026-01-01", "2026-02-27"),
    "analysis_as_of": "April 30, 2026",
}

EVENT_DATES   = EVENT_CONFIG["dates"]
EVENT_WINDOWS = EVENT_CONFIG["windows"]


# ---------------------------------------------------------------------------
# Asset universe
# DXY added: decomposes WTI move into real supply shock vs dollar weakness.
# DAX, Nikkei added: international spillover. Shanghai excluded — yfinance
# data quality issues with 000001.SS (timezone, holiday gaps).
# ---------------------------------------------------------------------------

ACTIVE_TICKERS = {
    "SP500": "^GSPC",
    "WTI":   "CL=F",
    "GOLD":  "GC=F",
    "XOM":   "XOM",
    "CVX":   "CVX",
    "VIX":   "^VIX",
    "JETS":  "JETS",
    "DXY":   "DX-Y.NYB",   # Dollar Index -- oil pricing context
    "DAX":   "^GDAXI",     # German equities -- European energy exposure
    "NKY":   "^N225",      # Nikkei -- Asia/oil importer reaction
}

# Assets used in main analysis charts (not every fetched ticker)
CORE_ASSETS   = ["SP500", "WTI", "GOLD", "XOM", "CVX", "VIX", "JETS"]
INTL_ASSETS   = ["SP500", "DAX", "NKY"]   # for spillover table
DXY_ASSET     = "DXY"


# ---------------------------------------------------------------------------
# Return / volatility helpers
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
# New derived-series helpers
# ---------------------------------------------------------------------------

def oil_gold_ratio(prices: pd.DataFrame,
                   oil_col: str = "WTI",
                   gold_col: str = "GOLD") -> pd.Series:
    """
    WTI/GOLD ratio rebased to 100 at start of 2026.
    Interpretation:
      Rising ratio  -> supply shock dominates (oil outpaces safe haven)
      Falling ratio -> fear/capital flight dominates (gold outpaces oil)
    Returns a Series with name 'OIL_GOLD_RATIO'.
    """
    if oil_col not in prices.columns or gold_col not in prices.columns:
        return pd.Series(dtype=float, name="OIL_GOLD_RATIO")

    subset = prices.loc["2026-01-01":"2026-04-30", [oil_col, gold_col]].dropna()
    if subset.empty:
        return pd.Series(dtype=float, name="OIL_GOLD_RATIO")

    ratio = (subset[oil_col] / subset[gold_col])
    ratio = ratio / ratio.iloc[0] * 100   # rebase to 100
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
# Chart styling
# ---------------------------------------------------------------------------

COLORS = {
    "pre":   "rgba(180,180,180,0.15)",
    "shock": "rgba(220,50,50,0.12)",
    "reopen":"rgba(50,180,80,0.12)",
}


def add_event_bands(fig, config: dict = None, row=None, col=None):
    if config is None:
        config = EVENT_CONFIG

    windows = config["windows"]
    labels  = config.get("window_labels", {})
    dates   = config["dates"]

    subplot_kwargs = {"row": row, "col": col} if row is not None else {}

    band_colors = {
        "pre_event": COLORS["pre"],
        "shock":     COLORS["shock"],
        "reopen":    COLORS["reopen"],
    }

    for name, (s, e) in windows.items():
        fig.add_vrect(
            x0=s, x1=e,
            fillcolor=band_colors.get(name, "rgba(200,200,200,0.1)"),
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


# ---------------------------------------------------------------------------
# Formatting helpers — ASCII-safe
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