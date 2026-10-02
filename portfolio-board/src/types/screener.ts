// 与 data/screener_results.json 的结构对应（由 screener/cloud_engine.py 或 engine.py 生成）

export interface StrategyMeta {
  id: string
  name: string
  principle: string
  source: string
  markets: string[]
  status: 'active' | 'watch' | 'paused'
  params: Record<string, number | string | boolean>
  risk: string
  hit_count: number
  error?: string
  cloud_note?: string
}

export interface ScreenHit {
  code: string
  name: string
  last_price: number
  prev_close_price: number
  change_rate?: number
  pe_ratio?: number
  pe_ttm_ratio?: number
  pb_ratio?: number
  dividend_ratio_ttm?: number
  highest52weeks_price?: number
  lowest52weeks_price?: number
  circular_market_val?: number
  turnover?: number
  turnover_rate?: number
  volume?: number
  amplitude?: number
  off_52w_high_pct?: number
  off_52w_low_pct?: number
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
  strategies: StrategyResult[]
}
