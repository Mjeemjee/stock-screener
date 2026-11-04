import type { Evaluation } from '../types/tracking'

export type Bar = [number, number, number, number, number, number]
export interface CandleData {
  schema_version: 1
  code: string
  generated_at: string
  as_of: number | null
  price_basis: 'source_adjusted'
  volume_unit: 'source_units'
  source: 'tracking_history' | 'chart_history'
  rejected_rows: number
  status: 'available' | 'unavailable'
  bars: Bar[]
}
export type BasketMode = 'selected' | 'original'
export interface ChartPeriod { id: string; row: Evaluation; mode: BasketMode }
export interface TradeMarker { time: string; kind: 'buy' | 'sell'; price: number }
export const validCode = (code: string) => /^(HK\.[0-9]{5}|US\.[A-Z0-9][A-Z0-9.\-]{0,29})$/.test(code)
export const dayLabel = (day: number) => `${String(day).slice(0, 4)}-${String(day).slice(4, 6)}-${String(day).slice(6, 8)}`
const positive = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v) && v > 0
const validDay = (v: unknown): v is number => {
  if (typeof v !== 'number' || !Number.isInteger(v) || String(v).length !== 8) return false
  const parsed = new Date(`${dayLabel(v)}T00:00:00Z`)
  return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === dayLabel(v)
}

export function isCandleData(value: unknown, code: string): value is CandleData {
  if (!value || typeof value !== 'object') return false
  const v = value as CandleData
  if (v.schema_version !== 1 || v.code !== code || v.price_basis !== 'source_adjusted' ||
    v.volume_unit !== 'source_units' || !['tracking_history', 'chart_history'].includes(v.source) || !Number.isInteger(v.rejected_rows) || v.rejected_rows < 0 ||
    !['available', 'unavailable'].includes(v.status) || !Number.isFinite(Date.parse(v.generated_at)) ||
    !Array.isArray(v.bars) || v.bars.length > 260) return false
  let previous = 0
  for (const row of v.bars) {
    if (!Array.isArray(row) || row.length !== 6) return false
    const [day, o, h, low, close, volume] = row
    if (!validDay(day) || day <= previous || ![o, h, low, close].every(positive) ||
      h < Math.max(o, close) || low > Math.min(o, close) || !Number.isFinite(volume) || volume < 0) return false
    previous = day
  }
  return v.as_of === (v.bars.at(-1)?.[0] ?? null) && (v.status === 'available') === (v.bars.length > 0)
}

export function chartPeriods(evaluations: Evaluation[], code: string): ChartPeriod[] {
  return evaluations.flatMap(row => (['selected', 'original'] as const).flatMap(mode =>
    row.baskets[mode]?.holdings.some(h => h.code === code)
      ? [{ id: `${row.snapshot_id}:${row.strategy_id}:${row.horizon}:${mode}`, row, mode }] : []))
    .sort((a, b) => (b.row.scheduled_entry_date ?? b.row.entry_date ?? 0) - (a.row.scheduled_entry_date ?? a.row.entry_date ?? 0) ||
      a.row.horizon - b.row.horizon || (a.mode === b.mode ? 0 : a.mode === 'selected' ? -1 : 1))
}

export function tradeMarkers(period: ChartPeriod | undefined, code: string, bars: Bar[]) {
  const markers: TradeMarker[] = []
  const warnings: string[] = []
  const holding = period?.row.baskets[period.mode]?.holdings.find(h => h.code === code)
  if (!period || !holding || holding.status === 'no_trade') return { markers, warnings }
  const events = [
    { kind: 'buy' as const, day: period.row.entry_date, price: holding.entry_price, label: '模拟买入' },
    { kind: 'sell' as const, day: period.row.exit_date, price: holding.exit_price, label: '模拟卖出' },
  ]
  for (const event of events) {
    // Planned dates and missing fills never become completed trade markers.
    if (!event.day || !positive(event.price)) continue
    const bar = bars.find(row => row[0] === event.day)
    if (!bar) warnings.push(`${event.label}日不在已取得的日线内，暂不画标记。`)
    else if (Math.abs(bar[1] - event.price) > Math.max(1e-6, Math.abs(event.price) * 1e-7))
      warnings.push(`${event.label}价与该日开盘价不同，可能是复权或来源变化，暂不画标记。`)
    else markers.push({ time: dayLabel(event.day), kind: event.kind, price: event.price })
  }
  return { markers: markers.sort((a, b) => a.time.localeCompare(b.time)), warnings }
}
