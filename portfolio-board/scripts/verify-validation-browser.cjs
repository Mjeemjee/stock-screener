const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright')

async function main() {
  const base = process.argv[2] || 'http://127.0.0.1:5184/'
  const output = path.resolve(process.argv[3] || '../reports/validation-page-20261110/browser-local')
  fs.mkdirSync(output, { recursive: true })
  const browser = await chromium.launch({ channel: 'msedge', headless: true })
  const context = await browser.newContext({ viewport: { width: 1440, height: 1100 } })
  const page = await context.newPage()
  const errors = [], writes = [], checks = []
  page.on('pageerror', error => errors.push(error.message))
  page.on('request', request => { if (!['GET', 'HEAD'].includes(request.method())) writes.push(request.url()) })
  const check = async (name, action) => { await action(); checks.push(name); console.log('PASS', name) }
  const noOverflow = async () => assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'whole page must fit viewport')
  const score = separated => page.getByRole('article').filter({ has: page.getByRole('heading', { name: separated ? '日期对照 · 不重叠期次' : '每天观察 · 全部完整期次', exact: true }) })
  const openValidation = async () => { await page.goto(base + '#/validation'); await page.getByTestId('actual-evidence').waitFor() }
  const fixtureRoute = async fixture => {
    await page.unroute('**/data/tracking.json')
    await page.route('**/data/tracking.json', route => route.fulfill({ json: fixture }))
    await page.reload()
  }
  try {
    const response = await context.request.get(new URL('data/tracking.json', base).href)
    assert.ok(response.ok())
    const payload = await response.json()
    await check('navigation opens validation from tracking and selects the correct top-level tab', async () => {
      await page.goto(base + '#/tracking')
      await page.getByRole('link', { name: /期数很多，证据就充分了吗/ }).click()
      await page.getByTestId('actual-evidence').waitFor()
      assert.equal(await page.getByRole('navigation', { name: '主导航' }).getByRole('link', { name: '验证', exact: true }).getAttribute('aria-current'), 'page')
      await noOverflow()
    })
    await check('both timeline modes have accurate accessible descriptions and keyboard controls', async () => {
      await page.getByRole('img', { name: '三期持有时间重叠', exact: true }).waitFor()
      const button = page.getByRole('button', { name: '结束后再开始', exact: true })
      await button.focus(); await page.keyboard.press('Space')
      assert.equal(await button.getAttribute('aria-pressed'), 'true')
      await page.getByRole('img', { name: '三期持有时间不重叠', exact: true }).waitFor()
      await page.getByRole('button', { name: '每天开始一期', exact: true }).click()
    })
    await check('real live complete-period count and mean agree with the published summary', async () => {
      const version = await page.getByLabel('规则版本', { exact: true }).inputValue()
      const strategy = await page.getByLabel('选股策略', { exact: true }).inputValue()
      const summary = payload.summary.find(row => row.market === 'US' && row.horizon === 5 && row.strategy_version === version && row.strategy_id === strategy)
      assert.ok(summary)
      await score(false).getByText(String(summary.matured_pairs), { exact: true }).waitFor()
      const value = summary.mean_selected_pct
      if (value !== null) await score(false).getByText(`${value > 0 ? '+' : ''}${value.toFixed(2)}%`, { exact: true }).waitFor()
      await page.screenshot({ path: path.join(output, 'validation-desktop.png'), fullPage: true })
    })
    await check('market, holding period and version filters stay distinct', async () => {
      await page.getByLabel('市场', { exact: true }).selectOption('HK')
      await page.getByLabel('持有期', { exact: true }).selectOption('60')
      const version = await page.getByLabel('规则版本', { exact: true }).inputValue()
      const strategy = await page.getByLabel('选股策略', { exact: true }).inputValue()
      const summary = payload.summary.find(row => row.market === 'HK' && row.horizon === 60 && row.strategy_version === version && row.strategy_id === strategy)
      assert.ok(summary)
      await score(false).getByText(String(summary.matured_pairs), { exact: true }).waitFor()
      await page.getByLabel('持有期', { exact: true }).selectOption('5')
      const options = await page.getByLabel('规则版本', { exact: true }).locator('option').evaluateAll(nodes => nodes.map(n => n.value))
      if (options.length > 1) { await page.getByLabel('规则版本', { exact: true }).selectOption(options.at(-1)); assert.equal(await page.getByLabel('规则版本', { exact: true }).inputValue(), options.at(-1)) }
      await page.getByLabel('市场', { exact: true }).selectOption('US')
      await page.getByLabel('规则版本', { exact: true }).selectOption({ index: 0 })
    })
    await check('capital rotation reuses funds on day six without inventing account profits', async () => {
      const slider = page.getByRole('slider', { name: '资金轮转交易日' })
      await slider.focus(); await page.keyboard.press('Home')
      assert.match(await page.getByTestId('funding-total').innerText(), /投入本金 2,000 元.*等待现金 8,000 元.*10,000 元/)
      for (let i = 0; i < 5; i++) await page.keyboard.press('ArrowRight')
      assert.equal(await slider.inputValue(), '6')
      await page.getByText('退出后再次投入', { exact: true }).waitFor()
      assert.match(await page.getByTestId('funding-total').innerText(), /投入本金 10,000 元.*等待现金 0 元.*10,000 元/)
      await page.getByText('概念演示 · 不代表账户收益', { exact: true }).waitFor()
    })
    for (const width of [320, 390, 768, 1440]) {
      await check(`responsive layout and controls at ${width}px`, async () => {
        await page.setViewportSize({ width, height: 1000 })
        await noOverflow()
        await page.getByRole('button', { name: '结束后再开始', exact: true }).click()
        await page.getByRole('region', { name: '逐期不重叠对照' }).focus()
        await page.keyboard.press('ArrowRight')
        await noOverflow()
        await page.evaluate(() => window.scrollTo(0, 0))
        await page.screenshot({ path: path.join(output, `validation-${width}.png`), fullPage: true })
        if (width === 320) await page.screenshot({ path: path.join(output, 'validation-mobile-viewport.png') })
      })
    }

    const basket = value => ({ count: 10, known_count: value === null ? 9 : 10, complete: value !== null, return_pct: value, holdings: [] })
    const row = (id, entry, exit, value, extras = {}) => ({ snapshot_id: id, strategy_id: 'oversold_watch', strategy_name: '核验用策略', market: 'US', strategy_version: 'fixture', horizon: 5,
      prospective: true, scheduled_entry_date: entry, scheduled_exit_date: exit, entry_date: entry, exit_date: exit,
      original_rank_known: true, baskets: { selected: basket(value), original: basket(1) }, benchmark_pct: 2, ...extras })
    const fixture = { ...payload, generated_at: '2026-11-20T22:00:00Z', evaluations: [row('missing', 20261102, 20261109, null), row('overlap', 20261103, 20261110, 50), row('next', 20261109, 20261116, -2)], summary: [] }
    fixture.archives = fixture.evaluations.map((r, i) => ({ id: r.snapshot_id, strategy_version: 'fixture', provenance: 'prospective', frozen_at: `2026-10-${20 + i}T20:00:00Z`, candidate_count: 10, complete_candidates: true }))
    await check('missing scheduled window is preserved and cannot be replaced with the later winning overlap', async () => {
      await fixtureRoute(fixture)
      await page.getByTestId('actual-evidence').waitFor()
      await score(false).getByText('+24.00%', { exact: true }).waitFor()
      await score(true).getByText('1', { exact: true }).waitFor()
      assert.equal(await score(true).getByText('待定', { exact: true }).count(), 3)
      const table = page.getByRole('region', { name: '逐期不重叠对照' })
      await table.getByRole('row').filter({ hasText: '2026-11-02 → 2026-11-09' }).getByText('缺价格，保留位置', { exact: true }).waitFor()
      await table.getByRole('row').filter({ hasText: '2026-11-03 → 2026-11-10' }).getByText('与前期重叠', { exact: true }).waitFor()
      await page.screenshot({ path: path.join(output, 'validation-missing.png'), fullPage: true })
    })
    await check('pending windows are shown without future or fabricated returns', async () => {
      const pending = structuredClone(fixture)
      pending.evaluations = [row('missing', 20261102, 20261109, null, { exit_date: null })]
      await fixtureRoute(pending)
      await page.getByText('目前还没有完整的不重叠持有期。', { exact: true }).waitFor()
      await page.getByRole('cell', { name: '未到期', exact: true }).waitFor()
      assert.equal(await score(true).getByText('待定', { exact: true }).count(), 3)
    })
    await check('empty and historical-only archives do not become evidence', async () => {
      const empty = { ...fixture, archives: [], evaluations: [], summary: [] }
      await fixtureRoute(empty)
      await page.getByText('当前筛选下暂无可比较的前瞻记录。历史导入不参与这项统计。', { exact: true }).waitFor()
      assert.equal(await page.getByTestId('actual-evidence').count(), 0)
    })
    await check('invalid JSON structure is explained rather than causing a page exception', async () => {
      await fixtureRoute({ schema_version: 1 })
      await page.getByRole('alert').filter({ hasText: '追踪数据格式不完整' }).waitFor()
    })
    await check('HTTP error offers retry and restores real data', async () => {
      await page.unroute('**/data/tracking.json')
      let fail = true
      await page.route('**/data/tracking.json', route => fail ? route.fulfill({ status: 503, body: 'Unavailable' }) : route.fulfill({ json: payload }))
      await page.reload()
      await page.getByRole('alert').filter({ hasText: '503' }).waitFor()
      fail = false
      await page.getByRole('button', { name: '刷新验证数据', exact: true }).click()
      await page.getByTestId('actual-evidence').waitFor()
      fail = true
      await page.getByRole('button', { name: '刷新验证数据', exact: true }).click()
      await page.getByRole('alert').filter({ hasText: '下方保留上次读取的记录' }).waitFor()
      await page.getByTestId('actual-evidence').waitFor()
    })
    await check('tracking and research destinations remain reachable', async () => {
      await page.unroute('**/data/tracking.json')
      await page.getByRole('link', { name: '查看股票与逐期跟踪' }).click()
      await page.getByRole('combobox', { name: '追踪持有期' }).waitFor()
      await openValidation()
      await page.getByRole('link', { name: '查看因子研究的验收条件', exact: true }).click()
      assert.match(page.url(), /#\/lab\/research$/)
      await page.getByRole('navigation', { name: '实验室分类' }).waitFor()
    })
    assert.deepEqual(errors, [])
    assert.deepEqual(writes, [])
    fs.writeFileSync(path.join(output, 'checks.json'), JSON.stringify({ base, checked_at: new Date().toISOString(), count: checks.length, checks, errors, writes, tracking_generated_at: payload.generated_at }, null, 2))
    console.log(`${checks.length} validation browser checks passed; no page errors or write requests.`)
  } catch (error) {
    await page.screenshot({ path: path.join(output, 'failure.png'), fullPage: true }).catch(() => {})
    fs.writeFileSync(path.join(output, 'failure.json'), JSON.stringify({ checks, errors, writes, error: String(error) }, null, 2))
    throw error
  } finally { await browser.close() }
}
main().catch(error => { console.error(error); process.exitCode = 1 })
