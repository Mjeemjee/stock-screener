const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright')

async function main() {
  const base = process.argv[2] || 'http://127.0.0.1:5177/'
  const reports = path.resolve(__dirname, '../../reports')
  const browser = await chromium.launch({ channel: 'msedge', headless: true })
  const context = await browser.newContext({ viewport: { width: 1440, height: 1100 } })
  const page = await context.newPage()
  const errors = [], requests = [], passed = []
  page.on('pageerror', error => errors.push(error.message))
  page.on('request', request => requests.push(request.url()))
  async function check(name, fn) { await fn(); passed.push(name); console.log(`PASS ${name}`) }
  async function noOverflow() { assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true) }
  const go = route => page.goto(base + '#' + route)
  try {
    await go('/methods')
    await page.getByRole('textbox', { name: '搜索人物或投资方法' }).waitFor()
    await check('six methods, no historical-price preload', async () => {
      assert.equal(await page.getByTestId('method-card').count(), 6)
      assert.ok(!requests.some(url => /data\/history\//.test(url)))
      await noOverflow()
      await page.screenshot({ path: path.join(reports, 'methods-desktop-20261017.png'), fullPage: true })
    })
    await check('search and capability conjunction, then clear', async () => {
      await page.getByRole('textbox', { name: '搜索人物或投资方法' }).fill('巴菲特')
      assert.equal(await page.getByTestId('method-card').count(), 1)
      await page.getByLabel('工具能力').selectOption('backtest')
      await page.getByText('没有符合当前条件的方法，请调整或清除筛选。').waitFor()
      await page.getByRole('button', { name: '清除筛选' }).click()
      assert.equal(await page.getByTestId('method-card').count(), 6)
    })
    for (const width of [390, 320]) {
      await check(`method directory responsive at ${width}`, async () => {
        await page.setViewportSize({ width, height: 900 })
        await noOverflow()
        await page.screenshot({ path: path.join(reports, `methods-mobile-${width}-20261017.png`), fullPage: true })
      })
    }
    for (const id of ['buffett-quality-value', 'graham-defensive', 'lynch-garp', 'greenblatt-magic-formula', 'oneil-canslim', 'turtle-breakout-adapted']) {
      await check(`method detail direct load and truthful tools: ${id}`, async () => {
        await go('/methods/' + id)
        await page.getByTestId('method-detail').waitFor()
        await noOverflow()
        assert.equal(await page.getByRole('link', { name: '回测简化版', exact: true }).count(), id === 'turtle-breakout-adapted' ? 1 : 0)
        const links = await page.locator('[data-testid="method-detail"] a[target="_blank"]').evaluateAll(nodes => nodes.map(node => node.href))
        assert.ok(links.length > 0 && links.every(url => url.startsWith('https://')))
        await page.getByText('暂无绑定的选股策略，不借用其他策略名单。').waitFor()
      })
    }
    await check('method preset opens a single executable module and runs', async () => {
      await page.getByRole('link', { name: '回测简化版', exact: true }).click()
      await page.getByTestId('method-backtest-context').waitFor()
      await page.waitForFunction(() => [...document.querySelectorAll('button')].some(b => b.textContent.includes('运行回测（1 块）') && !b.disabled))
      await page.getByRole('button', { name: '运行回测（1 块）', exact: true }).click()
      await page.getByText('交易次数', { exact: true }).waitFor()
      await noOverflow()
    })
    await check('changing preset becomes a custom configuration', async () => {
      const numeric = page.locator('input[type="number"]').first()
      const original = Number(await numeric.inputValue())
      await numeric.fill(String(original + 5))
      await numeric.blur()
      await page.getByTestId('method-backtest-context').getByText(/自定义配置/).waitFor()
    })
    await check('invalid deep link cannot silently run the default strategy', async () => {
      await go('/backtest?method=unknown')
      await page.getByRole('alert').filter({ hasText: '未找到该投资方法' }).waitFor()
      const buttons = page.getByRole('button', { name: /运行回测|数据加载中/ })
      for (const button of await buttons.all()) assert.equal(await button.isDisabled(), true)
    })
    await page.setViewportSize({ width: 1440, height: 1100 })
    await go('/')
    await page.getByRole('textbox', { name: '搜索代码或名称' }).waitFor()
    const response = await context.request.get(base + 'data/screener_results.json')
    const feed = await response.json()
    const value = feed.strategies.find(s => s.meta.id === 'value_dividend_hk')
    await check('actual free HK results and CSV use their declared market-cap basis', async () => {
      assert.ok(value && value.hits.length > 0)
      await page.getByRole('tab', { name: /低估值高股息/ }).click()
      assert.equal(await page.locator('tbody tr:visible').count(), value.hits.length)
      assert.ok(value.hits.every(h => h.code.startsWith('HK.') && h.market_cap_basis === 'hk_listed'))
      const downloadReady = page.waitForEvent('download')
      await page.getByRole('button', { name: '导出当前结果 CSV' }).click()
      const csv = fs.readFileSync(await (await downloadReady).path(), 'utf8')
      assert.ok(csv.includes('"hk_listed"') && csv.includes('"Eastmoney HK F10"'))
      await noOverflow()
      await page.screenshot({ path: path.join(reports, 'free-value-desktop-20261017.png'), fullPage: true })
    })
    for (const width of [390, 320]) {
      await check(`actual value results responsive at ${width}`, async () => {
        await page.setViewportSize({ width, height: 900 })
        await noOverflow()
        await page.getByText('免费云端港股数据，观察中。', { exact: false }).first().waitFor()
        await page.screenshot({ path: path.join(reports, `free-value-mobile-${width}-20261017.png`), fullPage: true })
      })
    }
    await check('source failure is unavailable rather than a zero-match claim', async () => {
      const failed = structuredClone(feed)
      const strategy = failed.strategies.find(s => s.meta.id === 'value_dividend_hk')
      strategy.hits = []
      Object.assign(strategy.meta, { hit_count: 0, displayed_count: 0, execution_status: 'unavailable', data_note: '财务数据源暂不可用，稍后重试。' })
      await page.route('**/data/screener_results.json', route => route.fulfill({ json: failed }))
      await page.reload()
      await page.getByRole('tab', { name: /低估值高股息/ }).click()
      await page.getByText('财务数据源暂不可用，稍后重试。', { exact: true }).waitFor()
      assert.equal(await page.getByText('本期策略没有命中标的。', { exact: true }).count(), 0)
      await page.unroute('**/data/screener_results.json')
    })
    assert.deepEqual(errors, [])
    fs.writeFileSync(path.join(reports, 'free-value-methods-browser-20261017.json'), JSON.stringify({ passed, checks: passed.length, page_errors: errors }, null, 2))
    console.log(`PASS ${passed.length} browser checks, no page errors`)
  } finally { await browser.close() }
}
main().catch(error => { console.error(error); process.exitCode = 1 })
