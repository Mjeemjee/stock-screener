const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const Module = require('node:module')
const ts = require('typescript')
const filename = path.join(__dirname, 'longResearch.ts')
const loaded = new Module(filename, module)
loaded._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
}).outputText, filename)
const { isLongReport } = loaded.exports
const actual = JSON.parse(fs.readFileSync(path.join(__dirname, '../../public/data/long_research.json'), 'utf8'))

test('real long-horizon report preserves pending forward results and separate retrospective diagnostics', () => {
  assert.ok(isLongReport(actual))
  assert.equal(actual.policy.horizon, 21)
  assert.equal(actual.policy.lookback, 251)
  assert.equal(actual.historical.kind, 'retrospective_replay_not_independent_oos')
})
test('malformed policy, basket, cohort, metric and historical data are rejected', () => {
  for (const v of [null, {}, { ...actual, policy: {} }, { ...actual, markets: [{}] },
    { ...actual, cohorts: [{}] }, { ...actual, historical: { summary: [{}] } },
    { ...actual, markets: [{ ...actual.markets[0], latest: {} }] },
    { ...actual, markets: [{ ...actual.markets[0], metrics: { stage: 'unknown' } }] }]) assert.equal(isLongReport(v), false)
})
