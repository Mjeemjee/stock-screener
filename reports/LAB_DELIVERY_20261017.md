# Strategy Lab Delivery - Updated 2026-10-18

## Published Release

- Website: https://mjeemjee.github.io/stock-screener/#/lab
- Deployed source: `c32f00dec870aa2de8f77b7ab87bbb46b41e0cdb`.
- Build: https://github.com/Mjeemjee/stock-screener/actions/runs/39088166550 (success).
- Pages: https://github.com/Mjeemjee/stock-screener/actions/runs/39088227378 (success).
- Public lab report: 2026-10-18 09:55:02 Hong Kong time, policy `lab-v1`, five mother/market groups, zero experimental branches.
- The overnight daily scan succeeded; published screening is 2026-10-18 00:30:36 Hong Kong time, snapshot `3a26377513c1f7de8a065fee`. This final source-only publication preserved it and all six public tracking archives.
- Production strategy modules, factor ranking and market rules remain unchanged. Tracking gained a separate lab hook; the cloud scanner gained an inactive-until-approved post-ranking refinement hook.

## Verification

- 122 regression checks passed locally and in the Linux publication job: 85 screener tests (including 26 laboratory tests), 24 script tests and 13 frontend helper tests.
- 27 browser checks passed against the public website: 8 laboratory, 11 screening and 8 tracking/detail/watchlist checks.
- Actual reports were used for normal/pending screens; synthetic fixtures were explicitly intercepted only in the isolated browser context for qualified/rejected/approved/paused and HTTP failure states.
- Review-request downloads contain the trial ID and pinned evidence hash. Browser tests recorded no non-GET/HEAD write requests.
- Desktop, 768px tablet and 390/320px mobile lab layouts passed overflow checks. Price/delta charts rendered nonblank; screenshots were inspected.
- Private positions, account quotes and environment configuration remained HTTP 404. Build publication passed the explicit public-data allowlist.
- A first publication attempt failed because optional ETF history was not published. The fetch helper now treats only that known optional 404 as unavailable; required screening/tracking failures still stop publication. This behavior has three regression tests.
- No real experiment has been promoted. Approval, stale evidence, tampering, parameter-only changes and pause behavior were tested on isolated fixtures, not production market policy.
- A synthetic-price integration test uses real NYSE sessions to mature eight mother cohorts, freeze 40 future paired cohorts, evaluate fixed checkpoints, create the second generation, require explicit approval, and compare the approved formal candidate list with the laboratory list. This tests workflow correctness, not investment performance.
- Promotion keeps the original prescreen/factor universe, then filters ranked hits. Tests verify identical branch order and factor scores, complete original ranks, subsequent promotions retaining the underlying universe, stale configurations failing closed, and no-op behavior without promotions.
- Rehashed definitions cannot reuse old review evidence; duplicate IDs and backups redefining an existing trial are rejected. The actual cumulative backup restored successfully during publication; the earlier repeated-restore smoke run also passed: https://github.com/Mjeemjee/stock-screener/actions/runs/39039630279.
- Direct Git transport timed out locally. The official GitHub Git Data API uploaded the exact local blobs, trees and commit IDs with a non-forced reference update; the existing GitHub Actions publication process still built and verified the site.

## Delivered Boundaries

- Automatic exploration after 8 evaluable mother cohorts; 5-session primary horizon.
- Fixed analysis checkpoints at 20/40/60 due cohorts, coverage and nonoverlap gates, paired net improvement, benchmark and 30bp-per-side stress checks.
- Approximate block-bootstrap lower bound adjusted for 12 lifetime trials and three looks. This is a research gate, not proof of profitability.
- At most six observed branches, two generations and two children per mother; no silent budget reset.
- Parameter refinements inherit the mother's candidate ranking. Arbitrary new strategy code generation and independent alpha discovery are outside this first version.
- Immutable paired snapshots and checkpoint price evidence; failed trials remain in the ledger. Old backups cannot roll back decisions or trial counts.
- Repository-owner workflow can pause, reject or approve. Approval revalidates frozen evidence bound to the exact definition/policy and unchanged source/parameters, then commits only the allowlisted market policy and dispatches a new scan. The policy stores separate post-ranking promotions rather than silently changing the factor scoring universe.
- Worst period is not portfolio NAV drawdown; live capital sizing, practical fills and full account risk remain separate review work.

Protocol: `screener/LAB_EVALUATION.md`. Owner operation notes: `screener/README.md`.

## Measuring Actual Effectiveness

The live laboratory currently has no mature experimental outcomes and cannot
claim a return improvement. Let the scheduled daily scans accumulate unchanged,
prospectively frozen cohorts. At each predefined checkpoint inspect paired net
improvement, benchmark excess, stressed costs, missing-data coverage, nonoverlap,
signal rate, worst period and the adjusted bootstrap lower bound together. A
passing research candidate still requires owner review and independent capital
allocation/fill/drawdown analysis before real-money use. Do not reset the study
budget or relax thresholds after seeing losses.
