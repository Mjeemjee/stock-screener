const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const Module = require('node:module')
const ts = require('typescript')
const filename = path.join(__dirname, 'candles.ts')
const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
}).outputText
const loaded = new Module(filename, module)
loaded._compile(compiled, filename)
const { isCandleData, validCode, chartPeriods, tradeMarkers } = loaded.exports
const code = 'US.TEST'
const bars = [[20261021, 10, 12, 9, 11, 100], [20261022, 11, 13, 10, 12, 0]]
const payload = { schema_version: 1, code, generated_at: '2026-10-23T22:00:00Z', as_of: 20261022, price_basis: 'source_adjusted', volume_unit: 'source_units', source: 'tracking_history', rejected_rows: 0, status: 'available', bars }
const row = { snapshot_id: 's', strategy_id: 'm', horizon: 5, entry_date: 20261021, exit_date: 20261022,
  baskets: { selected: { holdings: [{ code, status: 'matured', entry_price: 10, exit_price: 11, return_pct: 9 }] } } }
test('accepts exact OHLCV including genuine zero volume', () => assert.ok(isCandleData(payload, code)))
test('rejects invalid candles, dates, stale code and metadata', () => {
  for (const value of [null, {}, { ...payload, code: 'US.OTHER' }, { ...payload, as_of: 20261021 }, { ...payload, bars: [...bars].reverse() },
    { ...payload, bars: [[20260230, 10, 12, 9, 11, 100]] }, { ...payload, bars: [[20261021, 10, 9, 9, 11, 100]] },
    { ...payload, bars: [[20261021, 10, 12, 9, NaN, 100]] }, { ...payload, bars: [[20261021, 10, 12, 9, 11, -1]] }])
    assert.equal(isCandleData(value, code), false)
})
test('explicit unavailable data is valid without making candles', () => assert.ok(isCandleData({ ...payload, as_of: null, bars: [], status: 'unavailable' }, code)))
test('security filename disallows path traversal', () => {
  for (const value of ['US.BRK.B', 'HK.00700', 'US.A-B']) assert.ok(validCode(value))
  for (const value of ['US../secret', '../HK.00700', 'HK.700', 'US.A?x=1', '']) assert.equal(validCode(value), false)
})
test('periods preserve both baskets and distinct horizons', () => {
  const second = structuredClone(row); second.horizon = 20; second.baskets.original = second.baskets.selected
  assert.equal(new Set(chartPeriods([row, second], code).map(p => p.id)).size, 3)
  assert.equal(chartPeriods([row], 'US.OTHER').length, 0)
})
test('marks only matching recorded fill dates and open prices', () => {
  const { markers, warnings } = tradeMarkers(chartPeriods([row], code)[0], code, bars)
  assert.deepEqual(markers, [{ time: '2026-10-21', kind: 'buy', price: 10 }, { time: '2026-10-22', kind: 'sell', price: 11 }])
  assert.equal(warnings.length, 0)
})
test('adjustment mismatch hides the affected marker and explains why', () => {
  const changed = structuredClone(bars); changed[0][1] = 10.01
  const result = tradeMarkers(chartPeriods([row], code)[0], code, changed)
  assert.deepEqual(result.markers.map(x => x.kind), ['sell'])
  assert.match(result.warnings[0], /复权/)
})
test('planned exits, missing prices and no-trade cannot become fills', () => {
  const pending = structuredClone(row); pending.exit_date = null; pending.scheduled_exit_date = 20261022
  assert.equal(tradeMarkers(chartPeriods([pending], code)[0], code, bars).markers.length, 1)
  pending.baskets.selected.holdings[0].status = 'no_trade'
  assert.equal(tradeMarkers(chartPeriods([pending], code)[0], code, bars).markers.length, 0)
  assert.equal(tradeMarkers(chartPeriods([row], code)[0], code, []).markers.length, 0)
})
