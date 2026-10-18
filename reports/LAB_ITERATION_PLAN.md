# Lab v1 Implementation Note

- op_type: research_workflow (not a new alpha factor or change to production ranks).
- hypothesis: bounded one-parameter refinements can be compared prospectively to
  their unchanged mother, preserving failed trials and controlling trial budgets.
- change: add separate paired paper archives, a fixed evaluation policy, branching
  templates, checkpoint decisions and explicit repository-owner promotion.
- expected: reproducible future-only cohorts, no changes to formal selections
  without owner approval, no claimed performance gain before samples mature.
- scoring/evaluation contract: `screener/LAB_EVALUATION.md`.
- signal contract: inherit mother ranks; refinements are intentionally correlated
  controls, NOT independent new factors. Do not z-score them as novel alpha.
- accepted/rejected experiment ledger: cumulative `screening_archive/lab/state.json`.
- verification: 122 regression checks and 27 public browser checks passed. A real
  NYSE-calendar/synthetic-price lifecycle test verifies maturity through owner
  promotion without presenting fixture returns as live performance.
- consistency audit: promotions narrow the inherited ranked set, keeping the
  underlying factor universe unchanged. Evidence is bound to exact definitions;
  cumulative restoration cannot redefine an existing experiment.
- outcome: workflow accepted for prospective paper research. No branch has real
  qualifying results yet, and no investment-performance improvement is claimed.
