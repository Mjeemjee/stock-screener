const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const Module = require('node:module')
const ts = require('typescript')
const filename = path.join(__dirname, 'research.ts')
const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
}).outputText
const loaded = new Module(filename, module)
loaded._compile(compiled, filename)
const { isResearchData, parseProposal, formula, validExpression } = loaded.exports
const actual = JSON.parse(fs.readFileSync(path.join(__dirname, '../../public/data/research.json'), 'utf8'))
const proposal = { name: 'Gap hypothesis', market: actual.universes[0].market, parent_id: null,
  op_type: 'new_factor_family', hypothesis: 'Test forward gap information', change: 'gap input',
  expected: 'Future net improvement', expression: { op: 'feature', name: 'gap' }, filters: [] }

test('real independent research report validates without fabricated mature outcomes', () => {
  assert.ok(isResearchData(actual))
  assert.equal(new Set(actual.programs.map(p => p.family)).size, 3)
})
test('malformed nested reports fail before a page can render them', () => {
  for (const value of [null, {}, { ...actual, programs: [{}] }, { ...actual, observations: [{}] },
    { ...actual, quality: [{}] }, { ...actual, universes: [{}] }, { ...actual, searches: [{}] },
    { ...actual, features: { bad: {} } }, { ...actual, programs: [{ ...actual.programs[0], historical: { folds: [{}] } }] }]) {
    assert.equal(isResearchData(value), false)
  }
})
test('proposal parser rejects unknown code, extra fields and cross-market ancestry', () => {
  assert.deepEqual(parseProposal(JSON.stringify(proposal), actual), proposal)
  for (const bad of [{ ...proposal, command: 'shell' }, { ...proposal, market: 'CN' },
    { ...proposal, expression: { op: 'eval', code: 'alert(1)' } },
    { ...proposal, name: ' ' }, { ...proposal, parent_id: 'missing' },
    { ...proposal, filters: [{ feature: 'gap', gte: 3, lte: 2 }] },
    { ...proposal, filters: [{ feature: 'gap', gte: true }] }]) {
    assert.throws(() => parseProposal(JSON.stringify(bad), actual))
  }
})
test('bounded formulas render as named factors with the correct operator', () => {
  const expr = { op: 'product', args: [{ op: 'feature', name: 'gap' }, { op: 'neg', arg: { op: 'feature', name: 'reversal3' } }] }
  assert.ok(validExpression(expr, Object.keys(actual.features)))
  assert.match(formula(expr, actual.features), /交互/)
  assert.match(formula(expr, actual.features), /负向/)
  let deep = expr
  for (let i = 0; i < 6; i++) deep = { op: 'neg', arg: deep }
  assert.equal(validExpression(deep, Object.keys(actual.features)), false)
})
