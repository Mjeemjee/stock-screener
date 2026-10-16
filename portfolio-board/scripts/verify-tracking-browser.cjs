const assert = require('node:assert/strict')
const path = require('node:path')
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright')

async function main() {
  const base = process.argv[2] || 'http://127.0.0.1:5173/'
  const reports = path.resolve(__dirname, '../../reports')
  const browser = await chromium.launch({ channel: 'msedge', headless: true })
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
  const page = await context.newPage()
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  let count = 0
  async function check(name, action) { await action(); count++; console.log(`PASS ${name}`) }
  async function noOverflow() { assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true) }
  try {
    const payload = await (await context.request.get(new URL('data/tracking.json', base).href)).json()
    const code = Object.keys(payload.securities).find(key => payload.securities[key].history?.length > 20)
    assert.ok(code, 'One real archived security with chart data is required')
    await check('real tracking archives and holding-period controls', async () => {
      await page.goto(base + '#/tracking')
      await page.getByRole('combobox', { name: '追踪持有期' }).waitFor()
      await noOverflow()
      await page.getByRole('combobox', { name: '追踪持有期' }).selectOption('5')
      await page.getByRole('button', { name: '港股', exact: true }).click()
      await page.getByRole('button', { name: '美股', exact: true }).click()
      await page.screenshot({ path: path.join(reports, 'tracking-desktop.png') })
    })
    await check('real detail chart, risk fields and appearance history', async () => {
      await page.goto(base + '#/stock/' + encodeURIComponent(code))
      await page.getByRole('heading', { name: '近期价格', exact: true }).waitFor()
      assert.ok(await page.locator('.recharts-line-curve').evaluate(node => (node.getAttribute('d') || '').length > 50))
      await page.getByText('20 日年化波动', { exact: true }).waitFor()
      await page.getByText('暂无可靠数据', { exact: false }).waitFor()
      await noOverflow()
      await page.screenshot({ path: path.join(reports, 'stock-detail-desktop.png') })
    })
    await check('watchlist addition persists on reload and can be removed', async () => {
      await page.getByRole('button', { name: `加入观察名单 ${code}`, exact: true }).click()
      await page.getByRole('link', { name: '自选', exact: true }).click()
      await page.getByRole('button', { name: `移出观察名单 ${code}`, exact: true }).waitFor()
      await page.reload()
      await page.getByRole('button', { name: `移出观察名单 ${code}`, exact: true }).click()
      await page.getByText('观察名单为空。', { exact: true }).waitFor()
      await page.getByRole('textbox', { name: '添加观察标的' }).fill('US.AAPL')
      await page.getByRole('button', { name: '添加代码到观察名单', exact: true }).click()
      await page.getByRole('button', { name: '移出观察名单 US.AAPL', exact: true }).waitFor()
    })
    await check('malformed saved watchlist recovers without a page error', async () => {
      await page.evaluate(() => localStorage.setItem('screener.watchlist.v1', '{broken'))
      await page.reload()
      await page.getByText('观察名单为空。', { exact: true }).waitFor()
    })
    for (const width of [390, 320]) {
      await check(`tracking, detail and watchlist mobile ${width}px`, async () => {
        await page.setViewportSize({ width, height: 844 })
        await page.goto(base + '#/tracking')
        await page.getByRole('combobox', { name: '追踪持有期' }).waitFor()
        await noOverflow()
        await page.screenshot({ path: path.join(reports, `tracking-mobile-${width}.png`) })
        await page.goto(base + '#/stock/' + encodeURIComponent(code))
        await page.getByRole('heading', { name: '近期价格', exact: true }).waitFor()
        await noOverflow()
        await page.screenshot({ path: path.join(reports, `stock-detail-mobile-${width}.png`) })
        await page.getByRole('link', { name: '自选', exact: true }).click()
        await page.getByRole('textbox', { name: '添加观察标的' }).waitFor()
        await noOverflow()
      })
    }
    await check('matured, missing-price and paired summary states use distinct data', async () => {
      const fixture = structuredClone(payload)
      fixture.archives.push({ ...payload.archives[0], id: 'fixture', provenance: 'prospective', frozen_at: '2026-09-01T12:00:00Z' })
      const row = { ...payload.evaluations.find(value => value.market === 'US'), snapshot_id: 'fixture', market: 'US', prospective: true, horizon: 20, entry_date: 20260902, exit_date: 20260930,
        baskets: { selected: { count: 10, known_count: 10, complete: true, return_pct: 3, holdings: [] }, original: { count: 10, known_count: 10, complete: true, return_pct: 1, holdings: [] } }, benchmark_pct: 2 }
      fixture.evaluations.push(row, { ...row, snapshot_id: 'gap', baskets: { ...row.baskets, selected: { ...row.baskets.selected, complete: false, known_count: 9, return_pct: null } } })
      fixture.summary = [{ strategy_id: row.strategy_id, market: 'US', horizon: 20, strategy_version: 'fixture', cohorts: 2, matured_pairs: 1, mean_selected_pct: 3, mean_original_pct: 1, mean_benchmark_pct: 2, mean_delta_pp: 2 }]
      await page.route('**/data/tracking.json', route => route.fulfill({ json: fixture }))
      await page.goto(base + '#/tracking')
      await page.getByText('已到期', { exact: false }).waitFor()
      await page.getByRole('cell', { name: /缺价格/ }).waitFor()
      await page.getByText('2.00 pp', { exact: true }).waitFor()
      await noOverflow()
    })
    await check('tracking HTTP failure retries', async () => {
      await page.unroute('**/data/tracking.json')
      let failed = true
      await page.route('**/data/tracking.json', route => failed ? route.fulfill({ status: 503, body: 'unavailable' }) : route.fulfill({ json: payload }))
      await page.reload()
      await page.getByRole('alert').waitFor()
      failed = false
      await page.getByRole('button', { name: '刷新追踪数据', exact: true }).click()
      await page.getByRole('combobox', { name: '追踪持有期' }).waitFor()
    })
    assert.deepEqual(errors, [])
    console.log(`${count} tracking browser checks passed; no uncaught page errors.`)
  } finally { await browser.close() }
}
main().catch(error => { console.error(error); process.exitCode = 1 })
