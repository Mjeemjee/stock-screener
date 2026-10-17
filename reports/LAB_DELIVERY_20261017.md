# Strategy Lab Delivery - 2026-10-17

## Published Release

- Website: https://mjeemjee.github.io/stock-screener/#/lab
- Deployed source: `6633452f938c8535c792cb89826609dbbca819f7`.
- Build: https://github.com/Mjeemjee/stock-screener/actions/runs/39039307666 (success).
- Pages: https://github.com/Mjeemjee/stock-screener/actions/runs/39039376581 (success).
- Public lab report: 2026-10-17 22:06:29 Hong Kong time, policy `lab-v1`, five mother/market groups, zero experimental branches.
- Existing public screening remains at 2026-10-17 20:47:45 Hong Kong time, snapshot `9361a3f37576fa346c233eac`.
- Production strategy modules, factor ranking, market rules and scanner logic were not changed. Only the tracking pipeline gained a separate laboratory hook.

## Verification

- 115 regression checks passed in the Linux publication job: 78 screener tests (including 19 new laboratory tests), 24 script tests and 13 frontend helper tests.
- 27 browser checks passed against the public website: 8 laboratory, 11 screening and 8 tracking/detail/watchlist checks.
- Actual reports were used for normal/pending screens; synthetic fixtures were explicitly intercepted only in the isolated browser context for qualified/rejected/approved/paused and HTTP failure states.
- Review-request downloads contain the trial ID and pinned evidence hash. Browser tests recorded no non-GET/HEAD write requests.
- Desktop, 768px tablet and 390/320px mobile lab layouts passed overflow checks. Price/delta charts rendered nonblank; screenshots were inspected.
- Private positions, account quotes and environment configuration remained HTTP 404. Build publication passed the explicit public-data allowlist.
- A first publication attempt failed because optional ETF history was not published. The fetch helper now treats only that known optional 404 as unavailable; required screening/tracking failures still stop publication. This behavior has three regression tests.
- No real experiment has been promoted. Approval, stale evidence, tampering, parameter-only changes and pause behavior were tested on isolated fixtures, not production market policy.

## Delivered Boundaries

- Automatic exploration after 8 evaluable mother cohorts; 5-session primary horizon.
- Fixed analysis checkpoints at 20/40/60 due cohorts, coverage and nonoverlap gates, paired net improvement, benchmark and 30bp-per-side stress checks.
- Approximate block-bootstrap lower bound adjusted for 12 lifetime trials and three looks. This is a research gate, not proof of profitability.
- At most six observed branches, two generations and two children per mother; no silent budget reset.
- Parameter refinements inherit the mother's candidate ranking. Arbitrary new strategy code generation and independent alpha discovery are outside this first version.
- Immutable paired snapshots and checkpoint price evidence; failed trials remain in the ledger. Old backups cannot roll back decisions or trial counts.
- Repository-owner workflow can pause, reject or approve. Approval revalidates frozen evidence and unchanged source/parameters, then commits only the allowlisted market policy and dispatches a new scan.
- Worst period is not portfolio NAV drawdown; live capital sizing, practical fills and full account risk remain separate review work.

Protocol: `screener/LAB_EVALUATION.md`. Owner operation notes: `screener/README.md`.
