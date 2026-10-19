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
  page.on('pageerror', e => errors.push(e.message))
  page.on('request', r => { if (!['GET', 'HEAD'].includes(r.method())) writes.push(r.url()) })
  let count = 0
  const check = async (name, fn) => { await fn(); count++; console.log(`PASS ${name}`) }
  const noOverflow = async () => assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
  try {
    const response = await context.request.get(new URL('data/research.json', base).href)
    assert.equal(response.status(), 200, 'Published research report must be available')
    const actual = await response.json()
    await check('real independent families load with honest pending outcomes', async () => {
      await page.goto(base + '#/lab/research')
      await page.getByRole('heading', { name: '因子研究实验室' }).waitFor()
      await page.getByRole('button', { name: `查看研究 ${actual.programs[0].id}`, exact: true }).waitFor()
      assert.equal(await page.getByRole('button', { name: /^查看研究 / }).count(), actual.programs.length)
      await noOverflow()
      await page.screenshot({ path: path.join(reports, 'research-real-desktop.png'), fullPage: true })
    })
    await check('market/status/search filters and empty result recover', async () => {
      await page.getByLabel('研究市场', { exact: true }).selectOption('HK')
      assert.equal(await page.getByRole('button', { name: /^查看研究 / }).count(), actual.programs.filter(p => p.market === 'HK').length)
      await page.getByLabel('搜索研究').fill('does-not-exist')
      await page.getByText('当前条件下没有研究实验。').waitFor()
      await page.getByLabel('搜索研究').fill('')
      await page.getByLabel('研究市场', { exact: true }).selectOption('ALL')
      await page.getByLabel('研究状态', { exact: true }).selectOption('paused')
      await page.getByText('当前条件下没有研究实验。').waitFor()
      await page.getByLabel('研究状态', { exact: true }).selectOption('ALL')
    })
    await check('historical folds stay separate and charts render real data', async () => {
      await page.getByRole('button', { name: '历史诊断', exact: true }).click()
      await page.getByRole('heading', { name: '按时间分段的测试折' }).waitFor()
      await page.locator('.recharts-rectangle').first().waitFor()
      assert.ok(await page.locator('.recharts-rectangle').count() > 0)
      await page.getByText(/不计入前瞻成绩/).first().waitFor()
      await page.screenshot({ path: path.join(reports, 'research-history-desktop.png'), fullPage: true })
    })
    await check('fixed universe and feature registry are inspectable', async () => {
      await page.getByRole('button', { name: '数据与股票池', exact: true }).click()
      await page.getByRole('heading', { name: /美股固定研究池/ }).waitFor()
      const members = actual.universes.reduce((n, u) => n + u.members.length, 0)
      assert.equal(await page.locator('main a[href*="/stock/"]').count(), members)
      await page.getByRole('button', { name: '因子库', exact: true }).click()
      await page.getByRole('heading', { name: '可研究因子与对照因子' }).waitFor()
      assert.match(await page.locator('main').innerText(), /原有乖离趋势/)
    })
    await check('proposal construction downloads exact typed JSON and persists locally', async () => {
      await page.getByRole('button', { name: '研究提案', exact: true }).click()
      await page.getByLabel('研究名称', { exact: true }).fill('量价交互研究')
      await page.getByLabel('研究假设', { exact: true }).fill('检验量能与日内修复的交互是否改善未来五日表现。')
      await page.getByLabel('组合方式').selectOption('product')
      await page.getByRole('button', { name: '保存草稿', exact: true }).click()
      const ready = page.waitForEvent('download')
      await page.getByRole('button', { name: '导出提案', exact: true }).click()
      const file = await (await ready).path()
      const proposal = JSON.parse(fs.readFileSync(file, 'utf8'))
      assert.equal(proposal.expression.op, 'product')
      assert.equal(proposal.name, '量价交互研究')
      assert.equal(proposal.parent_id, null)
      await page.reload()
      await page.getByRole('button', { name: '研究提案', exact: true }).click()
      assert.match(await page.getByLabel('提案 JSON', { exact: true }).inputValue(), /量价交互研究/)
    })
    await check('unsafe proposal JSON is blocked and valid import recovers', async () => {
      await page.getByLabel('提案 JSON', { exact: true }).fill('{"expression":{"op":"eval","code":"alert(1)"}}')
      assert.ok(await page.getByRole('button', { name: '导出提案', exact: true }).isDisabled())
      const p = actual.programs[0]
      const proposal = Object.fromEntries(['name','market','op_type','hypothesis','change','expected','expression','filters'].map(k => [k, p[k]]))
      await page.getByLabel('导入提案文件').setInputFiles({ name: 'proposal.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(proposal)) })
      await page.getByText('已导入本机草稿，尚未启动实验').waitFor()
      assert.ok(await page.getByRole('button', { name: '导出提案', exact: true }).isEnabled())
    })
    const fixture = structuredClone(actual)
    const program = fixture.programs[0]
    program.status = 'review'
    program.metrics = { due: 40, paired: 40, coverage: 1, signal_rate: 1, independent: 8, mean_delta_pp: 1.2,
      lower_delta_pp: .2, mean_return_pct: 3, mean_excess_pp: 2, stress_excess_pp: 1.7, worst_period_pct: -4,
      rank_ic: .12, pearson_ic: .1, novelty: .4 }
    program.assessments = [{ checkpoint: 40, hash: 'fixture-evidence', metrics: program.metrics, gates: { novelty: true, improvement: true } }]
    fixture.observations = Array.from({ length: 8 }, (_, i) => ({ trial_id: program.id, entry_date: 20260901 + i,
      exit_date: 20260908 + i, due: true, rank_ic: .1, pearson_ic: .1, benchmark_pct: .5,
      branch: { count: 10, complete: true, return_pct: i % 3 ? 3 : -1, holdings: [] },
      parent: { complete: true, return_pct: 1 }, pool: { complete: true, return_pct: 1 } }))
    let mode = 'fixture'
    await page.route('**/data/research.json', route => mode === 'error' ? route.fulfill({ status: 503, body: 'unavailable' })
      : route.fulfill({ json: mode === 'malformed' ? { schema_version: 1 } : fixture }))
    await check('review gate, future chart and pinned owner request work without writes', async () => {
      await page.reload()
      await page.getByRole('button', { name: '下载审核申请', exact: true }).waitFor()
      await page.locator('.recharts-rectangle').first().waitFor()
      assert.ok(await page.locator('.recharts-rectangle').count() > 0)
      const ready = page.waitForEvent('download')
      await page.getByRole('button', { name: '下载审核申请', exact: true }).click()
      const request = JSON.parse(fs.readFileSync(await (await ready).path(), 'utf8'))
      assert.equal(request.program_id, program.id)
      assert.equal(request.evidence_hash, 'fixture-evidence')
      await page.screenshot({ path: path.join(reports, 'research-review-desktop.png'), fullPage: true })
    })
    for (const width of [768, 390, 320]) await check(`responsive research views at ${width}px`, async () => {
      await page.setViewportSize({ width, height: 900 })
      await noOverflow()
      assert.ok((await page.getByLabel('搜索研究').boundingBox()).width >= 150)
      await page.screenshot({ path: path.join(reports, `research-mobile-${width}.png`), fullPage: true })
      for (const tab of ['研究提案', '数据与股票池', '因子库', '研究实验']) {
        await page.getByRole('button', { name: tab, exact: true }).click()
        await noOverflow()
      }
    })
    await check('HTTP and malformed report errors remain recoverable', async () => {
      mode = 'error'; await page.reload(); await page.getByRole('alert').waitFor()
      mode = 'fixture'; await page.getByRole('button', { name: '重试', exact: true }).click()
      await page.getByRole('button', { name: '下载审核申请', exact: true }).waitFor()
      mode = 'malformed'; await page.reload(); await page.getByText('因子研究数据不完整').waitFor()
      mode = 'fixture'; await page.getByRole('button', { name: '重试', exact: true }).click()
      await page.getByRole('button', { name: '下载审核申请', exact: true }).waitFor()
    })
    assert.deepEqual(errors, [])
    assert.deepEqual(writes, [])
    console.log(`${count} research browser checks passed; no uncaught errors or write requests.`)
  } finally { await browser.close() }
}
main().catch(error => { console.error(error); process.exitCode = 1 })
