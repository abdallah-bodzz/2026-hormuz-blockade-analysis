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