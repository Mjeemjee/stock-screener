const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright')

async function main() {
  const base = process.argv[2] || 'http://127.0.0.1:5175/'
  const reports = path.resolve(__dirname, '../../reports')
  const browser = await chromium.launch({ channel: 'msedge', headless: true })
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
  const page = await context.newPage()
  const errors = [], writes = []
  page.on('pageerror', error => errors.push(error.message))
  page.on('request', request => { if (!['GET', 'HEAD'].includes(request.method())) writes.push(request.url()) })
  let checks = 0
  async function check(name, action) { await action(); checks++; console.log(`PASS ${name}`) }
  async function noOverflow() { assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true) }
  const actual = await (await context.request.get(new URL('data/lab.json', base).href)).json()
  try {
    await check('real parents show pending progress without fake trial results', async () => {
      assert.ok(actual.parents.length > 0)
      await page.goto(base + '#/lab')
      await page.getByRole('heading', { name: '母策略准备情况' }).waitFor()
      assert.equal(await page.locator('progress').count(), actual.parents.length)
      await noOverflow()
      await page.screenshot({ path: path.join(reports, 'lab-real-desktop.png'), fullPage: true })
    })
    const fixture = structuredClone(actual)
    fixture.trials = ['testing', 'review', 'rejected', 'approved', 'paused'].map((status, index) => ({
      id: `lab_fixture_${status}`, root_id: fixture.parents[0].root_id, parent_id: fixture.parents[0].id,
      generation: index === 2 ? 2 : 1, market: index === 0 ? 'HK' : 'US', source_version: 'fixture',
      created_at: '2026-09-01T10:00:00Z', name: `测试分支 ${status}`, hypothesis: '仅提高成交额门槛，验证未来配对收益。', expected: '独立前瞻验证',
      base_params: { min_turnover: 20000000 }, params: { min_turnover: 30000000 }, definition_hash: 'definition-fixture',
      change: { parameter: 'min_turnover', from: 20000000, to: 30000000 }, status, last_checkpoint: status === 'testing' ? 0 : 40,
      metrics: { due: 40, paired: 39, coverage: .975, signal_rate: 1, independent: 8, mean_delta_pp: 1.25,
        lower_delta_pp: .15, mean_return_pct: 3, mean_excess_pp: 2, stress_excess_pp: 1.7, worst_period_pct: -3 },
      assessments: status === 'testing' ? [] : [{ checkpoint: 40, metrics: {}, gates: { coverage: true, signal_rate: true, independent: true,
        improvement: true, uncertainty: true, benchmark: true, stress_cost: true, risk: status !== 'rejected' }, hash: 'evidence-fixture' }],
    }))
    fixture.observations = fixture.trials.flatMap(trial => Array.from({ length: 8 }, (_, index) => ({
      trial_id: trial.id, entry_date: 20260901 + index, due: true, benchmark_pct: 1,
      branch: { complete: true, count: 10, return_pct: index % 3 === 0 ? -1 : 3 }, parent: { complete: true, return_pct: 1 },
    })))
    fixture.events = fixture.trials.map(trial => ({ trial_id: trial.id, action: 'created', at: trial.created_at }))
    let mode = 'fixture'
    await page.route('**/data/lab.json', route => mode === 'error' ? route.fulfill({ status: 503, body: 'unavailable' })
      : route.fulfill({ json: mode === 'malformed' ? { schema_version: 1 } : fixture }))
    await check('all lifecycle states, experiment details and nonblank data chart', async () => {
      await page.reload()
      await page.getByRole('button', { name: '查看实验 lab_fixture_review', exact: true }).click()
      await page.getByRole('heading', { name: '测试分支 review', exact: true }).waitFor()
      assert.ok(await page.locator('.recharts-rectangle').count() > 0)
      await page.getByText('40 期关卡', { exact: false }).waitFor()
      await noOverflow()
      await page.screenshot({ path: path.join(reports, 'lab-fixture-desktop.png'), fullPage: true })
    })
    await check('review download carries pinned evidence and does not approve through the browser', async () => {
      const ready = page.waitForEvent('download')
      await page.getByRole('button', { name: '下载审核申请' }).click()
      const download = await ready
      const request = JSON.parse(fs.readFileSync(await download.path(), 'utf8'))
      assert.equal(request.trial_id, 'lab_fixture_review')
      assert.equal(request.evidence_hash, 'evidence-fixture')
      assert.equal(await page.getByRole('link', { name: '仓库权限审核' }).getAttribute('href'), actual.review_workflow)
      assert.deepEqual(writes, [])
    })
    await check('market/status filters and empty filtered state', async () => {
      await page.getByRole('combobox', { name: '实验状态' }).selectOption('review')
      assert.equal(await page.locator('tbody tr').count(), 1)
      await page.getByRole('button', { name: '港股', exact: true }).click()
      await page.getByText('当前条件下没有实验。', { exact: false }).waitFor()
      await page.getByRole('button', { name: '全部', exact: true }).click()
    })
    for (const width of [768, 390, 320]) {
      await check(`lab layout and chart at ${width}px`, async () => {
        await page.setViewportSize({ width, height: 900 })
        await page.getByRole('heading', { name: '测试分支 review', exact: true }).waitFor()
        await noOverflow()
        const bounds = await page.locator('[aria-label="配对差值图表"]').boundingBox()
        assert.ok(bounds.width > 200 && bounds.height > 100)
        await page.screenshot({ path: path.join(reports, `lab-mobile-${width}.png`), fullPage: true })
      })
    }
    await check('HTTP error retries and malformed report remains recoverable', async () => {
      mode = 'error'
      await page.reload()
      await page.getByRole('alert').waitFor()
      mode = 'fixture'
      await page.getByRole('button', { name: '重试', exact: true }).click()
      await page.getByRole('heading', { name: '母策略准备情况' }).waitFor()
      mode = 'malformed'
      await page.reload()
      await page.getByRole('alert').filter({ hasText: '实验室数据格式不完整' }).waitFor()
    })
    assert.deepEqual(errors, [])
    console.log(`${checks} laboratory browser checks passed; no uncaught errors or write requests.`)
  } finally { await browser.close() }
}
main().catch(error => { console.error(error); process.exitCode = 1 })
