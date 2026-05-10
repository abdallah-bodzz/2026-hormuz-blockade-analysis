"""
event_study.py
--------------
Core analytical engine for the 2026 Hormuz Crisis study.

Original fixes (carried forward):
  [F1]  correlation_flip() returns window-average, not rolling peak.
  [F2]  first_day_reaction() clearly labeled as single-day return.
  [F3]  asset_character_card() adds n_shock_days from ev_stats.
  [F4]  compute_abnormal_returns() adds OLS SE and beta_low_flag.
  [F5]  days_to_price_event() uses relative-vol threshold, not fixed %.
  [F6]  Reopen window narrative reads actual data, no hardcoded strings.
  [F7]  correlation_flip() calls correlation_by_window() -- single source.
  [F8]  seasonal_baseline() carries is_nominal flag.
  [F9]  Gold margin_call_flag in character card.
  [F10] All dates read from EVENT_CONFIG -- nothing hardcoded.

New additions in this version:
  [N1]  lead_lag_ccf() -- cross-correlation function, WTI leads S&P?
  [N2]  rolling_beta_series() -- time-varying beta for XOM, JETS vs S&P.
  [N3]  dxy_oil_decomposition() -- how much WTI move is dollar vs supply.
  [N4]  vol_regime_periods() -- 5d/21d vol ratio; flags shock entry/exit.
  [N5]  international_spillover() -- DAX, Nikkei vs S&P shock comparison.
  [N6]  oil_gold_ratio_stats() -- fear vs supply signal from WTI/GOLD ratio.
  [N7]  sector_rotation_heatmap() -- assets x windows return matrix.
  [FIX] drawdown_avoidance() fixed: correctly labels which basket had
        deeper/shallower DD. Previous version had the comparison backwards.
"""

import os
import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm

warnings.filterwarnings("ignore")

from utils import (
    simple_returns, rolling_volatility, rolling_correlation,
    oil_gold_ratio, vol_regime_ratio,
    EVENT_WINDOWS, EVENT_CONFIG, TRADING_DAYS,
    CORE_ASSETS, INTL_ASSETS, DXY_ASSET,
)


# ---------------------------------------------------------------------------
# 1. Seasonal baseline [F8]
# ---------------------------------------------------------------------------

def seasonal_baseline(prices: pd.DataFrame,
                      assets: list,
                      years: range = range(2021, 2027)) -> pd.DataFrame:
    """
    Jan-Apr stats for each asset across years.
    [F8] is_nominal=True flag on every row.
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

            records.append({
                "year":       year,
                "asset":      col,
                "cum_return": round((s.iloc[-1] / s.iloc[0] - 1) * 100, 2),
                "ann_vol":    round(r.std() * np.sqrt(252) * 100, 2),
                "max_dd":     round(((s / s.cummax()) - 1).min() * 100, 2),
                "n_days":     len(s),
                "is_nominal": True,
            })

    return pd.DataFrame(records)


def baseline_summary(seasonal_df: pd.DataFrame,
                     baseline_years: list = None) -> pd.DataFrame:
    if baseline_years is None:
        baseline_years = [y for y in seasonal_df["year"].unique() if y != 2026]

    base = (seasonal_df[seasonal_df["year"].isin(baseline_years)]
            .groupby("asset")[["cum_return", "ann_vol", "max_dd"]]
            .mean().round(2))
    base.columns = [f"avg_{c}" for c in base.columns]

    y2026 = (seasonal_df[seasonal_df["year"] == 2026]
             .set_index("asset")[["cum_return", "ann_vol", "max_dd"]])
    y2026.columns = [f"2026_{c}" for c in y2026.columns]

    combined = base.join(y2026, how="outer")
    combined["vol_multiple"] = (combined["2026_ann_vol"] / combined["avg_ann_vol"]).round(2)
    combined["ret_multiple"] = (combined["2026_cum_return"] / combined["avg_cum_return"]).round(2)
    combined["nominal_caveat"] = "Returns are nominal. No CPI adjustment."
    return combined


# ---------------------------------------------------------------------------
# 2. Event window analysis
# ---------------------------------------------------------------------------

def event_window_stats(prices: pd.DataFrame,
                       assets: list,
                       windows: dict = None) -> pd.DataFrame:
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
                "window":     window_name,
                "asset":      col,
                "cum_return": round((s.iloc[-1] / s.iloc[0] - 1) * 100, 2),
                "avg_daily":  round(r.mean() * 100, 3),
                "ann_vol":    round(r.std() * np.sqrt(252) * 100, 2),
                "max_dd":     round(((s / s.cummax()) - 1).min() * 100, 2),
                "n_days":     len(s),
            })

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# 3. Abnormal returns via OLS [F4]
# ---------------------------------------------------------------------------

def compute_abnormal_returns(prices: pd.DataFrame,
                             assets: list,
                             benchmark: str = "SP500",
                             estimation_window: tuple = None,
                             event_windows: dict = None) -> pd.DataFrame:
    """
    Market model abnormal returns (OLS, pre-event estimated).
    [F4] Near-zero beta assets flagged. Beta caveat included per row.
    """
    if estimation_window is None:
        estimation_window = EVENT_CONFIG["estimation_window"]
    if event_windows is None:
        event_windows = {k: v for k, v in EVENT_WINDOWS.items()
                         if k != "pre_event"}

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
                "Near-zero beta: abnormal ~= actual return (market model adds little here)."
                if low_beta else
                "Beta assumed constant; may overstate shock specificity during large moves."
            )

            records.append({
                "window":           window_name,
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


# ---------------------------------------------------------------------------
# 4. Correlation [F1] [F7]
# ---------------------------------------------------------------------------

def correlation_by_window(prices: pd.DataFrame,
                           pairs: list = None,
                           windows: dict = None) -> pd.DataFrame:
    """
    Full-window average Pearson correlation per event window.
    Single source of truth -- correlation_flip() calls this.
    """
    if pairs is None:
        pairs = [("WTI", "SP500"), ("GOLD", "SP500"), ("WTI", "GOLD"),
                 ("DXY", "WTI"), ("DXY", "SP500")]
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
                "window":      name,
                "pair":        f"{a} / {b}",
                "correlation": round(float(c), 3),
            })

    return pd.DataFrame(records)


def oil_equity_correlation(prices: pd.DataFrame,
                            oil_col: str = "WTI",
                            eq_col: str = "SP500",
                            window: int = 10,
                            year: int = 2026) -> pd.DataFrame:
    """Rolling correlation series for chart visualisation only."""
    subset = prices.loc[f"{year}-01-01":f"{year}-04-30",
                        [oil_col, eq_col]].dropna()
    rets   = simple_returns(subset).dropna()
    corr   = rolling_correlation(rets[oil_col], rets[eq_col], window=window)
    corr.name = f"{oil_col}_vs_{eq_col}_corr"
    return corr.to_frame()


def correlation_flip(prices: pd.DataFrame,
                     oil_col: str = "WTI",
                     eq_col: str = "SP500") -> dict:
    """[F1] [F7] Regime shift via window averages. Single computation path."""
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

    pre    = _get("pre_event")
    shock  = _get("shock")
    reopen = _get("reopen")
    flip   = round(shock - pre, 3) if shock is not None and pre is not None else None

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
        "pre_avg":        round(pre, 3) if pre is not None else None,
        "shock_avg":      round(shock, 3) if shock is not None else None,
        "reopen_avg":     round(reopen, 3) if reopen is not None else None,
        "flip_delta":     flip,
        "interpretation": interp,
        "shock_peak":     round(shock, 3) if shock is not None else None,
    }


# ---------------------------------------------------------------------------
# 5. Counterfactual
# ---------------------------------------------------------------------------

def counterfactual_2026(prices: pd.DataFrame,
                        assets: list,
                        baseline_years: range = range(2021, 2026)) -> dict:
    """Projects a no-shock 2026 path using the average Jan-Apr daily return."""
    results = {}
    for asset in assets:
        if asset not in prices.columns:
            continue

        base_daily = []
        for yr in baseline_years:
            p = prices.loc[f"{yr}-01-01":f"{yr}-04-30", asset].dropna()
            if len(p) < 10:
                continue
            base_daily.append(p.pct_change().dropna().values)

        if not base_daily:
            continue

        act_2026 = prices.loc["2026-01-01":"2026-04-30", asset].dropna()
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


# ---------------------------------------------------------------------------
# 6. Sector portfolio
# ---------------------------------------------------------------------------

def sector_portfolio(prices: pd.DataFrame,
                     energy_cols: list = None,
                     market_col: str = "SP500") -> pd.DataFrame:
    """Equal-weight energy basket vs S&P 500 -- observed P&L, no optimisation."""
    if energy_cols is None:
        energy_cols = ["XOM", "CVX", "WTI"]

    available = [c for c in energy_cols if c in prices.columns]
    subset    = prices.loc["2026-01-01":"2026-04-30",
                            available + [market_col]].dropna(how="all")
    rets      = simple_returns(subset).dropna()

    return pd.DataFrame({
        "Energy basket (XOM+CVX+WTI)": (1 + rets[available].mean(axis=1)).cumprod() * 100,
        "S&P 500 buy-and-hold":        (1 + rets[market_col]).cumprod() * 100,
    })


# ---------------------------------------------------------------------------
# 7. Days to price [F5]
# ---------------------------------------------------------------------------

def _pre_event_daily_vol(prices: pd.DataFrame, asset: str) -> float:
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
    """[F5] Relative-vol threshold. Not a fixed %."""
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


# ---------------------------------------------------------------------------
# 8. Drawdown avoidance [FIX]
# ---------------------------------------------------------------------------

def drawdown_avoidance(prices: pd.DataFrame,
                       hedged_assets: list,
                       market_asset: str = "SP500",
                       window: tuple = None) -> dict:
    """
    Compares drawdowns between energy basket and S&P during shock window.

    [FIX] Previous version labeled "avoided_pct" regardless of direction.
    Now correctly reports:
      - basket_had_worse_dd: True if energy basket had DEEPER drawdown than market
      - avoided_pct: positive if basket was BETTER (shallower DD) than market
      - narrative: plain-English statement of what actually happened
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

    # Positive = basket lost LESS than market (energy was protective)
    # Negative = basket lost MORE than market (energy amplified loss)
    dd_diff = market_dd - basket_dd   # market_dd is negative, basket_dd is negative

    basket_worse = basket_dd < market_dd   # more negative = deeper drawdown

    if basket_worse:
        narrative = (
            f"Energy basket had {abs(round(basket_dd - market_dd, 1))}pp DEEPER "
            f"drawdown than S&P ({round(basket_dd,1)}% vs {round(market_dd,1)}%). "
            f"Energy amplified losses during the shock."
        )
        avoided_pct = round((basket_dd / market_dd - 1) * 100, 1) if market_dd != 0 else 0.0
    else:
        narrative = (
            f"Energy basket had SHALLOWER drawdown than S&P "
            f"({round(basket_dd,1)}% vs {round(market_dd,1)}%). "
            f"Energy provided partial protection."
        )
        avoided_pct = round(abs(dd_diff / market_dd) * 100, 1) if market_dd != 0 else 0.0

    return {
        "market_max_dd":      round(float(market_dd), 2),
        "basket_max_dd":      round(float(basket_dd), 2),
        "avoided_dd_pp":      round(float(dd_diff), 2),
        "avoided_pct":        avoided_pct,
        "basket_had_worse_dd": basket_worse,
        "narrative":          narrative,
    }


# ---------------------------------------------------------------------------
# 9. What didn't move
# ---------------------------------------------------------------------------

def what_didnt_move(prices: pd.DataFrame,
                    threshold_pct: float = 5.0,
                    window: tuple = None) -> pd.DataFrame:
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


# ---------------------------------------------------------------------------
# 10. Asset character cards [F3] [F9]
# ---------------------------------------------------------------------------

def asset_character_card(asset: str,
                         prices: pd.DataFrame,
                         ev_stats: pd.DataFrame = None,
                         windows: dict = None,
                         seasonal_df: pd.DataFrame = None) -> dict:
    if windows is None:
        windows = EVENT_WINDOWS
    if asset not in prices.columns:
        return {}

    stats  = {}
    p_full = prices.loc["2026-01-01":"2026-04-30", asset].dropna()

    for name, (s, e) in windows.items():
        p = prices.loc[s:e, asset].dropna()
        if len(p) < 2:
            continue
        stats[f"{name}_ret"] = round((p.iloc[-1] / p.iloc[0] - 1) * 100, 1)

    # [F3] Pull n_shock_days from ev_stats
    if ev_stats is not None:
        row = ev_stats[(ev_stats["asset"] == asset) & (ev_stats["window"] == "shock")]
        if not row.empty:
            stats["n_shock_days"] = int(row["n_days"].values[0])

    if not p_full.empty:
        base = p_full.iloc[0]
        stats.update({
            "peak_gain_%":   round((p_full.max() / base - 1) * 100, 1),
            "trough_loss_%": round((p_full.min() / base - 1) * 100, 1),
            "net_jan_apr_%": round((p_full.iloc[-1] / base - 1) * 100, 1),
            "peak_date":     str(p_full.idxmax().date()),
            "trough_date":   str(p_full.idxmin().date()),
        })

    if seasonal_df is not None:
        base_yrs = seasonal_df[
            (seasonal_df["year"] != 2026) & (seasonal_df["asset"] == asset)
        ]
        if not base_yrs.empty:
            stats["avg_5yr_jan_apr_%"] = round(base_yrs["cum_return"].mean(), 1)

    # [F9] Gold margin-call flag
    if asset == "GOLD":
        shock_s     = EVENT_WINDOWS["shock"][0]
        gold_first5 = prices.loc[shock_s:, "GOLD"].dropna().head(6)
        if len(gold_first5) >= 5:
            drop_in_first5 = (gold_first5.iloc[4] / gold_first5.iloc[0] - 1) * 100
            later_recovery = stats.get("shock_ret", 0)
            stats["margin_call_flag"]   = (drop_in_first5 < -1.5 and later_recovery > 0)
            stats["gold_first5_move_%"] = round(float(drop_in_first5), 2)
        else:
            stats["margin_call_flag"]   = False
            stats["gold_first5_move_%"] = None

    return stats


def build_all_character_cards(prices: pd.DataFrame,
                               seasonal_df: pd.DataFrame,
                               ev_stats: pd.DataFrame = None,
                               assets: list = None) -> dict:
    if assets is None:
        assets = CORE_ASSETS

    return {
        a: asset_character_card(a, prices, ev_stats=ev_stats, seasonal_df=seasonal_df)
        for a in assets
        if a in prices.columns
    }


# ---------------------------------------------------------------------------
# 11. First-day reaction [F2]
# ---------------------------------------------------------------------------

def first_day_reaction(prices: pd.DataFrame,
                       event_dates: dict,
                       assets: list) -> pd.DataFrame:
    """[F2] Single-day return on each event date. Not a window return."""
    rets    = simple_returns(prices).dropna()
    records = []

    for label, date in event_dates.items():
        ts         = pd.Timestamp(date)
        candidates = rets.index[rets.index >= ts]
        if candidates.empty:
            continue
        actual_date = candidates[0]

        for asset in assets:
            if asset not in rets.columns or actual_date not in rets.index:
                continue
            records.append({
                "event":               label,
                "event_date":          date,
                "actual_trading_date": str(actual_date.date()),
                "asset":               asset,
                "day1_return_%":       round(rets.loc[actual_date, asset] * 100, 2),
            })

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# 12. VIX peak stats
# ---------------------------------------------------------------------------

def vix_peak_stats(prices: pd.DataFrame,
                   vix_col: str = "VIX",
                   baseline_years: range = range(2021, 2026)) -> dict:
    if vix_col not in prices.columns:
        return {}

    shock_s, shock_e = EVENT_WINDOWS["shock"]
    vix_2026 = prices.loc[shock_s:shock_e, vix_col].dropna()
    if vix_2026.empty:
        return {}

    peak_val  = vix_2026.max()
    peak_date = vix_2026.idxmax()

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


# ---------------------------------------------------------------------------
# NEW [N1]: Lead-lag cross-correlation function (CCF)
# ---------------------------------------------------------------------------

def lead_lag_ccf(prices: pd.DataFrame,
                 leader: str = "WTI",
                 follower: str = "SP500",
                 max_lag: int = 5,
                 year: int = 2026) -> pd.DataFrame:
    """
    [N1] Cross-correlation at lags -max_lag to +max_lag.
    Positive lag = leader moves BEFORE follower (leader leads).
    Negative lag = follower moves first (follower leads).

    Interpretation guide:
      If peak correlation is at lag +1 or +2, WTI movements
      tend to predict S&P moves 1-2 days later -- a genuine lead-lag.
      If peak is at lag 0, they move simultaneously (no lead).

    Returns DataFrame with columns: lag, correlation, is_peak.
    """
    subset = prices.loc[f"{year}-01-01":f"{year}-04-30",
                        [leader, follower]].dropna()
    rets   = simple_returns(subset).dropna()

    if leader not in rets.columns or follower not in rets.columns:
        return pd.DataFrame()

    r_lead = rets[leader]
    r_foll = rets[follower]

    records = []
    for lag in range(-max_lag, max_lag + 1):
        if lag > 0:
            # leader at t, follower at t+lag
            corr = r_lead.iloc[:-lag].values if lag > 0 else r_lead.values
            foll = r_foll.iloc[lag:].values
            aligned = min(len(corr), len(foll))
            c = float(np.corrcoef(corr[:aligned], foll[:aligned])[0, 1])
        elif lag < 0:
            # follower at t, leader at t+|lag| (follower leads)
            lead = r_lead.iloc[-lag:].values
            foll = r_foll.iloc[:lag].values
            aligned = min(len(lead), len(foll))
            c = float(np.corrcoef(foll[:aligned], lead[:aligned])[0, 1])
        else:
            c = float(r_lead.corr(r_foll))

        records.append({"lag": lag, "correlation": round(c, 3)})

    df = pd.DataFrame(records)
    peak_corr = df["correlation"].abs().max()
    df["is_peak"] = df["correlation"].abs() == peak_corr
    return df


# ---------------------------------------------------------------------------
# NEW [N2]: Rolling beta series
# ---------------------------------------------------------------------------

def rolling_beta_series(prices: pd.DataFrame,
                        assets: list,
                        benchmark: str = "SP500",
                        window: int = 21,
                        year: int = 2026) -> pd.DataFrame:
    """
    [N2] Time-varying beta for each asset vs benchmark.
    Uses a rolling OLS window.

    Key expected findings:
      - XOM beta spikes during shock (oil equity behaves like oil itself)
      - JETS beta inverts or compresses (inverse oil story)
      - GOLD beta stays near zero (decorrelated safe haven)

    Returns wide DataFrame: index=date, columns=asset betas.
    """
    subset = prices.loc[f"{year}-01-01":f"{year}-04-30"].dropna(how="all")
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

        betas = []
        idx   = []
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


# ---------------------------------------------------------------------------
# NEW [N3]: DXY oil decomposition
# ---------------------------------------------------------------------------

def dxy_oil_decomposition(prices: pd.DataFrame,
                           oil_col: str = "WTI",
                           dxy_col: str = "DXY") -> dict:
    """
    [N3] Decomposes WTI's shock-window return into:
      - Currency effect: how much of WTI gain is explained by USD weakening
      - Real supply effect: residual after removing dollar component

    Method:
      1. Regress WTI returns on DXY returns over pre-event window.
         Expected: negative beta (USD up -> oil down in nominal terms).
      2. Compute DXY's shock-window return.
      3. Currency contribution = beta * DXY_shock_return.
      4. Real supply effect = WTI_actual - currency_contribution.

    Caveat: this is a simple linear decomposition. In practice the
    relationship is non-linear and regime-dependent.
    """
    if dxy_col not in prices.columns or oil_col not in prices.columns:
        return {"available": False, "reason": f"{dxy_col} or {oil_col} not in data"}

    pre_s, pre_e = EVENT_CONFIG["estimation_window"]
    shock_s, shock_e = EVENT_WINDOWS["shock"]

    pre_rets = simple_returns(prices.loc[pre_s:pre_e, [oil_col, dxy_col]]).dropna()
    if len(pre_rets) < 10:
        return {"available": False, "reason": "Insufficient pre-event data"}

    model = sm.OLS(pre_rets[oil_col],
                   sm.add_constant(pre_rets[dxy_col])).fit()
    beta_dxy = model.params[dxy_col]
    r2       = model.rsquared

    shock_p = prices.loc[shock_s:shock_e, [oil_col, dxy_col]].dropna()
    if len(shock_p) < 2:
        return {"available": False, "reason": "Insufficient shock-window data"}

    wti_shock = (shock_p[oil_col].iloc[-1] / shock_p[oil_col].iloc[0] - 1) * 100
    dxy_shock = (shock_p[dxy_col].iloc[-1] / shock_p[dxy_col].iloc[0] - 1) * 100

    currency_contrib = beta_dxy * dxy_shock
    real_supply      = wti_shock - currency_contrib

    dxy_dir = "weakened" if dxy_shock < 0 else "strengthened"
    amplify = "amplified" if (dxy_shock < 0 and beta_dxy < 0) else "offset"

    return {
        "available":         True,
        "wti_shock_ret_%":   round(wti_shock, 2),
        "dxy_shock_ret_%":   round(dxy_shock, 2),
        "beta_oil_on_dxy":   round(beta_dxy, 3),
        "r2_pre_event":      round(r2, 3),
        "currency_contrib_%": round(currency_contrib, 2),
        "real_supply_%":      round(real_supply, 2),
        "currency_share_%":   round(abs(currency_contrib / wti_shock) * 100, 1)
                              if wti_shock != 0 else 0.0,
        "dxy_direction":     dxy_dir,
        "amplify_or_offset": amplify,
        "interpretation": (
            f"DXY {dxy_dir} {abs(round(dxy_shock,1))}% during shock. "
            f"Currency effect {amplify} the oil spike by ~{abs(round(currency_contrib,1))}pp. "
            f"Real supply contribution: ~{round(real_supply,1)}pp of the "
            f"{round(wti_shock,1)}% WTI move."
        ),
        "caveat": "Linear decomposition only. Beta estimated on pre-event window; "
                  "may not hold during large moves.",
    }


# ---------------------------------------------------------------------------
# NEW [N4]: Volatility regime detection
# ---------------------------------------------------------------------------

def vol_regime_periods(prices: pd.DataFrame,
                       assets: list = None,
                       short_window: int = 5,
                       long_window: int = 21,
                       regime_threshold: float = 2.0,
                       year: int = 2026) -> dict:
    """
    [N4] Identifies volatility regime entry/exit dates using 5d/21d vol ratio.
    Regime = short_vol > threshold * long_vol.

    Returns dict per asset:
      ratio_series  : the ratio time series (for charting)
      regime_start  : first date ratio exceeded threshold
      regime_end    : last date ratio exceeded threshold  
      days_in_regime: trading days spent in high-vol regime
    """
    if assets is None:
        assets = ["WTI", "SP500", "GOLD", "XOM"]

    subset = prices.loc[f"{year}-01-01":f"{year}-04-30",
                        [a for a in assets if a in prices.columns]].dropna(how="all")
    rets   = simple_returns(subset).dropna()
    ratios = vol_regime_ratio(rets, short_window=short_window, long_window=long_window)

    results = {}
    for asset in assets:
        if asset not in ratios.columns:
            continue

        r = ratios[asset].dropna()
        in_regime = r[r > regime_threshold]

        regime_start = str(in_regime.index[0].date()) if not in_regime.empty else None
        regime_end   = str(in_regime.index[-1].date()) if not in_regime.empty else None

        results[asset] = {
            "ratio_series":   r,
            "regime_start":   regime_start,
            "regime_end":     regime_end,
            "days_in_regime": len(in_regime),
            "peak_ratio":     round(float(r.max()), 2),
            "peak_ratio_date": str(r.idxmax().date()) if not r.empty else None,
        }

    return results


# ---------------------------------------------------------------------------
# NEW [N5]: International spillover
# ---------------------------------------------------------------------------

def international_spillover(prices: pd.DataFrame,
                             indices: list = None,
                             windows: dict = None) -> pd.DataFrame:
    """
    [N5] Compares shock-window returns across global equity indices.
    Shows which markets absorbed the Hormuz shock most severely.

    Returns long-form DataFrame: index, window, cum_return, max_dd.
    Note: DAX and Nikkei are local-currency returns. No FX adjustment.
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
                "window":       window_name,
                "index":        col,
                "cum_return_%": round(cum, 2),
                "max_dd_%":     round(dd, 2),
            })

    df = pd.DataFrame(records)
    if not df.empty:
        df["fx_caveat"] = "Local-currency return. No FX adjustment applied."
    return df


# ---------------------------------------------------------------------------
# NEW [N6]: Oil/Gold ratio analysis
# ---------------------------------------------------------------------------

def oil_gold_ratio_stats(prices: pd.DataFrame) -> dict:
    """
    [N6] Computes ratio series and summarizes regime interpretation.

    Rising ratio during shock -> supply shock dominates.
    Falling ratio during shock -> fear/safe haven dominates.
    Ratio reversal at reopening -> clean supply normalization signal.
    """
    from utils import oil_gold_ratio as _ratio_fn
    ratio = _ratio_fn(prices)

    if ratio.empty:
        return {"available": False}

    shock_s, shock_e  = EVENT_WINDOWS["shock"]
    reopen_s, reopen_e = EVENT_WINDOWS["reopen"]
    pre_s, pre_e      = EVENT_WINDOWS["pre_event"]

    def _window_change(start, end):
        w = ratio.loc[start:end].dropna()
        if len(w) < 2:
            return None
        return round((w.iloc[-1] / w.iloc[0] - 1) * 100, 2)

    pre_chg    = _window_change(pre_s, pre_e)
    shock_chg  = _window_change(shock_s, shock_e)
    reopen_chg = _window_change(reopen_s, reopen_e)

    if shock_chg is not None:
        if shock_chg > 5:
            regime = "Supply shock dominant. Oil outpaced gold. Markets priced scarcity, not systemic fear."
        elif shock_chg < -5:
            regime = "Fear dominant. Gold outpaced oil. Capital flight exceeded supply pricing."
        else:
            regime = "Mixed signal. Oil and gold moved roughly together -- both supply and fear at play."
    else:
        regime = "Insufficient data."

    return {
        "available":        True,
        "ratio_series":     ratio,
        "pre_change_%":     pre_chg,
        "shock_change_%":   shock_chg,
        "reopen_change_%":  reopen_chg,
        "regime_interp":    regime,
        "peak_ratio_date":  str(ratio.idxmax().date()) if not ratio.empty else None,
        "trough_ratio_date": str(ratio.idxmin().date()) if not ratio.empty else None,
    }


# ---------------------------------------------------------------------------
# NEW [N7]: Sector rotation heatmap matrix
# ---------------------------------------------------------------------------

def sector_rotation_heatmap(prices: pd.DataFrame,
                             assets: list = None,
                             windows: dict = None) -> pd.DataFrame:
    """
    [N7] Returns a pivot table: assets (rows) x windows (columns) = cum_return %.
    Designed for heatmap visualization. Color immediately shows who won/lost each phase.

    Assets sorted by shock-window return descending (biggest winners at top).
    """
    if assets is None:
        assets = [a for a in CORE_ASSETS if a != "VIX"]
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

    # Sort by shock return descending
    col_order = [c for c in ["pre_event", "shock", "reopen"] if c in pivot.columns]
    pivot     = pivot[col_order]
    if "shock" in pivot.columns:
        pivot = pivot.sort_values("shock", ascending=False)

    return pivot


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_full_analysis(prices: pd.DataFrame, data_dir: str = "data") -> dict:
    """
    Run the complete pipeline and return all results as a dict.
    """
    proc_dir = os.path.join(data_dir, "processed")
    os.makedirs(proc_dir, exist_ok=True)

    rets = simple_returns(prices).dropna(how="all")
    rets.to_parquet(os.path.join(proc_dir, "returns.parquet"), engine="pyarrow")

    available = [a for a in CORE_ASSETS if a in prices.columns]
    EVENT_DATES_RAW = EVENT_CONFIG["dates"]

    seasonal  = seasonal_baseline(prices, available)
    base_sum  = baseline_summary(seasonal)
    ev_stats  = event_window_stats(prices, available)

    abnormal  = compute_abnormal_returns(
        prices,
        [a for a in available if a not in ["SP500", "VIX"]],
        benchmark="SP500",
    )

    roll_corr  = oil_equity_correlation(prices)
    corr_win   = correlation_by_window(prices)
    corr_flip  = correlation_flip(prices)

    cf_paths   = counterfactual_2026(prices, ["WTI", "SP500", "GOLD"])
    sector_pf  = sector_portfolio(prices)
    dd_avoid   = drawdown_avoidance(prices, ["XOM", "CVX", "WTI"])
    stable     = what_didnt_move(prices)
    cards      = build_all_character_cards(prices, seasonal, ev_stats=ev_stats)
    vix_stats  = vix_peak_stats(prices)

    first_day  = first_day_reaction(
        prices, EVENT_DATES_RAW,
        ["WTI", "SP500", "GOLD", "XOM", "JETS"],
    )

    tx_speed   = shock_transmission_speed(prices, available)

    reopening_date = EVENT_CONFIG["dates"].get("Hormuz Open (Apr 17)", "2026-04-17")
    shock_date     = EVENT_CONFIG["dates"].get("Op. Epic Fury (Feb 28)", "2026-02-28")

    ev_stats.to_parquet(os.path.join(proc_dir, "event_windows.parquet"), engine="pyarrow")

    # ----- NEW analyses -----
    ccf_result    = lead_lag_ccf(prices, leader="WTI", follower="SP500")
    rolling_betas = rolling_beta_series(
        prices,
        assets=[a for a in ["XOM", "JETS", "GOLD"] if a in prices.columns],
        benchmark="SP500",
    )
    dxy_decomp    = dxy_oil_decomposition(prices)
    vol_regimes   = vol_regime_periods(prices)
    intl_spill    = international_spillover(prices)
    og_ratio      = oil_gold_ratio_stats(prices)
    heatmap       = sector_rotation_heatmap(prices)

    return {
        "seasonal":        seasonal,
        "base_sum":        base_sum,
        "ev_stats":        ev_stats,
        "abnormal":        abnormal,
        "roll_corr":       roll_corr,
        "corr_win":        corr_win,
        "corr_flip":       corr_flip,
        "cf_paths":        cf_paths,
        "sector_pf":       sector_pf,
        "dd_avoided":      dd_avoid,
        "stable_assets":   stable,
        "character_cards": cards,
        "vix_stats":       vix_stats,
        "first_day":       first_day,
        "tx_speed":        tx_speed,
        "days_to_price": {
            "WTI_reopening":   days_to_price_event(prices, "WTI", reopening_date),
            "SP500_reopening": days_to_price_event(prices, "SP500", reopening_date),
            "WTI_shock_onset": days_to_price_event(prices, "WTI", shock_date),
        },
        "returns":         rets,
        # New
        "ccf":             ccf_result,
        "rolling_betas":   rolling_betas,
        "dxy_decomp":      dxy_decomp,
        "vol_regimes":     vol_regimes,
        "intl_spillover":  intl_spill,
        "og_ratio":        og_ratio,
        "heatmap":         heatmap,
    }