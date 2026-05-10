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