const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const ts = require('typescript')

// Compile only the imported pure TypeScript modules; no Vite glob registry is required.
require.extensions['.ts'] = (mod, filename) => mod._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
}).outputText, filename)
const { INVESTMENT_METHODS } = require('../content/investmentMethods.ts')
const { filterInvestmentMethods, investmentMethodPreset } = require('./investmentMethods.ts')
const { strategy: breakout } = require('../backtest/strategies/breakout.ts')
const { combineSignals } = require('../backtest/combo.ts')
const { runBacktestCore, runBacktest } = require('../backtest/engine.ts')
const resolve = id => id === breakout.id ? breakout : undefined

test('six unique methods retain attributable sources and honest execution bindings', () => {
  assert.equal(INVESTMENT_METHODS.length, 6)
  assert.equal(new Set(INVESTMENT_METHODS.map(m => m.id)).size, 6)
  assert.equal(INVESTMENT_METHODS.filter(m => m.executionBinding.backtestId).length, 1)
  for (const method of INVESTMENT_METHODS) {
    assert.notEqual(method.representation, 'rule_replication')
    assert.ok(method.limitations.length && method.requiredData.length && method.people.length)
    assert.equal(method.executionBinding.screenerId, null)
    for (const source of method.sources) {
      assert.equal(new URL(source.url).protocol, 'https:')
      assert.ok(source.supports && source.limitations && source.sourceType && source.checkedOn)
    }
  }
})

test('combined filters preserve the conjunction and expose missing capabilities', () => {
  assert.equal(filterInvestmentMethods('巴菲特', 'ALL', 'HK', 'ALL').length, 1)
  assert.equal(filterInvestmentMethods('巴菲特', 'ALL', 'HK', 'backtest').length, 0)
  assert.equal(filterInvestmentMethods('', 'ALL', 'ALL', 'reference').length, 5)
  assert.equal(filterInvestmentMethods('', '趋势突破', 'HK', 'backtest').length, 1)
  assert.equal(filterInvestmentMethods('', 'ALL', 'ALL', 'ALL').length, 6)
})

test('deep link resolves only an existing bound module and validates parameter defaults', () => {
  assert.equal(investmentMethodPreset(null, resolve).error, null)
  for (const id of ['unknown', 'buffett-quality-value', '<script>']) {
    const preset = investmentMethodPreset(id, resolve)
    assert.ok(preset.error)
    assert.equal(preset.stack, null)
  }
  assert.ok(investmentMethodPreset('turtle-breakout-adapted', () => undefined).error)
  const preset = investmentMethodPreset('turtle-breakout-adapted', resolve)
  assert.equal(preset.error, null)
  assert.deepEqual(preset.stack.blocks[0].params, { lookback: 20, volMult: 1.5, exitLookback: 10 })
  for (const spec of breakout.params) assert.equal(preset.stack.blocks[0].params[spec.key], spec.default)
})

test('method and original breakout entry produce identical trades and equity with next-bar execution', () => {
  const bars = Array.from({ length: 120 }, (_, i) => {
    const c = i < 80 ? 100 + i : 180 - (i - 80) * 3
    return { d: Number(new Date(Date.UTC(2025, 0, i + 1)).toISOString().slice(0, 10).replaceAll('-', '')),
      o: c - .2, h: c + 1, l: c - 1, c, v: i === 65 ? 5000 : 1000 }
  })
  const stocks = [{ code: 'HK.TEST', name: 'Synthetic', bars }]
  const opts = { initialCash: 100000, maxPositions: 1, costPct: .15, stopLossPct: 0, takeProfitPct: 0, maxHoldDays: 0 }
  const stack = investmentMethodPreset('turtle-breakout-adapted', resolve).stack
  const original = runBacktest(stocks, breakout, stack.blocks[0].params, opts)
  const method = runBacktestCore(stocks, combineSignals(stack, resolve), opts)
  assert.ok(original.trades.length > 0)
  assert.deepEqual(method.trades, original.trades)
  assert.deepEqual(method.equity, original.equity)
  assert.deepEqual(method.metrics, original.metrics)
  assert.equal(method.trades[0].entryDate, bars[66].d)
  const changed = bars.map((b, i) => i < 100 ? b : { ...b, o: 10000, h: 10001, l: 9999, c: 10000 })
  const a = breakout.prepare(bars, stack.blocks[0].params)
  const b = breakout.prepare(changed, stack.blocks[0].params)
  assert.deepEqual(a.entries.slice(0, 100), b.entries.slice(0, 100))
  assert.deepEqual(a.exits.slice(0, 100), b.exits.slice(0, 100))
})
