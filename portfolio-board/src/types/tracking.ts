import type { ScreenHit } from './screener'

export interface ArchiveInfo {
  id: string
  generated_at: string
  frozen_at: string
  provenance: 'prospective' | 'historical_import'
  strategy_version: string
  complete_candidates: boolean
  candidate_count: number
}

export interface Basket {
  count: number
  complete: boolean
  known_count: number
  return_pct: number | null
  holdings: { code: string; status: string; return_pct: number | null }[]
}

export interface Evaluation {
  snapshot_id: string
  strategy_id: string
  strategy_name: string
  market: string
  strategy_version: string
  horizon: number
  prospective: boolean
  scheduled_entry_date?: number
  scheduled_exit_date?: number
  entry_date: number | null
  exit_date: number | null
  original_rank_known: boolean
  baskets: { selected: Basket; original?: Basket }
  benchmark_pct: number | null
}

export interface TrackingSummary {
  strategy_id: string
  market: string
  horizon: number
  strategy_version: string
  cohorts: number
  matured_pairs: number
  mean_selected_pct: number | null
  mean_original_pct: number | null
  mean_benchmark_pct: number | null
  mean_delta_pp: number | null
}

export interface Security extends ScreenHit {
  last_seen?: string
  history?: [number, number][]
}

export interface Appearance {
  snapshot_id: string
  generated_at: string
  strategy_name: string
  provenance: string
  original_market_rank?: number | null
  selection_market_rank?: number | null
  factor_score?: number | null
}

export interface TrackingData {
  schema_version: number
  generated_at: string
  protocol: { top_n: number; horizons: number[]; cost_bps_per_side: number }
  archives: ArchiveInfo[]
  evaluations: Evaluation[]
  summary: TrackingSummary[]
  securities: Record<string, Security>
  appearances: Record<string, Appearance[]>
  history_refresh: { needed: number; fetched: number; failed: string[]; budget_excluded: number }
}
