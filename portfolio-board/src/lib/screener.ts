import type { ScreenHit, ScreenerResults } from '../types/screener'

export type MarketFilter = 'ALL' | 'US' | 'HK'
export type SortKey = 'strategy' | 'code' | 'last_price' | 'change_rate' | 'circular_market_val' | 'factor_score'
export type SortDirection = 'asc' | 'desc'

export function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

export function marketOf(code: string) {
  return code.startsWith('US.') ? 'US' : code.startsWith('HK.') ? 'HK' : '?'
}

export function currencyOf(code: string) {
  return marketOf(code) === 'US' ? 'USD' : marketOf(code) === 'HK' ? 'HKD' : ''
}

export function formatNumber(value: unknown, digits = 2) {
  return isFiniteNumber(value) ? value.toFixed(digits) : '-'
}

export function filterAndSortHits(
  hits: ScreenHit[],
  query: string,
  market: MarketFilter,
  sort: SortKey,
  direction: SortDirection,
) {
  const needle = query.trim().toLocaleLowerCase()
  const selected = hits.filter((hit) =>
    (market === 'ALL' || marketOf(hit.code) === market) &&
    (!needle || hit.code.toLocaleLowerCase().includes(needle) || hit.name.toLocaleLowerCase().includes(needle)),
  )
  if (sort === 'strategy') return selected
  const sign = direction === 'asc' ? 1 : -1
  return selected.map((hit, index) => ({ hit, index })).sort((a, b) => {
    if (sort === 'code') return sign * a.hit.code.localeCompare(b.hit.code) || a.index - b.index
    const av = a.hit[sort]
    const bv = b.hit[sort]
    // Missing values stay last for both sort directions; ties retain strategy order.
    if (!isFiniteNumber(av)) return isFiniteNumber(bv) ? 1 : a.index - b.index
    if (!isFiniteNumber(bv)) return -1
    return sign * (av - bv) || a.index - b.index
  }).map(({ hit }) => hit)
}

export function csvCell(value: unknown) {
  let text = value == null || (typeof value === 'number' && !Number.isFinite(value)) ? '' : String(value)
  // Spreadsheet formulas can be introduced after leading whitespace or control characters.
  if (typeof value === 'string' && /^[\s\u0000-\u001f]*[=+@-]/u.test(text)) text = `'${text}`
  return `"${text.replaceAll('"', '""')}"`
}

export function hitsToCsv(hits: ScreenHit[], strategyName: string, generatedAt: string) {
  const rows: unknown[][] = [[
    'strategy', 'generated_at', 'code', 'name', 'market', 'currency', 'last_price',
    'change_rate_pct', 'market_cap', 'turnover', 'factor_rank', 'factor_score',
    'factor_status', 'factor_as_of', 'reason',
  ]]
  for (const hit of hits) rows.push([
    strategyName, generatedAt, hit.code, hit.name, marketOf(hit.code), currencyOf(hit.code),
    hit.last_price, hit.change_rate, hit.circular_market_val, hit.turnover,
    hit.factor_rank, hit.factor_score, hit.factor_status, hit.factor_as_of, hit.reason,
  ])
  return '\uFEFF' + rows.map((row) => row.map(csvCell).join(',')).join('\r\n') + '\r\n'
}

export function scanTimeInfo(generatedAt: string, now = Date.now()) {
  const timezoneKnown = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(generatedAt)
  const timestamp = timezoneKnown ? Date.parse(generatedAt) : NaN
  if (!Number.isFinite(timestamp)) return { display: generatedAt, ageHours: null, stale: false, future: false }
  const ageHours = (now - timestamp) / 3_600_000
  return {
    display: new Intl.DateTimeFormat('zh-CN', {
      timeZone: 'Asia/Hong_Kong', year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', hour12: false,
    }).format(timestamp),
    ageHours,
    stale: ageHours > 72,
    future: ageHours < -1,
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

export function isScreenerResults(value: unknown): value is ScreenerResults {
  if (!isRecord(value) || typeof value.generated_at !== 'string' ||
      !isFiniteNumber(value.universe_total) || !isFiniteNumber(value.universe_after_filter) ||
      !Array.isArray(value.strategies)) return false
  return value.strategies.every((strategy) => {
    if (!isRecord(strategy) || !isRecord(strategy.meta) || !Array.isArray(strategy.hits)) return false
    const meta = strategy.meta
    return ['id', 'name', 'principle', 'source', 'risk'].every((key) => typeof meta[key] === 'string') &&
      ['active', 'watch', 'paused'].includes(String(meta.status)) &&
      isFiniteNumber(meta.hit_count) && isRecord(meta.params) &&
      Array.isArray(meta.markets) && meta.markets.every((market) => typeof market === 'string') &&
      strategy.hits.every((hit) => isRecord(hit) && typeof hit.code === 'string' &&
        typeof hit.name === 'string' && typeof hit.reason === 'string')
  })
}
