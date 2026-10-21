export interface LongBasket {
  count: number; complete: boolean; return_pct: number | null
  holdings: { code: string; status: string; return_pct: number | null }[]
}
export interface LongCohort {
  id: string; market: string; frozen_at: string; entry_date: number; exit_date: number; due: boolean
  baskets: Record<string, LongBasket>; benchmark_pct: number | null
}
export interface LongReport {
  schema_version: number; generated_at: string; definition_hash: string
  policy: { horizon: number; lookback: number; cost_bps: number; stress_cost_bps: number; checkpoints: number[] }
  markets: { market: string; quality: { status: string; valid: number; total: number; session: number }
    metrics: { due: number; paired: number; coverage: number; stage: string; mean_net_pct: number | null
      mean_delta_pp: number | null; lower_delta_pp: number | null; mean_excess_pp: number | null; worst_period_pct: number | null }
    latest: LongCohort | null }[]
  cohorts: LongCohort[]
  historical: { kind: string; note: string; summary: { market: string; variant: string; due: number; complete: number
    coverage: number; mean_net_pct: number | null; mean_combo_improvement_pp: number | null }[] } | null
}
const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v)
const num = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)
const nullable = (v: unknown) => v === null || num(v)
const str = (v: unknown) => typeof v === 'string' && !!v
const array = (v: unknown, fn: (x: unknown) => boolean) => Array.isArray(v) && v.every(fn)
const basket = (v: unknown) => object(v) && num(v.count) && typeof v.complete === 'boolean' && nullable(v.return_pct)
  && array(v.holdings, h => object(h) && str(h.code) && str(h.status) && nullable(h.return_pct))
const cohort = (v: unknown) => object(v) && ['id', 'market', 'frozen_at'].every(k => str(v[k]))
  && num(v.entry_date) && num(v.exit_date) && typeof v.due === 'boolean' && nullable(v.benchmark_pct)
  && object(v.baskets) && ['combined', 'momentum', 'liquidity'].every(k => basket(v.baskets && (v.baskets as Record<string, unknown>)[k]))
export function isLongReport(v: unknown): v is LongReport {
  if (!object(v) || v.schema_version !== 1 || !str(v.generated_at) || !str(v.definition_hash) || !object(v.policy)) return false
  if (!['horizon', 'lookback', 'cost_bps', 'stress_cost_bps'].every(k => num((v.policy as Record<string, unknown>)[k]))
      || !array(v.policy.checkpoints, num) || !array(v.cohorts, cohort)) return false
  if (!array(v.markets, m => object(m) && str(m.market) && object(m.quality) && str(m.quality.status)
    && ['valid', 'total', 'session'].every(k => num((m.quality as Record<string, unknown>)[k]))
    && object(m.metrics) && str(m.metrics.stage) && ['due', 'paired', 'coverage'].every(k => num((m.metrics as Record<string, unknown>)[k]))
    && ['mean_net_pct', 'mean_delta_pp', 'lower_delta_pp', 'mean_excess_pp', 'worst_period_pct'].every(k => nullable((m.metrics as Record<string, unknown>)[k]))
    && (m.latest === null || cohort(m.latest)))) return false
  return v.historical === null || object(v.historical) && str(v.historical.kind) && str(v.historical.note)
    && array(v.historical.summary, h => object(h) && str(h.market) && str(h.variant)
      && ['due', 'complete', 'coverage'].every(k => num(h[k])) && nullable(h.mean_net_pct) && nullable(h.mean_combo_improvement_pp))
}
