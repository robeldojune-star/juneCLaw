# Fujimoto Strategy Research Validation (Credibility-First)

Use this reference when the user asks for deep research on Fujimoto-style strategy before implementation.

## 1) Source Credibility Tiers

- **Tier A (highest)**: Primary publisher/official pages, direct author interviews, full-text book TOC/official summaries.
- **Tier B**: Reputable financial media interviews/summaries with identifiable editorial standards.
- **Tier C (lowest)**: Blogs, recap posts, secondary summaries, SEO pages.

Rule: strategy rules are only **confirmed** when supported by Tier A/B overlap. Tier C is hypothesis-only.

## 2) Confidence Labeling (must appear in outputs)

- **Confirmed**: corroborated by Tier A or multiple Tier B with no conflict.
- **Plausible**: repeated in secondary sources but not fully verified in primary text.
- **Unverified**: single-source claim or paywalled/partial snippet only.

## 3) Claims observed in this session

- Confirmed/Plausible core themes:
  - Emphasis on **増収・増益・増配** (growth in sales/profit/dividend)
  - Heavy use of **technical indicators** and daily discipline
  - Existence of **1:2:6 rule** as a framing concept
- Unverified specifics (do not hard-code yet):
  - Exact RSI thresholds as immutable personal rule
  - Exact add-on execution semantics of 1:2:6 under adverse move

## 4) KR Day-Trading Adaptation Guardrails

When adapting to KR intraday pipeline:

1. Keep Fujimoto logic as **auxiliary filter** first (not independent auto-order strategy).
2. Separate:
   - Fundamental prefilter (OpenDART)
   - Timing filter (OR10/OR30 + RSI band)
   - Liquidity filter (volume/value thresholds)
   - Risk block (overheat gap, RSI extreme, OR re-breakdown)
3. Treat 1:2:6 as **risk-budgeted staged entry**, not unconditional averaging down.
4. If first entry thesis breaks, disallow additional entries.

## 5) Rollout Sequence

1. Register rules in docs/registry.
2. Run **shadow mode** logging first (score only, no behavior change).
3. Compare ON/OFF filter effects over accumulated samples.
4. Promote only after readiness gates pass (`rows_used`, `trade_count`, quality checks).

## 6) Reporting Template

For every research response, provide:

- source table (URL/domain/tier)
- claim table (claim/confidence/evidence)
- implementation status (`research_only`, `shadow_mode`, `paper_ready`, `live_blocked`)
- explicit unresolved questions

This prevents overfitting to biography content and keeps strategy implementation evidence-driven.
