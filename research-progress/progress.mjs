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
  if (['done', 'waiting'].includes(value.activity.status) && value.activity.active_at_snapshot) throw new Error('已交付或等待阶段不能显示进行中动画。')
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
  if (value.factor_research) {
    const f = value.factor_research
    if (f.unique_new_signals !== 3 || f.planned_horizon_trials !== 6 || f.new_net_account_candidates !== 0 ||
        !Array.isArray(f.items) || f.items.length !== 3 || new Set(f.items.map(i => i.id)).size !== 3 ||
        f.items.reduce((n, i) => n + (i.horizons?.length ?? 0), 0) !== 6) throw new Error('新因子与预定期限计数不完整。')
    for (const item of f.items) {
      if (!['clue', 'rejected', 'source_blocked'].includes(item.status) || !Array.isArray(item.diagnostics) || !item.diagnostics.length ||
          item.account_net_hkd !== null || item.account_max_drawdown_pct !== null) throw new Error('新信号尚无已验净账户，不能展示账户收益。')
      for (const d of item.diagnostics) {
        if (!item.horizons.includes(d.horizon) || ![d.rank_ic, d.hac_t, d.p_value, d.top_excess_bp].every(Number.isFinite) ||
            Math.abs(d.rank_ic) > 1 || d.p_value < 0 || d.p_value > 1) throw new Error('因子诊断单位或期限无效。')
      }
    }
  }
  if (value.sgov_history) {
    const h = value.sgov_history
    if (JSON.stringify(h.approved_capital_hkd) !== '[20000,30000]' || JSON.stringify(h.excluded_capital_hkd) !== '[10000]' ||
        !Array.isArray(h.cases) || h.cases.length !== 18 || new Set(h.cases.map(c => `${c.stage}-${c.capital_hkd}-${c.cost}`)).size !== 18) throw new Error('SGOV历史本金与情景不完整。')
    for (const c of h.cases) {
      if (!['A', 'B', 'C'].includes(c.stage) || ![10000, 20000, 30000].includes(c.capital_hkd) ||
          !['base', 'pressure'].includes(c.cost) || ![c.net_hkd, c.risk_pct].every(Number.isFinite) || c.risk_pct < 0) throw new Error('SGOV历史条件账户无效。')
    }
  }
  if (value.sgov_paper) {
    const p = value.sgov_paper
    if (typeof p.activated !== 'boolean' || p.orders_sent !== 0 || !Array.isArray(p.accounts)) throw new Error('SGOV纸面状态不完整。')
    if (!p.activated && (p.accounts.length || p.activation_utc !== null || p.first_session !== null)) throw new Error('SGOV未激活时不能出现起点或前向收益。')
    if (p.activated) {
      if (!Number.isFinite(Date.parse(p.source_quote_through)) || !Number.isFinite(Date.parse(p.checked_at))) throw new Error('SGOV纸面源日期或核对时间无效。')
      if (!Number.isFinite(Date.parse(p.activation_utc)) || !Number.isFinite(Date.parse(p.first_session)) || p.accounts.length !== 4 ||
          new Set(p.accounts.map(a => `${a.capital_hkd}-${a.cost}`)).size !== 4) throw new Error('SGOV纸面必须保留四个独立本金成本账户。')
      for (const a of p.accounts) {
        if (![20000, 30000].includes(a.capital_hkd) || !['base', 'pressure'].includes(a.cost) ||
            ![a.nav_hkd, a.change_hkd].every(v => v === null || Number.isFinite(v)) ||
            ![a.quantity, a.observations].every(v => Number.isSafeInteger(v) && v >= 0) ||
            a.status !== 'ACTIVE' && [a.nav_hkd, a.change_hkd].some(v => v !== null)) throw new Error('SGOV纸面资金或未知状态的收益无效。')
      }
    }
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
      ? `这是最近同步的研究快照。03086纸面行情核对至 ${snapshot.market_data_through}；其他因子与历史账户按各自期间显示。`
      : state === 'stale' ? '快照已超过15分钟。活动动画已停止，当前显示上次同步结论；点击刷新读取新快照。'
        : '同步时间暂无法确认。活动动画已停止，历史结论仍按原期间显示。'
    find('activity-tag').textContent = active ? '同步时进行中' : state === 'fresh' ? '阶段快照' : '上次同步阶段'
  }
  function renderWork(data) {
    find('work-owners').replaceChildren()
    for (const owner of data.current_work?.owners ?? []) {
      const item = element('li')
      item.append(element('strong', owner.name), element('p', owner.task))
      find('work-owners').append(item)
    }
    find('work-note').textContent = data.current_work?.note ?? ''
  }
  function renderFactors(data) {
    const research = data.factor_research
    find('factor-section').hidden = !research
    if (!research) return
    find('factor-summary').textContent = `${research.scope} ${research.note}`
    find('factor-limits').textContent = research.limitations
    find('archive-link').textContent = `查看旧目录 ${data.factor_archive.count} 条 · ${data.factor_archive.source_date}`
    find('factor-list').replaceChildren()
    for (const factor of research.items) {
      const article = element('article', undefined, 'factor-study')
      const head = element('div', undefined, 'study-head')
      head.append(element('h3', factor.name), element('span', factor.status_label, `badge ${factor.status === 'rejected' ? 'closed' : 'review'}`))
      article.append(head, element('code', factor.formula, 'factor-formula'), element('p', factor.conclusion))
      const diagnostics = element('div', undefined, 'diagnostics')
      for (const row of factor.diagnostics) {
        const group = element('div', undefined, 'diagnostic'), period = element('div', undefined, 'diagnostic-period')
        period.append(element('strong', `${row.horizon}日 · ${row.split}`), element('span', row.period))
        const stats = element('dl')
        for (const [name, value] of [['RankIC', row.rank_ic.toFixed(5)], ['HAC t', row.hac_t.toFixed(3)], [row.p_label, row.p_value.toFixed(5)]]) {
          const item = element('div'); item.append(element('dt', name), element('dd', value)); stats.append(item)
        }
        group.append(period, stats); diagnostics.append(group)
      }
      article.append(diagnostics, element('p', factor.limitation, 'caption'),
        element('p', '1万／2万／3万的可执行账户净利、账户回撤与资金适配：尚未验证。', 'caption'), element('p', factor.next, 'next'))
      find('factor-list').append(article)
    }
  }
  function renderSgovHistory(data) {
    const history = data.sgov_history
    find('sgov-history').hidden = !history
    if (!history) return
    find('sgov-history-note').textContent = `${history.rule ?? ''} ${history.note} ${history.comparison}`
    find('sgov-history-limits').textContent = history.limitations
    find('sgov-history-rows').replaceChildren()
    for (const stage of ['A', 'B', 'C']) for (const capital of [10000, 20000, 30000]) {
      const select = cost => history.cases.find(c => c.stage === stage && c.capital_hkd === capital && c.cost === cost)
      const base = select('base'), pressure = select('pressure'), row = element('tr')
      for (const value of [`${stage} · ${base.start.slice(0, 4)}—${base.end.slice(0, 4)}`, capital.toLocaleString('zh-HK'),
        money(base.net_hkd), money(pressure.net_hkd), `${pressure.risk_pct.toFixed(2)}%`, history.approved_capital_hkd.includes(capital) ? '可续条件纸面' : '不采用此本金']) row.append(element('td', value))
      find('sgov-history-rows').append(row)
    }
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
    const records = snapshot.registry.filter(row => (scope === 'all' || scope === row.category) && `${row.version} ${row.name} ${row.conclusion} ${row.id} ${row.definition ?? ''} ${row.qualification ?? ''}`.toLowerCase().includes(term))
    find('record-count').textContent = `${records.length} 条记录`
    find('record-list').replaceChildren()
    if (!records.length) find('record-list').append(element('p', '没有匹配的记录。试试其他标的或版本。', 'caption'))
    for (const row of records) {
      const detail = element('details', undefined, 'record'), summary = element('summary')
      summary.append(element('span', row.version, 'version'), element('span', row.name, 'name'))
      detail.append(summary, element('p', row.conclusion))
      if (row.diagnostic) detail.append(element('p', `旧快照指标：${row.diagnostic}`, 'source'))
      if (row.period) detail.append(element('p', row.period, 'source'))
      if (row.qualification) detail.append(element('p', row.qualification, 'source-warning'))
      if (row.definition) detail.append(element('pre', row.definition, 'record-formula'))
      detail.append(element('p', `${row.source} · ${row.source_date}`, 'source'))
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
    const sgov = data.sgov_paper
    find('sgov-paper-note').textContent = sgov ? sgov.activated
      ? `${sgov.note} 起点：${dateText(sgov.activation_utc)} HKT；首个可观察会话 ${sgov.first_session}、源日线核对至 ${sgov.source_quote_through}（均为纽约交易日）。状态核对 ${dateText(sgov.checked_at)} HKT。系统下单数 ${sgov.orders_sent}。`
      : sgov.note : 'SGOV纸面状态尚未随此快照提供。'
    find('sgov-paper-table').hidden = !sgov?.activated
    find('sgov-paper-rows').replaceChildren()
    for (const account of sgov?.accounts ?? []) {
      const row = element('tr'), unknown = account.status !== 'ACTIVE'
      for (const value of [`${account.capital_hkd.toLocaleString('zh-HK')} · ${account.cost === 'base' ? '基础' : '压力'}`,
        unknown ? '无法评估' : money(account.nav_hkd).replace(/^\+/, ''), unknown ? '无法评估' : money(account.change_hkd), account.quantity, account.observations]) row.append(element('td', value))
      find('sgov-paper-rows').append(row)
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
    renderWork(data); renderFactors(data); renderSgovHistory(data); renderCards(data); renderPaper(data); renderRecords()
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
  find('archive-link').addEventListener('click', () => { find('scope').value = 'factor-archive'; find('search').value = ''; renderRecords() })
  for (const key of ['history', 'paper']) find(`${key}-tab`).addEventListener('click', () => selectEvidenceView(key))
  setInterval(updateFreshness, 10000)
  setInterval(() => { if (document.visibilityState === 'visible') refresh() }, 60000)
  refresh()
}
