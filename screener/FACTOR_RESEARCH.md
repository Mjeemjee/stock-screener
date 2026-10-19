# Factor Research Contract

This is a separate study from the original parameter-branch lab. Its budget and
ledger never replace or reset lab-v1. No orders are placed.

## Hypotheses and Data

The initial hypotheses are volume-confirmed breakouts, compression breakouts and
short-term reversals, independently selected in each market. All use completed
OHLCV bars; benchmark prices are used only for evaluation. Larger signal values
are preferred. Cross-sectional feature values are winsorized (5/95 percentiles)
and standardized; constant features contribute zero. Missing data is not zero.
The existing three trend factors are included as redundancy controls.

Each market freezes the first 40 symbols from the available published liquidity
history pool, independently of current strategy hits. Membership is immutable,
including failures and later missing stocks. This is a bounded liquid-stock
study, not a representative whole-market sample. Initial historical diagnostics
use today's membership and revised adjusted bars: they have survivorship and
revision bias and are never prospective evidence. The first ingestion time is
recorded. Each future market session preserves its available OHLCV input and
feature panel, including missing-member reasons. No intraday or stale bar may
be used as a new signal. A session requires at least 20 valid stocks and 80%
pool coverage; skipped sessions are reported rather than silently backfilled.

## Formula and Iteration Contract

The registry accepts bounded expression trees using named features, mean,
product and negation, plus bounded raw-feature filters. No arbitrary Python,
JavaScript, shell commands, remote URLs or model-written code is executed.
Every proposal has op_type, hypothesis, change, expected, expression, parent,
creation time, engine/policy/universe hashes and immutable definition hash.
An experiment uses only inputs frozen at or after its creation.

Every seven days at most, after 20 fully observed cohorts, an automatic research
job evaluates at most 20 single-feature additions/interactions with a parent.
It records every candidate, including rejected and duplicate formulas. A
candidate needs positive exploratory paired improvement, mean rank IC > 0.02,
and maximum mean absolute daily rank correlation < 0.85 against its parent and
registered controls. Exploration is marked in-sample. At most six searches and
18 total programs are allowed, within 160 reserved comparisons. Qualified
proposals begin a NEW future-only paper experiment; no past cohort is reused as
their validation. Owner-submitted proposals use the same typed formula contract,
trial budget, fingerprint checks and future-only clock. AI-generated proposals
can use this interface; no model provider/credentials are assumed or fabricated.

## Evaluation

Primary horizon is five exchange sessions: first open strictly after decision,
exit five sessions after entry, fixed equal weights, 15bp per side, 30bp stress.
Seed baseline is the whole available research cross-section, equally weighted;
descendants also compare with their frozen parent formula on that same input.
Empty selected baskets stay in cash. Missing prices remain unknown; no dropping
or reweighting unavailable holdings. Zero-volume entry is unexecuted cash.
Benchmarks are SPX/HSI price indexes. Corporate actions and provider adjustments
are not a full execution ledger. The first complete paired price evidence and
completed cohort assessments are frozen; corrections require a separately recorded study.

Only fixed first-20/40/60 due cohort checkpoints can qualify a program for review.
Require 90% coverage, 50% signal rate, six nonoverlapping periods, positive net
paired improvement and benchmark/stressed excess, worst period >= -10%, a
positive approximate block-bootstrap lower bound, and novelty < 0.85. Budget
correction uses all 160 reserved comparisons and three looks, not just winners.
No overlapping-period compounding or misleading NAV/drawdown labels. Approval
marks a reviewed paper strategy; integration into formal screening is separate.

Historical diagnostics use 60-session training segments, purge five label
sessions, an additional five-session embargo, and nonoverlapping 20-session
test folds. Formulas are fixed; no fitting or parameter selection on test folds.
Both Pearson/Rank IC, net top-minus-pool returns, missing-data coverage and fold
dates are reported. These retrospective folds are diagnostics only.

## Workflow Mapping

- Policy/gates: research_policy.json and factor_research.py.
- Signals/validation: research_signals.py and research_validation.py.
- Audit/inputs/prices/runs/evidence: screening_archive/research/.
- Public report: data/research.json; UI: /lab/research.
- Daily operation: research workflow stage after refreshed public history.
- Owner actions: review-factor-research.yml; inputs are parsed as JSON, never code.
- Changes to engine/policy or frozen pool fail closed or pause affected programs;
  study budget never silently resets. Immutable artifacts survive deployment.
