# 2026 Strait of Hormuz Crisis
## Event-Driven Time-Series Analysis of Geopolitical Shock Transmission

**Lead Developer:** Abdallah A Khames (BODZZ)
**Analysis Date:** April 30, 2026 (static snapshot)
**Repository:** github.com/abdallah-bodzz/2026_hormuz_analysis

---

## Executive Summary

This project quantifies the market impact of a real geopolitical event: the 47-day closure of the Strait of Hormuz following Operation Epic Fury (Feb 28 – Apr 17, 2026). The analysis examines how a physical supply shock transmitted across 10 global assets, identifies which traditional hedges failed, and documents the speed of market repricing at resolution.

**Core finding:** Physical oil decoupled from energy equities during the acute shock. WTI rose +32.9% while XOM fell −1.5% in the same 33-day window. The market treated energy equities as risk assets, not commodity proxies.

**The question this answers:** "How did the 2026 Hormuz disruption affect oil prices, global equities, and cross-asset relationships compared to historical norms?"

**What this does NOT do:** No trading strategy claims. No ML predictions. No speculation on future geopolitical outcomes. Purely a quantitative post-mortem.

---

## Why This Project Exists

Most portfolio projects fall into one of three traps:

1. **Old school datasets** (Titanic, Iris, housing prices) → shows basic skills but zero domain relevance
2. **Crypto prediction models** → overfit, non-reproducible, academically weak
3. **Generic time-series forecasting** (ARIMA on BTC) → done thousands of times, adds no signal

This project avoids all three. It's a **real geopolitical event with clean dates, measurable market reactions, and direct relevance to risk management and macro analysis.** The data is fresh (April 2026 cutoff), the event is bounded, and the insights are actionable for institutional risk teams.

---

## Asset Selection

| Asset | Ticker | Role | Why Included |
|-------|--------|------|--------------|
| S&P 500 | ^GSPC | Equity benchmark | Broad market reaction |
| WTI Crude | CL=F | Primary shock vector | Direct supply disruption |
| Gold | GC=F | Safe-haven proxy | Tested the margin-call hypothesis |
| Exxon (XOM) | XOM | Energy equity | Does it track oil or the market? |
| Chevron (CVX) | CVX | Energy equity | Second data point for robustness |
| VIX | ^VIX | Fear gauge | Regime onset timing |
| Airlines ETF | JETS | Inverse oil story | Fuel cost vs demand destruction |
| Dollar Index | DX-Y.NYB | Currency decomposition | Isolate real supply from dollar weakness |
| DAX | ^GDAXI | European spillover | Industrial energy sensitivity |
| Nikkei 225 | ^N225 | Asian spillover | Oil import dependency (~90%) |

**In practice:** All 10 fetched cleanly via yfinance. No data quality issues. The pipeline handles 2,686 trading days (Jan 2016 – Apr 2026).

---

## Methodology Overview

### Three Event Windows

| Window | Dates | Trading Days | Purpose |
|--------|-------|--------------|---------|
| Pre-event (baseline) | Jan 1 – Feb 27, 2026 | 39 | Establish normal relationships & betas |
| Shock (closure) | Feb 28 – Apr 16, 2026 | 33 | Full blockade + peak war premium |
| Reopening (announcement) | Apr 17 – Apr 30, 2026 | 9 | Market response (not verified normalization) |

### Key Analytical Components

| Component | Method | Business Question |
|-----------|--------|-------------------|
| Seasonal baseline | Jan–Apr 2021–2025 vs 2026 | "Was 2026 actually unusual?" |
| Abnormal returns | OLS market model (pre-event beta) | "How much was pure Hormuz effect?" |
| Rolling correlations | 10-day window | "Did oil diversify or amplify equity risk?" |
| Volatility regime | 5d/21d annualized ratio | "Did volatility shift structurally?" |
| DXY decomposition | OLS (WTI ~ DXY) | "Was this currency or supply?" |
| International spillover | S&P, DAX, Nikkei comparison | "Did geography matter?" |

### What Was Planned vs What Was Built

| Planned | Built | Notes |
|---------|-------|-------|
| 5-year baseline (2021–2025) | ✅ Extended to 2016–2026 | More statistical power |
| 3 assets minimum | ✅ 10 assets total | Includes DXY, VIX, international |
| Simple rolling correlation | ✅ Rolling + window averages by phase | Cleaner regime detection |
| Energy basket simulation | ✅ Equal-weight XOM+CVX+WTI | Showed decoupling visually |
| Airlines as transport proxy | ✅ JETS ETF | Captured demand destruction |
| Interactive Plotly | ❌ Static matplotlib only | Clarity > interactivity for PDF export |
| "Best time to position" framing | ❌ Removed entirely | Honest: no statistical basis for timing claims |

---

## Key Findings (Quantified)

| Finding | Metric |
|---------|--------|
| WTI abnormal return (pure Hormuz effect) | **+20.9%** |
| WTI Jan–Apr return vs 5-year avg | **+86.5%** vs +13.4% (6.5×) |
| Energy basket (XOM+CVX+WTI) max drawdown vs S&P | −12.3% vs −7.8% (4.5pp deeper) |
| Long WTI / Short XOM (shock window) | **+34.4%** pre-cost |
| Gold shock-window return | **−9.6%** (failed safe haven) |
| WTI/Gold ratio change during closure | **+47%** (supply shock signal) |
| DXY contribution to WTI move | **<1%** (real supply, not currency) |
| VIX peak / 5-year average | 31.0 / 20.7 (elevated, not panic) |
| Days for S&P to price reopening | **1 trading day** |

---

## What This Project Proves (No BS)

1. **Energy equities are not oil proxies during supply shocks.** The rolling beta flip from +0.15 to -0.42 is unambiguous.

2. **Traditional safe havens can fail under margin pressure.** Gold sold off during the acute crisis despite rallying beforehand.

3. **The WTI/Gold ratio is a cleaner regime discriminator than VIX.** Rising ratio = supply shock. Falling ratio = systemic fear.

4. **Oil-importing economies absorb asymmetric drawdowns.** Nikkei's max DD was -12.1% vs S&P's -7.8%.

5. **The reopening was priced overnight in WTI futures.** The equity open confirmed, it did not discover.

---

## What This Project Does NOT Claim

- **Trading strategy viability.** The +34.4% pair trade is pre-cost. Real-world execution would be materially lower.

- **Generalizability to other shocks.** This describes 2026 specifically. Different geopolitical topologies may produce different dynamics.

- **Causation in the gold margin-call story.** The pattern fits forced liquidation. Position-level data would be required to confirm.

- **Intraday lead-lag detection.** Daily data cannot distinguish between same-day and overnight information flow.

---

## Technical Implementation

| Component | Implementation |
|-----------|----------------|
| Data source | yfinance (`auto_adjust=True`) |
| Storage | Parquet (2,686 rows × 10 cols) |
| Returns | Simple (arithmetic) period returns |
| Beta estimation | OLS, 39-day pre-event window |
| Abnormal returns | Actual − (α + β × market_return) |
| Volatility | Rolling 10-day & 21-day annualized |
| Correlations | Rolling 10-day Pearson |
| Event bands | Matplotlib vertical spans + annotations |
| Outputs | 20+ PNG charts, 11 CSV tables |

**Dependencies:** numpy, pandas, matplotlib, seaborn, statsmodels, yfinance, pyarrow, IPython

**Reproduction:** Clone repo, `pip install -r requirements.txt`, run notebook. Cached parquet included.

---

## Document Control

| Field | Value |
|-------|-------|
| Author | Abdallah A Khames |
| Organization | BODZZ |
| GitHub | github.com/abdallah-bodzz |
| Analysis date | April 30, 2026 |
| Data range | Jan 2016 – Apr 2026 |
| Status | Static snapshot (not live-updated) |
| License | MIT |

---

*This document serves as the project's methodological appendix. For the narrative version, see `STORY.md`. For the quick overview, see `README.md`.*

---
---

# 2026 Strait of Hormuz Crisis — Update 2
## Extended Event-Driven Analysis: From Decoupling to Regime Switching

**Lead Developer:** Abdallah A Khames (BODZZ)
**Analysis Date:** June 13, 2026 (static snapshot, extended)
**Repository:** github.com/abdallah-bodzz/2026-hormuz-blockade-analysis
**Supersedes for analytical scope:** Sections below extend, but do not replace, the Update 1 methodology above. Update 1's numbers are unchanged and untouched.

---

## Executive Summary

Update 2 extends the original 47-day, 10-asset, 3-window study into a **113-trading-day, 16-asset, 5-window** analysis (Jan 1 – Jun 13, 2026). It does not just add more data to the same question — it answers a different question that the original window was too short to ask: *what happens to the same decoupling once diplomacy enters the picture?*

**Core finding (Update 2):** Forward-looking diplomatic and ceasefire expectations overrode persistent physical supply constraints. The strait remained at roughly 2% transit capacity through May, while WTI fell sharply over the same month. Markets priced the *expected future barrel*, not the current physical one. We call this the **May Paradox**.

**The question this answers:** "Once a supply shock stops being new, does the market keep pricing physical scarcity, or does it start pricing the path to resolution — and how do you tell which one is happening?"

**What this does NOT do:** No prediction of the eventual outcome of the underlying conflict. No claim that the May Paradox generalizes to other protracted shocks. Still purely a quantitative post-mortem, now of a longer and more complex period.

---

## Why Update 2 Was Necessary, Not Optional

Update 1 was explicit that it covered a single, bounded 47-day event and that further evolution would be "a separate study." By late May, three things had happened that a 3-window, 10-asset framework structurally could not represent:

1. **The strait did not reopen, but price behaved as if risk was falling.** This is not capturable in a framework with only "shock" and "reopening" — neither label fits a month where the physical situation is unchanged but pricing reverses.
2. **A second escalation event occurred (June 10).** Update 1's framework was built around one shock. Testing whether markets "learned" from the first shock requires a second, comparable event inside the same analytical structure — something Update 1 flagged as future work.
3. **New asset classes became relevant.** Defense equities (backlog dynamics), freight markets (a shipping-specific decoupling), and the sovereign exporter itself (Aramco) were not answerable with the original 10-asset universe.

---

## Asset Universe — Update 2 (16 Total)

The original 10 assets are retained unchanged. Six are added:

| Asset | Ticker | Role | Why Added in Update 2 |
|-------|--------|------|------------------------|
| Defense ETF | `ITA` | Backlog vs. spot war-trade test | Original 47-day window was too short to separate day-1 reaction from multi-month order-book dynamics |
| Freight/Tanker ETF | `BWET` | Third decoupling layer (shipping) | Captures vessel scarcity / war-risk premium that neither WTI nor energy equities reflect |
| 20+ Year Treasury ETF | `TLT` | Second safe-haven test | Update 1 only tested gold; bonds are the other half of a traditional hedge and were a gap |
| Energy Sector ETF | `XLE` | Sector-level decoupling check | Confirms the XOM/CVX finding isn't a single-stock artifact |
| Saudi Aramco | `2222.SR` | Exporter-side perspective | Every other asset is a consumer or financial-market view; Aramco is the supply side |
| Natural Gas ETF | `UNG` | Completeness | Minor role, included once the pipeline supported it; flagged for roll decay, not load-bearing |

**Data range:** Jan 2016 – Jun 13, 2026 · 16 tickers · Source: yfinance (`auto_adjust=True`), with `align_gulf_asset()` handling the Tadawul (Sun–Thu) to US-calendar forward-fill for Aramco.

---

## Methodology Overview — Update 2

### Five Event Windows

| Window | Dates | Trading Days | Purpose |
|--------|-------|---------------|---------|
| Pre-event (baseline) | Jan 1 – Feb 27, 2026 | 39 | Unchanged from Update 1 — beta estimation baseline |
| Shock (closure) | Feb 28 – Apr 16, 2026 | 33 | Unchanged from Update 1 |
| Reopen (announcement) | Apr 17 – Apr 30, 2026 | 9 | Unchanged from Update 1 (same caveat: Iran re-closed Apr 18) |
| **Correction** | May 1 – May 29, 2026 | — | New. The May Paradox window — price fell while physical capacity stayed near 2% |
| **Diplomacy** | May 30 – Jun 13, 2026 | — | New. Isolates the Jun 10 re-escalation test from the broader correction regime |

### Key Analytical Components — New in Update 2

| Component | Method | Business Question |
|-----------|--------|--------------------|
| `pair_trade_extended()` | Long/short P&L across all 5 windows, multiple pairs | "Which decoupling trades survived into the correction/diplomacy phases?" |
| `freight_oil_spread()` | BWET vs. WTI spread by window | "Is shipping pricing something crude isn't?" |
| `aramco_sovereign_discount()` | 2222.SR vs. fundamental proxy, with Gulf calendar alignment | "Does the actual exporter trade differently from consumer-market proxies?" |
| `tlt_safe_haven_test()` | TLT return/vol by window, same structure as the Update 1 gold test | "Did duration fail the same way gold did?" |
| `window_regime_summary()` | WTI/Gold ratio direction by window | "Which regime — supply or diplomacy — was dominant in each phase?" |
| `escalation_replay()` | Day-1 reaction comparison, Feb 28 vs. Jun 10 | "Did the market react more calmly the second time?" |
| `cross_asset_correlation_delta()` | Correlation matrix, all pairs, all 5 windows | "How did relationships evolve across the full timeline, not just shock vs. pre-event?" |

All Update 1 functions (`seasonal_baseline`, `compute_abnormal_returns`, `correlation_by_window`, etc.) were extended to handle 5 windows and 16 assets automatically rather than rewritten — see `Methodological & Technical Overview: Update 2 Implementation` for the full engineering detail.

### What Was Planned vs. What Was Built (Round 2)

| Planned | Built | Notes |
|---------|-------|-------|
| Extend to ~100 trading days | ✅ 113 trading days (Jan 1–Jun 13) | Landed naturally on the Jun 13 cutoff, just ahead of the framework deal reported in mid-June |
| Add 4–5 new assets | ✅ 6 new assets (16 total) | Aramco ended up necessary, not optional, once the exporter-perspective question was posed |
| 4-window framework (add one "post-shock" window) | ❌ 5 windows | One window wasn't enough to separate the May correction from the Jun 10 re-escalation — they are different regimes and conflating them would have hidden the second-shock finding |
| Reuse Update 1 functions as-is | ❌ Extended in place, backward-compatible | Needed multi-window support; rewriting from scratch would have risked breaking Update 1 reproducibility |
| Single "new findings" chapter | ❌ Split into themed sections (Defense, Freight, Bonds, Aramco) | Each new asset class answers a different question; bundling them would have buried the Aramco and freight findings under the headline May Paradox result |

---

## Key Findings (Quantified) — Update 2

| Finding | Metric |
|---------|--------|
| WTI shock-window return (unchanged from U1) | **+32.9%** |
| WTI correction-window return (May Paradox) | **−14.3% to −20%** |
| Strait transit capacity during correction window | **~2%** (physically unchanged from shock window) |
| BWET shock-window return | **+71.1%** |
| BWET diplomacy-window return | **+20.5%** |
| ITA correction-window return | **+8.9%** (more resilient than broader market) |
| TLT shock-window return | **−3.3%** (second safe-haven failure, alongside gold) |
| Aramco shock-window return | **+8.0%** (lagged WTI, muted across all windows) |
| Jun 10 re-escalation, WTI day-1 reaction | Smaller than Feb 28 (market-learning signature) |

---

## What This Project Proves — Update 2 (No BS)

1. **Diplomacy can override physical scarcity in pricing, even when scarcity hasn't resolved.** The May Paradox is the clearest demonstration: capacity stayed near 2%, price fell anyway.

2. **The WTI/Gold ratio is a regime signal across more than one regime type.** It correctly flagged both the original supply shock (Update 1) and the May reversal (Update 2) — the same tool, two different jobs.

3. **Decoupling is not a single event — it's a recurring structural feature, and it has layers.** Physical oil vs. energy equities (Update 1), now joined by freight vs. crude (Update 2). Each new asset class tested produced its own version of the same underlying phenomenon: financial markets pricing different things than the physical commodity.

4. **Backlog-driven assets (defense) behave differently from spot-driven assets (oil) under the same shock.** ITA's resilience through the correction window — while WTI fell sharply — shows that "war trade" is not one trade.

5. **Markets show a measurable learning effect across repeated shocks.** The muted Jun 10 reaction relative to Feb 28 is evidence, not just intuition, that repeated exposure to the same type of event changes transmission speed and magnitude.

---

## What This Project Does NOT Claim — Update 2

- **That the May Paradox will hold up as "correct" in hindsight.** It describes how the market priced the situation through June 13. It does not predict whether diplomacy or supply risk wins out longer-term.

- **That BWET is investable at the returns shown.** Low AUM (~$25M), 2-year history, futures-based with contango roll decay. The freight-decoupling finding is analytical, not a trade recommendation, more so than any other number in this study.

- **That the Jun 10 "market learning" effect generalizes.** One repeated-event comparison inside one conflict is suggestive, not proof of a general market-learning law.

- **Anything about the eventual resolution of the underlying conflict.** This is explicitly a pre-resolution snapshot. See Update 3 for the resolution chapter.

---

## Technical Implementation — Update 2

| Component | Implementation |
|-----------|-----------------|
| Data source | yfinance (`auto_adjust=True`), 16 tickers |
| Storage | `prices_2016_2026_u2.parquet`, separate from Update 1's parquet |
| New windows | Correction (May 1–29), Diplomacy (May 30–Jun 13) |
| Gulf calendar handling | `align_gulf_asset()` — Tadawul Sun–Thu forward-fill to US calendar (~18h lag, caveated) |
| New functions | 10+ in `event_study.py` — see Methodological & Technical Overview for full list |
| Outputs | 30+ PNG charts (`outputs/update_2/charts/`, new charts prefixed 21–30), 11+ new CSVs (`outputs/update_2/data/`, `_u2` suffix) |

**Dependencies:** unchanged from Update 1 — numpy, pandas, matplotlib, seaborn, statsmodels, yfinance, pyarrow, IPython.

**Reproduction:** Clone repo, `pip install -r requirements.txt`, open `notebooks/02_hormuz_update2.ipynb`, run end-to-end. Cached U2 parquet loads by default; set `CACHE_DATA = False` to re-fetch.

---

## Document Control — Update 2

| Field | Value |
|-------|-------|
| Author | Abdallah A Khames |
| Organization | BODZZ |
| GitHub | github.com/abdallah-bodzz |
| Analysis date | June 13, 2026 |
| Data range | Jan 2016 – Jun 13, 2026 |
| Status | Static snapshot (not live-updated) — second in a series |
| License | MIT |

---

*This section extends the project's methodological appendix for Update 2. For the narrative version of the new chapters, see `STORY.md` (Act V onward). For the quick overview, see `README.md`. Update 1's methodology above this section is preserved unmodified.*