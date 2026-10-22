import type { LabMetrics } from './lab'

export type Expression = { op: 'feature'; name: string } | { op: 'neg'; arg: Expression }
  | { op: 'mean' | 'product'; args: Expression[] }
export interface ResearchCard { version: 1; evidence: string; failure_condition: string; data_risks: string }
export interface Proposal {
  name: string; market: string; parent_id?: string | null; op_type: string; hypothesis: string
  change: string; expected: string; expression: Expression; filters: { feature: string; gte?: number; lte?: number }[]
  research_card?: ResearchCard
}
export interface ProgramReview {
  program_id: string; definition_hash: string; evidence_hash: string; assessment_hash: string | null; headline: string
  card: { origin: 'frozen' | 'legacy'; hypothesis: string; change: string; expected: string; features: string[]
    evidence: string; failure_condition: string; data_risks: string }
  summary: { total: number; pending: number; due: number; paired: number; missing: number; duplicate: boolean
    independent: number; wins: number; losses: number; flat: number; beat_parent: number; beat_benchmark: number; cash: number
    mean_return_pct: number | null; mean_delta_pp: number | null; mean_excess_pp: number | null
    stress_excess_pp: number | null; worst_period_pct: number | null }
  checks: { id: string; label: string; status: 'pass' | 'fail' | 'pending'; detail: string }[]
}
export interface ResearchMetrics extends LabMetrics { rank_ic: number | null; pearson_ic: number | null; novelty: number | null }
export interface ResearchFold {
  train_start: number; train_end: number; test_start: number; test_end: number; purged: number; embargo: number
  test_periods: number; complete: number; train_rank_ic: number | null; rank_ic: number | null
  pearson_ic: number | null; mean_delta_pp: number | null; coverage: number; icir: number | null
  ic_lower: number | null; ic_upper: number | null; degradation: number | null; q5_q1_pp: number | null
}
export interface ResearchProgram extends Proposal {
  id: string; family: string; generation: number; created_at: string; definition_hash: string; engine_version: string
  universe_hash: string; policy_hash: string; status: 'testing' | 'review' | 'approved' | 'paused' | 'rejected'
  discovery: { kind: string; note?: string; actor?: string; last_label_date?: number; exploratory_delta_pp?: number; research_card?: ResearchCard }
  metrics?: ResearchMetrics; last_checkpoint: number
  assessments: { checkpoint: number; hash: string; metrics: ResearchMetrics; gates: Record<string, boolean> }[]
  historical: { kind: string; status: string; note: string; as_of: string; folds: ResearchFold[] }
  latest_selection: { code: string; score: number; features: Record<string, number> }[]; latest_frozen_at: string | null
}
export interface ResearchRow {
  trial_id: string; entry_date: number; exit_date: number; due: boolean; rank_ic: number | null; pearson_ic: number | null
  branch: { count: number; complete: boolean; return_pct: number | null; holdings: { code: string; status: string; return_pct: number | null }[] }
  parent: { complete: boolean; return_pct: number | null }; pool: { complete: boolean; return_pct: number | null }; benchmark_pct: number | null
}
export interface ResearchData {
  schema_version: number; generated_at: string; policy_hash: string; engine_version: string; review_workflow: string
  generator: string; model_connected: boolean
  research_review?: { version: 'research-review-v1'; mode: 'read_only'; source_generated_at: string
    source_engine_version: string; source_policy_hash: string; programs: ProgramReview[] }
  model_research?: {
    provider: string; model: string; connection: string; checked_at: string; max_calls: number; min_cohorts: number; mode: 'owner_review'
    calls: { id: string; at: string; parent_id: string; status: string; rejected_count: number; usage: Record<string, number>
      proposals: { proposal: Proposal; started_program_id: string | null }[] }[]
  }
  policy: { version: string; pool_size: number; horizon: number; max_programs: number; max_searches: number
    max_active: number; comparison_budget: number; discovery_after: number; checkpoints: number[]
    max_correlation: number; min_data_coverage: number; cost_bps: number; stress_cost_bps: number }
  features: Record<string, { name: string; formula: string; family: string }>
  universes: { market: string; hash: string; created_at: string; basis: string; members: { code: string; name: string }[] }[]
  quality: { market: string; session: number; valid: number; total: number; coverage: number; status: string; missing: Record<string, string> }[]
  programs: ResearchProgram[]; observations: ResearchRow[]
  events: { action: string; at: string; program_id: string | null; actor?: string; reason?: string; tested?: number; qualified?: number }[]
  searches: { hash: string; at: string; parent_id: string; market: string; cohort_count: number; last_label_date: number
    candidates: { spec: Proposal; mean_delta_pp: number; rank_ic: number | null; novelty: number | null; signal_rate: number; duplicate: boolean; qualified: boolean }[] }[]
}
