# Factor Research v2 Delivery - 2026-10-19

## Published Version

- Site: https://mjeemjee.github.io/stock-screener/#/lab/research
- Application source: `9cac1486ecfadcc6260ab3a864deb3fb89da6e77`.
- Pages revision: `375ed55388b2ff14b573cf40b24e31b56cd8f3da`.
- Verified publisher: https://github.com/Mjeemjee/stock-screener/actions/runs/39262021290
- Successful Pages deployment: https://github.com/Mjeemjee/stock-screener/actions/runs/39262240895
- Subsequent test/documentation-only changes do not change the research engine
  hash or the deployed application bundle.

## Delivered

Independent volume-confirmed breakout, compression breakout and short reversal
studies, each for US and HK markets. Each market freezes 40 liquid-history-pool
members. Twelve named inputs include nine research features and three legacy
controls. Bounded formula search adds an unused input or interaction after 20
complete cohorts, not merely a tighter threshold. Every search candidate is
recorded; new experiments only use inputs frozen after their creation.

The website provides forward results, separate historical diagnostics, formula
and lineage details, fixed pool quality, a factor registry and a typed proposal
editor with local drafts/import/export. Repository-owner actions start, pause,
reject or approve paper studies through a dedicated workflow. Approval neither
replaces production selection nor places orders.

## Verification

- 102 backend tests, 24 archive/build/validation tests and 17 frontend data tests
  passed locally. Clean cloud regression/build/privacy checks also passed.
- 38 public browser checks passed: research 11, parameter lab 8, screener 11,
  tracking/detail/watchlist 8. Includes desktop and 320/390/768px research layouts,
  real charts, filters, imports/exports, local persistence and recoverable errors.
- Browser-only fixtures exercise mature/review/error states; they are never
  written to public data or the research archive.
- Downloaded the actual cumulative cloud artifact and restored it twice into an
  isolated destination: every JSON record matched, six formal snapshots remained,
  and two research input/run bindings and six programs passed integrity checks.
- Public `data/positions.json`, `data/quotes.json` and `.env` returned 404.
- Public engine hash matched the local engine; the source deploy revision matched.
- The follow-up frontend test accepts additional custom strategy families while
  still checking that all three initial families remain present.

## Initial Live State

Verified report generated at `2026-10-19T13:40:06.429824+00:00`: six testing
programs, zero mature outcomes, two market input snapshots and six pending
observations. Both markets had 40/40 valid members for their latest completed
exchange session, `20261016`. No performance improvement has been established.

## How to Judge Effectiveness

Daily runs accumulate immutable forward decisions and five-session outcomes.
Monitor data coverage first, then paired net improvement against the parent/pool,
benchmark excess, higher-cost excess, worst period, correlation and uncertainty.
Only fixed 20/40/60-period checkpoints can qualify for owner review, with at least
six nonoverlapping intervals and the other policy gates. Twenty overlapping daily
observations alone cannot satisfy that independence gate. Retrospective folds
remain diagnostic and never substitute for forward samples.

Automatic research is bounded formula search, not a connected external language
model or an unlimited source of novel data. New external data families still
require availability, timestamp, quality and leakage validation. Current-pool
historical diagnostics carry survivorship and adjusted-price revision biases;
fees do not fully model market impact or real execution. Passing software tests
does not establish profitability. Full protocol: `screener/FACTOR_RESEARCH.md`.
