// 与 data/screener_results.json 的结构对应（由 screener/cloud_engine.py 或 engine.py 生成）

export interface StrategyMeta {
  id: string
  name: string
  principle: string
  source: string
  markets: string[]
  status: 'active' | 'watch' | 'paused'
  params: Record<string, number | string | boolean>
  policy_version?: string
  market_params?: Record<string, Record<string, number | string | boolean>>
  risk: string
  hit_count: number
  displayed_count?: number
  truncated?: boolean
  execution_status?: 'ok' | 'unavailable' | 'paused' | 'error'
  missing_fields?: string[]
  data_note?: string
  eligible_count?: number
  unavailable_count?: number
  error?: string
  cloud_note?: string
}

export interface ScreenHit {
  code: string
  name: string
  last_price: number | null
  prev_close_price: number | null
  change_rate?: number | null
  pe_ratio?: number | null
  pe_ttm_ratio?: number | null
  pb_ratio?: number | null
  dividend_ratio_ttm?: number | null
  highest52weeks_price?: number | null
  lowest52weeks_price?: number | null
  circular_market_val?: number | null
  turnover?: number | null
  turnover_rate?: number | null
  volume?: number | null
  amplitude?: number | null
  off_52w_high_pct?: number | null
  off_52w_low_pct?: number | null
  factor_score?: number | null
  factor_rank?: number | null
  factor_note?: string
  factor_status?: string
  factor_as_of?: string
  original_market_rank?: number
  sector?: string | null
  industry?: string | null
  quote_time?: string | null
  risk_status?: string
  risk_as_of?: string
  volatility_20d_pct?: number | null
  drawdown_120d_pct?: number | null
  median_turnover_20d?: number | null
  risk_window_sessions?: number
  earnings_date?: string | null
  reason: string
}

export interface StrategyResult {
  meta: StrategyMeta
  hits: ScreenHit[]
}

export interface ScreenerResults {
  generated_at: string
  elapsed_sec: number
  data_source?: string
  universe_total: number
  universe_after_filter: number
  data_quality?: {
    snapshot_count: number
    filtered_count: number
    excluded_count: number
    duplicate_count: number
    requested_count?: number
    received_count?: number
    coverage_pct?: number
    failed_batches?: number
  }
  factor_rank?: {
    applied: boolean
    method?: string
    scope?: string
    candidates?: number
    attempted?: number
    fetched: number
    failures: number
    ranked: number
    coverage?: number
    reason?: string
    elapsed_sec?: number
  }
  strategies: StrategyResult[]
}
