/* Run against the local dev server; PLAYWRIGHT_MODULE can point to a bundled runtime. */
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright')

async function main() {
  const url = process.argv[2] || 'http://127.0.0.1:5173/'
  const reports = path.resolve(__dirname, '../../reports')
  const browser = await chromium.launch({ channel: 'msedge', headless: true })
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
  const page = await context.newPage()
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  let checks = 0
  async function check(name, action) {
    await action()
    checks++
    console.log(`PASS ${name}`)
  }
  async function loaded() {
    await page.getByRole('textbox', { name: '搜索代码或名称' }).waitFor()
  }
  async function noOverflow() {
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true)
  }
  try {
    const response = await context.request.get(new URL('data/screener_results.json', url).href)
    assert.equal(response.status(), 200)
    const real = await response.json()
    const first = real.strategies.find(s => s.meta.status !== 'paused' && s.hits.length)
    const searchHit = first.hits.find(hit => first.hits.filter(other =>
      other.code.toLowerCase().includes(hit.code.toLowerCase()) ||
      other.name.toLowerCase().includes(hit.code.toLowerCase())).length === 1)
    assert.ok(searchHit, 'A unique search target is required')
    await page.goto(url)
    await loaded()
    await check('desktop render and first-screen results', async () => {
      await noOverflow()
      assert.ok(await page.locator('tbody tr:visible').count() > 0)
      await page.screenshot({ path: path.join(reports, 'screener-desktop.png') })
    })
    await check('search, clear, market filter and CSV export', async () => {
      await page.getByRole('textbox', { name: '搜索代码或名称' }).fill(searchHit.code)
      assert.equal(await page.locator('tbody tr:visible').count(), 1)
      const downloadReady = page.waitForEvent('download')
      await page.getByRole('button', { name: '导出当前结果 CSV' }).click()
      const download = await downloadReady
      const csv = fs.readFileSync(await download.path(), 'utf8')
      assert.ok(csv.includes(searchHit.code))
      assert.equal(csv.trim().split('\r\n').length, 2)
      await page.getByRole('button', { name: '清空搜索' }).click()
      await page.getByRole('button', { name: '港股', exact: true }).click()
      const rows = await page.locator('tbody tr:visible').allTextContents()
      assert.equal(rows.length, first.hits.filter(hit => hit.code.startsWith('HK.')).length)
      assert.ok(rows.every(row => row.includes('HK.') && !row.includes('US.')))
      await page.getByRole('button', { name: '全部', exact: true }).click()
    })
    await check('empty search disables export', async () => {
      await page.getByRole('textbox', { name: '搜索代码或名称' }).fill('NO_MATCH_93847234')
      await page.getByText('没有符合当前条件的标的。', { exact: true }).waitFor()
      assert.equal(await page.getByRole('button', { name: '导出当前结果 CSV' }).isDisabled(), true)
      await page.getByRole('button', { name: '清空搜索' }).click()
    })
    for (const width of [390, 320]) {
      await check(`mobile ${width}px layout and navigation`, async () => {
        await page.setViewportSize({ width, height: 844 })
        await noOverflow()
        assert.ok(await page.locator('article:visible').count() > 0)
        assert.equal(await page.getByRole('link', { name: '回测', exact: true }).isVisible(), true)
        const title = page.getByRole('heading', { name: '港美股选股台', exact: true })
        assert.equal(await title.evaluate(node => node.scrollWidth <= node.clientWidth), true)
        await page.screenshot({ path: path.join(reports, `screener-mobile-${width}.png`) })
      })
    }
    await page.setViewportSize({ width: 1440, height: 1000 })
    const fixture = structuredClone(real)
    fixture.generated_at = '2026-10-01T00:00:00+00:00'
    fixture.factor_rank = { applied: true, scope: 'US momentum_breakout', candidates: 3, ranked: 2, failures: 1, coverage: 2 / 3 }
    fixture.strategies = [{ ...first, meta: { ...first.meta, hit_count: 3 }, hits: [
      { ...first.hits[0], code: 'US.EMPTY', name: 'Empty score', factor_score: null, factor_rank: null, factor_status: 'history_unavailable' },
      { ...first.hits[0], code: 'US.LOW', name: 'Low score', factor_score: -1, factor_rank: 2 },
      { ...first.hits[0], code: 'US.HIGH', name: 'High score', factor_score: 2, factor_rank: 1 },
    ] }]
    let mode = 'valid'
    await page.route('**/data/screener_results.json', route => mode === 'error'
      ? route.fulfill({ status: 503, body: 'unavailable' })
      : route.fulfill({ json: mode === 'malformed' ? { strategies: [{}] } : fixture }))
    await check('sorting missing scores last in both directions and stale scan warning', async () => {
      await page.reload()
      await loaded()
      await page.getByText('扫描已超过 72 小时', { exact: false }).waitFor()
      await page.getByRole('combobox', { name: '排序字段' }).selectOption('factor_score')
      let rows = await page.locator('tbody tr:visible').allTextContents()
      assert.ok(rows[0].includes('US.HIGH') && rows[2].includes('US.EMPTY'))
      await page.getByRole('button', { name: '当前降序，切换升序' }).click()
      rows = await page.locator('tbody tr:visible').allTextContents()
      assert.ok(rows[0].includes('US.LOW') && rows[2].includes('US.EMPTY'))
    })
    await check('HTTP failure retry restores results', async () => {
      mode = 'error'
      await page.reload()
      await page.getByRole('alert').waitFor()
      mode = 'valid'
      await page.getByRole('button', { name: '重试', exact: true }).click()
      await loaded()
      assert.equal(await page.getByRole('alert').count(), 0)
    })
    await check('malformed feed is a recoverable error', async () => {
      mode = 'malformed'
      await page.reload()
      await page.getByRole('alert').waitFor()
      assert.ok((await page.getByRole('alert').textContent()).includes('数据格式不完整'))
      mode = 'valid'
      await page.getByRole('button', { name: '重试', exact: true }).click()
      await loaded()
    })
    await check('lazy route navigation and return', async () => {
      await page.getByRole('link', { name: '指南', exact: true }).click()
      await page.getByRole('link', { name: '选股', exact: true }).waitFor()
      await page.getByRole('link', { name: '选股', exact: true }).click()
      await loaded()
    })
    await check('backtest route lazy-loads successfully', async () => {
      await page.getByRole('link', { name: '回测', exact: true }).click()
      await page.getByRole('heading', { name: '策略回测实验室', exact: true }).waitFor()
      await page.getByRole('link', { name: '选股', exact: true }).click()
      await loaded()
    })
    await check('unavailable strategy is distinguished from zero matches', async () => {
      fixture.strategies[0].meta.execution_status = 'unavailable'
      fixture.strategies[0].meta.data_note = '缺少股息率数据，暂时无法执行筛选。'
      fixture.strategies[0].meta.hit_count = 0
      fixture.strategies[0].hits = []
      await page.reload()
      await page.getByText('缺少股息率数据，暂时无法执行筛选。', { exact: true }).waitFor()
      assert.equal(await page.getByRole('button', { name: '导出当前结果 CSV' }).isDisabled(), true)
    })
    assert.deepEqual(errors, [])
    console.log(`${checks} browser checks passed; no uncaught page errors.`)
  } finally {
    await browser.close()
  }
}

main().catch(error => { console.error(error); process.exitCode = 1 })
