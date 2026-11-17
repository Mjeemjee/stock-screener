export const money = value => typeof value === 'number' && Number.isFinite(value)
  ? `${value > 0 ? '+' : ''}${new Intl.NumberFormat('zh-HK', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value)}` : '待验收'
export const freshness = (updatedAt, minutes = 15, now = Date.now()) => {
  const stamp = Date.parse(updatedAt), age = now - stamp
  if (!Number.isFinite(stamp) || age < -60000) return 'unknown'
  return age <= minutes * 60000 ? 'fresh' : 'stale'
}
export function validateSnapshot(value) {
  if (!value || value.schema_version !== 1 || !Array.isArray(value.cards) || !Array.isArray(value.registry) ||
      !Array.isArray(value.stages) || value.stages.length !== 6 || !value.activity || !value.paper || !Array.isArray(value.paper.accounts)) {
    throw new Error('研究快照格式不完整，请稍后刷新。')
  }
  for (const card of value.cards) {
    if (typeof card.name !== 'string' || !Number.isFinite(card.capital_hkd) || card.capital_hkd <= 0 || !Array.isArray(card.results) || card.results.length !== 2) throw new Error('账户口径缺失，暂不展示收益。')
    if (new Set(card.results.map(r => r.cost)).size !== 2) throw new Error('两档成本需要分别列示。')
    for (const row of card.results) {
      if (!['base', 'pressure'].includes(row.cost) || ![row.net_hkd, row.risk_pct, row.cagr_pct].every(v => v === null || typeof v === 'number' && Number.isFinite(v))) throw new Error('收益字段无效，暂不展示数字。')
      const optional = [row.closed_net_hkd, row.open_contribution_hkd]
      if (!optional.every(v => v === undefined || v === null || typeof v === 'number' && Number.isFinite(v)) ||
          row.open_quantity !== undefined && row.open_quantity !== null && (!Number.isSafeInteger(row.open_quantity) || row.open_quantity < 0)) throw new Error('持仓拆分字段无效，暂不展示数字。')
      if (['pending', 'unknown'].includes(card.status) && [row.net_hkd, row.risk_pct, row.cagr_pct, ...optional, row.open_quantity].some(v => v !== undefined && v !== null)) throw new Error('待验收或不可评估记录不能展示收益结论。')
    }
  }
  if (value.ipo_observation) {
    const o=value.ipo_observation
    if (!Number.isSafeInteger(o.count) || o.count<=0 || ![o.up_count,o.broken_count,o.flat_count,o.one_member_max_up_count].every(n=>Number.isSafeInteger(n)&&n>=0&&n<=o.count) ||
        o.up_count+o.broken_count+o.flat_count!==o.count || o.one_member_max_up_count<o.up_count || o.one_member_max_up_count>Math.min(o.count,o.up_count+1) || !Number.isFinite(o.median_pct) || o.median_pct < -100 ||
        !Number.isFinite(Date.parse(o.observed_at_hkt)) || o.observed_proxy_only!==true || o.not_an_account_win_rate!==true || o.paper_decision_registered!==false) throw new Error('IPO样本观察口径不完整，暂不展示指标。')
  }
  return value
}

if (typeof document !== 'undefined') {
  const find = id => document.getElementById(id)
  const element = (tag, value, className) => {
    const node = document.createElement(tag)
    if (value !== undefined) node.textContent = String(value)
    if (className) node.className = className
    return node
  }
  const dateText = value => {
    const date = new Date(value)
    if (!Number.isFinite(date.getTime())) return '时间未知'
    return new Intl.DateTimeFormat('zh-HK', { timeZone: 'Asia/Hong_Kong', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(date)
  }
  let snapshot = null, failed = false, inflight = false, selectedEvidenceView = null
  function selectEvidenceView(key) {
    selectedEvidenceView = key
    for (const tab of ['history', 'paper']) { find(`${tab}-view`).hidden = tab !== key; find(`${tab}-tab`).setAttribute('aria-pressed', String(tab === key)) }
  }
  function updateFreshness() {
    if (!snapshot) return
    const state = freshness(snapshot.updated_at, snapshot.activity.fresh_for_minutes)
    const active = !failed && state === 'fresh' && snapshot.activity.active_at_snapshot
    document.body.classList.toggle('is-active', active)
    if (failed) return
    find('notice').classList.toggle('fresh', state === 'fresh')
    find('notice').textContent = state === 'fresh'
      ? `这是最近同步的研究快照。行情覆盖到 ${snapshot.market_data_through}，收益所属期间见各账户说明。`
      : state === 'stale' ? '快照已超过15分钟。活动动画已停止，当前显示上次同步结论；点击刷新读取新快照。'
        : '同步时间暂无法确认。活动动画已停止，历史结论仍按原期间显示。'
    find('activity-tag').textContent = active ? '同步时进行中' : state === 'fresh' ? '阶段快照' : '上次同步阶段'
  }
  function renderCards(data) {
    find('cards').replaceChildren()
    for (const card of data.cards) {
      const article = element('article', undefined, 'study')
      const head = element('div', undefined, 'study-head')
      head.append(element('h3', card.name), element('span', card.status_label, `badge ${card.status}`))
      article.append(head, element('p', `${new Intl.NumberFormat('zh-HK').format(card.capital_hkd)} 港币假设账户 · ${card.period}\n${card.basis}`, 'basis'))
      for (const result of card.results) {
        const row = element('div', undefined, 'result-row'), detail = element('div')
        row.append(element('span', result.cost === 'base' ? '基础' : '压力', 'cost-label'))
        const tone = result.net_hkd === null ? '' : result.net_hkd >= 0 ? 'positive' : 'negative'
        detail.append(element('span', card.status === 'unknown' ? '无法评估' : money(result.net_hkd), `money ${tone}`))
        if (result.risk_pct !== null) detail.append(element('span', `报价回撤代理 ${result.risk_pct.toFixed(2)}%`, 'risk'))
        if (result.cagr_pct !== null) detail.append(element('span', `历史日历复合年化 ${result.cagr_pct.toFixed(2)}%`, 'risk'))
        if (typeof result.closed_net_hkd === 'number') detail.append(element('span', `已闭合 ${money(result.closed_net_hkd)}`, 'risk'))
        if (typeof result.open_contribution_hkd === 'number') detail.append(element('span', `开放贡献 ${money(result.open_contribution_hkd)} · ${result.open_quantity}份`, 'risk'))
        row.append(detail); article.append(row)
      }
      article.append(element('p', card.conclusion), element('p', card.next, 'next'))
      find('cards').append(article)
    }
  }
  function renderRecords() {
    if (!snapshot) return
    const term = find('search').value.trim().toLowerCase(), scope = find('scope').value
    const records = snapshot.registry.filter(row => (scope === 'all' || scope === row.category) && `${row.version} ${row.name} ${row.conclusion}`.toLowerCase().includes(term))
    find('record-count').textContent = `${records.length} 条记录`
    find('record-list').replaceChildren()
    if (!records.length) find('record-list').append(element('p', '没有匹配的记录。试试其他标的或版本。', 'caption'))
    for (const row of records) {
      const detail = element('details', undefined, 'record'), summary = element('summary')
      summary.append(element('span', row.version, 'version'), element('span', row.name, 'name'))
      detail.append(summary, element('p', row.conclusion), element('p', `${row.source} · ${row.source_date}`, 'source'))
      find('record-list').append(detail)
    }
  }
  function renderPaper(data) {
    const names = { 'monthly-only-base': '月度复核 · 基础', 'monthly-only-pressure': '月度复核 · 压力', 'three-month-base': '三月退出 · 基础', 'three-month-pressure': '三月退出 · 压力' }
    find('paper-note').textContent = `${data.paper.note} 起点：${dateText(data.paper.activation_utc)} HKT；状态核对：${dateText(data.paper.checked_at)} HKT。研究系统下单数 ${data.paper.orders_sent}。`
    find('paper-rows').replaceChildren()
    for (const account of data.paper.accounts) {
      const row = element('tr')
      for (const value of [names[account.id] ?? account.id, money(account.nav_hkd).replace(/^\+/, ''), money(account.change_hkd), account.quantity, account.closed_rounds]) row.append(element('td', value))
      find('paper-rows').append(row)
    }
  }
  function render(data) {
    snapshot = data
    find('updated').textContent = `最近同步 ${dateText(data.updated_at)} HKT`
    find('focus-title').textContent = data.activity.focus
    find('activity-text').textContent = data.activity.text
    const observation=data.activity.focus.startsWith('IPO') ? data.ipo_observation : null
    find('ipo-observation').hidden=!observation
    if (observation) {
      find('ipo-median').textContent=`${observation.median_pct.toFixed(2)}%`
      find('ipo-up').textContent=`${observation.up_count}/${observation.count}`
      find('ipo-broken').textContent=`${observation.broken_count}/${observation.count}`
      find('ipo-observation-note').textContent=`观测于 ${dateText(observation.observed_at_hkt)} HKT。当前资料内的10只，不是账户胜率或中签率。03275成员仍未证；增加这一项最多${observation.one_member_max_up_count}/10上涨，仍未满足严格多数。正式申购决定尚未登记。`
    }
    find('stages').replaceChildren()
    const names = { done: '已完成', active: '同步时进行中', pending: '尚未开始', not_opened: '按规则未打开', unknown: '资料不足' }
    for (const stage of data.stages) {
      const item = element('li', stage.name, `stage ${stage.status}`)
      item.append(element('small', names[stage.status] ?? stage.status)); find('stages').append(item)
    }
    renderCards(data); renderPaper(data); renderRecords()
    if (selectedEvidenceView === null) selectEvidenceView(data.default_evidence_view === 'paper' ? 'paper' : 'history')
    find('research-note').textContent = data.research_note
    find('baseline-note').textContent = `同为3万初始资金，基础成本月度版历史标记 ${money(data.baseline.monthly_base_net_hkd)} 港元，报价回撤约 ${data.baseline.monthly_base_risk_pct.toFixed(2)}%；被动参考 ${money(data.baseline.passive_base_net_hkd)} 港元、约 ${data.baseline.passive_base_risk_pct.toFixed(2)}%。未证明稳定独立超额收益。`
    find('factor-note').textContent = `早期因子目录有 ${data.factor_archive.count} 条记录，快照日期 ${data.factor_archive.source_date}。${data.factor_archive.note}`
    for (const id of ['activity', 'results-section', 'evidence-section', 'records']) find(id).hidden = false
    updateFreshness()
  }
  async function refresh() {
    if (inflight) return
    inflight = true; find('refresh').disabled = true
    try {
      const response = await fetch(new URL(`progress.json?t=${Date.now()}`, import.meta.url), { cache: 'no-store' })
      if (!response.ok) throw new Error(`快照读取失败（${response.status}），请点击刷新重试。`)
      const data = validateSnapshot(await response.json())
      failed = false; render(data)
    } catch (error) {
      failed = true; document.body.classList.remove('is-active'); find('notice').classList.remove('fresh')
      find('notice').textContent = `${error instanceof Error ? error.message : '读取失败，请刷新重试。'}${snapshot ? ' 保留上次同步内容。' : ''}`
    } finally { inflight = false; find('refresh').disabled = false }
  }
  find('refresh').addEventListener('click', refresh)
  find('search').addEventListener('input', renderRecords)
  find('scope').addEventListener('change', renderRecords)
  for (const key of ['history', 'paper']) find(`${key}-tab`).addEventListener('click', () => selectEvidenceView(key))
  setInterval(updateFreshness, 10000)
  setInterval(() => { if (document.visibilityState === 'visible') refresh() }, 60000)
  refresh()
}
