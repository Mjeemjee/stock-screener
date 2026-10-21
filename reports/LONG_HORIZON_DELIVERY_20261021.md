# Independent Long-Horizon Study Delivery

Date: 2026-10-21. Public route: `#/lab/long-horizon`.

## Scope

- Preserve production strategies, their tracking output, and the six existing factor studies.
- Add an independent, immutable, long-only 21-session paper study with combined,
  momentum-only and liquidity-only branches. No automatic promotion or orders.
- Freeze actual creation timestamps and inputs; use the next unopened exchange
  session; preserve every cohort and first complete paired outcome in cumulative backups.
- Missing exact execution prices stay unknown. Missing members cannot change the
  fixed pool or receive redistributed weights. Coverage below 80% blocks new signals.
- Refresh at most eight missing fixed members daily using existing public providers.

## Evidence And Limitations

The strict replay uses 140 periods per market. Combined complete-period coverage:
HK 101/140 (72.1%); US 137/140 (97.9%). Conditional paired mean improvements over
momentum are only 0.0731 and 0.1785 percentage points per period. Against liquidity
they are -0.1251 and -0.1523 points. Different comparisons have different paired
subsets. These are not complete-sample returns or proof of superiority. Membership
survivorship and inspected discovery history prevent treating this as untouched OOS.

The lab legacy ledger is preserved and explicitly excluded. Local and cloud studies
have separate real creation timestamps; neither is backfilled to the old signal day.

## Validation Clock

First result: about one month after the first valid freeze. Six, twelve and twenty-four
nonoverlapping 21-session cohorts take roughly six months, one year and two years.
Data interruptions may delay or invalidate assessment. The first 24 due cohorts are
the fixed formal review sample; later winners cannot rescue a failed first-24 test.
Review requires >=90% paired coverage, positive multiplicity-adjusted approximate
block-bootstrap bounds against both controls and benchmark, positive high-cost excess,
and worst period >=-15%. This is a manual-review gate, never a profit guarantee.

Methodological context: [Harvey, Liu and Zhu, NBER w20592](https://www.nber.org/papers/w20592).
Full implementation rules: `screener/LONG_HORIZON_PROTOCOL.md`.

## Local Verification

- Main Python tests: 124 passed; archive/public-build helpers: 26 passed.
- Frontend contract tests: 20 passed; TypeScript project build passed.
- New browser checks: 8 passed; existing factor-research browser checks: 12 passed.
- Desktop and 768/390/320px mobile layouts inspected; chart rendering and downloads checked.
- Lab contract assertions: 188 passed; forward regression tests: 4 passed.
- Legacy ledger digest unchanged; strict export retains real frozen records while
  all legacy imports remain historical. Separate preflight archive preserved.

## Publication And Live Verification

- Code commit: `d62ce8ea8f152f499609c41b6bf2567031843159`.
- [Verified publication](https://github.com/Mjeemjee/stock-screener/actions/runs/39577877368)
  succeeded, including 124 + 26 Python tests, 20 Node tests, TypeScript/Vite build
  and public-file allowlist verification.
- [Pages deployment](https://github.com/Mjeemjee/stock-screener/actions/runs/39578040080)
  succeeded. [Live study](https://mjeemjee.github.io/stock-screener/#/lab/long-horizon).
- Live browser checks: long study 8/8, existing factor research 12/12, parameter
  laboratory 8/8; responsive screens, nonblank charts, exports, errors and retry tested.
- Cloud first US cohort frozen at `2026-10-21T09:34:06+00:00`, before the US open;
  scheduled entry 2026-10-21 and exit 2026-11-19. Actual outcome still pending.
- US input coverage 216/259. HK latest completed session is 2026-10-21, but
  published history has not supplied usable current-session observations: 0/218,
  so no cloud HK cohort was created. Daily rotation may recover availability;
  no guaranteed recovery date and its own validation clock has not started.
- Restored the downloaded cloud archive twice to an isolated directory: all 580
  JSON files unchanged, all 8 production snapshots retained, 1 new strict forward
  cohort retained, all 6 prior factor-study definition hashes unchanged.
- Private `data/positions.json`, `data/quotes.json` and `.env` return HTTP 404.
- Existing local edits to `screener_results.json` and `tracking.json` were neither
  staged nor published. Publication reused the already-public market files.
