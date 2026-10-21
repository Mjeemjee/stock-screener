const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright')

async function main() {
  const base = process.argv[2] || 'http://127.0.0.1:5175/'
  const browser = await chromium.launch({ channel: 'msedge', headless: true })
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
  const page = await context.newPage()
  const errors = [], writes = []
  page.on('pageerror', e => errors.push(e.message))
  page.on('request', r => { if (!['GET', 'HEAD'].includes(r.method())) writes.push(r.url()) })
  let count = 0
  const check = async (name, fn) => { await fn(); count++; console.log('PASS', name) }
  const fit = async () => assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
  const choose = async market => page.getByRole('group', { name: '长期研究市场' }).getByRole('button', { name: market === 'US' ? '美股' : '港股', exact: true }).click()
  try {
    const response = await context.request.get(new URL('data/long_research.json', base).href)
    assert.equal(response.status(), 200)
    const actual = await response.json()
    await check('real fixed long-horizon study loads with honest pending evidence', async () => {
      await page.goto(base + '#/lab/long-horizon')
      await page.getByRole('heading', { name: '流动性与长期动量', exact: true }).waitFor()
      await page.getByRole('heading', { name: '真实创建后的独立研究期', exact: true }).waitFor()
      await fit()
      await page.screenshot({ path: path.resolve(__dirname, '../../reports/long-forward-desktop.png'), fullPage: true })
    })
    await check('market filter and complete frozen-cohort download work', async () => {
      const market = actual.cohorts[0]?.market || 'HK'
      await choose(market)
      const rows = actual.cohorts.filter(r => r.market === market)
      if (rows.length) {
        const ready = page.waitForEvent('download')
        await page.getByRole('button', { name: '导出研究期', exact: true }).click()
        assert.deepEqual(JSON.parse(fs.readFileSync(await (await ready).path(), 'utf8')), rows)
      } else assert.ok(await page.getByRole('button', { name: '导出研究期', exact: true }).isDisabled())
      await choose('US'); await choose('HK')
    })
    await check('retrospective results, three controls and nonblank chart remain separate', async () => {
      await page.getByRole('button', { name: '历史诊断', exact: true }).click()
      await page.getByRole('heading', { name: '修正口径后的历史回放', exact: true }).waitFor()
      assert.equal(await page.locator('tbody tr').count(), 3)
      await page.locator('.recharts-rectangle').first().waitFor()
      assert.equal(await page.locator('.recharts-rectangle').count(), 3)
      await page.getByText(/历史数字不计入前瞻进度/).waitFor()
      await page.screenshot({ path: path.resolve(__dirname, '../../reports/long-history-desktop.png'), fullPage: true })
    })
    await check('fixed six/twelve/twenty-four period checkpoints and limitations are visible', async () => {
      await page.getByRole('button', { name: '验证进度', exact: true }).click()
      for (const n of [6, 12, 24]) await page.getByText(new RegExp(`^${n} 期 ·`)).waitFor()
      await page.getByText(/样本数量达标仍不保证有效/).waitFor()
    })
    for (const width of [768, 390, 320]) await check(`long research fits ${width}px in every view`, async () => {
      await page.setViewportSize({ width, height: 900 })
      for (const tab of ['前瞻记录', '历史诊断', '验证进度']) {
        await page.getByRole('button', { name: tab, exact: true }).click()
        await fit()
      }
      await page.getByRole('button', { name: '历史诊断', exact: true }).click()
      await page.screenshot({ path: path.resolve(__dirname, `../../reports/long-mobile-${width}.png`), fullPage: true })
    })
    let mode = 'error'
    await page.route('**/data/long_research.json', route => mode === 'error' ? route.fulfill({ status: 503, body: 'unavailable' })
      : route.fulfill({ json: mode === 'malformed' ? { schema_version: 1 } : actual }))
    await check('HTTP and malformed-report errors recover without page exceptions', async () => {
      await page.reload(); await page.getByRole('alert').waitFor()
      mode = 'malformed'; await page.getByRole('button', { name: '重试', exact: true }).click()
      await page.getByText('长期研究数据不完整').waitFor()
      mode = 'actual'; await page.getByRole('button', { name: '重试', exact: true }).click()
      await page.getByRole('heading', { name: '真实创建后的独立研究期', exact: true }).waitFor()
    })
    assert.deepEqual(errors, []); assert.deepEqual(writes, [])
    console.log(`${count} long-horizon browser checks passed.`)
  } finally { await browser.close() }
}
main().catch(e => { console.error(e); process.exitCode = 1 })
