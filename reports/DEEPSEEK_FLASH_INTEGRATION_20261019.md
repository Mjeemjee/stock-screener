# DeepSeek Flash Integration

- op_type: proposal_provider_integration; no scoring or evaluation changes.
- hypothesis: bounded model-generated hypotheses can complement formula search
  without using model assertions as performance evidence.
- change: add the official `deepseek-flash` Responses API adapter, authenticated
  model availability checks, immutable request reservations and pending proposals.
- expected: zero calls before eligibility, no credentials in public artifacts,
  bounded retries and valid typed proposals requiring owner review before tracking.
- acceptance: existing engine hash and study definitions must remain unchanged;
  malformed output, absent credentials and provider failures must fail closed.

## Operating Boundaries

High thinking effort; 4,096 output tokens including reasoning, 24KB context,
three proposals per round, two attempts per round, one round per seven days,
six lifetime rounds and one per parent. Failed/interrupted requests consume quota.
Only 20 fully settled forward cohorts trigger generation, not retrospective folds.
No tools or browsing. No reasoning text or provider error bodies retained.
No automatic approval, new data-source fabrication, live orders or profit claims.

Secrets are supplied via the repository Actions secret `DEEPSEEK_API_KEY` to the
model step only. Published status distinguishes missing key, failed authentication,
model unavailable and verified model-list connectivity. A connectivity check does
not prove successful inference. With zero mature cohorts, inference remains idle.

Existing formula-search budgets and evaluation-engine files are untouched. Sealed
model request files are included in cumulative restoration and cannot be removed
by restoring an older backup over a newer request ledger.

Official API contracts checked 2026-10-19:
- https://api-docs.deepseek.com/quick_start/pricing/
- https://api-docs.deepseek.com/api/create-response/

## Local Verification

114 backend tests, 25 archive/build tests and 18 frontend data tests passed.
Twelve research browser checks passed, including model proposal export, pending
status, authentication failure and 320px mobile layout. Provider responses in
automated tests are fixtures, not successful live paid inference. Existing engine
source files and their engine hash are unchanged.
