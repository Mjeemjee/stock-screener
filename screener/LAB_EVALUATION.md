# Strategy Lab Evaluation Contract

The lab is bounded, long-only paper research. It never places trades. Existing
production selections are unchanged unless a repository owner explicitly approves
a qualified branch using the protected GitHub workflow.

## Hypothesis and Branch Contract

- One branch changes one parameter. It only narrows the frozen mother candidate
  set and inherits its ranking. Factor scores are NOT recomputed on the subset.
- Momentum: tighten the distance to the annual high, or raise minimum turnover.
- Oversold: tighten the distance to the annual low, or raise minimum market cap.
- HK value: lower maximum PE, or raise the minimum dividend yield.
- These are predefined research hypotheses, not claims of profitability. They are
  deliberately correlated refinements, not independent new alpha factors.
- Every definition records parent, root, generation, effective parameters,
  source version, hypothesis, expected effect, creation time and definition hash.
- No branch may use a mother snapshot frozen before its creation. Lab execution
  freezes a fresh paired baseline at actual processing time, then reuses the
  existing next-open/calendar/fee evaluator. Re-running the same source is a no-op.

## Score and Gates

- Primary horizon: 5 sessions. Ranking: mean paired branch-minus-parent net return.
- Eight evaluable mother cohorts permit exploration, not promotion.
- Observe only predefined checkpoints of 20, 40 and 60 due cohorts. A checkpoint
  uses the first N due cohorts, not a retrospectively chosen profitable interval.
- Require 90% complete paired/benchmark coverage, 50% nonempty signal rate and
  at least six nonoverlapping complete periods.
- Require positive mean net improvement, positive mean net excess over the price
  benchmark at 15bp and at 30bp per side, and worst net period at least -10%.
- Require a positive approximate lower bound for paired improvement using a
  circular moving-block bootstrap (block length 5, deterministic seed). Alpha is
  divided by the total trial budget and the three looks. This is a conservative
  research gate, NOT a guarantee of formal statistical validity or future profit.
- No annualization or compounding of overlapping cohort returns. Worst period is
  NOT portfolio drawdown; real capital allocation and NAV drawdown remain a
  separate review requirement before practical trading.
- Failure at 60 due cohorts stops the branch. Earlier failed looks keep observing.
  Qualified branches are 'awaiting review', not automatically successful/live.
- Maximum 12 lifetime trials, 6 concurrently observed branches, 2 generations and
  2 children per mother. All failed trials and decisions remain in the ledger.

## Workflow Mapping

Policy: `lab_policy.json`; score and gate runner: `screener/research_lab.py`;
definition notes: immutable lab snapshots plus state event history;
daily loop: `tracking.update_tracking`; archive: `screening_archive/lab/`;
public report: `data/lab.json`; manual approval: `review-lab.yml`.

Changing the policy requires an explicit migration/new study. No silent reset of
the trial budget. Source or mother-parameter changes pause incompatible branches.
Approval requires matching evidence hash, current gates, and unchanged mother
code/parameters. It produces an allowlisted market_rules.json change, committed
by the owner-triggered workflow. It does not silently modify trading code.

Approved refinements are stored in `market_rules.json` under `promotions`, not
in the prescreen parameter map. The cloud scanner ranks the unchanged mother
universe first, then applies the approved narrowing without recomputing scores.
Exported effective market parameters and promotion evidence remain auditable.
Later refinements keep the same underlying ranking universe. Incompatible mother
parameter changes fail closed until explicitly revalidated. Evidence must bind
to the exact current definition and policy, and backup restoration cannot redefine
an existing trial.
