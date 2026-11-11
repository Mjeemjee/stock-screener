import type { ArchiveInfo, Basket, Evaluation, TrackingData } from '@/types/tracking'

export type PeriodState = 'complete' | 'missing' | 'pending'
export interface ValidationPeriod {
  row: Evaluation
  entry: number
  exit: number
  state: PeriodState
  separated: boolean
}
export interface PeriodStats {
  complete: number
  missing: number
  pending: number
  net: number | null
  benchmark: number | null
  excess: number | null
}
export interface ValidationGroup {
  strategy: string
  name: string
  market: string
  horizon: number
  version: string
  frozenAt: string
  periods: ValidationPeriod[]
  duplicates: number
  all: PeriodStats
  separated: PeriodStats
}

const finite = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)
function validDate(value: unknown): value is number {
  if (!Number.isInteger(value) || String(value).length !== 8) return false
  const s = String(value)
  const date = new Date(`${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}T00:00:00Z`)
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10).replaceAll('-', '') === s
}
function completeBasket(basket: Basket | undefined) {
  return basket?.complete === true && finite(basket.return_pct) &&
    basket.count > 0 && basket.known_count === basket.count
}
function stateOf(row: Evaluation): PeriodState {
  if (!row.entry_date || !row.exit_date) return 'pending'
  return completeBasket(row.baskets?.selected) && completeBasket(row.baskets?.original) &&
    finite(row.benchmark_pct) ? 'complete' : 'missing'
}
function summarize(periods: ValidationPeriod[], requireAllDue = false): PeriodStats {
  const complete = periods.filter(p => p.state === 'complete')
  const missing = periods.filter(p => p.state === 'missing').length
  const usable = complete.length > 0 && (!requireAllDue || missing === 0)
  const net = usable ? complete.reduce((s, p) => s + p.row.baskets.selected.return_pct!, 0) / complete.length : null
  const benchmark = usable ? complete.reduce((s, p) => s + p.row.benchmark_pct!, 0) / complete.length : null
  return { complete: complete.length, missing, pending: periods.filter(p => p.state === 'pending').length,
    net, benchmark, excess: net !== null && benchmark !== null ? net - benchmark : null }
}

/** Display-only comparison. Reserve windows using schedules BEFORE reading outcomes.
 * This never promotes a strategy, edits a frozen record, or creates a new forward trial. */
export function validationGroups(data: TrackingData): { groups: ValidationGroup[]; invalid: number } {
  const archives = new Map<string, ArchiveInfo>(data.archives.filter(a => a && typeof a.id === 'string').map(a => [a.id, a]))
  const grouped = new Map<string, { archive: ArchiveInfo; row: Evaluation; entry: number; exit: number }[]>()
  let invalid = 0
  for (const row of data.evaluations) {
    if (!row || typeof row !== 'object') { invalid++; continue }
    const archive = archives.get(row.snapshot_id)
    if (!row.prospective || archive?.provenance === 'historical_import') continue
    const entry = row.scheduled_entry_date ?? row.entry_date
    const exit = row.scheduled_exit_date ?? row.exit_date
    if (!archive || archive.provenance !== 'prospective' || archive.strategy_version !== row.strategy_version ||
      !Number.isFinite(Date.parse(archive.frozen_at)) || !row.strategy_id || !row.strategy_version ||
      !['US', 'HK'].includes(row.market) || ![5, 20, 60].includes(row.horizon) ||
      !validDate(entry) || !validDate(exit) || entry >= exit ||
      (row.entry_date != null && row.entry_date !== entry) || (row.exit_date != null && row.exit_date !== exit)) {
      invalid++
      continue
    }
    const key = JSON.stringify([row.market, row.strategy_id, row.horizon, row.strategy_version])
    const values = grouped.get(key) ?? []
    values.push({ archive, row, entry, exit })
    grouped.set(key, values)
  }
  const groups: ValidationGroup[] = []
  for (const values of grouped.values()) {
    // Multiple scans targeting one opening are one cohort. Earliest freeze wins,
    // regardless of the later scan's price availability or performance.
    values.sort((a, b) => Date.parse(a.archive.frozen_at) - Date.parse(b.archive.frozen_at) ||
      a.archive.id.localeCompare(b.archive.id))
    const first = values[0]
    const byEntry = new Map<number, typeof first>()
    for (const value of values) if (!byEntry.has(value.entry)) byEntry.set(value.entry, value)
    let lastExit = 0
    const periods = [...byEntry.values()].sort((a, b) => a.entry - b.entry).map(({ row, entry, exit }) => {
      const separated = entry >= lastExit
      if (separated) lastExit = exit
      return { row, entry, exit, separated, state: stateOf(row) }
    })
    groups.push({ strategy: first.row.strategy_id, name: first.row.strategy_name,
      market: first.row.market, horizon: first.row.horizon, version: first.row.strategy_version,
      frozenAt: first.archive.frozen_at, periods, duplicates: values.length - periods.length,
      all: summarize(periods), separated: summarize(periods.filter(p => p.separated), true) })
  }
  return { groups: groups.sort((a, b) => Date.parse(b.frozenAt) - Date.parse(a.frozenAt) || a.strategy.localeCompare(b.strategy)), invalid }
}

export function dateLabel(value: number) {
  const s = String(value)
  return `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`
}

export function fundingSlots(day: number, capital: number) {
  const step = Math.max(1, Math.min(11, Math.floor(day)))
  return Array.from({ length: 5 }, (_, i) => {
    const start = step < i + 1 ? null : i + 1 + 5 * Math.floor((step - i - 1) / 5)
    return { slot: i + 1, amount: capital / 5, start, exit: start === null ? null : start + 5,
      renewed: start === step && step > 5, entering: start === step }
  })
}
