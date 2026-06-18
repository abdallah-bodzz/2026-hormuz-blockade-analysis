# Project Planning Log: 2026 Hormuz Analysis
## What We Planned, What We Changed, What We Learned

**Lead Developer:** Abdallah A Khames
**Timeline:** April 2026 (1 week from concept to publication)

---

## Original Concept

The initial idea was straightforward: study the market impact of the Feb 28, 2026 US/Israel strikes on Iran and the subsequent Strait of Hormuz closure. The core appeal was timeliness — this was happening in real time as we planned the analysis.

**First draft scope:**
- 3 assets (S&P, WTI, Gold)
- Basic event windows (pre, during, post)
- Simple return comparisons

**Problem:** Too thin. Would look like a weekend project, not a portfolio piece.

---

## The Pivot

The key insight came from identifying the **structural weakness** of a short event window (only ~7 weeks of crisis data). The fix: a **multi-year seasonal baseline** (Jan–Apr 2021–2025 vs 2026). This turned a weakness into a strength — suddenly we could quantify "how unusual was 2026?" with hard numbers.

**What we added based on this insight:**
- 5-year baseline (later expanded to 10 years)
- Rolling volatility comparison across years
- Counterfactual projection ("what if no shock?")

**What we removed:**
- "Best time to buy" framing (no statistical basis)
- Trading strategy claims (pre-cost only, clearly caveated)

---

## Asset Expansion Decisions

| Asset | Added? | Rationale |
|-------|--------|-----------|
| DXY (dollar index) | ✅ | Needed to decompose WTI move into currency vs supply |
| VIX | ✅ | Test whether commodity volatility translated to equity panic |
| JETS (airlines) | ✅ | Capture demand destruction vs fuel cost channel |
| DAX, Nikkei | ✅ | Test geography as a transmission factor |
| Crypto (BTC) | ❌ | Would add complexity without clear signal; decision matrix said skip |

**BTC decision matrix:**
| If... | Then... |
|-------|---------|
| Data available cleanly | Include as 1 cell |
| Complicates pipeline | Drop it |

We dropped it. No value lost. The project already has 10 assets.

---

## What We Planned vs What We Actually Built

| Planned | Built | Why the change |
|---------|-------|----------------|
| 5-year baseline (2021–2025) | 10-year baseline (2016–2026) | More statistical power, negligible extra effort |
| Simple OLS abnormal returns | OLS + bootstrap confidence intervals | Needed to show uncertainty around point estimates |
| Rolling correlation only | Rolling + window-averaged correlations | Cleaner regime detection for presentation |
| Basic matplotlib charts | 20+ publication-ready PNGs | All saved to outputs/ for inclusion in README/STORY |
| Interactive Plotly dashboard | Static matplotlib only | PDF/PNG export more useful for reporting |
| "Best time to position" framing | "Observed patterns and regime shifts" | Honest scope limitation |

---

## What Worked Well

**1. The WTI/Gold ratio as regime discriminator**
This was a late addition. It turned out to be the single cleanest signal in the entire dataset. Rising ratio = supply shock, falling ratio = fear. Simple, interpretable, actionable for risk managers.

**2. The counterfactual projection**
Planned as a "cool insight" — ended up being essential for communicating shock magnitude. The shaded region in the chart is instantly understandable, even to non-technical readers.

**3. The seasonal baseline chart (02_seasonal_baseline.png)**
One chart that shows 2026 as a complete outlier across 5 prior years. Kills the "was this really that unusual?" question immediately.

**4. The pair trade (Long WTI / Short XOM)**
We nearly omitted this because it felt too "trading desk." But the decoupling was so stark that ignoring it would have been dishonest. We added it with explicit pre-cost caveats.

**5. The limitations section**
Placed prominently, written honestly. This builds more trust than any number of perfect R² values.

---

## What We'd Do Differently

**With unlimited time (not realistic):**
- Add intraday data to resolve the lag 0 CCF ambiguity
- Collect institutional position-level data to confirm gold margin-call hypothesis
- Run event studies on historical supply shocks (2019 tanker attacks, 2022 Russian oil ban) for comparison

**With the same 1 week:**
- Nothing. The scope was correct. More would have been over-engineering.

---

## Key Decisions We're Defending

| Decision | Criticism we anticipated | Our defense |
|----------|-------------------------|-------------|
| No ML / no predictions | "Why not predict oil?" | No statistical basis. This is a post-mortem, not a forecasting engine. |
| Static matplotlib only | "Why not Plotly?" | PNGs embed in README/STORY. Interactivity adds zero value for PDF distribution. |
| "Reopening" window naming | "It wasn't actually reopened" | We caveat this 4+ times. The market treated it as a reopening — that market reaction is informative regardless of facts on the ground. |
| No transaction costs in pair trade | "This overstates returns" | We state "pre-cost" repeatedly. Adding realistic costs would require assumptions we can't defend. Directional finding, not trade rec. |

---

## Lessons for Next Project

1. **Seasonal baselines turn short windows into strengths.** Apply this pattern to any event study with limited temporal data.

2. **Ratio signals (WTI/Gold) often beat volatility signals (VIX) for regime detection.** Worth exploring other asset pairs (e.g., Copper/Gold for growth shocks).

3. **Acknowledge what you don't know explicitly.** The gold margin-call hypothesis is directional, not proven. Saying this openly is disarming.

4. **Ship when it's "done enough."** This project took 1 week. Week 2 would have had diminishing returns. Perfectionism kills publication.

---

## Final Thoughts (Personal)

This project was built while the event was still unfolding (April 2026). The dual blockade — US on Iranian ports, Iran on commercial traffic — continues as of the April 30 cutoff. That means the analysis is a snapshot of market reactions to an ongoing situation, not a final verdict.

That's fine. That's the point. Markets react to information in real time, not at "the end of history." Capturing that reaction is valuable regardless of what happens next.

If the situation evolves materially (full resolution, re-escalation, new blockade), that's a separate study. This one closes at April 30, 2026.

---

**Abdallah A Khames**
**BODZZ · May 2026**

*"The market treated energy equities and physical oil as fundamentally different exposures during the 47-day closure. One rose 33%. The other fell. They were not the same trade."*

---
---

# Update 2 Planning Log: Expanding the Window
## What Changed, Why, and What We Learned the Second Time

**Lead Developer:** Abdallah A Khames
**Timeline:** June 2026 · Data cutoff extended to June 13, 2026

---

## Why Update 2 Happened

Update 1 closed at April 30, 2026, with an explicit note in this log: *"If the situation evolves materially (full resolution, re-escalation, new blockade), that's a separate study."*

It evolved materially. The strait stayed at roughly 2% transit capacity through May while WTI fell sharply — the opposite of what a naive "supply still constrained → price still elevated" model would predict. Then a second escalation hit on June 10. That's not noise sitting on top of Update 1's story. That's a second regime the original 3-window framework had no language for. The fix isn't a patch to Update 1 — it's a second study built on the same scaffolding.

**The decision we made early and didn't relitigate:** Update 1's files stay untouched. New parquet, new notebook, new output folder, `_u2` suffix on every derived file. If Update 2 had broken backward compatibility with Update 1, we would have lost the ability to show "here's what changed in our own thinking" — which is itself part of the value of a multi-part series.

---

## The Core Pivot: From "Decoupling" to "Regime Switching"

Update 1's spine was a single decoupling: physical oil vs. energy equities. Update 2's spine is different in kind, not just bigger — it's about **which regime is pricing the asset at any given moment**, and how that regime flips.

**The May Paradox is the reason the whole update exists.** Without it, Update 2 would just be "Update 1 but longer," which isn't worth shipping. With it, there's a genuine second finding: forward-looking diplomacy expectations overrode physical scarcity pricing, inverting the mechanism (not just the magnitude) of Update 1's core result. WTI/Gold ratio — which was already Update 1's best signal — turned out to be the same tool that detects this second regime. That continuity is the throughline we built the new chapters around.

---

## Asset Expansion Decisions (Round 2)

| Asset | Added? | Rationale |
|-------|--------|-----------|
| ITA (Defense ETF) | ✅ | Tests whether "war trades" are spot-driven or backlog-driven over a multi-month horizon — couldn't ask this question in a 47-day window |
| BWET (Freight/Tanker ETF) | ✅ | A third decoupling layer (shipping vs. crude vs. equities). High signal, but flagged hard for limited history and low AUM — see caveats |
| TLT (20+Y Treasury ETF) | ✅ | Update 1 tested gold as a safe haven and it failed. Bonds were the obvious missing half of "traditional 60/40 hedge" — should have been in Update 1, wasn't, fixed here |
| XLE (Energy Sector ETF) | ✅ | XOM/CVX are single names; XLE lets the energy-equity-vs-oil decoupling be tested as a sector-level effect, not a stock-picking artifact |
| ARAMCO (2222.SR) | ✅ | Every other asset in the study is a consumer-side or financial-market view of the shock. Aramco is the actual exporter. Needed the supply-side perspective, with explicit Tadawul calendar caveats |
| UNG (Natural Gas ETF) | ✅ | Cheap addition once the pipeline was extended; included for completeness, flagged for roll decay, not load-bearing for any core finding |

**What we didn't add, and why:** we considered pulling in a second freight benchmark to cross-check BWET, given how thin its trading history is. Decision matrix said skip — one already-caveated proxy is honest; two thin proxies just compounds uncertainty without resolving it. Better to flag BWET clearly once than to dilute the caveat across two assets.

---

## Window Expansion: 3 → 5

| Old (Update 1) | New (Update 2) | Why |
|---|---|---|
| Pre-event | Pre-event | Unchanged — still the beta estimation baseline |
| Shock | Shock | Unchanged — Feb 28–Apr 16 closure, untouched |
| Reopening | Reopen | Renamed for consistency, same dates, same caveat (Iran re-closed Apr 18) |
| — | **Correction** | New. May 1–29. Required to even state the May Paradox — without a window boundary here, "WTI fell in May" has no event-study structure behind it |
| — | **Diplomacy** | New. May 30–Jun 13. Separates the Jun 10 re-escalation test from the broader correction regime, so the second shock doesn't get averaged away inside a 6-week window |

The two-window expansion wasn't scope creep — it was a structural requirement. You cannot make a falsifiable claim like "diplomacy decoupled from supply in May" using a 3-window framework built for a single shock-and-resolution arc. The framework had to grow before the new thesis could be tested at all, not after.

---

## What Worked Well (Round 2)

**1. The WTI/Gold ratio, again.** Same signal, new regime. It correctly flagged the May reversal and gave us a clean, pre-existing tool rather than requiring a new metric invented post-hoc to fit the narrative. This is the strongest continuity argument for the whole series.

**2. Keeping U1 and U2 fully separate.** Backward-compatible function signatures in `event_study.py` meant zero risk of silently changing an Update 1 number while building Update 2. Worth the extra discipline.

**3. The Jun 10 second-shock test.** Comparing day-1 reactions across two separate escalation events (Feb 28 vs. Jun 10) inside the same study is the kind of repeated-event comparison Update 1 explicitly flagged as future work ("run event studies on historical supply shocks... for comparison"). We didn't have to wait for a different historical event — this project generated its own second data point.

**4. ARAMCO forward-fill.** Getting the Tadawul (Sun–Thu) to US-calendar alignment right, with an explicit ~18h lag caveat attached everywhere the asset appears, meant we could include the exporter's perspective without quietly overstating same-day comparability.

---

## What We're Defending (Round 2)

| Decision | Criticism we anticipated | Our defense |
|---|---|---|
| Including BWET despite 2-year history | "Not enough baseline to mean anything" | Flagged everywhere — character card, every chart, every CSV note. It's presented as a signal, not a statistically mature time series. The alternative (excluding it) loses the freight-decoupling finding entirely. |
| Calling May a "paradox" rather than just "a correction" | "Markets always mean-revert, this isn't surprising" | The strait *did not reopen* in May — capacity stayed near 2%. A pure mean-reversion story doesn't explain why price fell while the physical constraint didn't change. That gap between price and physical reality is the actual paradox, not the direction of the move alone. |
| Keeping the analysis as a static snapshot through a live, fast-moving diplomatic situation | "Why not wait for resolution before publishing?" | Same answer as Update 1: capturing the market's read of an unresolved situation is itself the finding. Waiting for resolution turns this into hindsight commentary instead of a documented real-time read. The series format (U1 → U2 → U3) is the actual answer to "shouldn't you wait" — we don't wait, we iterate. |
| Five windows instead of trying to model continuous regime transitions | "Discrete windows are an oversimplification of a continuous process" | True, and stated as a limitation. Discrete windows are legible and reproducible. A continuous regime-switching model is a legitimate follow-up, not a reason to withhold a simpler, auditable version now. |

---

## Lessons for Update 3

1. **The framework absorbed a second event without a rewrite.** `EVENT_CONFIG` being the single source of truth for window dates meant adding two windows was a config change plus a notebook re-run, not a redesign. That validates the re-extensibility bet made early in Update 2.

2. **A thesis needs a window boundary before it's a finding.** The May Paradox didn't exist as a statement until the Correction window existed as a defined object. Anticipate this for Update 3: whatever the post-resolution thesis turns out to be, it will need its own window before it's anything more than a narrative claim.

3. **Caveat density should scale with asset thinness, not with how good the story is.** BWET produced the most dramatic numbers in Update 2 and got the most caveats, on purpose. That ordering should hold for Update 3 too — the more compelling a number is, the more scrutiny its underlying data deserves, not less.

4. **Keep shipping in discrete updates rather than one continuously-revised document.** A versioned series (U1, U2, U3) is more honest about what was known and when than a single file that quietly gets rewritten as new information arrives. Future readers can see what the May-2026 view looked like even after Update 3 changes the ending.

---

**Abdallah A Khames**
**BODZZ · June 2026**

*"The May Paradox isn't that the market was wrong. It's that the market was answering a different question than 'is the strait open' — it was pricing whether it would stay closed. Those are not the same number."*