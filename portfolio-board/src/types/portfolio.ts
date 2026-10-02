// 与 data/*.json 的结构对应（由 fetch_positions.py / fetch_quotes.py 生成，仅本机版）

export interface Position {
  code: string // e.g. "US.NVDA" / "HK.00883"
  stock_name: string
  qty: number
  can_sell_qty: number
  cost_price: number
  market_val: number
  nominal_price: number
  pl_ratio: number // 浮盈亏比例（%）
  pl_val: number // 浮盈亏额（原币）
  currency: string
}

export interface Funds {
  total_assets: number
  cash: number
  market_val: number
  frozen_cash?: number
  currency: string
}

export interface PositionsFile {
  fetched_at: string
  acc_id: number
  funds: Funds[]
  positions: Position[]
}

export interface QuoteSnap {
  code: string
  name?: string
  last_price: number
  prev_close_price: number
  pe_ratio?: number
}

export interface QuotesFile {
  fetched_at: string
  snapshot: QuoteSnap[]
}

export interface HoldingRow extends Position {
  last_price: number
  prev_close_price: number
  day_pl: number // (last - prevClose) * qty，原币
  market: 'US' | 'HK' | 'OTHER'
}
