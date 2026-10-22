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
const { isResearchData, parseProposal, formula, validExpression, validResearchCard } = loaded.exports
const actual = JSON.parse(fs.readFileSync(path.join(__dirname, '../../public/data/research.json'), 'utf8'))
const proposal = { name: 'Gap hypothesis', market: actual.universes[0].market, parent_id: null,
  op_type: 'new_factor_family', hypothesis: 'Test forward gap information', change: 'gap input',
  expected: 'Future net improvement', expression: { op: 'feature', name: 'gap' }, filters: [] }

test('research report retains seed families and accepts future custom families', () => {
  assert.ok(isResearchData(actual))
  const families = new Set(actual.programs.map(p => p.family))
  for (const family of ['volume_breakout', 'compression_breakout', 'short_reversal']) assert.ok(families.has(family))
  const extended = structuredClone(actual)
  delete extended.research_review
  extended.programs.push({ ...extended.programs[0], id: 'future-custom-study', family: 'custom' })
  assert.ok(isResearchData(extended))
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
    { ...proposal, op_type: 'auto_trade' },
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

test('model status and proposals are optional for old reports and validated when present', () => {
  const legacy = { ...actual }; delete legacy.model_research
  assert.ok(isResearchData(legacy))
  const model = { provider: 'DeepSeek', model: 'deepseek-flash', connection: 'missing_key', checked_at: actual.generated_at,
    max_calls: 6, min_cohorts: 20, mode: 'owner_review', calls: [] }
  assert.ok(isResearchData({ ...actual, model_research: model }))
  for (const m of [{}, { ...model, calls: [{}] }, { ...model, max_calls: 'six' }, { ...model, mode: 'auto_trade' }]) {
    assert.equal(isResearchData({ ...actual, model_research: m }), false)
  }
  const call = { id: 'fixture', at: actual.generated_at, parent_id: actual.programs[0].id, status: 'completed',
    rejected_count: 0, usage: { output_tokens: 10 }, proposals: [{ proposal: { ...proposal, parent_id: actual.programs[0].id }, started_program_id: null }] }
  assert.ok(isResearchData({ ...actual, model_research: { ...model, calls: [call] } }))
  assert.equal(isResearchData({ ...actual, model_research: { ...model, calls: [{ ...call, proposals: [{}] }] } }), false)
})

test('hypothesis cards accept bounded text and reject executable fields, blanks and unsupported versions', () => {
  const card = { version: 1, evidence: 'Completed outcomes', failure_condition: 'Fail at the original checkpoint', data_risks: 'No news data' }
  assert.ok(validResearchCard(card))
  assert.deepEqual(parseProposal(JSON.stringify({ ...proposal, research_card: card }), actual).research_card, card)
  for (const c of [null, {}, { ...card, version: true }, { ...card, command: 'shell' },
    { ...card, failure_condition: ' ' }, { ...card, evidence: 'x'.repeat(401) }]) {
    assert.equal(validResearchCard(c), false)
    assert.throws(() => parseProposal(JSON.stringify({ ...proposal, research_card: c }), actual))
  }
})

test('read-only reviews are optional, version-bound and reject malformed nested fields', () => {
  const legacy = structuredClone(actual); delete legacy.research_review
  assert.ok(isResearchData(legacy))
  const enriched = structuredClone(actual)
  if (!enriched.research_review) {
    const p = actual.programs[0]
    enriched.research_review = { version: 'research-review-v1', mode: 'read_only', source_generated_at: actual.generated_at,
      source_policy_hash: actual.policy_hash, source_engine_version: actual.engine_version,
      programs: actual.programs.map(p => ({ program_id: p.id, definition_hash: p.definition_hash, evidence_hash: 'test', assessment_hash: null,
        headline: 'No evidence', card: { origin: 'legacy', hypothesis: p.hypothesis, change: p.change, expected: p.expected,
          features: [], evidence: 'Undeclared', failure_condition: 'Original gates', data_risks: 'OHLCV' },
        summary: { total: 0, pending: 0, due: 0, paired: 0, missing: 0, independent: 0, wins: 0, losses: 0, flat: 0,
          beat_parent: 0, beat_benchmark: 0, cash: 0, duplicate: false,
          mean_return_pct: null, mean_delta_pp: null, mean_excess_pp: null, stress_excess_pp: null, worst_period_pct: null },
        checks: [{ id: 'sample', label: 'Sample', status: 'pending', detail: 'No evidence' }] })) }
    assert.ok(p)
  }
  assert.ok(isResearchData(enriched))
  for (const transform of [r => { r.mode = 'auto_trade' }, r => { r.source_policy_hash = 'other' },
    r => { r.source_engine_version = 'other' }, r => { r.source_generated_at = 'old' }, r => { r.programs = [{}] },
    r => { r.programs[0].summary.paired = -1 }, r => { r.programs[0].summary.mean_return_pct = Infinity },
    r => { r.programs[0].card.features = ['fake_news'] }, r => { r.programs[0].checks[0].status = 'DEPLOY' },
    r => { r.programs.push(structuredClone(r.programs[0])) }]) {
    const changed = structuredClone(enriched); transform(changed.research_review)
    assert.equal(isResearchData(changed), false)
  }
})
