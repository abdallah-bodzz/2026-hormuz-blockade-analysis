# Hormuz 2026 — Update 2 Implementation Report
## "When Diplomacy Decoupled From Supply"
### Technical & Analytical Implementation Plan · June 14, 2026

---

## 0. Executive Summary

This document is the working blueprint for Update 2. It covers everything
from data pipeline changes to dashboard architecture decisions. Nothing in
here is aspirational — every item maps to a file you already own or a
specific addition you need to make.

**Cutoff:** June 13, 2026 (captures the volatile diplomacy + June 10
re-escalation; explicitly pre-ceasefire announcement).

**New assets:** 6 additions → 16 total.

**New phases:** 5-window structure replaces 3.

**New notebook:** `02_hormuz_update2.ipynb` (original untouched).

**Headline finding to build toward:** Forward expectations decoupled from
physical supply. The strait was still closed in May while WTI dropped 20%.
That inverts your original finding and gives the project a genuine second
thesis.

---

## 1. Data Pipeline Changes

### 1.1 `src/utils.py` — the only config file you touch first

**`ACTIVE_TICKERS` additions:**

```python
ACTIVE_TICKERS = {
    # --- original 10 ---
    "SP500": "^GSPC",
    "WTI":   "CL=F",
    "GOLD":  "GC=F",
    "XOM":   "XOM",
    "CVX":   "CVX",
    "VIX":   "^VIX",
    "JETS":  "JETS",
    "DXY":   "DX-Y.NYB",
    "DAX":   "^GDAXI",
    "NKY":   "^N225",
    # --- 6 new additions ---
    "ITA":   "ITA",       # iShares US Aerospace & Defense ETF
    "BWET":  "BWET",      # Breakwave Tanker Shipping ETF (NYSE Arca)
    "TLT":   "TLT",       # iShares 20+ Year Treasury Bond ETF
    "XLE":   "XLE",       # Energy Select Sector SPDR ETF
    "ARAMCO": "2222.SR",  # Saudi Aramco (Tadawul)
    "UNG":   "UNG",       # United States Natural Gas Fund
}
```

**BWET note:** NYSE Arca listed, yfinance ticker is `BWET`. Only launched
May 2023, so your 2016-start baseline will have ~3 years of pre-crisis
history. Handle this in `seasonal_baseline()` — it'll have fewer baseline
years than others, flag it explicitly in the caveat column.

**ARAMCO note:** `2222.SR` fetches via yfinance but with caveats: Tadawul
timezone (UTC+3), trades Sun–Thu, different holidays from US markets.
Same issue as Shanghai that you excluded originally. The fix: in
`data_fetcher.py`, after fetching, reindex ARAMCO to the common US trading
calendar and forward-fill weekends/holiday gaps — same approach you should
use, not dropping it. Add it to a new `GULF_ASSETS` list and include a
caveat about non-aligned sessions in `quality_report()`. The analytical
payoff (only Gulf exporter in the universe) justifies the complexity.

**New asset group constants:**

```python
CORE_ASSETS      = ["SP500", "WTI", "GOLD", "XOM", "CVX", "VIX", "JETS"]
DEFENSE_ASSETS   = ["ITA"]
FREIGHT_ASSETS   = ["BWET"]
BOND_ASSETS      = ["TLT"]
ENERGY_SECTOR    = ["XLE"]
GULF_ASSETS      = ["ARAMCO"]
COMMODITY_ASSETS = ["UNG"]
INTL_ASSETS      = ["SP500", "DAX", "NKY"]
DXY_ASSET        = "DXY"
# Convenience: everything for broad analysis
ALL_ASSETS       = list(ACTIVE_TICKERS.keys())
```

**`EVENT_CONFIG` — 5-window structure:**

```python
EVENT_CONFIG = {
    "dates": {
        "Op. Epic Fury (Feb 28)":    "2026-02-28",
        "Ceasefire (Apr 7)":         "2026-04-07",
        "Lebanon CF (Apr 16)":       "2026-04-16",
        "Hormuz Open (Apr 17)":      "2026-04-17",
        "May Correction Start":      "2026-05-01",
        "Iran Re-escalation (Jun 10)":"2026-06-10",
    },
    "windows": {
        # --- original 3, unchanged ---
        "pre_event": ("2026-01-01", "2026-02-27"),
        "shock":     ("2026-02-28", "2026-04-16"),
        "reopen":    ("2026-04-17", "2026-04-30"),
        # --- 2 new phases ---
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
    "estimation_window": ("2026-01-01", "2026-02-27"),
    "analysis_as_of": "June 13, 2026",
    "snapshot_note": (
        "Update 2 static snapshot. Iran–Israel ceasefire announced "
        "June 21–25 — after this cutoff. Update 3 will cover resolution."
    ),
}
```

**`FETCH_END` constant:** change to `"2026-06-13"`.

---

### 1.2 `src/data_fetcher.py` — minimal changes

Add ARAMCO timezone/calendar alignment logic:

```python
def align_gulf_asset(series: pd.Series, reference_index: pd.DatetimeIndex) -> pd.Series:
    """
    Reindex a Gulf-market series (Sun-Thu, UTC+3) to match the
    US trading calendar used by all other assets.
    Forward-fills weekends and holidays — same approach as VIX gaps.
    Adds caveat to quality_report.
    """
    return series.reindex(reference_index, method='ffill')
```

Call this in `fetch_all()` after building the joint DataFrame, specifically
for the `ARAMCO` column before returning.

Add to `quality_report()` caveats:
```
"ARAMCO (2222.SR): Tadawul trades Sun–Thu UTC+3. Reindexed to US calendar
 via forward-fill. Same-day comparison with US assets has a structural lag.
 Treat as directional indicator, not precise same-day data."
```

```
"BWET: Only exists since May 2023. Seasonal baseline covers 2024–2025 only
 (2 years vs 5 for original assets). Baseline statistics marked accordingly."
```

```
"UNG holds near-term natural gas futures subject to roll decay. Returns
 reflect futures performance, not spot nat gas prices."
```

---

### 1.3 Parquet versioning

Don't overwrite `prices_2016_2026.parquet`. Create alongside it:

```
data/raw/
  prices_2016_2026.parquet     ← original, untouched
  prices_2016_2026_u2.parquet  ← Update 2 (16 assets, Jun 13 cutoff)
```

The new notebook loads `prices_2016_2026_u2.parquet`. If that file doesn't
exist, it runs `data_fetcher.run(force_refresh=True)` which writes it fresh.
The original study notebook still finds its original parquet untouched.

---

## 2. New Notebook: `02_hormuz_update2.ipynb`

### Structure overview

```
Part 0:  Update 2 Header & Executive Summary
Part 1:  Setup & Data (16 assets, 5 windows)
Part 2:  What Changed Since April 30 — Phase 4 & 5 Overview
Part 3:  Seasonal Baseline (extended, new assets)
Part 4:  Event Window Analysis — All 5 Windows
Part 5:  The Paradox Correction: May Analysis
Part 6:  June 10 Re-escalation: Second Shock Test
Part 7:  Defense as an Asset Class (ITA analysis)
Part 8:  Freight Rates vs Oil Price (BWET vs WTI)
Part 9:  Bond Market Reaction (TLT — missing from Update 1)
Part 10: Aramco: The Exporter Perspective
Part 11: Energy Sector ETF vs Physical Oil (XLE vs WTI — new pair trade)
Part 12: Updated Cross-Asset Correlation Matrix (all 5 windows)
Part 13: WTI/Gold Ratio — Full Timeline (peace pricing vs scarcity)
Part 14: Updated Lead-Lag & Rolling Beta (new assets)
Part 15: DXY Decomposition — Updated
Part 16: International Spillover — Updated
Part 17: Updated Abnormal Returns (all assets, correction + diplomacy windows)
Part 18: Full Sector Heatmap — 16 assets × 5 windows
Part 19: Pair Trade Analysis — New & Updated
Part 20: Asset Character Cards — All 16 Assets
Part 21: Key Numbers Summary
Appendix A: Methodology
Appendix B: Limitations & Caveats
```

### Key analytical code additions to `src/event_study.py`

**`forward_expectations_signal()`** — new function, goes in after the oil/gold
ratio analysis. Tests whether WTI moves in Phase 4 are correlated with
Polymarket peace probability or ceasefire headline frequency. You won't have
Polymarket data in yfinance, but you can approximate with a dummy binary
variable (0/1) for ceasefire headline days and test the correlation pattern.
Add as a clearly-caveated qualitative analysis with a note that proper
implementation requires event-count data.

**`pair_trade_extended()`** — generalizes the existing Long WTI / Short XOM
function to accept any long/short asset pair. Use it for:
- Long WTI / Short XOM (original, carried forward)
- Long WTI / Short XLE (broader energy equity comparison)
- Long ITA / Short SP500 (defense premium over market — does it exist and when does it close?)
- Long BWET / Short WTI (freight rate premium over commodity price)

**`escalation_replay()`** — runs `first_day_reaction()` on the June 10
re-escalation event the same way you ran it on Feb 28. Direct comparability.
Key question: did assets reprice faster the second time (market already had a
playbook) or slower (shock fatigue)? That's a testable hypothesis.

**Update `vol_regime_periods()`** to accept the new assets. ITA and BWET will
have interesting vol regime patterns worth flagging.

---

## 3. New Findings Structure

The notebook should build toward 6 findings that parallel the original 6:

**Finding 01 (new primary):** Diplomacy decouples from supply.
WTI dropped ~20% in May while the strait was still at 2% transit capacity.
Forward expectations — peace probability — overrode physical scarcity. The
WTI/Gold ratio is the proof: it should peak around April 7 (ceasefire
announcement) and decline through May even as physical conditions are
unchanged. That's the regime shift signal.

**Finding 02:** Defense is not a "war trade" — it's a backlog trade.
ITA gained on day 1 (RTX +4.7%, NOC +6%) then flattened and lagged. But
defense stocks did NOT crater on ceasefire headlines the same way oil did.
Multi-year backlogs ($194B for LMT alone) absorb peace signals differently
than commodity spot prices. Rolling beta of ITA vs SP500 vs WTI tells this
story — ITA should become more correlated with SP500 over time and less
correlated with WTI.

**Finding 03:** Freight rates decoupled from tanker equity stocks — a third
layer of decoupling. BWET returned ~+100% YTD while tanker stocks averaged
flat to -1% since Feb 27. VLCC rates spiked +150% then fell back. The ETF
holds futures, not equities. That's a direct parallel to your original oil/
energy-equity finding, now in the shipping space.

**Finding 04:** Treasury bonds failed as a safe haven in Phase 3-4 (TLT
likely sold off on inflation expectations from supply shock, then recovered
as peace pricing dominated). This completes the safe haven failure trifecta:
gold failed, bonds failed, traditional risk-off didn't work.

**Finding 05:** Aramco's behavior under its own product shock. Aramco
maintained 12.6M bbl/day production using the East-West pipeline to bypass
the strait — its Q1 2026 EPS beat forecasts by 22% and free cash flow jumped
62%. But the stock has been under pressure, trading well below its 52-week
high. The finding: a state-owned exporter that benefits from the price shock
but faces geopolitical sovereign discount is a third asset regime — not
the same as a Western energy equity.

**Finding 06:** Second shock replication test (June 10). Did the day-1
reaction pattern from Feb 28 repeat? If oil spiked and equities fell again
but with a smaller magnitude, that's evidence of playbook adoption and
diminishing shock transmission — a market learning effect.

---

## 4. `src/event_study.py` — Specific New Functions

```python
def pair_trade_extended(prices, pairs: list, windows: dict = None) -> pd.DataFrame:
    """
    Generalized version of the existing long/short analysis.
    pairs: list of (long_asset, short_asset, label) tuples.
    Returns long-form DataFrame with per-window P&L for each pair.
    """

def escalation_replay(prices, event_dates: dict, assets: list) -> pd.DataFrame:
    """
    Runs first_day_reaction() on all event dates and returns a 
    side-by-side comparison structured for chart visualization.
    Designed to test whether shock magnitude changed across events.
    """

def forward_expectations_proxy(prices, oil_col='WTI', 
                               ceasefire_dates: list = None) -> pd.DataFrame:
    """
    Constructs a simple binary proxy for 'diplomacy dominates' days.
    ceasefire_dates: list of known ceasefire/peace announcement dates.
    Returns a DataFrame aligning WTI daily returns with a 0/1 diplomacy flag.
    Caveat: this is a post-hoc proxy. Real implementation needs event-count data.
    """

def defense_premium(prices, defense_col='ITA', benchmark='SP500',
                    windows: dict = None) -> pd.DataFrame:
    """
    Measures ITA abnormal return over SP500 per window.
    Equivalent to compute_abnormal_returns() but purpose-built
    to isolate the 'geopolitical premium' in defense stocks.
    """

def freight_oil_spread(prices, freight_col='BWET', 
                       oil_col='WTI') -> pd.DataFrame:
    """
    Tracks the spread between freight futures (BWET) and
    physical oil (WTI) returns across event windows.
    The spread is the third decoupling finding.
    """
```

---

## 5. Outputs Structure

```
outputs/
  # --- original 20 charts, regenerated with updated data where relevant ---
  01_normalised_prices.png         ← regenerate: show all 5 windows
  02_seasonal_baseline.png         ← regenerate: new assets added
  03_rolling_volatility.png        ← regenerate: updated date range
  04_rolling_correlation.png       ← regenerate
  05_abnormal_returns.png          ← regenerate: new windows
  06_counterfactual.png            ← regenerate
  07_sector_portfolio.png          ← regenerate
  08_vix_fear_gauge.png            ← regenerate: full timeline
  09_vol_comparison.png            ← regenerate
  10_transmission_speed.png        ← regenerate
  11_first_day_reactions.png       ← regenerate: now shows all 6 events
  12_lead_lag_ccf.png              ← regenerate
  13_rolling_beta.png              ← regenerate: ITA and BWET added
  14_dxy_decomposition.png         ← regenerate
  15_vol_regime.png                ← regenerate
  16_international_spillover.png   ← regenerate
  17_oil_gold_ratio.png            ← regenerate: full timeline
  18_sector_heatmap.png            ← regenerate: 16×5 matrix
  19_long_short_wti_xom.png        ← regenerate
  20_three_panel_performance.png   ← regenerate

  # --- new charts (21–30) ---
  21_five_window_overview.png      ← 5-phase price paths, hero chart for Update 2
  22_defense_asset_analysis.png    ← ITA day-1 reaction, rolling beta, premium
  23_freight_vs_oil.png            ← BWET vs WTI vs tanker equity spread
  24_treasury_safe_haven.png       ← TLT behavior across all 5 windows
  25_aramco_exporter.png           ← 2222.SR vs WTI — exporter paradox
  26_xle_vs_wti_pair.png           ← New pair trade: Long WTI / Short XLE
  27_escalation_replay.png         ← Feb 28 vs Jun 10 first-day comparison
  28_forward_expectations.png      ← WTI/Gold ratio full timeline + diplomacy events
  29_all_pairs_pnl.png             ← All 4 pair trades in one comparison chart
  30_16x5_heatmap.png              ← Full 16-asset × 5-window heatmap

  # --- updated CSVs ---
  event_window_stats_u2.csv        ← _u2 suffix on all CSVs, keeps originals
  abnormal_returns_u2.csv
  seasonal_baseline_u2.csv
  correlation_by_window_u2.csv
  sector_heatmap_u2.csv
  lead_lag_ccf_u2.csv
  rolling_betas_u2.csv
  international_spillover_u2.csv
  first_day_reactions_u2.csv
  shock_transmission_speed_u2.csv
  summary_key_numbers_u2.csv
```

**Naming convention:** `_u2` suffix on all new outputs. This means the
dashboard can link to both versions, original CSVs stay downloadable, and
you don't break the existing site while updating it.

---

## 6. `index.html` — Dashboard Updates

The current HTML is well-structured. The update strategy is additive, not
a rewrite. Specific changes:

### 6.1 Version banner — add at the top of `#topnav`

```html
<!-- Under the nav brand, before nav links -->
<div class="version-strip">
  <span class="version-badge">Update 2 · Jun 13, 2026</span>
  <span class="version-note">Pre-ceasefire snapshot · Update 3 covers resolution</span>
</div>
```

Style it as a 1px-high strip in `--red-dim` background, `--font-mono` text at
0.55rem. Positioned just under the nav or as part of it. It tells the reader
immediately this is a living document.

### 6.2 `#timeline` section — extend to 5-column grid

Current: `grid-template-columns: 2fr 1fr 1fr`
New: `grid-template-columns: 2fr 1fr 1fr 1fr 1fr`

At tablet breakpoint (≤1024px): stack all 5 as `1fr`.

Add two new phase blocks:

```html
<div class="phase-block correction">
  <div class="phase-badge correction">Correction</div>
  <div class="phase-dates">May 1 – May 29, 2026 · 21 days</div>
  <div class="phase-title">Diplomacy Beats Supply</div>
  <p class="phase-desc">
    The strait was still at 2% transit capacity. WTI dropped 20% anyway —
    worst oil month since COVID — as ceasefire negotiations dominated 
    forward pricing. The WTI/Gold ratio reversed. Physical scarcity lost
    to market expectations for the first time.
  </p>
  <div class="phase-stat">
    WTI: <span class="nval">−~20%</span> · Strait still closed<br>
    VIX: normalizing · Gold: recovering
  </div>
</div>

<div class="phase-block diplomacy">
  <div class="phase-badge diplomacy">Diplomacy</div>
  <div class="phase-dates">Jun 1 – Jun 13, 2026 · 9 days</div>
  <div class="phase-title">Re-escalation & Cutoff</div>
  <p class="phase-desc">
    Iran's June 10 announcement of full commercial closure. WTI spiked 
    toward $100+ on Trump ceasefire rejection, then fell on renewed 
    deal talks. Second shock event — same framework, new test.
  </p>
  <div class="phase-stat">
    Jun 10 WTI day-1: <span class="nval">TBD</span><br>
    Cutoff: Jun 13 · Ceasefire announced Jun 21–25 (after cutoff)
  </div>
</div>
```

Add corresponding CSS for `.phase-badge.correction` (amber/gold color) and
`.phase-badge.diplomacy` (steel blue). Also add `.phase-block.correction` and
`.phase-block.diplomacy` with appropriate border-top accent colors.

### 6.3 `#findings` section — add Update 2 findings

After the existing `.fragmentation-box`, add a new block:

```html
<div class="update2-findings">
  <div class="update2-label">Update 2 · New Findings</div>
  <!-- 3 new finding items in the same .finding-item structure -->
  Finding 07: Diplomacy decouples from supply
  Finding 08: Defense is a backlog trade, not a war trade
  Finding 09: Freight futures vs tanker equity — a third decoupling
</div>
```

Keep it visually separated from Update 1 findings with a thin labeled divider.

### 6.4 `#charts` section — add new tab

Current tabs: Primary / Counterfactual / Seasonal / Volatility / All 20 Charts

Add: **Update 2 Charts** tab (shows 21–30).

The tab structure already supports this — just add a `.tab-btn` and a
`#tab-update2` panel in the same pattern.

Update the "All Charts" tab to "All 30 Charts" and include the new thumbnails.

### 6.5 `#data` section — add Update 2 tables

After Table 3 (seasonal), add:

- Table 4: 5-Window Return Matrix (16 assets × 5 windows)
- Table 5: New Asset Debut Performance (ITA, BWET, TLT, XLE, ARAMCO, UNG)

Update CSV download strip to include `_u2` versions.

### 6.6 `#mandates` section — add Mandate VII

```html
<div class="mandate-item">
  <button class="mandate-toggle">
    <span class="mandate-n">VII</span>
    <span class="mandate-title">
      When peace pricing dominates physical supply, exit the pair trade 
      and watch the WTI/Gold ratio for the reversal signal
    </span>
    ...
  </button>
  <div class="mandate-body">
    <p>
      The May 2026 correction proved that forward expectations can override
      physical scarcity. The WTI/Gold ratio peaked on April 7 and began
      declining even as the strait remained closed. That ratio peak is the
      exit signal for the Long WTI / Short XOM pair trade — not the 
      ceasefire announcement itself, which came later and with more noise.
    </p>
  </div>
</div>
```

---

## 7. `README.md` Updates

**TL;DR table** — add 3-4 new rows:

```markdown
| May Correction (WTI) | −~20% | Strait still closed — diplomacy dominated |
| ITA day-1 (Feb 28) | +4-6% | Defense priced as escalation hedge |
| BWET YTD | +~100% | Freight futures vs tanker equity: third decoupling |
| June 10 re-escalation day-1 | TBD (from notebook) | Second shock test |
```

**Asset Universe table** — extend to 16 assets.

**Event Windows table** — extend to 5 windows.

**Navigation section** — add Update 2 sections.

**Snapshot note** — update `analysis_as_of` and add the ceasefire-after-cutoff
caveat prominently.

---

## 8. `STORY.md` Updates

The story currently has a natural ending at the April 30 "false dawn."
Update 2 needs a new chapter structure.

**Add between "Act IV: The False Dawn" and "What Broke":**

```markdown
## Act V: The Paradox — When Supply Stopped Mattering
[~600 words on the May correction]
The strait was still closed. Physically nothing changed.
But WTI dropped 20% in May anyway...
```

```markdown
## Act VI: The Second Shock — June 10 Replay
[~400 words on the June 10 re-escalation]
Iran re-closed on June 10. Markets had a playbook now...
```

**Update "What This Means for the Next Time"** — add a fourth mandate on the
diplomacy/supply decoupling exit signal.

**Update "What This Does NOT Prove"** — add the forward-expectations caveat.

**Update all static KPI references** at the top of the file.

**Add at the very top:**

```markdown
> **Update 2 — June 13, 2026:** This document has been extended through
> June 13. The Iran–Israel ceasefire was announced June 21–25, after this
> cutoff. Update 3 will cover the resolution chapter. 
```

---

## 9. `CITATION.cff` Updates

```yaml
title: "Hormuz 2026: When Oil Decoupled from Everything [Update 2]"
abstract: "Update 2 extends the study through June 13, 2026, adding
  Phases 4–5 (May correction, volatile diplomacy) and 6 new assets
  (ITA, BWET, TLT, XLE, ARAMCO, UNG). Key new finding: forward
  expectations decoupled from physical supply — WTI dropped ~20% in
  May while the strait remained at 2% transit capacity. Defense stocks
  exhibited backlog-driven persistence. Freight futures (BWET) created
  a third decoupling layer. Total assets: 16. Windows: 5. Data cutoff:
  June 13, 2026. Pre-ceasefire snapshot."
date-released: 2026-06-14
```

---

## 10. `docs/Planning & Brainstorming Log.md`

Add an Update 2 section documenting:
- Asset selection rationale and what was rejected
- The 5-window vs 3-window decision
- June 13 cutoff choice and why
- Key decisions you made and are defending

This log is underrated — it's what makes the repo feel like active research
rather than a finished artifact.

---

## 11. Re-extensibility Design Principles

The reason to think about this now rather than later: every structural
decision you make in Update 2 either makes Update 3 a 30-minute job or
a full rewrite.

**In `utils.py`:** The `EVENT_CONFIG` dict is already the single source of
truth. Keep it that way. Never hardcode a date in the notebook.

**In the notebook:** Keep Phase analysis modular — each Part should run
independently so adding Phase 6 windows doesn't require rerunning Parts 1–15.

**In `index.html`:** The phase blocks, tab system, and mandate accordion
are all data-driven from the HTML structure. Adding Update 3 means adding
two HTML blocks, not restructuring the layout.

**Parquet versioning:** `prices_2016_2026_u2.parquet`, `prices_2016_2026_u3.parquet`.
Never overwrite. Total file size per parquet is ~15-20MB for 16 assets so
storage is irrelevant.

**Chart naming:** `21_` through `30_` prefix for Update 2 new charts.
Update 3 new charts start at `31_`. The "All Charts" tab just expands.

**CSV naming:** `_u2` suffix, `_u3` for next round. Original downloads
always remain available.

**The `snapshot_note` field in `EVENT_CONFIG`:** This is shown in the footer
of `index.html` and at the top of both markdown files. Update it in one
place and it propagates everywhere. Add code in the notebook to read and
display this note rather than embedding the date as a string literal.

---

## 12. Execution Order

This is the order to do the work, not just the order the files exist:

1. `src/utils.py` — update tickers, windows, constants. Everything else
   depends on this.

2. `src/data_fetcher.py` — add ARAMCO alignment logic, update `FETCH_END`.
   Run `data_fetcher.run(force_refresh=True)` to generate `_u2.parquet`.
   Verify all 16 assets fetched cleanly. Check BWET has data from May 2023+.

3. `src/event_study.py` — add 4 new functions. Do not touch existing
   functions — extend only. Verify all existing functions still work with
   5 windows in `EVENT_WINDOWS` (they should, they're dict-driven).

4. `02_hormuz_update2.ipynb` — build Parts 0–21 sequentially.
   Run end to end. Fix fetch errors. Generate all 30 charts and 11 new CSVs.

5. `README.md` and `STORY.md` — update narratives and tables.
   These depend on the notebook numbers being finalized.

6. `index.html` — structural updates (version banner, 5-window timeline,
   new findings, new chart tab, updated tables, new mandate). This is the
   most time-intensive single file.

7. `CITATION.cff` and `docs/Planning Log.md` — quick updates, do last.

8. Git commit with a clean message: `Update 2: Jun 13 cutoff — 16 assets,
   5 windows, diplomacy decoupling finding`.

9. GitHub Pages redeploys automatically on push to main if configured.
   Verify the live dashboard renders correctly.

---

## 13. Data Validation Checklist

Before moving to notebook work, verify:

- [ ] All 16 tickers fetch without error in yfinance
- [ ] BWET has data from at least January 2024 (pre-crisis baseline available)
- [ ] 2222.SR fetches and aligns correctly after the timezone fix
- [ ] UNG returns look correct (futures-based, subject to roll — verify
      it doesn't show obvious data errors around month-end)
- [ ] `prices_2016_2026_u2.parquet` has shape `(~2,700+ rows, 16 cols)`
- [ ] Missing % for all assets is <10% (flag anything above that)
- [ ] ITA and TLT show pre-crisis data from January 2026 onward without gaps

---

## 14. One Risk to Flag Explicitly

**BWET liquidity caveat:** BWET has only $24.9M AUM and trades at volumes
that make it a poor real-world trading instrument. The 3.5% expense ratio
and K-1 tax treatment also matter. For the study you're tracking its price
as a *market signal* of tanker rate expectations, not recommending it as
an investment. State this clearly in the notebook (Part 8) and in the new
limitations section. The finding (freight futures vs tanker equity
decoupling) is analytically valid regardless of whether BWET is investable
at scale.

**Aramco political economy caveat:** Aramco's stock behavior reflects Saudi
state policy as much as market fundamentals. The Saudi government can and
does intervene in production, pricing, and dividend decisions. A 22% EPS
beat during a supply shock is partly because Aramco rerouted production via
the East-West pipeline — a decision made by the state, not the market. Frame
the Aramco analysis as "exporter sovereign response" not "energy equity
response." That distinction is analytically important and makes Finding 05
more precise.

---

*Report compiled June 14, 2026 · Hormuz Update 2 planning document*
