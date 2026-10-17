const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const Module = require('node:module')
const ts = require('typescript')
const filename = path.join(__dirname, 'lab.ts')
const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
}).outputText
const loaded = new Module(filename, module)
loaded._compile(compiled, filename)
const { isLabData } = loaded.exports
const actual = JSON.parse(fs.readFileSync(path.join(__dirname, '../../public/data/lab.json'), 'utf8'))

test('real pending laboratory report validates without invented trials', () => assert.ok(isLabData(actual)))
test('incomplete or malformed experiment records are rejected before rendering', () => {
  for (const value of [null, {}, { ...actual, trials: [{}] }, { ...actual, parents: [{}] },
    { ...actual, observations: [{}] }, { ...actual, events: [{}] },
    { ...actual, policy: { ...actual.policy, checkpoints: [] } }]) assert.equal(isLabData(value), false)
})
