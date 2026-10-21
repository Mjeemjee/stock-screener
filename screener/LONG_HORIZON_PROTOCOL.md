# Fixed Long-Horizon Forward Study

This is a new, independent paper study of the factor lab's two-factor hypothesis.
It does not reuse the legacy paper account as prospective evidence and does not
modify the six existing factor experiments. Production selection is unchanged.

## Frozen Definition

- Original fixed membership: HK 218, US 259, carried from the reviewed lab data.
- Two inputs: negative log mean 20-session adjusted-close times volume, and
  close[t-20]/close[t-250]-1. Both must be available on the same exchange grid.
- Equal average of cross-sectional percentile ranks; deterministic code tie breaks.
- Three same-input controls: combined, momentum only, liquidity only.
- Top 20% equally weighted, long only, 21 exchange-session holding horizon.
- At least 30 valid stocks and 80% fixed-pool data coverage to freeze a signal.
- Actual creation time, available input prefix, membership and code definition
  are immutable. Entry is the first exchange opening strictly after creation.
- Subsequent entries are at least 21 sessions apart. Missed decisions are not
  backfilled. Missing members remain in the pool, never silently replaced.
- Each cohort closes and opens independently: 15bp per side, stress 30bp. This
  conservative full-round-trip assumption is not a claim of drift-adjusted
  continuous portfolio turnover or real fills. Zero-volume entry is cash.
- Exact entry/exit prices are required. Missing prices and ambiguous >60% price
  jumps remain unknown; weights are never reassigned to survivors.
- The first complete paired outcome is sealed. Input/provider corrections require
  separate recorded research; completed evidence is not silently revised.

## Review Clock

6/12/24 nonoverlapping matured cohorts correspond roughly to 6/12/24 months of
uninterrupted operation. Missing or incomplete cohorts can lengthen that period.
The first 24 due cohorts are the fixed review sample; later observations do not
turn a failed first-24 assessment into a selective success. At least 90% paired
coverage, positive adjusted lower bounds against both controls and benchmark,
positive higher-cost benchmark excess, and worst period >= -15% are required for
manual review. Six market/comparison tests share a 5% family alpha. Circular
three-cohort block bootstrap with a fixed seed supplies approximate bounds.
No automatic promotion or trading follows a review label.

Six or twelve months support preliminary monitoring, not proof of durable alpha.
Under a simplified independent-return approximation, t grows with annualized
information ratio times sqrt(years); an unknown true effect size means no fixed
calendar duration can guarantee significance. Correlation, regime changes,
non-normal returns and research selection make inference harder.

## Retrospective Evidence

`long_horizon_history.json` is derived from the lab's strict three-control replay.
Current membership has survivorship bias. History was already inspected during
factor discovery and is not untouched OOS. Unknown periods are retained; summary
means use only complete periods and are explicitly conditional. No complete
strategy NAV or annual return is inferred across missing periods. The short-leg
replay is diagnostic only and does not model borrow availability or borrow fees.
Historical evidence has not qualified this strategy for production promotion.

## Operation

Daily workflow refreshes at most eight missing fixed members using existing
public history providers, then updates the study. The request queue rotates;
failures cannot remove members or lower the 80% gate. Source outages can pause
new signals. Publish workflows preserve frozen records and do not backdate them.
`screening_archive/long_study/` is included in cumulative, anti-rollback restores.
Public output: `long_research.json`; website route: `/lab/long-horizon`.

The local lab reuses this exact forward module from `paper/forward_study.py`.
The old account stays in `paper/state.json` as a historical demonstration, with
a sealed exclusion record. Newly exported tracking uses every strict snapshot,
including already superseded periods, and keeps legacy periods historical.
