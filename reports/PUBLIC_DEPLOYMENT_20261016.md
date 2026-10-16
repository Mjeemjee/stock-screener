# Public Deployment Verification - 2026-10-16

## Release

- Website: https://mjeemjee.github.io/stock-screener/
- Deployed source: `748779a24641e3a7622f02e0f6d69205ffb04e8f`
- Scan/build/privacy checks: https://github.com/Mjeemjee/stock-screener/actions/runs/38862332119 (success)
- GitHub Pages deployment: https://github.com/Mjeemjee/stock-screener/actions/runs/38864306722 (success)
- The full cloud scan completed in 20 minutes 26 seconds. No fallback static release was published.

## Public Data

- Scan timestamp: `2026-10-16T14:42:04+08:00`.
- Universe: 9,422 securities; snapshot coverage: 99.97%.
- Full candidates: 233 (95 momentum, 138 oversold); displayed candidates: 100.
- Latest immutable snapshot: `d83eebaf9edab4440e29866c`.
- Archives: two prospective snapshots and one historical import.
- Downloaded the cumulative cloud artifact and verified all archive payload hashes/ranking annotations.
- Both original seed IDs remain present: `578090639ac7a4bb0e2acb56`, `8352631d645ac0599ed5ab43`.
- Matured paired cohorts: 0. This release verifies operation and data integrity, not investment profitability.

## Checks

- 63 regression tests passed: 44 strategy/tracking, 9 research validation, 4 publication privacy, 6 frontend helpers.
- Follow-up: direct `gh run download` over tracked seed files refused to overwrite existing files. Daily restore now downloads to a fresh directory and validates/merges snapshots without replacing immutable originals. Six additional regression tests cover collisions, CRLF differences, derived cache refresh, tampering, invalid IDs, and empty/self restores.
- 19 browser checks passed against the public website, with no uncaught page errors.
- Search, market filters, stable sorting, CSV, retry, lazy navigation, tracking controls, stock charts, and persistent watchlists passed.
- Desktop and 390/320 px mobile layouts passed overflow checks and screenshot inspection.
- Browser tests used public data for normal workflows and explicitly mocked responses for failure/maturity states; watchlists used isolated browser contexts.
- The published data allowlist passed in CI: screening, tracking, and four public history files only.
- Public `data/positions.json`, `data/quotes.json`, `.env`, and `.env.local` returned HTTP 404.

## Reproduce

```bash
python -m unittest discover -s screener/tests -v
python -m unittest discover -s scripts -p test_validate_factor_optimization.py -v
python -m unittest discover -s scripts -p test_verify_public_build.py -v
python -m unittest discover -s scripts -p test_restore_screening_archive.py -v
cd portfolio-board
node --test src/lib/screener.test.cjs
node scripts/verify-screener-browser.cjs https://mjeemjee.github.io/stock-screener/
node scripts/verify-tracking-browser.cjs https://mjeemjee.github.io/stock-screener/
```

Browser checks require Playwright and Edge; `PLAYWRIGHT_MODULE` can point to an existing Playwright installation. Local deployment builds must start from a clean checkout, since local public directories can contain private holdings.

Daily scanning remains scheduled for 13:22 UTC, Monday through Saturday. Cumulative archives retain the latest three artifact copies, each with 90-day retention. Long interruptions still require an independent backup. Evaluate selection effectiveness after the 5/20/60-session cohorts mature, comparing the paired original/final rankings with costs and benchmarks.
