const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const Module = require('node:module')
const ts = require('typescript')
const filename = path.join(__dirname, 'validation.ts')
const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
}).outputText
const loaded = new Module(filename, module)
loaded._compile(compiled, filename)
const { validationGroups, fundingSlots } = loaded.exports

function basket(value = 3) {
  return { count: 10, known_count: value === null ? 9 : 10, complete: value !== null, return_pct: value, holdings: [] }
}
function row(id, entry, exit, value = 3, overrides = {}) {
  return { snapshot_id: id, strategy_id: 'test', strategy_name: '测试策略', market: 'US', strategy_version: 'v1',
    horizon: 5, prospective: true, scheduled_entry_date: entry, scheduled_exit_date: exit,
    entry_date: entry, exit_date: exit, original_rank_known: true,
    baskets: { selected: basket(value), original: basket(1) }, benchmark_pct: 2, ...overrides }
}
function data(rows) {
  return { archives: rows.filter(Boolean).map((r, i) => ({ id: r.snapshot_id, provenance: 'prospective',
    strategy_version: r.strategy_version, frozen_at: `2026-10-${String(15 + i).padStart(2, '0')}T20:00:00Z` })), evaluations: rows }
}

test('keeps a missing first window instead of replacing it with a later winning overlapping period', () => {
  const d = data([row('first', 20261102, 20261109, null), row('winner', 20261103, 20261110, 50), row('next', 20261109, 20261116, -2)])
  const g = validationGroups(d).groups[0]
  assert.deepEqual(g.periods.filter(p => p.separated).map(p => p.row.snapshot_id), ['first', 'next'])
  assert.deepEqual(g.separated, { complete: 1, missing: 1, pending: 0, net: null, benchmark: null, excess: null })
  assert.equal(g.all.net, 24)
})

test('earliest frozen scan wins even when a duplicate has better price coverage', () => {
  const d = data([row('early', 20261102, 20261109, null), row('late', 20261102, 20261109, 70)])
  d.evaluations.reverse()
  const g = validationGroups(d).groups[0]
  assert.equal(g.duplicates, 1)
  assert.equal(g.periods[0].row.snapshot_id, 'early')
  assert.equal(g.all.complete, 0)
  assert.equal(g.separated.missing, 1)
})

test('scheduled windows reserve positions before outcomes arrive', () => {
  const d = data([row('a', 20261102, 20261109, 2), row('b', 20261109, 20261116, null, { exit_date: null }),
    row('c', 20261110, 20261117, null, { entry_date: null, exit_date: null })])
  const g = validationGroups(d).groups[0]
  assert.deepEqual(g.periods.map(p => p.separated), [true, true, false])
  assert.equal(g.separated.pending, 1)
  assert.equal(g.separated.missing, 0)
  assert.equal(g.separated.net, 2)
})

test('separates strategies, versions, markets and horizons without pooling their evidence', () => {
  const d = data([row('a', 20261102, 20261109), row('b', 20261102, 20261109, 4, { strategy_version: 'v2' }),
    row('c', 20261102, 20261109, 4, { market: 'HK' }), row('d', 20261102, 20261130, 4, { horizon: 20 }),
    row('e', 20261102, 20261109, 4, { strategy_id: 'other' })])
  const groups = validationGroups(d).groups
  assert.equal(groups.length, 5)
  assert.ok(groups.every(g => g.separated.complete === 1))
})

test('rejects historical imports, orphaned archives, invalid dates and mismatched definitions', () => {
  const d = data([row('ok', 20261102, 20261109), row('history', 20261102, 20261109),
    row('orphan', 20261102, 20261109), row('bad-date', 20260230, 20261109), row('bad-version', 20261102, 20261109)])
  d.archives[1].provenance = 'historical_import'
  d.archives = d.archives.filter(a => a.id !== 'orphan')
  d.archives.find(a => a.id === 'bad-version').strategy_version = 'unrelated'
  d.evaluations.push(null)
  const r = validationGroups(d)
  assert.equal(r.groups.length, 1)
  assert.equal(r.groups[0].periods.length, 1)
  assert.equal(r.invalid, 4)
})

test('requires complete original and index data and accepts genuine zero returns', () => {
  const d = data([row('zero', 20261102, 20261109, 0, { benchmark_pct: 0 }),
    row('original-gap', 20261109, 20261116, 4, { baskets: { selected: basket(4), original: basket(null) } }),
    row('index-gap', 20261116, 20261123, 4, { benchmark_pct: null })])
  const g = validationGroups(d).groups[0]
  assert.equal(g.all.complete, 1)
  assert.equal(g.all.net, 0)
  assert.equal(g.all.excess, 0)
  assert.equal(g.separated.missing, 2)
  assert.equal(g.separated.net, null)
})

test('does not let NaN or an incomplete basket produce a valid score', () => {
  const d = data([row('a', 20261102, 20261109, NaN), row('b', 20261109, 20261116, 3, { benchmark_pct: Infinity })])
  const g = validationGroups(d).groups[0]
  assert.equal(g.all.complete, 0)
  assert.equal(g.separated.missing, 2)
})

test('window choice is unchanged when returns or input order change', () => {
  const d = data([row('a', 20261102, 20261109, -90), row('b', 20261103, 20261110, 90), row('c', 20261109, 20261116, 0)])
  const before = structuredClone(d)
  const expected = validationGroups(d).groups[0].periods.filter(p => p.separated).map(p => p.row.snapshot_id)
  assert.deepEqual(d, before, 'analysis must not mutate frozen input')
  d.evaluations.forEach(r => { r.baskets.selected.return_pct *= -1 })
  d.evaluations.reverse()
  assert.deepEqual(validationGroups(d).groups[0].periods.filter(p => p.separated).map(p => p.row.snapshot_id), expected)
})

test('published snapshot complete-period means agree with the existing paired summary', () => {
  const snapshot = JSON.parse(fs.readFileSync(process.env.VALIDATION_SNAPSHOT || path.join(__dirname, '../../public/data/tracking.json'), 'utf8'))
  const { groups, invalid } = validationGroups(snapshot)
  assert.equal(invalid, 0)
  assert.ok(groups.length > 0)
  for (const g of groups) {
    const s = snapshot.summary.find(r => r.strategy_id === g.strategy && r.market === g.market && r.horizon === g.horizon && r.strategy_version === g.version)
    assert.ok(s)
    assert.equal(g.all.complete, s.matured_pairs)
    if (s.mean_selected_pct !== null) assert.ok(Math.abs(g.all.net - s.mean_selected_pct) < 1e-8)
  }
})

test('funding illustration reuses one fifth without multiplying total principal', () => {
  for (let day = 1; day <= 11; day++) {
    const slots = fundingSlots(day, 10000)
    assert.equal(slots.reduce((s, x) => s + x.amount, 0), 10000)
    assert.equal(slots.filter(x => x.entering).length, 1)
    assert.ok(slots.filter(x => x.start !== null).every(x => x.exit - x.start === 5))
  }
  assert.equal(fundingSlots(1, 10000).filter(x => x.start === null).length, 4)
  assert.equal(fundingSlots(6, 10000)[0].renewed, true)
  assert.equal(fundingSlots(6, 10000)[0].start, 6)
})
