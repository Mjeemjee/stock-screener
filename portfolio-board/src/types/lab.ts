export interface LabMetrics {
  due: number; paired: number; coverage: number; signal_rate: number; independent: number
  mean_delta_pp: number | null; lower_delta_pp: number | null; mean_return_pct: number | null
  mean_excess_pp: number | null; stress_excess_pp: number | null; worst_period_pct: number | null
}
export interface LabAssessment {
  checkpoint: number; metrics: LabMetrics; gates: Record<string, boolean>; hash: string
}
export interface LabTrial {
  id: string; root_id: string; parent_id: string; generation: number; market: string
  source_version: string; created_at: string; name: string; hypothesis: string; expected: string
  base_params: Record<string, unknown>; params: Record<string, unknown>; definition_hash: string
  change: { parameter: string; from: number; to: number }
  status: 'testing' | 'review' | 'rejected' | 'approved' | 'paused'
  last_checkpoint: number; assessments: LabAssessment[]; metrics?: LabMetrics
}
export interface LabData {
  schema_version: number; generated_at: string; policy_hash: string
  policy: { version: string; horizon: number; spawn_after: number; max_active: number; max_trials: number
    max_generations: number; children_per_parent: number; checkpoints: number[]; min_coverage: number
    min_independent_periods: number; min_signal_rate: number; cost_bps: number; stress_cost_bps: number
    worst_period_floor_pct: number; family_alpha: number; bootstrap_samples: number }
  parents: { id: string; root_id: string; name: string; market: string; source_version: string; matured: number; supported: boolean }[]
  trials: LabTrial[]
  events: { trial_id: string; action: string; at: string; reason?: string; actor?: string; checkpoint?: number; evidence_hash?: string }[]
  observations: { trial_id: string; entry_date: number; due: boolean; benchmark_pct: number | null
    branch: { complete: boolean; count: number; return_pct: number | null }
    parent: { complete: boolean; return_pct: number | null } }[]
  review_workflow: string
}
