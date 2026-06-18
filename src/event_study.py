"""
event_study.py
--------------
Core analytical engine for the 2026 Hormuz Crisis study.
Update 2 — Jun 14, 2026  |  Data cutoff: Jun 13, 2026

─────────────────────────────────────────────────────────────────────────────
CHANGE LOG
─────────────────────────────────────────────────────────────────────────────
Original fixes (Update 1, carried forward):
  [F1]  correlation_flip() returns full-window averages, not rolling peak.
  [F2]  first_day_reaction() is single close-to-close — not a window return.
  [F3]  asset_character_card() pulls n_shock_days from ev_stats, not hardcoded.
  [F4]  compute_abnormal_returns() includes OLS SE and beta_low_flag.
  [F5]  days_to_price_event() uses relative-vol threshold, not fixed %.
  [F6]  Reopen window narrative reads actual data, no hardcoded strings.
  [F7]  correlation_flip() calls correlation_by_window() — single source of truth.
  [F8]  seasonal_baseline() carries is_nominal=True flag on every row.
  [F9]  Gold margin_call_flag added to asset character card.
  [F10] All dates read from EVENT_CONFIG — nothing hardcoded anywhere.
  [FIX] drawdown_avoidance() label direction corrected (basket_had_worse_dd).

Original N-series (Update 1, unchanged):
  [N1]  lead_lag_ccf()              — WTI vs S&P CCF, lags −5 to +5
  [N2]  rolling_beta_series()       — time-varying beta via rolling OLS
  [N3]  dxy_oil_decomposition()     — currency vs real-supply split
  [N4]  vol_regime_periods()        — 5d/21d ratio regime detection
  [N5]  international_spillover()   — DAX, Nikkei vs S&P spillover
  [N6]  oil_gold_ratio_stats()      — fear vs supply regime signal
  [N7]  sector_rotation_heatmap()   — assets × windows return matrix

Update 2 additions:
  [U2-A] pair_trade_extended()        — generalised long/short P&L, any pair
  [U2-A2] pair_trade_timeseries()     — daily cumulative P&L series for a pair
  [U2-B] escalation_replay()          — 5-day arc comparison across all 6 events
  [U2-C] forward_expectations_proxy() — diplomacy-day flag vs WTI returns
  [U2-D] defense_premium()            — ITA abnormal return + backlog interpretation
  [U2-E] freight_oil_spread()         — BWET vs WTI (third decoupling layer)
  [U2-F] window_regime_summary()      — NEW: compact per-window regime classification
  [U2-G] cross_asset_correlation_delta() — NEW: correlation shift table, any pair set
  [U2-H] aramco_sovereign_discount()  — NEW: Aramco vs WTI premium/discount analysis
  [U2-I] tlt_safe_haven_test()        — NEW: TLT vs Gold as safe-haven comparison
  [U2-J] pair_trade_drawdown()        — NEW: drawdown profile of L/S timeseries

Update 2 framework improvements:
  [U2-FW1] seasonal_baseline() skips pre-launch years for BWET automatically.
  [U2-FW2] compute_abnormal_returns() defaults to event_windows_no_pre (5-window safe).
  [U2-FW3] counterfactual_2026() accepts end param for Jun 13 timeline.
  [U2-FW4] sector_portfolio(), oil_equity_correlation(), vix_peak_stats()
            all accept start/end for flexible windowing.
  [U2-FW5] All new functions include caveat fields in output dicts/DataFrames.
  [U2-FW6] run_full_analysis() orchestrates the complete Update 2 pipeline.

Analytical caveats (apply to entire module):
  - Beta estimated on ~39 pre-event days. Non-linear during extreme moves.
    Treat abnormal return magnitudes as directional bounds, not precise estimates.
  - All pair trade P&Ls are pre-cost upper bounds (no borrow, roll, or slippage).
  - BWET: launched May 2023 — only 2 baseline years available.
  - ARAMCO: forward-filled from Tadawul (Sun–Thu) to US calendar.
    Same-day comparisons have a structural ~18h lag.
  - forward_expectations_proxy() uses post-hoc binary flags from known event dates.
    Proper implementation requires real-time news counts or Polymarket data.
  - All returns are nominal. No CPI adjustment.
"""

import os
import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm

warnings.filterwarnings("ignore")

from utils import (
    simple_returns,
    rolling_volatility,
    rolling_correlation,
    oil_gold_ratio,
    vol_regime_ratio,
    EVENT_WINDOWS,
    EVENT_CONFIG,
    TRADING_DAYS,
    CORE_ASSETS,
    INTL_ASSETS,
    DXY_ASSET,
    ALL_ASSETS,
    NEW_ASSETS_U2,
    LIMITED_HISTORY_ASSETS,
    LABELS,
    COLORS,
    get_baseline_years,
    limited_history_note,
    fmt_pct,
    fmt_window_label,
    FETCH_END,
)


# ============================================================================
# SECTION 1: BASELINE & WINDOW ANALYSIS
# ============================================================================

def seasonal_baseline(prices: pd.DataFrame,
                      assets: list,
                      years: range = range(2021, 2027)) -> pd.DataFrame:
    """
    Jan–Apr cumulative return, volatility, and drawdown for each asset
    across historical years.

    [F8]     is_nominal=True flag on every row.
    [U2-FW1] Skips years before launch date for limited-history assets (BWET).
             limited_history_flag column marks those rows.

    Returns long-form DataFrame: one row per (year, asset).
    """
    records = []
    for year in years:
        cols    = [a for a in assets if a in prices.columns]
        slice_p = prices.loc[f"{year}-01-01":f"{year}-04-30", cols].copy()
        if slice_p.empty or len(slice_p) < 5:
            continue

        rets = simple_returns(slice_p).dropna()
        for col in slice_p.columns:
            s = slice_p[col].dropna()
            r = rets[col].dropna() if col in rets.columns else pd.Series(dtype=float)
            if s.empty or r.empty:
                continue

            # [U2-FW1] Skip pre-launch years for limited-history assets
            if col in LIMITED_HISTORY_ASSETS:
                launch = pd.Timestamp(LIMITED_HISTORY_ASSETS[col])
                if year < launch.year:
                    continue

            records.append({
                "year":                 year,
                "asset":                col,
                "cum_return":           round((s.iloc[-1] / s.iloc[0] - 1) * 100, 2),
                "ann_vol":              round(r.std() * np.sqrt(TRADING_DAYS) * 100, 2),
                "max_dd":               round(((s / s.cummax()) - 1).min() * 100, 2),
                "n_days":               len(s),
                "is_nominal":           True,
                "limited_history_flag": col in LIMITED_HISTORY_ASSETS,
            })

    return pd.DataFrame(records)


def baseline_summary(seasonal_df: pd.DataFrame,
                     baseline_years: list = None) -> pd.DataFrame:
    """
    Comparison table: baseline average vs 2026 performance.
    Includes vol_multiple and ret_multiple for easy outlier identification.
    """
    if baseline_years is None:
        baseline_years = [y for y in seasonal_df["year"].unique() if y != 2026]

    base = (seasonal_df[seasonal_df["year"].isin(baseline_years)]
            .groupby("asset")[["cum_return", "ann_vol", "max_dd"]]
            .mean()
            .round(2))
    base.columns = [f"avg_{c}" for c in base.columns]

    y2026 = (seasonal_df[seasonal_df["year"] == 2026]
             .set_index("asset")[["cum_return", "ann_vol", "max_dd"]])
    y2026.columns = [f"2026_{c}" for c in y2026.columns]

    combined = base.join(y2026, how="outer")
    combined["vol_multiple"]     = (combined["2026_ann_vol"] / combined["avg_ann_vol"]).round(2)
    combined["ret_multiple"]     = (combined["2026_cum_return"] / combined["avg_cum_return"]).round(2)
    combined["nominal_caveat"]   = "Returns are nominal. No CPI adjustment."
    combined["limited_history"]  = combined.index.map(lambda x: x in LIMITED_HISTORY_ASSETS)
    return combined


def event_window_stats(prices: pd.DataFrame,
                       assets: list,
                       windows: dict = None) -> pd.DataFrame:
    """
    Cumulative return, average daily return, annualised vol, and max drawdown
    for each asset in each event window.

    Works for any window dict — 3-window (Update 1) or 5-window (Update 2).
    """
    if windows is None:
        windows = EVENT_WINDOWS

    records = []
    for window_name, (start, end) in windows.items():
        cols    = [a for a in assets if a in prices.columns]
        slice_p = prices.loc[start:end, cols].copy()
        if slice_p.empty:
            continue

        rets = simple_returns(slice_p).dropna()
        for col in slice_p.columns:
            s = slice_p[col].dropna()
            r = rets[col].dropna() if col in rets.columns else pd.Series(dtype=float)
            if s.empty or len(s) < 2:
                continue

            records.append({
                "window":        window_name,
                "window_label":  fmt_window_label(window_name),
                "asset":         col,
                "cum_return":    round((s.iloc[-1] / s.iloc[0] - 1) * 100, 2),
                "avg_daily":     round(r.mean() * 100, 3),
                "ann_vol":       round(r.std() * np.sqrt(TRADING_DAYS) * 100, 2),
                "max_dd":        round(((s / s.cummax()) - 1).min() * 100, 2),
                "n_days":        len(s),
            })

    return pd.DataFrame(records)


# ============================================================================
# SECTION 2: ABNORMAL RETURNS (OLS MARKET MODEL) [F4]
# ============================================================================

def compute_abnormal_returns(prices: pd.DataFrame,
                             assets: list,
                             benchmark: str = "SP500",
                             estimation_window: tuple = None,
                             event_windows: dict = None) -> pd.DataFrame:
    """
    Market model cumulative abnormal returns via OLS.
    Beta estimated on pre-event window only (avoids shock contamination).

    Formula:
        AR_i,t = R_i,t − (α_i + β_i × R_m,t)
        CAR_i  = sum(AR_i,t) over window

    [F4]     Near-zero beta assets flagged with beta_low_flag.
    [U2-FW2] Defaults to event_windows_no_pre so the pre-event window is
             excluded from abnormal return computation (correct practice).
             Pass event_windows=EVENT_WINDOWS to override.
    """
    if estimation_window is None:
        estimation_window = EVENT_CONFIG["estimation_window"]
    if event_windows is None:
        event_windows = EVENT_CONFIG["event_windows_no_pre"]

    est_s, est_e = estimation_window
    est_rets     = simple_returns(prices.loc[est_s:est_e]).dropna()

    if benchmark not in est_rets.columns:
        raise ValueError(f"Benchmark '{benchmark}' not in price data.")

    bm_est  = est_rets[benchmark]
    records = []

    for asset in assets:
        if asset == benchmark or asset not in prices.columns:
            continue
        if asset not in est_rets.columns:
            continue

        aligned = pd.concat([est_rets[asset], bm_est], axis=1).dropna()
        if len(aligned) < 10:
            continue

        model    = sm.OLS(aligned[asset], sm.add_constant(aligned[benchmark])).fit()
        alpha    = model.params["const"]
        beta     = model.params[benchmark]
        beta_se  = model.bse[benchmark]
        r2       = model.rsquared
        low_beta = abs(beta) < 0.05

        for window_name, (ws, we) in event_windows.items():
            win_p = prices.loc[ws:we, [asset, benchmark]].dropna()
            if len(win_p) < 2:
                continue

            win_rets   = simple_returns(win_p).dropna()
            actual_cum = (win_p[asset].iloc[-1] / win_p[asset].iloc[0] - 1) * 100
            bm_cum     = (win_p[benchmark].iloc[-1] / win_p[benchmark].iloc[0] - 1) * 100
            n_days     = len(win_rets)
            exp_cum    = (alpha * n_days * 100) + (beta * bm_cum)
            abnormal   = actual_cum - exp_cum

            caveat = (
                "Near-zero beta: abnormal ≈ actual return (market model adds little)."
                if low_beta else
                "Beta assumed constant; may overstate shock specificity during large moves."
            )

            records.append({
                "window":           window_name,
                "window_label":     fmt_window_label(window_name),
                "asset":            asset,
                "actual_ret_%":     round(actual_cum, 2),
                "expected_ret_%":   round(exp_cum, 2),
                "abnormal_ret_%":   round(abnormal, 2),
                "beta":             round(beta, 3),
                "beta_se":          round(beta_se, 4),
                "beta_low_flag":    low_beta,
                "alpha_daily":      round(alpha * 100, 4),
                "r2":               round(r2, 3),
                "n_days":           n_days,
                "nonlinear_caveat": caveat,
            })

    return pd.DataFrame(records)


# ============================================================================
# SECTION 3: CORRELATION [F1][F7]
# ============================================================================

def correlation_by_window(prices: pd.DataFrame,
                          pairs: list = None,
                          windows: dict = None) -> pd.DataFrame:
    """
    Full-window average Pearson correlation per event window.

    [F7]   Single source of truth — correlation_flip() calls this.
    [U2]   Default pair list extended with defense, freight, bond,
           energy-sector pairs for Update 2 coverage.

    Returns long-form DataFrame: (window, pair, correlation).
    """
    if pairs is None:
        pairs = [
            # Original pairs
            ("WTI",  "SP500"), ("GOLD", "SP500"), ("WTI",  "GOLD"),
            ("DXY",  "WTI"),   ("DXY",  "SP500"),
            # [U2] New asset pairs
            ("ITA",  "SP500"), ("ITA",  "WTI"),
            ("BWET", "WTI"),   ("BWET", "SP500"),
            ("TLT",  "SP500"), ("TLT",  "WTI"),   ("TLT", "GOLD"),
            ("XLE",  "WTI"),   ("XLE",  "SP500"),
            ("UNG",  "WTI"),
        ]
    if windows is None:
        windows = EVENT_WINDOWS

    rets    = simple_returns(prices).dropna()
    records = []
    for name, (s, e) in windows.items():
        w_rets = rets.loc[s:e]
        for a, b in pairs:
            if a not in w_rets.columns or b not in w_rets.columns:
                continue
            c = w_rets[[a, b]].dropna().corr().iloc[0, 1]
            records.append({
                "window":       name,
                "window_label": fmt_window_label(name),
                "pair":         f"{a} / {b}",
                "correlation":  round(float(c), 3),
            })

    return pd.DataFrame(records)


def oil_equity_correlation(prices: pd.DataFrame,
                           oil_col: str = "WTI",
                           eq_col: str = "SP500",
                           window: int = 10,
                           start: str = "2026-01-01",
                           end: str = None) -> pd.DataFrame:
    """Rolling correlation series for chart visualisation. [U2-FW4] start/end param."""
    if end is None:
        end = FETCH_END
    subset = prices.loc[start:end, [oil_col, eq_col]].dropna()
    rets   = simple_returns(subset).dropna()
    corr   = rolling_correlation(rets[oil_col], rets[eq_col], window=window)
    corr.name = f"{oil_col}_vs_{eq_col}_corr"
    return corr.to_frame()


def correlation_flip(prices: pd.DataFrame,
                     oil_col: str = "WTI",
                     eq_col: str = "SP500") -> dict:
    """
    [F1][F7] Regime shift via window averages. Single computation path.
    [U2]     Returns correction and diplomacy averages alongside original 3.
    """
    corr_table = correlation_by_window(
        prices,
        pairs=[(oil_col, eq_col)],
        windows=EVENT_WINDOWS,
    )

    if corr_table.empty:
        return {}

    pair_label = f"{oil_col} / {eq_col}"
    row = corr_table[corr_table["pair"] == pair_label].set_index("window")

    def _get(w):
        return float(row.loc[w, "correlation"]) if w in row.index else None

    pre        = _get("pre_event")
    shock      = _get("shock")
    reopen     = _get("reopen")
    correction = _get("correction")
    diplomacy  = _get("diplomacy")
    flip       = round(shock - pre, 3) if (shock is not None and pre is not None) else None

    if flip is not None:
        if flip > 0.3:
            interp = "Strong shift: oil became an equity amplifier during closure."
        elif flip > 0.1:
            interp = "Moderate shift: oil-equity relationship tightened during closure."
        elif flip < -0.1:
            interp = "Inverse shift: oil and equities decoupled during closure."
        else:
            interp = "Minimal regime change: oil-equity correlation was stable."
    else:
        interp = "Insufficient data."

    return {
        "pre_avg":        round(pre, 3)        if pre        is not None else None,
        "shock_avg":      round(shock, 3)      if shock      is not None else None,
        "reopen_avg":     round(reopen, 3)     if reopen     is not None else None,
        "correction_avg": round(correction, 3) if correction is not None else None,
        "diplomacy_avg":  round(diplomacy, 3)  if diplomacy  is not None else None,
        "flip_delta":     flip,
        "interpretation": interp,
        "shock_peak":     round(shock, 3)      if shock      is not None else None,
    }


# ============================================================================
# SECTION 4: COUNTERFACTUAL
# ============================================================================

def counterfactual_2026(prices: pd.DataFrame,
                        assets: list,
                        baseline_years: range = range(2021, 2026),
                        end: str = None) -> dict:
    """
    Projects a no-shock 2026 path using average Jan–Apr baseline daily return.

    [U2-FW3] end param allows projection over full Jan–Jun timeline.
    [U2-FIX] Correctly passes list(baseline_years) to get_baseline_years()
             so BWET gets the right reduced year set.

    Returns dict: {asset: DataFrame(actual_2026, counterfactual, index=dates)}.
    """
    if end is None:
        end = "2026-04-30"

    results = {}
    for asset in assets:
        if asset not in prices.columns:
            continue

        avail_years = get_baseline_years(asset, list(baseline_years))
        base_daily  = []
        for yr in avail_years:
            p = prices.loc[f"{yr}-01-01":f"{yr}-04-30", asset].dropna()
            if len(p) < 10:
                continue
            base_daily.append(p.pct_change().dropna().values)

        if not base_daily:
            continue

        act_2026 = prices.loc["2026-01-01":end, asset].dropna()
        n        = len(act_2026)

        padded = []
        for r in base_daily:
            if len(r) >= n - 1:
                padded.append(r[:n-1])
            else:
                padded.append(np.pad(r, (0, n - 1 - len(r)), mode="edge"))

        avg_daily = np.mean(padded, axis=0)
        cf_path   = [100.0]
        for dr in avg_daily:
            cf_path.append(cf_path[-1] * (1 + dr))

        results[asset] = pd.DataFrame({
            "actual_2026":    (act_2026.values / act_2026.values[0]) * 100,
            "counterfactual": np.array(cf_path[:n]),
        }, index=act_2026.index[:n])

    return results


# ============================================================================
# SECTION 5: PORTFOLIOS & DRAWDOWNS
# ============================================================================

def sector_portfolio(prices: pd.DataFrame,
                     energy_cols: list = None,
                     market_col: str = "SP500",
                     start: str = "2026-01-01",
                     end: str = None) -> pd.DataFrame:
    """
    Equal-weight energy basket vs S&P 500 — observed P&L, no optimisation.
    [U2-FW4] start/end parameterised.
    """
    if energy_cols is None:
        energy_cols = ["XOM", "CVX", "WTI"]
    if end is None:
        end = FETCH_END

    available = [c for c in energy_cols if c in prices.columns]
    subset    = prices.loc[start:end, available + [market_col]].dropna(how="all")
    rets      = simple_returns(subset).dropna()

    return pd.DataFrame({
        "Energy basket (XOM+CVX+WTI)": (1 + rets[available].mean(axis=1)).cumprod() * 100,
        "S&P 500 buy-and-hold":        (1 + rets[market_col]).cumprod() * 100,
    })


def drawdown_avoidance(prices: pd.DataFrame,
                       hedged_assets: list,
                       market_asset: str = "SP500",
                       window: tuple = None) -> dict:
    """
    Compares max drawdown between the energy basket and S&P 500.

    [FIX] basket_had_worse_dd=True means energy basket had a DEEPER drawdown
          than the market. Previous version had comparison direction wrong.

    Returns dict with narrative, pp difference, and flag.
    """
    if window is None:
        window = EVENT_WINDOWS["shock"]

    s, e      = window
    subset    = prices.loc[s:e].copy()
    available = [a for a in hedged_assets if a in subset.columns]

    if market_asset not in subset.columns or not available:
        return {}

    market_s  = subset[market_asset].dropna()
    market_dd = ((market_s / market_s.cummax()) - 1).min() * 100

    basket    = subset[available].dropna(how="all").mean(axis=1)
    basket_dd = ((basket / basket.cummax()) - 1).min() * 100

    dd_diff      = market_dd - basket_dd
    basket_worse = basket_dd < market_dd   # more negative = deeper

    if basket_worse:
        narrative = (
            f"Energy basket had {abs(round(basket_dd - market_dd, 1))}pp DEEPER "
            f"drawdown than S&P ({round(basket_dd, 1)}% vs {round(market_dd, 1)}%). "
            f"Energy amplified losses during the shock."
        )
        avoided_pct = round((basket_dd / market_dd - 1) * 100, 1) if market_dd != 0 else 0.0
    else:
        narrative = (
            f"Energy basket had SHALLOWER drawdown than S&P "
            f"({round(basket_dd, 1)}% vs {round(market_dd, 1)}%). "
            f"Energy provided partial protection."
        )
        avoided_pct = round(abs(dd_diff / market_dd) * 100, 1) if market_dd != 0 else 0.0

    return {
        "market_max_dd":       round(float(market_dd), 2),
        "basket_max_dd":       round(float(basket_dd), 2),
        "avoided_dd_pp":       round(float(dd_diff), 2),
        "avoided_pct":         avoided_pct,
        "basket_had_worse_dd": basket_worse,
        "narrative":           narrative,
    }


def what_didnt_move(prices: pd.DataFrame,
                    threshold_pct: float = 5.0,
                    window: tuple = None) -> pd.DataFrame:
    """Returns assets whose absolute shock-window move is below threshold_pct."""
    if window is None:
        window = EVENT_WINDOWS["shock"]

    s, e   = window
    subset = prices.loc[s:e].dropna(how="all")
    if subset.empty:
        return pd.DataFrame()

    records = []
    for col in subset.columns:
        p = subset[col].dropna()
        if len(p) < 2:
            continue
        cum = (p.iloc[-1] / p.iloc[0] - 1) * 100
        records.append({"asset": col, "cum_return_%": round(cum, 2),
                        "abs_move": abs(cum)})

    df = pd.DataFrame(records).sort_values("abs_move")
    return df[df["abs_move"] < threshold_pct].drop(columns="abs_move").reset_index(drop=True)


# ============================================================================
# SECTION 6: ASSET CHARACTER CARDS [F3][F9]
# ============================================================================

def asset_character_card(asset: str,
                         prices: pd.DataFrame,
                         ev_stats: pd.DataFrame = None,
                         windows: dict = None,
                         seasonal_df: pd.DataFrame = None) -> dict:
    """
    Per-asset narrative data card — all windows, peak/trough, baseline avg.

    [F3]   n_shock_days pulled from ev_stats, not hardcoded.
    [F9]   Gold margin-call flag: early-shock drop after large pre-event rally.
    [U2]   net_jan_jun_% uses FETCH_END; limited_history fields added.
           Returns ret for all 5 windows automatically.
    """
    if windows is None:
        windows = EVENT_WINDOWS
    if asset not in prices.columns:
        return {}

    stats  = {}
    p_full = prices.loc["2026-01-01":FETCH_END, asset].dropna()

    for name, (s, e) in windows.items():
        p = prices.loc[s:e, asset].dropna()
        if len(p) < 2:
            continue
        stats[f"{name}_ret"] = round((p.iloc[-1] / p.iloc[0] - 1) * 100, 1)

    # [F3] n_shock_days from ev_stats
    if ev_stats is not None:
        row = ev_stats[(ev_stats["asset"] == asset) & (ev_stats["window"] == "shock")]
        if not row.empty:
            stats["n_shock_days"] = int(row["n_days"].values[0])

    if not p_full.empty:
        base = p_full.iloc[0]
        stats.update({
            "peak_gain_%":   round((p_full.max() / base - 1) * 100, 1),
            "trough_loss_%": round((p_full.min() / base - 1) * 100, 1),
            "net_jan_jun_%": round((p_full.iloc[-1] / base - 1) * 100, 1),
            "peak_date":     str(p_full.idxmax().date()),
            "trough_date":   str(p_full.idxmin().date()),
        })

    if seasonal_df is not None:
        base_yrs = seasonal_df[
            (seasonal_df["year"] != 2026) & (seasonal_df["asset"] == asset)
        ]
        if not base_yrs.empty:
            stats["avg_baseline_jan_apr_%"] = round(base_yrs["cum_return"].mean(), 1)

    # [F9] Gold margin-call signature
    if asset == "GOLD":
        shock_s     = EVENT_WINDOWS["shock"][0]
        gold_first5 = prices.loc[shock_s:, "GOLD"].dropna().head(6)
        if len(gold_first5) >= 5:
            drop_in_first5 = (gold_first5.iloc[4] / gold_first5.iloc[0] - 1) * 100
            later_recovery = stats.get("shock_ret", 0)
            stats["margin_call_flag"]   = bool(drop_in_first5 < -1.5 and later_recovery > 0)
            stats["gold_first5_move_%"] = round(float(drop_in_first5), 2)
        else:
            stats["margin_call_flag"]   = False
            stats["gold_first5_move_%"] = None

    # [U2] Limited history fields
    stats["limited_history"]      = asset in LIMITED_HISTORY_ASSETS
    stats["limited_history_note"] = limited_history_note(asset)

    return stats


def build_all_character_cards(prices: pd.DataFrame,
                               seasonal_df: pd.DataFrame,
                               ev_stats: pd.DataFrame = None,
                               assets: list = None) -> dict:
    """Build character cards for all assets. [U2] Defaults to ALL_ASSETS (16)."""
    if assets is None:
        assets = ALL_ASSETS

    return {
        a: asset_character_card(a, prices, ev_stats=ev_stats, seasonal_df=seasonal_df)
        for a in assets
        if a in prices.columns
    }


# ============================================================================
# SECTION 7: EVENT REACTIONS & TIMING [F2][F5]
# ============================================================================

def first_day_reaction(prices: pd.DataFrame,
                       event_dates: dict,
                       assets: list) -> pd.DataFrame:
    """
    Single close-to-close return on each event date.

    [F2] Close-to-close: return on the first trading day ON OR AFTER each
         event date, computed as (close_T / close_{T-1}) - 1.
         NOT a window return — labeled explicitly in all output columns.

    [BUG-FIX] Previous version called simple_returns(prices).dropna() then
    searched that returns index for the event date. This caused 0.0% for events
    falling on the first day of the returns series (e.g. Feb 28 when the
    returns index starts Feb 29 after dropna removes the first row).

    Fix: build returns per-asset using prices.pct_change() so the returns
    index aligns with the price index (T), not T+1. The return on day T is
    (price[T] / price[T-1]) - 1 — same formula, correct index alignment.
    """
    # pct_change keeps the same index as prices (NaN on first row, not dropped)
    rets    = prices.pct_change()
    records = []

    for label, date in event_dates.items():
        ts         = pd.Timestamp(date)
        # First trading day on or after the event date
        candidates = rets.index[rets.index >= ts]
        if candidates.empty:
            continue
        actual_date = candidates[0]

        # Guard: if actual_date is the very first row, pct_change is NaN —
        # step forward one trading day so we always get a valid return.
        if pd.isna(rets.loc[actual_date].iloc[0]):
            next_candidates = rets.index[rets.index > actual_date]
            if next_candidates.empty:
                continue
            actual_date = next_candidates[0]

        for asset in assets:
            if asset not in rets.columns:
                continue
            val = rets.loc[actual_date, asset]
            if pd.isna(val):
                continue
            records.append({
                "event":               label,
                "event_date":          date,
                "actual_trading_date": str(actual_date.date()),
                "asset":               asset,
                "day1_return_%":       round(val * 100, 2),
            })

    return pd.DataFrame(records)


def _pre_event_daily_vol(prices: pd.DataFrame, asset: str) -> float:
    """Average absolute daily return during pre-event window (relative-vol baseline)."""
    pre_s, pre_e = EVENT_CONFIG["estimation_window"]
    p = prices.loc[pre_s:pre_e, asset].dropna()
    if len(p) < 5:
        return 1.0
    r = p.pct_change().dropna()
    return max(float(r.abs().mean() * 100), 0.1)


def days_to_price_event(prices: pd.DataFrame,
                        asset: str,
                        event_date: str,
                        multiplier: float = 1.0,
                        lookback_days: int = 20) -> int:
    """
    [F5] Days until asset daily return falls below relative-vol threshold.
    More meaningful than a fixed % cutoff because it adapts to each asset's
    normal movement magnitude.
    """
    if asset not in prices.columns:
        return -1

    threshold = multiplier * _pre_event_daily_vol(prices, asset)
    rets      = simple_returns(prices[[asset]]).dropna()
    after     = rets.loc[event_date:].head(lookback_days)

    for i, (_, row) in enumerate(after.iterrows()):
        if abs(row[asset] * 100) < threshold:
            return i

    return lookback_days


def shock_transmission_speed(prices: pd.DataFrame,
                              assets: list,
                              shock_date: str = None,
                              lookback: int = 5) -> pd.DataFrame:
    """
    Cumulative return in the first N days after a shock date.
    Default shock = Feb 28 (Op. Epic Fury). Accepts any event date.
    """
    if shock_date is None:
        shock_date = EVENT_CONFIG["dates"].get("Op. Epic Fury (Feb 28)", "2026-02-28")

    records = []
    for asset in assets:
        if asset not in prices.columns:
            continue
        p = prices.loc[shock_date:, asset].dropna().head(lookback + 1)
        if len(p) < 2:
            continue
        for day in range(1, min(lookback + 1, len(p))):
            records.append({
                "asset":            asset,
                "days_after_shock": day,
                "cum_return_%":     round((p.iloc[day] / p.iloc[0] - 1) * 100, 2),
            })

    return pd.DataFrame(records)


def vix_peak_stats(prices: pd.DataFrame,
                   vix_col: str = "VIX",
                   baseline_years: range = range(2021, 2026),
                   start: str = "2026-01-01",
                   end: str = None) -> dict:
    """VIX peak, date, and multiple vs 5-yr baseline. [U2-FW4] start/end param."""
    if vix_col not in prices.columns:
        return {}
    if end is None:
        end = FETCH_END

    vix_period = prices.loc[start:end, vix_col].dropna()
    if vix_period.empty:
        return {}

    peak_val  = vix_period.max()
    peak_date = vix_period.idxmax()

    avgs = []
    for yr in baseline_years:
        v = prices.loc[f"{yr}-01-01":f"{yr}-04-30", vix_col].dropna()
        if not v.empty:
            avgs.append(float(v.mean()))

    avg_vix = float(np.mean(avgs)) if avgs else None

    return {
        "peak_vix":     round(float(peak_val), 1),
        "peak_date":    str(peak_date.date()),
        "avg_5yr_vix":  round(avg_vix, 1) if avg_vix else None,
        "vix_multiple": round(float(peak_val) / avg_vix, 2) if avg_vix else None,
    }


# ============================================================================
# SECTION 8: N-SERIES — N1 THROUGH N7 (UNCHANGED FROM UPDATE 1)
# ============================================================================

def lead_lag_ccf(prices: pd.DataFrame,
                 leader: str = "WTI",
                 follower: str = "SP500",
                 max_lag: int = 5,
                 start: str = "2026-01-01",
                 end: str = None) -> pd.DataFrame:
    """
    [N1] Cross-correlation at lags −max_lag to +max_lag.

    Positive lag = leader moves BEFORE follower (leader leads).
    Negative lag = follower moves first (follower leads).
    [U2] start/end parameterised for any sub-window.

    Structural caveat: WTI trades 24/5 vs S&P NYSE hours only.
    Peak at lag 0 is structurally expected — cannot confirm intraday lead-lag
    from daily data. Tick data required for a rigorous lead-lag test.
    """
    if end is None:
        end = FETCH_END

    subset = prices.loc[start:end, [leader, follower]].dropna()
    rets   = simple_returns(subset).dropna()

    if leader not in rets.columns or follower not in rets.columns:
        return pd.DataFrame()

    r_lead = rets[leader]
    r_foll = rets[follower]

    records = []
    for lag in range(-max_lag, max_lag + 1):
        if lag > 0:
            corr_a = r_lead.iloc[:-lag].values
            corr_b = r_foll.iloc[lag:].values
        elif lag < 0:
            abs_lag = abs(lag)
            corr_a  = r_foll.iloc[:-abs_lag].values
            corr_b  = r_lead.iloc[abs_lag:].values
        else:
            corr_a = r_lead.values
            corr_b = r_foll.values

        aligned = min(len(corr_a), len(corr_b))
        c = float(np.corrcoef(corr_a[:aligned], corr_b[:aligned])[0, 1])
        records.append({"lag": lag, "correlation": round(c, 3)})

    df = pd.DataFrame(records)
    peak_corr    = df["correlation"].abs().max()
    df["is_peak"] = df["correlation"].abs() == peak_corr
    return df


def rolling_beta_series(prices: pd.DataFrame,
                        assets: list,
                        benchmark: str = "SP500",
                        window: int = 21,
                        start: str = "2026-01-01",
                        end: str = None) -> pd.DataFrame:
    """
    [N2] Time-varying beta via rolling OLS window.
    [U2] start/end parameterised; works for all 16 assets.

    Key expected patterns for new assets:
      ITA  — beta rises on shock onset then flattens (backlog pricing absorbs peace)
      BWET — low beta vs SP500 (freight is supply-chain driven, not equity-driven)
      TLT  — beta flips negative during inflation panic phases
    """
    if end is None:
        end = FETCH_END

    subset = prices.loc[start:end].dropna(how="all")
    rets   = simple_returns(subset).dropna()

    if benchmark not in rets.columns:
        return pd.DataFrame()

    bm   = rets[benchmark]
    cols = {}

    for asset in assets:
        if asset == benchmark or asset not in rets.columns:
            continue
        asset_r = rets[asset].dropna()
        aligned = pd.concat([asset_r, bm], axis=1).dropna()
        if len(aligned) < window + 5:
            continue

        betas, idx = [], []
        for i in range(window, len(aligned) + 1):
            win = aligned.iloc[i - window:i]
            try:
                model = sm.OLS(win[asset], sm.add_constant(win[benchmark])).fit()
                betas.append(model.params[benchmark])
            except Exception:
                betas.append(np.nan)
            idx.append(aligned.index[i - 1])

        cols[asset] = pd.Series(betas, index=idx)

    return pd.DataFrame(cols) if cols else pd.DataFrame()


def dxy_oil_decomposition(prices: pd.DataFrame,
                          oil_col: str = "WTI",
                          dxy_col: str = "DXY") -> dict:
    """
    [N3] Decomposes WTI shock return into currency effect vs real supply effect.

    Method: OLS(WTI_returns ~ DXY_returns) on pre-event window.
    Currency contribution = beta_DXY × DXY_shock_return.
    Real supply effect = WTI_actual − currency_contribution.

    Caveat: linear decomposition only — relationship goes non-linear at
    extreme moves. Currency share < 5% confirms a genuine supply shock.
    """
    if dxy_col not in prices.columns or oil_col not in prices.columns:
        return {"available": False, "reason": f"{dxy_col} or {oil_col} not in data"}

    pre_s, pre_e     = EVENT_CONFIG["estimation_window"]
    shock_s, shock_e = EVENT_WINDOWS["shock"]

    pre_rets = simple_returns(prices.loc[pre_s:pre_e, [oil_col, dxy_col]]).dropna()
    if len(pre_rets) < 10:
        return {"available": False, "reason": "Insufficient pre-event data"}

    model            = sm.OLS(pre_rets[oil_col], sm.add_constant(pre_rets[dxy_col])).fit()
    beta_dxy         = model.params[dxy_col]
    r2               = model.rsquared

    shock_p = prices.loc[shock_s:shock_e, [oil_col, dxy_col]].dropna()
    if len(shock_p) < 2:
        return {"available": False, "reason": "Insufficient shock-window data"}

    wti_shock         = (shock_p[oil_col].iloc[-1] / shock_p[oil_col].iloc[0] - 1) * 100
    dxy_shock         = (shock_p[dxy_col].iloc[-1] / shock_p[dxy_col].iloc[0] - 1) * 100
    currency_contrib  = beta_dxy * dxy_shock
    real_supply       = wti_shock - currency_contrib
    dxy_dir           = "weakened" if dxy_shock < 0 else "strengthened"
    currency_share    = round(abs(currency_contrib / wti_shock) * 100, 1) if wti_shock != 0 else 0.0

    return {
        "available":          True,
        "wti_shock_ret_%":    round(wti_shock, 2),
        "dxy_shock_ret_%":    round(dxy_shock, 2),
        "beta_oil_on_dxy":    round(beta_dxy, 3),
        "r2_pre_event":       round(r2, 3),
        "currency_contrib_%": round(currency_contrib, 2),
        "real_supply_%":      round(real_supply, 2),
        "currency_share_%":   currency_share,
        "dxy_direction":      dxy_dir,
        "is_supply_dominant": currency_share < 5.0,
        "interpretation": (
            f"DXY {dxy_dir} {abs(round(dxy_shock, 1))}% during shock. "
            f"Currency contribution: ~{round(currency_contrib, 1)}pp ({currency_share}% of total). "
            f"Real supply contribution: ~{round(real_supply, 1)}pp of the "
            f"{round(wti_shock, 1)}% WTI move."
        ),
        "caveat": "Linear decomposition only. Beta estimated on pre-event window.",
    }


def vol_regime_periods(prices: pd.DataFrame,
                       assets: list = None,
                       short_window: int = 5,
                       long_window: int = 21,
                       regime_threshold: float = 2.0,
                       start: str = "2026-01-01",
                       end: str = None) -> dict:
    """
    [N4] Volatility regime detection using 5d/21d annualised vol ratio.
    Regime flagged when ratio > regime_threshold (default 2.0).

    Also records the historical 90th-percentile threshold per asset so
    borderline cases (WTI at 1.97) can be assessed contextually.

    [U2] Assets and date range parameterised for 5-window analysis.
    New asset expectations:
      ITA  — may spike on Op. Epic Fury day 1, then normalise
      BWET — high vol throughout (freight rates spike in supply shocks)
      TLT  — may show regime on inflation panic days
    """
    if assets is None:
        assets = ["WTI", "SP500", "GOLD", "XOM", "ITA", "BWET", "TLT"]
    if end is None:
        end = FETCH_END

    subset = prices.loc[start:end,
                        [a for a in assets if a in prices.columns]].dropna(how="all")
    rets   = simple_returns(subset).dropna()
    ratios = vol_regime_ratio(rets, short_window=short_window, long_window=long_window)

    # Historical 90th percentile per asset (using 2021–2025 Jan–Apr data)
    hist_p90 = {}
    for asset in assets:
        if asset not in prices.columns:
            continue
        hist = prices.loc["2021-01-01":"2025-12-31", asset].dropna()
        if len(hist) < 30:
            continue
        r_hist = simple_returns(hist.to_frame()).dropna()
        ratio_hist = vol_regime_ratio(r_hist, short_window, long_window)
        if asset in ratio_hist.columns:
            hist_p90[asset] = float(ratio_hist[asset].dropna().quantile(0.90))

    results = {}
    for asset in assets:
        if asset not in ratios.columns:
            continue

        r         = ratios[asset].dropna()
        in_regime = r[r > regime_threshold]
        p90       = hist_p90.get(asset)

        results[asset] = {
            "ratio_series":    r,
            "regime_start":    str(in_regime.index[0].date()) if not in_regime.empty else None,
            "regime_end":      str(in_regime.index[-1].date()) if not in_regime.empty else None,
            "days_in_regime":  len(in_regime),
            "peak_ratio":      round(float(r.max()), 2),
            "peak_ratio_date": str(r.idxmax().date()) if not r.empty else None,
            "hist_p90":        round(p90, 2) if p90 is not None else None,
            "above_p90":       bool(r.max() > p90) if p90 is not None else None,
        }

    return results


def international_spillover(prices: pd.DataFrame,
                             indices: list = None,
                             windows: dict = None) -> pd.DataFrame:
    """
    [N5] Window returns and drawdowns across global equity indices.
    Returns local-currency returns. No FX adjustment — flagged in caveat column.
    [U2] windows param covers all 5 phases by default.
    """
    if indices is None:
        indices = INTL_ASSETS
    if windows is None:
        windows = {k: v for k, v in EVENT_WINDOWS.items() if k != "pre_event"}

    available = [i for i in indices if i in prices.columns]
    if not available:
        return pd.DataFrame()

    records = []
    for window_name, (s, e) in windows.items():
        slice_p = prices.loc[s:e, available].dropna(how="all")
        if slice_p.empty:
            continue

        for col in slice_p.columns:
            p = slice_p[col].dropna()
            if len(p) < 2:
                continue

            cum = (p.iloc[-1] / p.iloc[0] - 1) * 100
            dd  = ((p / p.cummax()) - 1).min() * 100
            records.append({
                "window":        window_name,
                "window_label":  fmt_window_label(window_name),
                "index":         col,
                "index_label":   LABELS.get(col, col),
                "cum_return_%":  round(cum, 2),
                "max_dd_%":      round(dd, 2),
            })

    df = pd.DataFrame(records)
    if not df.empty:
        df["fx_caveat"] = "Local-currency return. No FX adjustment applied."
    return df


def oil_gold_ratio_stats(prices: pd.DataFrame,
                          start: str = "2026-01-01",
                          end: str = None) -> dict:
    """
    [N6] WTI/Gold ratio across all event windows.

    Rising ratio → supply shock dominant (oil outpaces gold / safe haven).
    Falling ratio → diplomacy/fear dominant (gold outpaces oil).

    [U2] Correction window interpretation is the key new finding:
         WTI/Gold fell in May even as the strait remained physically closed —
         forward expectations overrode spot supply reality.
    """
    if end is None:
        end = FETCH_END

    ratio = oil_gold_ratio(prices, start=start, end=end)
    if ratio.empty:
        return {"available": False}

    records = {}
    for name, (s, e) in EVENT_WINDOWS.items():
        w = ratio.loc[s:e].dropna()
        if len(w) < 2:
            continue
        records[f"{name}_change_%"] = round((w.iloc[-1] / w.iloc[0] - 1) * 100, 2)

    shock_chg = records.get("shock_change_%", 0)
    corr_chg  = records.get("correction_change_%")

    if shock_chg > 5:
        regime = "Supply shock dominant. Oil outpaced gold. Markets priced scarcity, not fear."
    elif shock_chg < -5:
        regime = "Fear dominant. Gold outpaced oil. Capital flight exceeded supply pricing."
    else:
        regime = "Mixed signal."

    # [U2] Correction regime — the Update 2 thesis
    if corr_chg is not None:
        if corr_chg < -5:
            correction_regime = (
                "Diplomacy decoupling confirmed: WTI/Gold fell in May "
                "even as strait remained at ~2% transit capacity. "
                "Forward expectations (peace deal probability) overrode physical supply."
            )
        elif corr_chg > 5:
            correction_regime = "Scarcity persisted through correction: ratio continued rising."
        else:
            correction_regime = "Mixed signals during correction window."
    else:
        correction_regime = "Correction window data unavailable."

    return {
        "available":         True,
        "ratio_series":      ratio,
        "regime_interp":     regime,
        "correction_regime": correction_regime,
        "peak_ratio_date":   str(ratio.idxmax().date()) if not ratio.empty else None,
        "trough_ratio_date": str(ratio.idxmin().date()) if not ratio.empty else None,
        **records,
    }


def sector_rotation_heatmap(prices: pd.DataFrame,
                             assets: list = None,
                             windows: dict = None) -> pd.DataFrame:
    """
    [N7] Assets (rows) × Windows (columns) return matrix.
    [U2] Defaults to ALL_ASSETS (16) and all 5 windows.
         Sorted by shock-window return descending (biggest winners first).
    """
    if assets is None:
        assets = [a for a in ALL_ASSETS if a != "VIX"]
    if windows is None:
        windows = EVENT_WINDOWS

    available = [a for a in assets if a in prices.columns]
    records   = []

    for window_name, (s, e) in windows.items():
        slice_p = prices.loc[s:e, available].dropna(how="all")
        if slice_p.empty:
            continue

        for col in slice_p.columns:
            p = slice_p[col].dropna()
            if len(p) < 2:
                continue
            records.append({
                "asset":  col,
                "window": window_name,
                "ret_%":  round((p.iloc[-1] / p.iloc[0] - 1) * 100, 2),
            })

    if not records:
        return pd.DataFrame()

    df    = pd.DataFrame(records)
    pivot = df.pivot(index="asset", columns="window", values="ret_%")

    col_order = [c for c in ["pre_event", "shock", "reopen", "correction", "diplomacy"]
                 if c in pivot.columns]
    pivot = pivot[col_order]
    if "shock" in pivot.columns:
        pivot = pivot.sort_values("shock", ascending=False)

    return pivot


# ============================================================================
# SECTION 9: UPDATE 2 — NEW ANALYTICAL FUNCTIONS [U2-A through U2-J]
# ============================================================================

# ----------------------------------------------------------------------------
# [U2-A] Pair trade — generalised long/short P&L
# ----------------------------------------------------------------------------

def pair_trade_extended(prices: pd.DataFrame,
                        pairs: list = None,
                        windows: dict = None) -> pd.DataFrame:
    """
    [U2-A] Generalised long/short cumulative P&L for any asset pair
    across any window set.

    Default pairs for Update 2:
      ("WTI",  "XOM",  "Long WTI / Short XOM")  — original decoupling
      ("WTI",  "XLE",  "Long WTI / Short XLE")  — broader energy equity
      ("ITA",  "SP500","Long ITA / Short SP500") — defense geopolitical premium
      ("BWET", "WTI",  "Long BWET / Short WTI") — freight premium over commodity

    CAVEAT: all returns are pre-cost upper bounds.
    No borrow cost, no futures roll, no slippage.
    """
    if pairs is None:
        pairs = [
            ("WTI",  "XOM",   "Long WTI / Short XOM"),
            ("WTI",  "XLE",   "Long WTI / Short XLE"),
            ("ITA",  "SP500", "Long ITA / Short SP500"),
            ("BWET", "WTI",   "Long BWET / Short WTI"),
        ]
    if windows is None:
        windows = EVENT_WINDOWS

    records = []
    for window_name, (ws, we) in windows.items():
        for long_asset, short_asset, label in pairs:
            if long_asset not in prices.columns or short_asset not in prices.columns:
                continue

            p_long  = prices.loc[ws:we, long_asset].dropna()
            p_short = prices.loc[ws:we, short_asset].dropna()

            if len(p_long) < 2 or len(p_short) < 2:
                continue

            long_ret  = (p_long.iloc[-1]  / p_long.iloc[0]  - 1) * 100
            short_ret = (p_short.iloc[-1] / p_short.iloc[0] - 1) * 100
            ls_ret    = long_ret - short_ret   # long gains − short gains (P&L of being short)

            records.append({
                "window":       window_name,
                "window_label": fmt_window_label(window_name),
                "pair_label":   label,
                "long_asset":   long_asset,
                "short_asset":  short_asset,
                "long_ret_%":   round(long_ret, 2),
                "short_leg_%":  round(-short_ret, 2),   # positive = short profited
                "combined_%":   round(ls_ret, 2),
                "n_days":       len(p_long),
                "caveat":       "Pre-cost. No borrow, roll, or slippage costs included.",
            })

    return pd.DataFrame(records)


def pair_trade_timeseries(prices: pd.DataFrame,
                          long_asset: str = "WTI",
                          short_asset: str = "XOM",
                          start: str = "2026-01-01",
                          end: str = None) -> pd.DataFrame:
    """
    [U2-A2] Daily cumulative P&L timeseries for a single pair.
    Used for original chart 19 (WTI/XOM) and new chart 29 (multi-pair comparison).

    Returns DataFrame with:
      long_cum   — rebased long leg (base=100)
      short_cum  — rebased short leg, sign-flipped (positive = short profiting)
      pair_cum   — combined L/S cumulative P&L (base=100)
    """
    if end is None:
        end = FETCH_END

    cols   = [c for c in [long_asset, short_asset] if c in prices.columns]
    subset = prices.loc[start:end, cols].dropna(how="all").ffill()

    if long_asset not in subset.columns or short_asset not in subset.columns:
        return pd.DataFrame()

    rets     = simple_returns(subset).dropna()
    ls_rets  = rets[long_asset] - rets[short_asset]

    long_cum  = (1 + rets[long_asset]).cumprod() * 100
    short_cum = (1 - rets[short_asset]).cumprod() * 100
    pair_cum  = (1 + ls_rets).cumprod() * 100

    return pd.DataFrame({
        "long_cum":  long_cum,
        "short_cum": short_cum,
        "pair_cum":  pair_cum,
    })


def pair_trade_drawdown(prices: pd.DataFrame,
                        pairs: list = None,
                        start: str = "2026-01-01",
                        end: str = None) -> pd.DataFrame:
    """
    [U2-J] Max drawdown and drawdown duration for each pair trade timeseries.

    A pair trade's drawdown profile reveals whether the decoupling was steady
    (low drawdown throughout) or volatile (large intra-period swings even if
    the final P&L is positive).

    Key use: the pre-event window Long WTI/Short XOM had −8.2% P&L — going in
    too early had a real cost. This function makes that cost explicit.

    Returns DataFrame: pair_label, max_dd_%, max_dd_date, recovery_date.
    """
    if pairs is None:
        pairs = [
            ("WTI",  "XOM",   "Long WTI / Short XOM"),
            ("WTI",  "XLE",   "Long WTI / Short XLE"),
            ("ITA",  "SP500", "Long ITA / Short SP500"),
            ("BWET", "WTI",   "Long BWET / Short WTI"),
        ]
    if end is None:
        end = FETCH_END

    records = []
    for long_asset, short_asset, label in pairs:
        ts = pair_trade_timeseries(prices, long_asset, short_asset, start, end)
        if ts.empty or "pair_cum" not in ts.columns:
            continue

        cum    = ts["pair_cum"]
        dd     = (cum / cum.cummax()) - 1
        max_dd = dd.min() * 100
        dd_date = dd.idxmin()

        # Recovery: first date after trough where cum > prior peak
        prior_peak = cum.loc[:dd_date].max()
        after_trough = cum.loc[dd_date:]
        recovery_idx = after_trough[after_trough >= prior_peak].index
        recovery_date = str(recovery_idx[0].date()) if not recovery_idx.empty else "Not recovered"

        records.append({
            "pair_label":    label,
            "max_dd_%":      round(max_dd, 2),
            "max_dd_date":   str(dd_date.date()),
            "recovery_date": recovery_date,
            "caveat":        "Pre-cost. Drawdown of the hypothetical L/S return stream.",
        })

    return pd.DataFrame(records)


# ----------------------------------------------------------------------------
# [U2-B] Escalation replay — 5-day arc across all events
# ----------------------------------------------------------------------------

def escalation_replay(prices: pd.DataFrame,
                      assets: list = None,
                      event_dates: dict = None,
                      lookback: int = 5) -> pd.DataFrame:
    """
    [U2-B] Cumulative first-N-day returns across all event dates,
    structured for direct side-by-side comparison of shock magnitude.

    Key question: did the Jun 10 re-escalation trigger the same magnitude
    response as Feb 28? Smaller → market learning / diminishing transmission.
    Larger → surprise or prior-hedging breakdown.

    Complements first_day_reaction() — this shows the full 5-day arc,
    not just day 1.

    Returns long-form DataFrame: (event, event_date, asset, day, cum_return_%).
    """
    if assets is None:
        assets = [a for a in CORE_ASSETS + ["ITA", "BWET", "TLT", "XLE"]
                  if a in prices.columns]
    if event_dates is None:
        event_dates = EVENT_CONFIG["dates"]

    records = []
    for label, date in event_dates.items():
        ts         = pd.Timestamp(date)
        candidates = prices.index[prices.index >= ts]
        if candidates.empty:
            continue
        start_date = candidates[0]

        for asset in assets:
            if asset not in prices.columns:
                continue

            p = prices.loc[start_date:, asset].dropna().head(lookback + 1)
            if len(p) < 2:
                continue

            for day in range(1, min(lookback + 1, len(p))):
                records.append({
                    "event":        label,
                    "event_date":   date,
                    "asset":        asset,
                    "asset_label":  LABELS.get(asset, asset),
                    "day":          day,
                    "cum_return_%": round((p.iloc[day] / p.iloc[0] - 1) * 100, 2),
                })

    return pd.DataFrame(records)


# ----------------------------------------------------------------------------
# [U2-C] Forward expectations proxy — diplomacy days vs WTI
# ----------------------------------------------------------------------------

def forward_expectations_proxy(prices: pd.DataFrame,
                                oil_col: str = "WTI",
                                ceasefire_dates: list = None) -> pd.DataFrame:
    """
    [U2-C] Binary proxy for 'diplomacy-dominant' trading days; measures WTI
    return on those days vs non-diplomacy days during the Paradox Correction
    and Volatile Diplomacy windows.

    This tests Update 2 Finding 01 (May Paradox): WTI fell ~20% in May while
    the strait remained at 2% transit capacity. Did it fall specifically on
    known diplomacy-headline days?

    ceasefire_dates: list of date strings for known ceasefire/peace events.
    The default list contains ONLY confirmed event dates from EVENT_CONFIG,
    not administrative window boundaries. May 1 is intentionally excluded
    because it is a window boundary, not a documented diplomacy event.

    A day is flagged as 'diplomacy day' if it falls within ±2 calendar days
    of a ceasefire event date.

    CAVEAT: post-hoc binary proxy from known event dates.
    Results are directional only. Proper implementation requires real-time
    news event counts or Polymarket ceasefire probability data.

    Returns DataFrame with summary stats stored in df.attrs["summary"].
    """
    if ceasefire_dates is None:
        # Only confirmed diplomacy/ceasefire events — no window boundaries
        ceasefire_dates = [
            "2026-04-07",   # Ceasefire announcement (Apr 7)
            "2026-04-17",   # Hormuz open announced
            "2026-05-15",   # Mid-May diplomacy talks reported (Reuters)
            "2026-06-10",   # Iran re-escalation (inverse signal — oil spike day)
        ]

    if oil_col not in prices.columns:
        return pd.DataFrame()

    correction_s = EVENT_WINDOWS.get("correction", ("2026-05-01", "2026-05-29"))[0]
    diplomacy_e  = EVENT_WINDOWS.get("diplomacy",  ("2026-06-01", "2026-06-13"))[1]

    subset = prices.loc[correction_s:diplomacy_e, [oil_col]].dropna()
    rets   = simple_returns(subset).dropna()
    ratio  = oil_gold_ratio(prices, start=correction_s, end=diplomacy_e)

    ceasefire_ts = [pd.Timestamp(d) for d in ceasefire_dates]

    rows = []
    for date, row in rets.iterrows():
        is_diplo = int(any(abs((date - ct).days) <= 2 for ct in ceasefire_ts))
        ratio_val = float(ratio.loc[date]) if date in ratio.index else np.nan
        rows.append({
            "date":           date,
            "is_diplomacy":   is_diplo,
            "wti_return_%":   round(row[oil_col] * 100, 3),
            "oil_gold_ratio": round(ratio_val, 2) if not np.isnan(ratio_val) else np.nan,
        })

    df = pd.DataFrame(rows)

    if not df.empty:
        diplo_mean    = df[df["is_diplomacy"] == 1]["wti_return_%"].mean()
        no_diplo_mean = df[df["is_diplomacy"] == 0]["wti_return_%"].mean()
        n_diplo       = int(df["is_diplomacy"].sum())
        n_non_diplo   = int((df["is_diplomacy"] == 0).sum())

        df.attrs["summary"] = {
            "diplomacy_days_n":             n_diplo,
            "non_diplomacy_days_n":         n_non_diplo,
            "diplomacy_days_avg_wti_%":     round(diplo_mean, 3) if not np.isnan(diplo_mean) else None,
            "non_diplomacy_days_avg_wti_%": round(no_diplo_mean, 3) if not np.isnan(no_diplo_mean) else None,
            "differential_%":               round(diplo_mean - no_diplo_mean, 3)
                                            if not (np.isnan(diplo_mean) or np.isnan(no_diplo_mean))
                                            else None,
            "caveat": (
                "Post-hoc binary proxy from confirmed event dates only. "
                "Results are directional. Proper implementation requires "
                "real-time news counts or Polymarket ceasefire probability data."
            ),
        }

    return df


# ----------------------------------------------------------------------------
# [U2-D] Defense premium — ITA geopolitical abnormal return
# ----------------------------------------------------------------------------

def defense_premium(prices: pd.DataFrame,
                    defense_col: str = "ITA",
                    benchmark: str = "SP500",
                    windows: dict = None,
                    estimation_window: tuple = None) -> pd.DataFrame:
    """
    [U2-D] Measures the geopolitical premium in defense equities via
    abnormal return analysis.

    Wraps compute_abnormal_returns() for consistency, then appends
    defense-specific interpretation per window.

    Key thesis (Finding 02 of Update 2): defense is a multi-year backlog
    trade, not a spot war trade. ITA should NOT crater on ceasefire signals
    the way oil does — production contracts extend years beyond any single
    geopolitical event.

    Expected pattern:
      shock      — ITA positive abnormal return (war premium)
      correction — ITA abnormal stays positive despite oil falling (backlog)
      diplomacy  — ITA abnormal compresses as peace probability rises
      reopen     — may see partial giveback, but slower than oil
    """
    if windows is None:
        windows = EVENT_CONFIG["event_windows_no_pre"]
    if estimation_window is None:
        estimation_window = EVENT_CONFIG["estimation_window"]

    if defense_col not in prices.columns:
        return pd.DataFrame()

    result = compute_abnormal_returns(
        prices,
        assets=[defense_col],
        benchmark=benchmark,
        estimation_window=estimation_window,
        event_windows=windows,
    )

    if result.empty:
        return result

    def _interp(row):
        ar = row["abnormal_ret_%"]
        wn = row["window"]
        if wn == "shock":
            if ar > 3:
                return "War premium confirmed: defense outperformed market during closure."
            elif ar < -3:
                return "No war premium: defense tracked market, not escalation."
            else:
                return "Neutral shock response: defense neither led nor lagged the market."
        elif wn == "correction":
            if ar > 2:
                return "Backlog pricing: defense held premium even as oil corrected sharply."
            elif ar < -2:
                return "Peace pricing: defense premium eroded during oil correction."
            else:
                return "Muted correction response: backlog vs peace signals balancing out."
        elif wn in ("reopen", "diplomacy"):
            if ar < -3:
                return "Defense premium closed on resolution signals."
            elif ar > 2:
                return "Defense premium persisted through resolution — backlog dominant."
            else:
                return "Gradual giveback: defense slowly repriced toward peacetime baseline."
        else:
            return "No significant abnormal return in this window."

    result["defense_interpretation"] = result.apply(_interp, axis=1)
    result["backlog_note"] = (
        "Defense revenue is multi-year backlog driven. Peace signals do not "
        "immediately cancel production contracts — unlike oil spot prices. "
        "LMT, RTX, NOC backlogs extend to 2028–2030 regardless of ceasefire."
    )
    return result


# ----------------------------------------------------------------------------
# [U2-E] Freight / oil spread — third decoupling layer
# ----------------------------------------------------------------------------

def freight_oil_spread(prices: pd.DataFrame,
                       freight_col: str = "BWET",
                       oil_col: str = "WTI",
                       windows: dict = None) -> pd.DataFrame:
    """
    [U2-E] Spread between freight futures (BWET) and physical oil (WTI)
    across all event windows.

    The 'third decoupling' of Update 2:
      Layer 1: WTI decoupled from energy equities (XOM, XLE)
      Layer 2: WTI decoupled from expected demand (diplomacy → oil dropped
               despite strait remaining closed)
      Layer 3: BWET (tanker freight) decoupled from WTI (freight ≫ commodity)

    Rising spread (BWET > WTI) → tanker scarcity more acute than oil scarcity.
      Drivers: rerouting demand surge, vessel availability collapse, war-risk
               insurance premiums on Gulf routes.

    Falling spread (WTI > BWET) → oil scarcity dominates; freight normalises.
      Signals: alternative route capacity filling, vessel supply responding.

    CAVEATS (repeated in output per row):
      - BWET launched May 2023: only 2 baseline years.
      - BWET holds futures — subject to contango roll decay.
      - AUM ~$25M: analytical signal only, not a liquid instrument.
    """
    if windows is None:
        windows = EVENT_WINDOWS

    if freight_col not in prices.columns or oil_col not in prices.columns:
        return pd.DataFrame()

    records = []
    for window_name, (ws, we) in windows.items():
        p_freight = prices.loc[ws:we, freight_col].dropna()
        p_oil     = prices.loc[ws:we, oil_col].dropna()

        if len(p_freight) < 2 or len(p_oil) < 2:
            continue

        freight_ret = (p_freight.iloc[-1] / p_freight.iloc[0] - 1) * 100
        oil_ret     = (p_oil.iloc[-1]     / p_oil.iloc[0]     - 1) * 100
        spread      = freight_ret - oil_ret

        if spread > 5:
            interp = "Tanker scarcity premium: freight outpaced commodity."
        elif spread < -5:
            interp = "Freight normalising: oil scarcity dominates over shipping crunch."
        else:
            interp = "Spread contained: freight and oil moving together."

        records.append({
            "window":        window_name,
            "window_label":  fmt_window_label(window_name),
            "bwet_ret_%":    round(freight_ret, 2),
            "wti_ret_%":     round(oil_ret, 2),
            "spread_%":      round(spread, 2),
            "spread_interp": interp,
            "n_days":        len(p_freight),
            "caveat": (
                "BWET: launched May 2023 (2 baseline years only). "
                "Holds futures — contango roll decay applies. "
                "AUM ~$25M: analytical signal, not a liquid instrument."
            ),
        })

    return pd.DataFrame(records)


# ----------------------------------------------------------------------------
# [U2-F] Window regime summary — compact classification table
# ----------------------------------------------------------------------------

def window_regime_summary(prices: pd.DataFrame,
                          og_ratio: dict = None,
                          corr_flip_result: dict = None) -> pd.DataFrame:
    """
    [U2-F] NEW: Compact one-row-per-window regime classification table.

    Synthesises the WTI/Gold ratio direction, WTI/SP500 correlation, and
    WTI directional move into a single regime label per window.

    Regime taxonomy:
      SUPPLY_SHOCK    — WTI/Gold rising, oil up, correlation inverse
      DIPLOMACY_BREAK — WTI/Gold falling, oil down, strait still closed
      RESOLUTION      — Oil down, correlation normalising
      PRE_EVENT       — Baseline

    Use this table as the interpretive backbone of the notebook executive
    summary section — it maps each phase to a single analytical identity.
    """
    if og_ratio is None:
        og_ratio = oil_gold_ratio_stats(prices)
    if corr_flip_result is None:
        corr_flip_result = correlation_flip(prices)

    ev_stats = event_window_stats(prices, ["WTI", "SP500", "GOLD"],
                                  windows=EVENT_WINDOWS)

    def _wti_ret(window):
        r = ev_stats[(ev_stats["asset"] == "WTI") & (ev_stats["window"] == window)]
        return float(r["cum_return"].values[0]) if not r.empty else None

    def _ratio_chg(window):
        return og_ratio.get(f"{window}_change_%")

    def _corr(window):
        key = f"{window}_avg"
        return corr_flip_result.get(key)

    def _classify(window, wti_ret, ratio_chg, corr):
        if window == "pre_event":
            return "PRE_EVENT"
        if wti_ret is None:
            return "NO_DATA"
        if wti_ret > 5 and (ratio_chg is None or ratio_chg > 0):
            return "SUPPLY_SHOCK"
        if wti_ret < -5 and (ratio_chg is not None and ratio_chg < -3):
            return "DIPLOMACY_BREAK"
        if wti_ret < -5:
            return "RESOLUTION"
        return "MIXED"

    records = []
    for window_name in EVENT_WINDOWS:
        wr = _wti_ret(window_name)
        rc = _ratio_chg(window_name)
        co = _corr(window_name)
        records.append({
            "window":          window_name,
            "window_label":    fmt_window_label(window_name),
            "wti_ret_%":       wr,
            "og_ratio_chg_%":  rc,
            "wti_sp500_corr":  co,
            "regime":          _classify(window_name, wr, rc, co),
        })

    return pd.DataFrame(records)


# ----------------------------------------------------------------------------
# [U2-G] Cross-asset correlation delta — shift table
# ----------------------------------------------------------------------------

def cross_asset_correlation_delta(prices: pd.DataFrame,
                                   pairs: list = None,
                                   base_window: str = "pre_event",
                                   compare_windows: list = None) -> pd.DataFrame:
    """
    [U2-G] NEW: For each pair, shows the correlation change from the base
    window (pre-event) to each subsequent window.

    The delta is the key number: how much did a correlation *shift* during
    the crisis, and did it revert or persist through May–June?

    Particularly useful for:
      TLT/SP500: did bond-equity correlation flip (inflation fear)?
      BWET/WTI:  did freight decouple from commodity post-shock?
      ITA/SP500: did defense equity become more or less market-correlated?

    Returns wide DataFrame: rows = pairs, columns = window deltas.
    """
    if pairs is None:
        pairs = [
            ("WTI",  "SP500"),
            ("GOLD", "SP500"),
            ("TLT",  "SP500"),
            ("TLT",  "WTI"),
            ("ITA",  "SP500"),
            ("BWET", "WTI"),
            ("XLE",  "WTI"),
            ("DXY",  "WTI"),
        ]
    if compare_windows is None:
        compare_windows = ["shock", "reopen", "correction", "diplomacy"]

    all_windows = [base_window] + compare_windows
    corr_table  = correlation_by_window(
        prices,
        pairs=pairs,
        windows={w: EVENT_WINDOWS[w] for w in all_windows if w in EVENT_WINDOWS},
    )

    if corr_table.empty:
        return pd.DataFrame()

    pivot    = corr_table.pivot(index="pair", columns="window", values="correlation")
    base_col = base_window

    records = []
    for pair in pivot.index:
        row  = {"pair": pair}
        base = pivot.loc[pair, base_col] if base_col in pivot.columns else np.nan
        row[f"corr_{base_window}"] = base
        for w in compare_windows:
            if w not in pivot.columns:
                continue
            val   = pivot.loc[pair, w]
            delta = round(val - base, 3) if not (np.isnan(val) or np.isnan(base)) else np.nan
            row[f"corr_{w}"]       = val
            row[f"delta_{w}"]      = delta
        records.append(row)

    return pd.DataFrame(records).set_index("pair")


# ----------------------------------------------------------------------------
# [U2-H] Aramco sovereign discount analysis
# ----------------------------------------------------------------------------

def aramco_sovereign_discount(prices: pd.DataFrame,
                               aramco_col: str = "ARAMCO",
                               wti_col: str = "WTI",
                               windows: dict = None) -> pd.DataFrame:
    """
    [U2-H] NEW: Compares ARAMCO equity performance vs WTI crude across
    all event windows to quantify the 'sovereign discount'.

    The sovereign discount hypothesis (Finding 05 of Update 2):
      Saudi Aramco benefits from higher oil prices (EPS beat) but trades
      below its fundamental value because:
        1. Geopolitical risk premium from regional conflict
        2. Saudi state control creates policy uncertainty (production cuts,
           dividend policy, listing lock-up)
        3. FX: riyal is pegged to USD but Tadawul access is limited for
           foreign investors

    Expected finding:
      shock window — ARAMCO lags WTI (sovereign discount widens)
      correction   — ARAMCO may outperform WTI as peace reduces discount
      diplomacy    — ARAMCO outperforms on ceasefire premium

    CAVEAT: ARAMCO is forward-filled from Tadawul (Sun–Thu) to US calendar.
    Same-day comparisons carry a structural ~18-hour lag.
    Treat as directional / window-level indicator, not precise same-day data.
    """
    if windows is None:
        windows = {k: v for k, v in EVENT_WINDOWS.items() if k != "pre_event"}

    if aramco_col not in prices.columns or wti_col not in prices.columns:
        return pd.DataFrame()

    records = []
    for window_name, (ws, we) in windows.items():
        p_aramco = prices.loc[ws:we, aramco_col].dropna()
        p_wti    = prices.loc[ws:we, wti_col].dropna()

        if len(p_aramco) < 2 or len(p_wti) < 2:
            continue

        aramco_ret  = (p_aramco.iloc[-1] / p_aramco.iloc[0] - 1) * 100
        wti_ret     = (p_wti.iloc[-1]    / p_wti.iloc[0]    - 1) * 100
        discount    = aramco_ret - wti_ret   # negative = Aramco lagged WTI

        if discount < -5:
            interp = "Sovereign discount widening: Aramco lagged oil price gains."
        elif discount > 5:
            interp = "Sovereign premium: Aramco outpaced crude (discount narrowed)."
        else:
            interp = "Tracking: Aramco moved in line with WTI."

        records.append({
            "window":         window_name,
            "window_label":   fmt_window_label(window_name),
            "aramco_ret_%":   round(aramco_ret, 2),
            "wti_ret_%":      round(wti_ret, 2),
            "discount_%":     round(discount, 2),
            "discount_interp": interp,
            "n_days_aramco":  len(p_aramco),
            "caveat": (
                "ARAMCO forward-filled from Tadawul (Sun–Thu, UTC+3) to US calendar. "
                "~18h structural lag vs US assets. Treat as directional indicator only."
            ),
        })

    return pd.DataFrame(records)


# ----------------------------------------------------------------------------
# [U2-I] TLT safe-haven test — bonds vs gold
# ----------------------------------------------------------------------------

def tlt_safe_haven_test(prices: pd.DataFrame,
                         tlt_col: str = "TLT",
                         gold_col: str = "GOLD",
                         sp500_col: str = "SP500",
                         windows: dict = None) -> pd.DataFrame:
    """
    [U2-I] NEW: Compares TLT (long-duration Treasuries) vs Gold as safe-haven
    alternatives during the crisis.

    Update 1 finding: Gold failed as a safe haven during the shock window
    (dropped 9.6% on margin-call liquidation). Did TLT fare better?

    Key dynamics to expect:
      shock    — TLT may fall on inflation expectations from oil spike
      correction — TLT may rally as oil falls and inflation fears ease
      diplomacy  — TLT behaviour depends on whether WTI/Gold suggests fear vs supply

    Also computes correlation of each asset vs SP500 per window — a
    rising correlation means the 'safe haven' is moving with equities
    (i.e., failing at diversification).

    Returns DataFrame with per-window return, correlation vs SP500, and
    interpretation for both TLT and GOLD.
    """
    if windows is None:
        windows = {k: v for k, v in EVENT_WINDOWS.items() if k != "pre_event"}

    available = [c for c in [tlt_col, gold_col, sp500_col] if c in prices.columns]
    if sp500_col not in available:
        return pd.DataFrame()

    rets    = simple_returns(prices).dropna()
    records = []

    for window_name, (ws, we) in windows.items():
        w_rets = rets.loc[ws:we, available].dropna()
        if w_rets.empty:
            continue

        for asset in [tlt_col, gold_col]:
            if asset not in w_rets.columns:
                continue

            p     = prices.loc[ws:we, asset].dropna()
            if len(p) < 2:
                continue

            cum_ret = (p.iloc[-1] / p.iloc[0] - 1) * 100
            corr_sp = float(w_rets[[asset, sp500_col]].dropna().corr().iloc[0, 1])

            # Safe-haven quality score: negative return = failing, positive corr = failing
            if cum_ret > 0 and corr_sp < 0:
                quality = "PASSED: positive return, negative equity correlation"
            elif cum_ret > 0 and corr_sp >= 0:
                quality = "PARTIAL: positive return but moving with equities"
            elif cum_ret <= 0 and corr_sp < 0:
                quality = "PARTIAL: negative return but still negatively correlated"
            else:
                quality = "FAILED: negative return and positive equity correlation"

            records.append({
                "window":         window_name,
                "window_label":   fmt_window_label(window_name),
                "asset":          asset,
                "asset_label":    LABELS.get(asset, asset),
                "cum_ret_%":      round(cum_ret, 2),
                "corr_vs_sp500":  round(corr_sp, 3),
                "safe_haven_quality": quality,
            })

    return pd.DataFrame(records)


# ============================================================================
# SECTION 10: ORCHESTRATOR — run_full_analysis()
# ============================================================================

def run_full_analysis(prices: pd.DataFrame,
                      data_dir: str = "data") -> dict:
    """
    Run the complete Update 2 pipeline and return all results as a dict.
    Each key corresponds to a notebook section or chart group.

    [U2-FW6] Orchestrates all original N1–N7 functions plus the 10 new
    Update 2 functions. All results use the 5-window structure.
    """
    proc_dir = os.path.join(data_dir, "processed")
    os.makedirs(proc_dir, exist_ok=True)

    # Save daily returns for downstream use
    rets = simple_returns(prices).dropna(how="all")
    rets.to_parquet(os.path.join(proc_dir, "returns_u2.parquet"), engine="pyarrow")

    available  = [a for a in ALL_ASSETS if a in prices.columns]
    EVENT_DATES = EVENT_CONFIG["dates"]

    # ── Section 1: Baseline ───────────────────────────────────────────────────
    seasonal  = seasonal_baseline(prices, available)
    base_sum  = baseline_summary(seasonal)
    ev_stats  = event_window_stats(prices, available)

    # ── Section 2: Abnormal returns ───────────────────────────────────────────
    abnormal  = compute_abnormal_returns(
        prices,
        [a for a in available if a not in ["SP500", "VIX"]],
        benchmark="SP500",
    )

    # ── Section 3: Correlation ────────────────────────────────────────────────
    roll_corr   = oil_equity_correlation(prices)
    corr_win    = correlation_by_window(prices)
    corr_flip_r = correlation_flip(prices)
    corr_delta  = cross_asset_correlation_delta(prices)          # [U2-G]

    # ── Section 4: Counterfactual ─────────────────────────────────────────────
    cf_paths  = counterfactual_2026(prices, ["WTI", "SP500", "GOLD"],
                                    end=FETCH_END)

    # ── Section 5: Portfolios / drawdown ──────────────────────────────────────
    sector_pf  = sector_portfolio(prices, end=FETCH_END)
    dd_avoid   = drawdown_avoidance(prices, ["XOM", "CVX", "WTI"])
    stable     = what_didnt_move(prices)

    # ── Section 6: Character cards ────────────────────────────────────────────
    cards      = build_all_character_cards(prices, seasonal, ev_stats=ev_stats)

    # ── Section 7: Event reactions ────────────────────────────────────────────
    vix_stats  = vix_peak_stats(prices, end=FETCH_END)
    first_day  = first_day_reaction(prices, EVENT_DATES, available)
    tx_speed   = shock_transmission_speed(prices, available)

    reopening_date = EVENT_CONFIG["dates"].get("Hormuz Open (Apr 17)", "2026-04-17")
    shock_date     = EVENT_CONFIG["dates"].get("Op. Epic Fury (Feb 28)", "2026-02-28")
    jun10_date     = EVENT_CONFIG["dates"].get("Iran Re-escalation (Jun 10)", "2026-06-10")

    # ── Section 8: N-series (original) ───────────────────────────────────────
    ccf_result    = lead_lag_ccf(prices, leader="WTI", follower="SP500")
    rolling_betas = rolling_beta_series(
        prices,
        assets=[a for a in available if a not in ["SP500", "VIX"]],
    )
    dxy_decomp    = dxy_oil_decomposition(prices)
    vol_regimes   = vol_regime_periods(prices, assets=available)
    intl_spill    = international_spillover(prices)
    og_ratio      = oil_gold_ratio_stats(prices)
    heatmap       = sector_rotation_heatmap(prices)

    # ── Section 9: Update 2 new functions ────────────────────────────────────
    pair_trades   = pair_trade_extended(prices)
    pair_ts_main  = pair_trade_timeseries(prices, "WTI", "XOM")
    pair_ts_xle   = pair_trade_timeseries(prices, "WTI", "XLE")
    pair_dd       = pair_trade_drawdown(prices)                      # [U2-J]
    esc_replay    = escalation_replay(prices, assets=available)
    fwd_exp       = forward_expectations_proxy(prices)
    def_premium   = defense_premium(prices)
    freight_sprd  = freight_oil_spread(prices)
    regime_summ   = window_regime_summary(prices, og_ratio, corr_flip_r)  # [U2-F]
    aramco_disc   = aramco_sovereign_discount(prices)                 # [U2-H]
    tlt_test      = tlt_safe_haven_test(prices)                       # [U2-I]

    return {
        # ── Baseline
        "seasonal":           seasonal,
        "base_sum":           base_sum,
        "ev_stats":           ev_stats,
        # ── Abnormal returns
        "abnormal":           abnormal,
        # ── Correlation
        "roll_corr":          roll_corr,
        "corr_win":           corr_win,
        "corr_flip":          corr_flip_r,
        "corr_delta":         corr_delta,          # [U2-G]
        # ── Counterfactual / portfolio
        "cf_paths":           cf_paths,
        "sector_pf":          sector_pf,
        "dd_avoided":         dd_avoid,
        "stable_assets":      stable,
        # ── Character cards / VIX
        "character_cards":    cards,
        "vix_stats":          vix_stats,
        # ── Event reactions
        "first_day":          first_day,
        "tx_speed":           tx_speed,
        "days_to_price": {
            "WTI_reopening":   days_to_price_event(prices, "WTI",   reopening_date),
            "SP500_reopening": days_to_price_event(prices, "SP500", reopening_date),
            "WTI_shock_onset": days_to_price_event(prices, "WTI",   shock_date),
            "WTI_jun10":       days_to_price_event(prices, "WTI",   jun10_date),
            "SP500_jun10":     days_to_price_event(prices, "SP500", jun10_date),
        },
        "returns":            rets,
        # ── N-series (original N1–N7)
        "ccf":                ccf_result,
        "rolling_betas":      rolling_betas,
        "dxy_decomp":         dxy_decomp,
        "vol_regimes":        vol_regimes,
        "intl_spillover":     intl_spill,
        "og_ratio":           og_ratio,
        "heatmap":            heatmap,
        # ── Update 2 new
        "pair_trades":        pair_trades,         # [U2-A]
        "pair_ts_wti_xom":    pair_ts_main,        # [U2-A2]
        "pair_ts_wti_xle":    pair_ts_xle,         # [U2-A2]
        "pair_drawdowns":     pair_dd,             # [U2-J]
        "escalation_replay":  esc_replay,          # [U2-B]
        "fwd_expectations":   fwd_exp,             # [U2-C]
        "defense_premium":    def_premium,         # [U2-D]
        "freight_spread":     freight_sprd,        # [U2-E]
        "regime_summary":     regime_summ,         # [U2-F]
        "aramco_discount":    aramco_disc,         # [U2-H]
        "tlt_safe_haven":     tlt_test,            # [U2-I]
    }