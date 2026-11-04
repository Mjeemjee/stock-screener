const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright')

async function main() {
  const base = process.argv[2] || 'http://127.0.0.1:5183/'
  const output = path.resolve(process.argv[3] || '../reports/candles-20261104/browser')
  fs.mkdirSync(output, { recursive: true })
  const browser = await chromium.launch({ channel: 'msedge', headless: true })
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
  const page = await context.newPage()
  const errors = [], writes = [], results = []
  page.on('pageerror', e => errors.push(e.message))
  page.on('request', r => { if (!['GET', 'HEAD'].includes(r.method())) writes.push(r.url()) })
  const check = async (name, action) => { await action(); results.push(name); console.log('PASS', name) }
  const noOverflow = async () => assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
  const canvas = () => page.getByRole('img', { name: /日K线与成交量/ }).locator('canvas').first()
  try {
    const tracking = await (await context.request.get(new URL('data/tracking.json', base).href)).json()
    let code, real
    for (const security of Object.values(tracking.securities).filter(s => s.history?.length > 20).slice(0, 30)) {
      const response = await context.request.get(new URL(`data/candles/${security.code}.json`, base).href)
      if (response.ok()) { const data = await response.json(); if (data.bars?.length > 20) { code = security.code; real = data; break } }
    }
    assert.ok(code, 'real OHLCV available')
    await check('real daily candles, volume, OHLC and data table', async () => {
      await page.goto(base + '#/stock/' + encodeURIComponent(code))
      await canvas().waitFor()
      assert.ok(await canvas().evaluate(c => c.width > 100 && c.height > 100))
      await page.getByText(`日线截至 ${String(real.as_of).replace(/(\d{4})(\d{2})(\d{2})/, '$1-$2-$3')}`, { exact: false }).waitFor()
      await page.locator('summary').filter({ hasText: '日线价格表' }).click()
      const rows = page.getByRole('region', { name: '股票日K线' }).locator('details table').getByRole('row')
      assert.equal(await rows.count(), real.bars.length + 1)
      assert.equal(Number((await rows.nth(1).getByRole('cell').nth(1).innerText()).replaceAll(',', '')), real.bars.at(-1)[1])
      await noOverflow()
      await page.evaluate(() => window.scrollTo(0, 0))
      await page.screenshot({ path: path.join(output, 'real-desktop.png'), fullPage: true })
    })
    await check('range, zoom and fit controls work', async () => {
      await page.getByRole('button', { name: '1个月', exact: true }).click()
      assert.equal(await page.getByRole('button', { name: '1个月', exact: true }).getAttribute('aria-pressed'), 'true')
      await page.getByRole('button', { name: '放大K线', exact: true }).click()
      await page.getByRole('button', { name: '缩小K线', exact: true }).click()
      await page.getByRole('button', { name: '显示全部', exact: true }).click()
      await page.getByRole('button', { name: '12个月', exact: true }).click()
    })
    await check('tracking basket link opens the exact period', async () => {
      await page.goto(base + '#/tracking')
      await page.getByRole('combobox', { name: '追踪持有期' }).selectOption('5')
      await page.locator('summary').filter({ hasText: '查看股票 / K线' }).first().click()
      const link = page.locator('a[href*="?period="]').first()
      const href = await link.getAttribute('href')
      assert.ok(href)
      const id = new URLSearchParams(href.split('?')[1]).get('period')
      await link.click()
      await page.getByRole('combobox', { name: 'K线跟踪期' }).waitFor()
      assert.equal(await page.getByRole('combobox', { name: 'K线跟踪期' }).inputValue(), id)
    })
    const fixture = structuredClone(tracking)
    const dates = real.bars.slice(-6)
    const trade = { snapshot_id: 'chart-fixture', strategy_id: 'chart-fixture', strategy_name: '图表验收', market: code.split('.')[0], strategy_version: 'fixture', horizon: 5,
      prospective: true, scheduled_entry_date: dates[0][0], scheduled_exit_date: dates.at(-1)[0], entry_date: dates[0][0], exit_date: dates.at(-1)[0], original_rank_known: false,
      baskets: { selected: { count: 1, complete: true, known_count: 1, return_pct: 1, holdings: [{ code, status: 'matured', entry_price: dates[0][1], exit_price: dates.at(-1)[1], return_pct: 1 }] } }, benchmark_pct: 0 }
    fixture.evaluations = [trade]
    await page.route('**/data/tracking.json', r => r.fulfill({ json: fixture }))
    const url = base + '#/stock/' + encodeURIComponent(code)
    await check('both matching simulated trade markers appear', async () => {
      await page.goto(url); await page.reload()
      await page.getByText('2 个模拟买卖标记', { exact: false }).waitFor()
      await canvas().waitFor()
    })
    await check('adjustment mismatch hides only the incorrect marker', async () => {
      fixture.evaluations[0].baskets.selected.holdings[0].entry_price += 1
      await page.reload()
      await page.getByText('1 个模拟买卖标记', { exact: false }).waitFor()
      await page.getByText(/模拟买入价与该日开盘价不同/).waitFor()
    })
    await check('future planned exit is not a completed trade marker', async () => {
      fixture.evaluations[0].baskets.selected.holdings[0].entry_price = dates[0][1]
      fixture.evaluations[0].exit_date = null
      fixture.evaluations[0].baskets.selected.holdings[0].status = 'pending'
      await page.reload()
      await page.getByText('1 个模拟买卖标记', { exact: false }).waitFor()
      await page.getByText(/模拟卖出：预计/).waitFor()
      await page.getByText('扣费收益：待定', { exact: true }).waitFor()
    })
    for (const width of [768, 390, 320]) await check(`mobile ${width}px candles and table fit`, async () => {
      await page.setViewportSize({ width, height: 1000 })
      await page.reload(); await canvas().waitFor(); await noOverflow()
      await page.locator('summary').filter({ hasText: '日线价格表' }).click(); await noOverflow()
      await page.evaluate(() => window.scrollTo(0, 0))
      await page.screenshot({ path: path.join(output, `mobile-${width}.png`), fullPage: true })
    })
    await check('404 is explicit and retry restores chart', async () => {
      let failed = true
      await page.route('**/data/candles/*.json', r => failed ? r.fulfill({ status: 404, body: 'missing' }) : r.fulfill({ json: real }))
      await page.reload(); await page.getByText(/该股票暂无公开日K线/).waitFor()
      assert.equal(await canvas().count(), 0)
      failed = false
      await page.getByRole('button', { name: '重试日K线', exact: true }).click(); await canvas().waitFor()
    })
    await check('malformed candles stop charting and empty data stays empty', async () => {
      await page.unroute('**/data/candles/*.json')
      await page.route('**/data/candles/*.json', r => r.fulfill({ json: { ...real, bars: [[20261022, 10, 1, 9, 11, 0]] } }))
      await page.reload(); await page.getByText(/日K线格式或价格不完整/).waitFor()
      await page.unroute('**/data/candles/*.json')
      await page.route('**/data/candles/*.json', r => r.fulfill({ json: { ...real, as_of: null, bars: [], status: 'unavailable' } }))
      await page.reload(); await page.getByText(/暂无完整的开、高、低、收/).waitFor()
      assert.equal(await canvas().count(), 0)
    })
    assert.deepEqual(errors, [])
    assert.deepEqual(writes, [])
    fs.writeFileSync(path.join(output, 'checks.json'), JSON.stringify({ base, code, checks: results, errors, writes }, null, 2))
    console.log(`${results.length} candle browser checks passed; no uncaught errors or write requests.`)
  } finally { await browser.close() }
}
main().catch(e => { console.error(e); process.exitCode = 1 })
