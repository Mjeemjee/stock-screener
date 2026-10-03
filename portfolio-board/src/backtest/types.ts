/** 回测引擎公共类型 */

/** 原始 K 线数组：[yyyymmdd, open, high, low, close, volume]（前复权，升序） */
export type RawBar = [number, number, number, number, number, number]

export interface Bar {
  d: number // yyyymmdd
  o: number
  h: number
  l: number
  c: number
  v: number
}

export interface StockSeries {
  code: string
  name: string
  bars: Bar[]
}

/** 策略参数说明：驱动网页表单自动生成 */
export interface ParamSpec {
  key: string
  label: string
  description?: string
  default: number
  min: number
  max: number
  step: number
}

/**
 * 策略模块契约（详见 src/backtest/README.md）：
 * prepare 对单只股票一次性算好信号数组；
 * entries[i] / exits[i] 表示「第 i 根 K 线收盘时」的信号，引擎在下一根 K 线开盘成交（T+1，无未来函数）。
 */
export interface StrategyModule {
  id: string
  name: string
  description: string
  params: ParamSpec[]
  prepare(bars: Bar[], p: Record<string, number>): { entries: boolean[]; exits: boolean[] }
}

export interface BacktestOptions {
  initialCash: number
  maxPositions: number
  /** 单边成本 %（佣金+滑点合并） */
  costPct: number
  startDate?: number // yyyymmdd
  endDate?: number
  /** 止损 %，0 = 关闭 */
  stopLossPct: number
  /** 止盈 %，0 = 关闭 */
  takeProfitPct: number
  /** 最大持有 K 线数，0 = 关闭 */
  maxHoldDays: number
}

export interface Trade {
  code: string
  name: string
  entryDate: number
  entryPrice: number
  exitDate: number
  exitPrice: number
  pnlPct: number
  pnl: number
  holdingDays: number
  reason: string
}

export interface Metrics {
  totalReturnPct: number
  cagrPct: number
  maxDrawdownPct: number
  sharpe: number
  winRatePct: number
  tradeCount: number
  avgPnlPct: number
  profitFactor: number | null
  finalEquity: number
}

export interface EquityPoint {
  d: number
  /** 策略净值（起点 = 1） */
  v: number
  /** 基准净值（起点 = 1），缺失为 null */
  bench: number | null
}

export interface BacktestResult {
  metrics: Metrics
  equity: EquityPoint[]
  drawdown: { d: number; dd: number }[]
  trades: Trade[]
  strategyId: string
  params: Record<string, number>
  options: BacktestOptions
  stockCount: number
  elapsedMs: number
}

/** 历史数据文件（hk.json / us.json）的原始结构 */
export interface HistoryFile {
  generated_at: string
  market: string
  survivorship_note: string
  stocks: { code: string; name: string; bars: RawBar[] }[]
}

export interface IndexFile {
  generated_at: string
  indexes: Record<string, { name: string; bars: RawBar[] }>
}
