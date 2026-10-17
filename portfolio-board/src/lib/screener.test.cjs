const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const Module = require('node:module')
const ts = require('typescript')

const filename = path.join(__dirname, 'screener.ts')
const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
}).outputText
const loaded = new Module(filename, module)
loaded._compile(compiled, filename)
const { filterAndSortHits, hitsToCsv, csvCell, scanTimeInfo, formatNumber, isScreenerResults } = loaded.exports

const hit = (code, score, patch = {}) => ({
  code, name: code, last_price: 10, prev_close_price: 9,
  factor_score: score, reason: 'matched', ...patch,
})

test('factor sorting keeps null, absent and nonfinite scores last in both directions', () => {
  const hits = [hit('US.NONE', undefined), hit('US.LOW', -2), hit('US.HIGH', 4), hit('HK.NULL', null), hit('US.NAN', NaN), hit('US.TIE', 4)]
  assert.deepEqual(filterAndSortHits(hits, '', 'ALL', 'factor_score', 'desc').map((h) => h.code), ['US.HIGH', 'US.TIE', 'US.LOW', 'US.NONE', 'HK.NULL', 'US.NAN'])
  assert.deepEqual(filterAndSortHits(hits, '', 'ALL', 'factor_score', 'asc').map((h) => h.code), ['US.LOW', 'US.HIGH', 'US.TIE', 'US.NONE', 'HK.NULL', 'US.NAN'])
  assert.equal(hits[0].code, 'US.NONE')
})

test('search combines market and name/code without changing strategy order', () => {
  const hits = [hit('HK.00700', 2, { name: 'Tencent' }), hit('US.TCEHY', 5, { name: 'Tencent' }), hit('US.OTHER', 0)]
  assert.deepEqual(filterAndSortHits(hits, ' tencent ', 'HK', 'strategy', 'desc').map((h) => h.code), ['HK.00700'])
  assert.deepEqual(filterAndSortHits(hits, 'tcehy', 'ALL', 'strategy', 'asc').map((h) => h.code), ['US.TCEHY'])
  assert.deepEqual(filterAndSortHits(hits, '', 'ALL', 'strategy', 'desc'), hits)
  assert.deepEqual(filterAndSortHits(hits, 'missing', 'ALL', 'code', 'desc'), [])
})

test('CSV exports only the filtered order, escapes cells, and preserves numeric negatives', () => {
  const hits = [hit('US.DROP', 10), hit('HK.00700', -2, { name: '=HYPERLINK("unsafe")', change_rate: -1.5, reason: 'a,"b"\nline' })]
  const shown = filterAndSortHits(hits, '', 'HK', 'factor_score', 'desc')
  const csv = hitsToCsv(shown, 'Test', '2026-10-14T00:00:00+00:00')
  assert.ok(csv.startsWith('\uFEFF"strategy"'))
  assert.ok(!csv.includes('US.DROP'))
  assert.ok(csv.includes('"\'=HYPERLINK(""unsafe"")"'))
  assert.ok(csv.includes('"-1.5"'))
  assert.ok(csv.includes('"a,""b""\nline"'))
  for (const input of ['=1+1', '+1', '-1', '@SUM(1)', ' \t=1', '\r\n@sum(1)']) assert.equal(csvCell(input)[1], "'")
  assert.equal(csvCell(-1), '"-1"')
  assert.equal(csvCell(null), '""')
})

test('scan timestamps respect explicit timezone and avoid guessing legacy timezone', () => {
  const now = Date.parse('2026-10-14T04:00:00Z')
  assert.equal(scanTimeInfo('2026-10-14T12:00:00+08:00', now).ageHours, 0)
  assert.equal(scanTimeInfo('2026-10-10T00:00:00Z', now).stale, true)
  assert.equal(scanTimeInfo('2026-10-15T00:00:00Z', now).future, true)
  assert.equal(scanTimeInfo('2026-10-14 12:00:00', now).ageHours, null)
  assert.equal(scanTimeInfo('not a date', now).ageHours, null)
})

test('missing prices format as a placeholder while zero remains a number', () => {
  for (const value of [undefined, null, NaN, Infinity, '12']) assert.equal(formatNumber(value), '-')
  assert.equal(formatNumber(0), '0.00')
})

test('listed-cap variant sorts and exports its declared cap and financial provenance', () => {
  const a = hit('HK.00941', null, { market_cap_basis: 'hk_listed', hk_market_val: 50e9,
    circular_market_val: 1, pe_ttm_ratio: 8, pb_ratio: 1, dividend_ratio_ttm: 6,
    fundamentals_source: 'Eastmoney HK F10', fundamentals_fetched_at: '2026-10-17T12:00:00Z',
    fundamentals_report_date: '2026-06-30' })
  const b = hit('HK.00005', null, { market_cap_basis: 'hk_listed', hk_market_val: 40e9, circular_market_val: 99e9 })
  assert.deepEqual(filterAndSortHits([b, a], '', 'HK', 'circular_market_val', 'desc').map(h => h.code), ['HK.00941', 'HK.00005'])
  const csv = hitsToCsv([a], 'HK value', '2026-10-17T12:00:00Z')
  assert.ok(csv.includes('"50000000000"'))
  assert.ok(csv.includes('"hk_listed"'))
  assert.ok(csv.includes('"Eastmoney HK F10"'))
  assert.ok(csv.includes('"dividend_yield_ttm_pct"'))
})

test('malformed feed is rejected before rendering and shipped legacy data remains compatible', () => {
  const legacy = JSON.parse(fs.readFileSync(path.join(__dirname, '../../public/data/screener_results.json'), 'utf8').replace(/^\uFEFF/, ''))
  assert.equal(isScreenerResults(legacy), true)
  assert.equal(isScreenerResults(null), false)
  assert.equal(isScreenerResults({ ...legacy, strategies: [{}] }), false)
  const broken = structuredClone(legacy)
  broken.strategies[0].hits[0].code = null
  assert.equal(isScreenerResults(broken), false)
})
