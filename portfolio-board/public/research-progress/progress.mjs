export const money = value => typeof value === 'number' && Number.isFinite(value)
  ? `${value > 0 ? '+' : ''}${new Intl.NumberFormat('zh-HK', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value)}` : '待验收'
export const freshness = (updatedAt, minutes = 15, now = Date.now()) => {
  const stamp = Date.parse(updatedAt), age = now - stamp
  if (!Number.isFinite(stamp) || age < -60000) return 'unknown'
  return age <= minutes * 60000 ? 'fresh' : 'stale'
}
export const exactMoney = value => {
  if (typeof value !== 'string' || !/^-?(?:0|[1-9]\d*)\.\d{2}$/.test(value)) return '—'
  const [whole, fraction] = value.split('.')
  return `${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}.${fraction}`
}
export function validateTipHistory(h, cards) {
  const card = cards.find(c => c.id === 'us-tip-history-A')
  const fail = () => { throw new Error('TIP仅展示root已接受的五年条件历史，金额或证据边界无效。') }
  if (h === undefined) { if (card) fail(); return h }
  if (!h || h.new_factor_trials !== 0 || h.new_horizon_trials !== 0 || h.new_paper_T0 !== false || h.B_computed !== false) fail()
  if (h.status === 'awaiting_root_account_acceptance') {
    if (card || h.chart !== null || h.primary_net_W_hkd !== null || !Array.isArray(h.cases) || h.cases.length) fail()
    return h
  }
  if (h.status !== 'accepted_conditional_A' || h.claim_level !== 'CONDITIONAL_HISTORICAL_MODEL' ||
      h.actual_income_certified !== false || h.stable_profitability_proven !== false || h.nav_points !== 1258 ||
      h.source_amount_scenarios !== 2 || h.related_scenarios !== 12 || h.chart !== 'assets/tip-history-A-v1.png' ||
      !Number.isFinite(Date.parse(h.accepted_at_utc)) || !/^[0-9a-f]{64}$/.test(h.receipt_sha256) ||
      !Array.isArray(h.cases) || h.cases.length !== 6 || new Set(h.cases.map(c => `${c.capital_hkd}-${c.cost}`)).size !== 6 ||
      !Array.isArray(h.yearly_B_changes) || h.yearly_B_changes.map(y => y.period).join() !== '2015,2016,2017,2018,2019' ||
      h.primary_capital_hkd !== 30000 || h.primary_cost !== 'pressure' || !card) fail()
  const cents = v => {
    if (typeof v !== 'string' || !/^-?(?:0|[1-9]\d*)\.\d{2}$/.test(v)) fail()
    return BigInt(v.replace('.', ''))
  }
  for (const c of h.cases) {
    if (![10000, 20000, 30000].includes(c.capital_hkd) || !['base', 'pressure'].includes(c.cost) ||
        !Number.isFinite(c.risk_pct) || c.risk_pct < 0 || c.months !== 60 || c.years !== 5 ||
        !Number.isSafeInteger(c.quantity) || c.quantity < 0 ||
        !Number.isSafeInteger(c.negative_months) || c.negative_months < 0 || c.negative_months > 60 ||
        !Number.isSafeInteger(c.negative_years) || c.negative_years < 0 || c.negative_years > 5) fail()
    const capital = BigInt(c.capital_hkd) * 100n
    if (cents(c.B_hkd) - cents(c.W_hkd) !== cents(c.K_hkd) || cents(c.W_hkd) - capital !== cents(c.net_W_hkd) ||
        cents(c.B_hkd) - capital !== cents(c.net_B_hkd)) fail()
    cents(c.net_distributions_usd)
  }
  const primary = h.cases.find(c => c.capital_hkd === 30000 && c.cost === 'pressure')
  for (const [key, field] of [['primary_net_W_hkd', 'net_W_hkd'], ['primary_B_hkd', 'B_hkd'], ['primary_W_hkd', 'W_hkd'], ['primary_K_hkd', 'K_hkd']]) {
    if (h[key] !== primary[field]) fail()
  }
  const best = h.yearly_B_changes.map(y => cents(y.B_change_hkd)).reduce((a, b) => a > b ? a : b)
  if (cents(h.concentration_without_best_year_W_hkd) !== cents(primary.net_W_hkd) - best ||
      h.concentration_formula !== '全期净W − 最佳年度B账面增量') fail()
  for (const row of card.results) {
    const c = h.cases.find(c => c.capital_hkd === 30000 && c.cost === row.cost)
    if (!c || row.net_hkd !== Number(c.net_W_hkd) || row.risk_pct !== c.risk_pct || row.cagr_pct !== null) fail()
  }
  return h
}
export function validateTipContinuation(h, cards) {
  const card = cards.find(c => c.id === 'us-tip-history-B')
  const fail = () => { throw new Error('TIP B必须由root接受，独立后段与固定失败结论不能改作盈利证明。') }
  if (h === undefined) { if (card) fail(); return h }
  if (!h || h.new_factor_trials !== 0 || h.new_horizon_trials !== 0 || h.new_paper_T0 !== false) fail()
  if (h.status === 'awaiting_root_account_acceptance') {
    if (card || h.chart !== null || h.primary_net_W_hkd !== null || !Array.isArray(h.cases) || h.cases.length) fail()
    return h
  }
  if (h.status !== 'accepted_rejected_B' || h.claim_level !== 'CONDITIONAL_HISTORICAL_MODEL' ||
      h.primary_original_screen_met !== false || h.actual_income_certified !== false || h.stable_profitability_proven !== false ||
      h.independent_initial_capital !== true || h.combined_with_A !== false || h.nav_points !== 1258 ||
      h.source_amount_scenarios !== 2 || h.related_scenarios !== 12 || h.chart !== 'assets/tip-history-B-v1.png' ||
      !Number.isFinite(Date.parse(h.accepted_at_utc)) || !/^[0-9a-f]{64}$/.test(h.receipt_sha256) ||
      !Array.isArray(h.cases) || h.cases.length !== 6 || new Set(h.cases.map(c => `${c.capital_hkd}-${c.cost}`)).size !== 6 ||
      !Array.isArray(h.yearly_B_changes) || h.yearly_B_changes.map(y => y.period).join() !== '2020,2021,2022,2023,2024' ||
      h.primary_capital_hkd !== 30000 || h.primary_cost !== 'pressure' || !card || card.status !== 'closed') fail()
  const cents = v => {
    if (typeof v !== 'string' || !/^-?(?:0|[1-9]\d*)\.\d{2}$/.test(v)) fail()
    return BigInt(v.replace('.', ''))
  }
  for (const c of h.cases) {
    if (![10000, 20000, 30000].includes(c.capital_hkd) || !['base', 'pressure'].includes(c.cost) ||
        !Number.isFinite(c.risk_pct) || c.risk_pct < 0 || c.months !== 60 || c.years !== 5 ||
        !Number.isSafeInteger(c.quantity) || c.quantity < 0 ||
        !Number.isSafeInteger(c.negative_months) || c.negative_months < 0 || c.negative_months > 60 ||
        !Number.isSafeInteger(c.negative_years) || c.negative_years < 0 || c.negative_years > 5) fail()
    const capital = BigInt(c.capital_hkd) * 100n
    if (cents(c.B_hkd) - cents(c.W_hkd) !== cents(c.K_hkd) || cents(c.W_hkd) - capital !== cents(c.net_W_hkd) ||
        cents(c.B_hkd) - capital !== cents(c.net_B_hkd)) fail()
    cents(c.net_distributions_usd)
  }
  for (const y of h.yearly_B_changes) cents(y.B_change_hkd)
  const primary = h.cases.find(c => c.capital_hkd === 30000 && c.cost === 'pressure')
  for (const [key, field] of [['primary_net_W_hkd', 'net_W_hkd'], ['primary_B_hkd', 'B_hkd'], ['primary_W_hkd', 'W_hkd'], ['primary_K_hkd', 'K_hkd']]) {
    if (h[key] !== primary[field]) fail()
  }
  for (const row of card.results) {
    const c = h.cases.find(c => c.capital_hkd === 30000 && c.cost === row.cost)
    if (!c || row.net_hkd !== Number(c.net_W_hkd) || row.risk_pct !== c.risk_pct || row.cagr_pct !== null) fail()
  }
  return h
}
export function validateDiversifiedPaper(p) {
  const date = v => v === null || typeof v === 'string' && Number.isFinite(Date.parse(v))
  const amount = v => v === null || typeof v === 'string' && /^-?(?:0|[1-9]\d*)\.\d{2}$/.test(v)
  const count = v => Number.isSafeInteger(v) && v >= 0
  const expected = new Set([20000, 30000].flatMap(c => ['base', 'pressure'].flatMap(k => ['annual', 'once'].map(r => `HKD${c}_${k}_${r}`))))
  if (!p || typeof p.activated !== 'boolean' || p.actual_orders !== 0 || !['status', 'status_label', 'note'].every(k => typeof p[k] === 'string' && p[k]) ||
      !Array.isArray(p.arms) || p.arms.length !== 8 || new Set(p.arms.map(a => a.id)).size !== 8 ||
      !['activation_utc', 'first_session', 'last_observation', 'source_through'].every(k => date(p[k])) || !p.intent ||
      !date(p.intent.date) || !date(p.intent.completed_utc) || ![null, true, false].includes(p.intent.timely)) throw new Error('组合纸面事实不完整，停止展示。')
  for (const a of p.arms) {
    if (!expected.has(a.id) || a.id !== `HKD${a.capital_hkd}_${a.cost}_${a.policy}` ||
        !['nav_hkd', 'net_hkd', 'settled_cash_usd'].every(k => amount(a[k])) || !a.shares ||
        Object.keys(a.shares).sort().join('|') !== 'US.GLD|US.SGOV|US.VTI' || !Object.values(a.shares).every(q => q === null || count(q))) throw new Error('组合必须保留8个相关情景与精确金额，不从净值反推持仓。')
    if (p.activated ? !['ACTIVE', 'MISSED', 'UNKNOWN'].includes(a.status) || a.status === 'UNKNOWN' && [a.nav_hkd, a.net_hkd].some(v => v !== null)
      : a.status !== 'NOT_ACTIVATED' || [a.nav_hkd, a.net_hkd, a.settled_cash_usd, ...Object.values(a.shares)].some(v => v !== null)) throw new Error('未激活或未知状态不能出现完整收益。')
  }
  if (p.activated) {
    if (![p.observations, p.security_trades].every(count) || [p.activation_utc, p.first_session, p.source_through].some(v => v === null) || p.observations > 0 && p.last_observation === null) throw new Error('已激活组合必须有实际起点和接续事实。')
  } else if ([p.activation_utc, p.first_session, p.last_observation, p.source_through, p.observations, p.security_trades, ...Object.values(p.intent)].some(v => v !== null)) throw new Error('未激活组合不能伪造T0、观察或交易数。')
  return p
}
export function validateSnapshot(value) {
  if (!value || value.schema_version !== 1 || !Array.isArray(value.cards) || !Array.isArray(value.registry) ||
      !Array.isArray(value.stages) || value.stages.length !== 6 || !value.activity || !value.paper || !Array.isArray(value.paper.accounts)) {
    throw new Error('研究快照格式不完整，请稍后刷新。')
  }
  if (['done', 'waiting'].includes(value.activity.status) && value.activity.active_at_snapshot) throw new Error('已交付或等待阶段不能显示进行中动画。')
  if (value.filing_event) {
    const {sources, result, event_tests: tests} = value.filing_event
    const e = value.filing_event.expansion
    if (e && (!result || e.planned !== 48 || e.priced !== 48 || !Number.isSafeInteger(e.positive) || e.positive < 0 || e.positive > e.priced ||
        ![e.positive_peer_bp, e.other_peer_bp, e.leave_best_peer_bp, e.cost50?.filtered_bp, e.cost50?.unconditional_bp, e.cost50?.increment_bp].every(Number.isFinite) ||
        !Array.isArray(e.years) || e.years.map(y=>y.year).join(',') !== '2016,2017,2018' ||
        !e.years.every(y => y.priced === 16 && [y.filtered_bp,y.unconditional_bp,y.increment_bp].every(Number.isFinite)))) {
      throw new Error('财报扩样数据不完整。')
    }
    if (sources.length !== 8 || !sources.every(s => /^https:\/\/www\.sec\.gov\/Archives\//.test(s.official_index)) ||
        tests !== Number(Boolean(result)) || result && (result.rows.length !== 8 || result.cells !== 8 || result.issuers !== 4 ||
        result.horizon_sessions !== 20 || result.net_account_hkd !== null || result.real_orders !== 0)) {
      throw new Error('财报事件来源或验收数据不完整。')
    }
  }
  if (value.current_work?.goal_status === 'ACTIVE') {
    if (value.current_work.stable_profitability_proven !== false || !['delivered', 'pending'].includes(value.current_work.candidate_milestone_status)) throw new Error('持续研究目标与候选里程碑必须分列。')
    if (value.stages.every(s => s.status === 'done')) throw new Error('总目标运行中，不能把全部证据阶段显示为完成。')
    if (value.activity.active_at_snapshot && !value.stages.some(s => s.status === 'active')) throw new Error('活动动画必须对应同步时的实际工作节点。')
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
  validateTipHistory(value.tip_history, value.cards)
  validateTipContinuation(value.tip_continuation, value.cards)
  if (value.next_factor_progress) {
    const p = value.next_factor_progress
    if (p.id !== 'v204' || !['preparing', 'preparation_snapshot', 'running_unaccepted', 'incomplete_unaccepted', 'author_complete_pending_review', 'independent_review_pending_root', 'root_accepted'].includes(p.state) ||
        typeof p.active_at_snapshot !== 'boolean' || typeof p.author_result_complete !== 'boolean' ||
        typeof p.independent_review_accepted !== 'boolean' || typeof p.root_accepted !== 'boolean' ||
        p.new_account_runs !== 0 || p.new_paper_T0 !== false || !p.task ||
        (!p.root_accepted && (p.accepted_signal_increment !== 0 || p.accepted_horizon_increment !== 0)) ||
        (p.root_accepted && (!p.independent_review_accepted || p.accepted_signal_increment !== 1 || p.accepted_horizon_increment !== 2))) throw new Error('下一因子进度和已验收结果必须分开计数。')
  }
  if (value.sgov_paper?.valuation_current === false) {
    const p = value.sgov_paper
    if (!p.activated || p.status !== 'review_required' || !p.latest_attempt || p.accounts.length !== 4 ||
        p.accounts.some(a => a.status !== 'UNKNOWN' || a.nav_hkd !== null || a.change_hkd !== null || a.quantity !== null ||
          !a.last_successful || !Number.isFinite(a.last_successful.nav_hkd) || !Number.isFinite(a.last_successful.change_hkd) ||
          !Number.isSafeInteger(a.last_successful.quantity) || a.last_successful.quantity < 0 ||
          !Number.isFinite(Date.parse(a.last_successful.observation)))) throw new Error('本次SGOV估值失败，最近成功旧值必须与当前未知状态分开。')
  }
  if (value.ipo_observation) {
    const o=value.ipo_observation
    if (!Number.isSafeInteger(o.count) || o.count<=0 || ![o.up_count,o.broken_count,o.flat_count,o.one_member_max_up_count].every(n=>Number.isSafeInteger(n)&&n>=0&&n<=o.count) ||
        o.up_count+o.broken_count+o.flat_count!==o.count || o.one_member_max_up_count<o.up_count || o.one_member_max_up_count>Math.min(o.count,o.up_count+1) || !Number.isFinite(o.median_pct) || o.median_pct < -100 ||
        !Number.isFinite(Date.parse(o.observed_at_hkt)) || o.observed_proxy_only!==true || o.not_an_account_win_rate!==true || o.paper_decision_registered!==false) throw new Error('IPO样本观察口径不完整，暂不展示指标。')
  }
  if (value.factor_research) {
    const f = value.factor_research
    if (!Number.isSafeInteger(f.unique_new_signals) || f.unique_new_signals <= 0 || !Number.isSafeInteger(f.planned_horizon_trials) || f.new_net_account_candidates !== 0 ||
        !Array.isArray(f.items) || f.items.length !== f.unique_new_signals || new Set(f.items.map(i => i.id)).size !== f.unique_new_signals ||
        f.items.reduce((n, i) => n + new Set(i.horizons ?? []).size, 0) !== f.planned_horizon_trials) throw new Error('新因子与预定期限计数不完整。')
    for (const item of f.items) {
      if (!['clue', 'rejected', 'source_blocked'].includes(item.status) || !Array.isArray(item.diagnostics) || !item.diagnostics.length ||
          item.account_net_hkd !== null || item.account_max_drawdown_pct !== null) throw new Error('新信号尚无已验净账户，不能展示账户收益。')
      for (const d of item.diagnostics) {
        if (!item.horizons.includes(d.horizon) || ![d.rank_ic, d.hac_t, d.p_value, d.top_excess_bp].every(Number.isFinite) ||
            Math.abs(d.rank_ic) > 1 || d.p_value < 0 || d.p_value > 1) throw new Error('因子诊断单位或期限无效。')
      }
    }
  }
  if (value.evidence_updates) {
    const q = value.evidence_updates.sgov_qii, f = value.evidence_updates.forward_evaluation
    if (q?.status !== 'accepted_issuer_classification_only' || !Number.isSafeInteger(q.source_events) || q.source_events <= 0 ||
        !Array.isArray(q.annual) || !q.annual.length || new Set(q.annual.map(r => r.year)).size !== q.annual.length ||
        q.annual.some(r => !Number.isSafeInteger(r.year) || !Number.isFinite(Number(r.weighted_qii_percent)) || Number(r.weighted_qii_percent) < 0 || Number(r.weighted_qii_percent) > 100 ||
          !/^https:\/\/www\.(blackrock|ishares)\.com\/.+\.pdf$/.test(r.source_url)) ||
        q.classification_is_personal_tax_rate !== false || q.actual_broker_withholding_refunds_fees_known !== false || q.existing_model_amounts_changed !== false) throw new Error('QII仅为发行人分类，不能改称个人税率或改写旧模型金额。')
    if (f?.status !== 'accepted_descriptive_only' || f.claim_level !== 'DESCRIPTIVE_ONLY' || !Number.isFinite(Date.parse(f.actual_freeze_utc)) ||
        !Number.isFinite(Date.parse(f.durable_completion_utc)) || f.formal_statistical_stability_method_frozen !== false || f.existing_arms_reported !== 8 ||
        f.new_paper_t0 !== false || f.stable_profitability_proven !== false || f.automatic_goal_completion !== false ||
        f.original_t0s?.hk03086 !== value.paper.activation_utc || f.original_t0s?.us_sgov !== value.sgov_paper?.activation_utc) throw new Error('描述性月报接受与原纸面T0、正式稳定性统计必须分别显示。')
    const wrapper = value.evidence_updates.hk_usd_cash_wrapper
    if (wrapper && (wrapper.status !== 'accepted_dated_kfs_current_metadata_only' || wrapper.ticker !== 'HK.03196' ||
        wrapper.distribution_currency !== 'USD' || wrapper.regular_distribution_guaranteed !== false ||
        wrapper.distribution_2025_certified !== false || wrapper.executable_depth_certified !== false ||
        wrapper.existing_model_amounts_changed !== false || wrapper.new_paper_t0 !== false ||
        [wrapper.new_factor_trials, wrapper.new_horizon_trials, wrapper.new_account_return_trials].some(n => n !== 0) ||
        !/^https:\/\/www\.bosera\.com\.hk\/api\/infobase\/downloadattfile\.do\?attachmentId=[A-Za-z0-9]+$/.test(wrapper.source_url))) throw new Error('03196当前来源补证不能升级为全年分派、成交或盈利证明。')
    const activity = value.evidence_updates.hk_usd_activity
    if (activity && (activity.status !== 'accepted_fixed_date_execution_prescreen_not_passed' || activity.ticker !== 'HK.03196' ||
        activity.year !== 2024 || activity.year_sessions !== 246 || activity.positive_volume_sessions !== 21 || activity.zero_volume_sessions !== 225 ||
        activity.fixed_entry_volume !== 0 || activity.fixed_exit_volume !== 0 || activity.net_profit_hkd !== null ||
        activity.fixed_entry_date !== '2024-01-02' || activity.fixed_exit_date !== '2024-12-31' ||
        [activity.new_factor_trials,activity.new_horizon_trials,activity.new_account_return_trials].some(n => n !== 0) ||
        [activity.new_paper_t0,activity.opening_depth_certified,activity.whole_fund_invalid,activity.distribution_2025_certified,activity.existing_model_amounts_changed].some(v => v !== false))) throw new Error('03196执行预筛不能变成成交、利润或全基金无效的结论。')
  }
  if (value.portfolio_research) {
    const p = value.portfolio_research
    if (p.status === 'implementation_pending_review') {
      if ([p.net_hkd, p.risk_pct, p.chart].some(v => v !== null)) throw new Error('组合账户尚未验收，不能展示收益或曲线。')
    } else if (['accepted_conditional_A_only', 'accepted_conditional_AB_C_pending', 'accepted_conditional_ABC'].includes(p.status)) {
      if (![p.net_hkd, p.risk_pct].every(Number.isFinite) || p.chart !== 'assets/portfolio-A-v2.png' ||
          p.actual_income_certified !== false || p.stable_profitability_proven !== false || p.new_paper_t0 !== null || p.B_C_computed !== (p.C_accepted === true) ||
          !Array.isArray(p.cases) || p.cases.length !== 6 || new Set(p.cases.map(c => `${c.capital_hkd}-${c.cost}`)).size !== 6 ||
          !Array.isArray(p.nav_series) || p.nav_series.length !== 756) throw new Error('A段条件账户、曲线或未完成边界不完整。')
      for (const c of p.cases) if (![10000, 20000, 30000].includes(c.capital_hkd) || !['base', 'pressure'].includes(c.cost) ||
          ![c.net_hkd, c.risk_pct].every(Number.isFinite) || c.months !== 36 || !Number.isSafeInteger(c.negative_months) || c.negative_months < 0 || c.negative_months > 36) throw new Error('A段本金/成本记录不完整。')
      for (const [i, point] of p.nav_series.entries()) if (!Number.isFinite(Date.parse(point.date)) || !Number.isFinite(point.nav_hkd) || point.nav_hkd <= 0 ||
          i > 0 && point.date <= p.nav_series[i - 1].date) throw new Error('A段历史净值点无效。')
      if (['accepted_conditional_AB_C_pending', 'accepted_conditional_ABC'].includes(p.status)) {
        const cAccepted = p.status === 'accepted_conditional_ABC'
        if (p.B_accepted !== true || p.C_accepted !== cAccepted || !Array.isArray(p.B_cases) || p.B_cases.length !== 6 ||
            new Set(p.B_cases.map(c => `${c.capital_hkd}-${c.cost}`)).size !== 6 || !Array.isArray(p.segment_rows) || p.segment_rows.length !== 3 ||
            p.segment_rows.map(s => s.stage).join('') !== 'ABC') throw new Error('A/B独立账户与C待核状态不完整。')
        for (const c of p.B_cases) if (![10000, 20000, 30000].includes(c.capital_hkd) || !['base', 'pressure'].includes(c.cost) ||
            ![c.net_hkd, c.risk_pct].every(Number.isFinite) || c.months !== 24 || !Number.isSafeInteger(c.negative_months) || c.negative_months < 0 || c.negative_months > 24) throw new Error('B段本金/成本记录不完整。')
        const c = p.segment_rows[2]
        if (!cAccepted && (c.status !== 'awaiting_root_review' || [c.base_net_hkd, c.net_hkd, c.risk_pct, c.negative_months, c.months].some(v => v !== null))) throw new Error('C段待根验收，不能预填结果。')
        if (cAccepted) {
          if (!Array.isArray(p.C_cases) || p.C_cases.length !== 6 || new Set(p.C_cases.map(c => `${c.capital_hkd}-${c.cost}`)).size !== 6 ||
              !Array.isArray(p.capital_cost_rows) || p.capital_cost_rows.length !== 18 || new Set(p.capital_cost_rows.map(c => `${c.stage}-${c.capital_hkd}-${c.cost}`)).size !== 18 || p.C_A_prefix_verified !== true) throw new Error('C连续账户与18行资本成本证据不完整。')
          for (const item of p.C_cases) if (![10000, 20000, 30000].includes(item.capital_hkd) || !['base', 'pressure'].includes(item.cost) ||
              ![item.net_hkd, item.risk_pct].every(Number.isFinite) || item.months !== 60 || !Number.isSafeInteger(item.negative_months) || item.negative_months < 0 || item.negative_months > 60) throw new Error('C段本金/成本记录不完整。')
        }
        for (const [i, segment] of p.segment_rows.entries()) {
          if (i === 2 && !cAccepted) continue
          const cases = [p.cases, p.B_cases, p.C_cases][i]
          const base = cases.find(c => c.capital_hkd === 30000 && c.cost === 'base'), pressure = cases.find(c => c.capital_hkd === 30000 && c.cost === 'pressure')
          if (segment.status !== 'accepted_conditional' || segment.capital_hkd !== 30000 || segment.base_net_hkd !== base.net_hkd || segment.net_hkd !== pressure.net_hkd ||
              segment.risk_pct !== pressure.risk_pct || segment.negative_months !== pressure.negative_months || segment.months !== pressure.months) throw new Error('分段摘要必须匹配各自独立核算记录，不能相加或拼接。')
        }
      }
    } else throw new Error('组合研究验收状态未知。')
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
            !(Number.isSafeInteger(a.quantity) && a.quantity >= 0 || p.valuation_current === false && a.status === 'UNKNOWN' && a.quantity === null) ||
            !Number.isSafeInteger(a.observations) || a.observations < 0 ||
            a.status !== 'ACTIVE' && [a.nav_hkd, a.change_hkd].some(v => v !== null)) throw new Error('SGOV纸面资金或未知状态的收益无效。')
      }
    }
  }
  if (value.diversified_paper !== undefined) {
    validateDiversifiedPaper(value.diversified_paper)
    if (value.diversified_paper.TEST_ONLY && value.TEST_ONLY !== true) throw new Error('模拟组合必须显式标记TEST_ONLY。')
  }
  if (value.evidence_updates?.hk_cash_2024) {
    const cash = value.evidence_updates.hk_cash_2024
    if (cash.status !== 'accepted_2024_nil_ordinary_addendum_only' || cash.full_window_upgraded !== false ||
        cash.existing_model_amounts_changed !== false || cash.new_strategy_trials !== 0) throw new Error('03152局部来源补强不能升级全期资格或收益。')
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
    const work = data.current_work
    find('goal-summary').hidden = !work?.goal_status
    find('goal-status').textContent = work?.goal_label ?? ''
    find('goal-milestone').textContent = work?.milestone_label ?? ''
    find('goal-evidence').textContent = work?.evidence_label ?? ''
    find('work-owners').replaceChildren()
    for (const owner of data.current_work?.owners ?? []) {
      const item = element('li')
      item.append(element('strong', owner.name), element('p', owner.task))
      find('work-owners').append(item)
    }
    find('work-note').textContent = data.current_work?.note ?? ''
  }
  function renderMerger(data) {
    const source = data.merger
    find('merger-source').hidden = !source
    if (!source) return
    find('merger-proxy').textContent = `以 2019 年第一季度公开投票结果为试点。代理申报目录覆盖 2018 年第四季度 ${source.q4_proxy} 份、2019 年第一季度 ${source.q1_proxy} 份，共 ${source.proxy_roster} 份，${source.proxy_available} 份原件可读。已分类 ${source.proxy_classified} 份，识别 ${source.proxy_vote_candidates} 个有批准结果的固定现金候选。还有 ${source.proxy_open} 份待分类。`
    find('merger-vote').textContent = `投票关键词筛查命中 merger ${source.vote_merger_docs} 件文档、acquisition ${source.vote_acquisition_docs} 件文档。合并去重后有 ${source.vote_union_docs} 件文档，分属 ${source.vote_union_accessions} 个 SEC 申报编号。两组共同命中 ${source.vote_overlap_accessions} 个申报编号，合并后还有 ${source.vote_unreviewed_accessions} 个待逐件人工核查。`
    const controls = find('merger-controls')
    const civitas = data.merger_execution_control
    controls.replaceChildren()
    for (const detail of [
      '完成｜Red Hat、Imperva、athenahealth。',
      '批准后失败｜PacBio 于 2019 年 1 月 24 日获股东批准，2020 年 1 月 2 日宣布终止。',
      '同日终局｜MINDBODY 在同一份 SEC 申报中披露投票结果和收购完成，尚未证实投票结果曾更早公开。',
      '待核行情｜RHT 的候选开盘报价仍需核对证券身份，终交易日成交量仍需核对。PacBio 的候选入场及终止行情目前各有一个报价来源。ROG 属于样本窗外。'
    ]) {
      const item = document.createElement('li')
      item.textContent = detail
      controls.append(item)
    }
    if (civitas) {
      const item = document.createElement('li')
      item.textContent = `次日无开盘｜Civitas Solutions（${civitas.symbol}）于 ${civitas.public_shareholder_approval_date} 公布批准结果。纽交所确认股票在 ${civitas.next_scheduled_open} 开盘前已停牌，该信号无法按次日开盘入场。`
      controls.append(item)
    }
    find('merger-result').textContent = `两条路径合并确认 ${source.firm_vote_cash_candidates} 个有批准结果的固定现金候选，其中 ${source.completed_candidates} 个完成、${source.terminated_candidates} 个终止。样本覆盖和可执行行情仍待核查，收益检验 ${source.return_tests} 次。`
    const links = find('merger-links')
    links.replaceChildren()
    const references = [['SEC 申报目录',source.links.index], ['PacBio 批准申报',source.links.approved_pacb],
      ['PacBio 终止申报',source.links.terminated_pacb], ['MINDBODY 投票及完成申报',source.links.mindbody]]
    if (civitas) references.push(['CIVI 纽交所停牌申报',civitas.proof_exchange_source])
    for (const [label, url] of references) {
      if (links.childNodes.length) links.append(' · ')
      const link = document.createElement('a')
      link.href = url
      link.textContent = label
      links.append(link)
    }
    links.hidden = !links.childNodes.length
  }

  function renderForm4(data) {
    const source = data.form4
    find('form4-source').hidden = !source
    if (!source) return
    find('form4-metrics').replaceChildren()
    find('form4-sample').textContent = `2018 年第二季度核对 ${source.issuers} 家公司的 ${source.filings} 份披露，包括 ${source.forms_4} 份 Form 4 和 ${source.amendments} 份 Form 4/A 更正。`
    for (const [label, value] of [
      ['P 买入交易行', source.purchases_coded],
      ['S 卖出交易行', source.sales_coded],
      ['买入场所未知', source.unknown_buy_venue],
      ['明确公开市场买入', source.explicit_public_market_purchase_rows],
      ['收益检验次数', source.actual_return_tests],
    ]) {
      const item = document.createElement('div')
      const name = document.createElement('dt')
      const count = document.createElement('dd')
      name.textContent = label
      count.textContent = value
      item.append(name, count)
      find('form4-metrics').append(item)
    }
    for (const [id, value] of [
      ['form4-dataset', source.evidence_url],
      ['form4-example', source.buy_example_url],
      ['form4-timing', source.timing_url],
    ]) {
      const url = new URL(value)
      if (url.protocol === 'https:' && ['www.sec.gov', 'investors.abbvie.com'].includes(url.hostname)) find(id).href = url.href
    }
    const annual = source.annual
    find('form4-annual').hidden = !annual
    const audit = annual?.attachment_audit
    const final = annual?.final_review
    find('form4-final').hidden = !final
    find('form4-annual-audit').hidden = !audit
    if (final) {
      find('form4-final-reviewed').textContent = `全年候选共 ${final.candidate_filings} 份披露、${final.candidate_rows} 条交易行。已核原件 ${final.original_filings_reviewed} 份、${final.rows_reviewed} 条，其中 ${final.automatic_dividend_reinvestment_rows} 条为自动股息再投资、${final.prearranged_plan_purchase_rows} 条为预设计划买入、${final.direction_conflict_rows} 条存在买卖方向矛盾，另有 ${final.other_paid_acquisition_rows} 条付价买入的场所未确认。`
      find('form4-final-unresolved').textContent = `另有 ${final.missing_original_filings} 份披露、${final.missing_original_rows} 条交易行未能取得可核查原件，交易场所仍待确认。`
      find('form4-final-result').textContent = `已核原件中，能确认属于严格公开市场买入的交易行有 ${final.explicit_public_market_rows} 条。本样本证据不足，收益检验 ${final.actual_return_tests} 次，研究转向下一条机制。`
    }
    if (annual) {
      const filings = annual.filings.toLocaleString('en-US')
      find('form4-annual-coverage').textContent = `固定样本的 ${annual.issuers} 家公司共 ${filings} 份披露。筛得 ${annual.structure_rows} 条符合预设买入结构的交易行，涉及 ${annual.structure_filings} 份披露和 ${annual.structure_issuer_days} 个发行人披露日。`
      find('form4-annual-review').textContent = `其中 ${annual.dividend_reinvestment_hints} 条有股息再投资线索。批量数据脚注明示公开市场的交易行有 ${annual.explicit_public_market_footnotes} 条。` + (final ? '' : `交易场所仍在逐份核对原件，已做收益检验 ${annual.actual_return_tests} 次。`)
    }
    if (audit) {
      find('form4-annual-audit').textContent = `首批按特征选取 ${audit.original_filings_reviewed} 份原件核查 ${audit.rows_reviewed} 条交易行，证实公开市场买入 ${audit.explicit_public_market_rows} 条。抽查涉及 ${audit.automatic_dividend_reinvestment_rows} 条自动股息再投资、${audit.prearranged_plan_purchase_rows} 条预设计划买入、${audit.direction_conflict_rows} 条买卖方向矛盾，以及 ${audit.other_paid_acquisition_rows} 条可证付价买入但原件未披露场所。抽查结果仅适用于这批原件。`
    }
  }

  function renderFiling(data) {
    const events = data.filing_event
    find('filing-event').hidden = !events
    if (!events) return
    const r = events.result
    const amount = x => Number.isFinite(x) ? (x > 0 ? '+' : '') + x.toFixed(2) : '—'
    find('filing-stage').textContent = r ? '20日历史小样本' : '八份公告已核实'
    find('filing-summary').textContent = r
      ? `4家公司、2个报季，共${r.cells}次公告。每股盈利同比增加时买入，${r.completed_entries}次有可比结果，其中${r.wins_gross_excess}次跑赢同日股票池。`
      : '已核对4家公司在2015和2019年的8次盈利披露，20日收益诊断待验收。'
    find('filing-timing').textContent = r?.source_note_zh ?? '8-K收件日后的下一交易日开盘为入场参照。'
    find('filing-metrics').replaceChildren()
    find('filing-metrics').hidden = !r
    if (r) {
      for (const [title, value] of [['股票减同池 · 毛差', r.mean_excess_pct], ['扣往返0.20%后', r.mean_excess_after_20bp_pct], ['扣往返0.50%后', r.mean_excess_after_50bp_pct], ['全部公告的毛差',r.unfiltered_event_mean_excess_pct]]) {
        const pair = element('div')
        pair.append(element('dt', title), element('dd', amount(value) + ' 个百分点'))
        find('filing-metrics').append(pair)
      }
    }
    find('filing-verdict').textContent = r?.verdict_zh ?? ''
    const eq = events.equal_opportunity
    find('filing-equal').textContent = r && eq
      ? `对八次机会各分配相同金额，跳过时现金收益按零计，每笔扣往返0.50%费用。只买盈利增长的公告，平均收益为${amount(eq.buy_positive_equal_opportunity_pct)}%；每次公告都买为${amount(eq.buy_all_equal_opportunity_pct)}%。筛选少赚了${Math.abs(eq.filter_minus_unfiltered_pp).toFixed(2)}个百分点。此处按事件分别核算，资金重叠及换汇尚未建模。` : ''
    find('filing-rows').replaceChildren()
    for (const s of events.sources) {
      const result = r?.rows.find(v => v.issuer === s.issuer && Number(v.year) === Number(s.year))
      const tr = element('tr'), td = element('td'), a = element('a', s.issuer + ' · ' + s.year)
      a.href = s.official_index; a.target = '_blank'; a.rel = 'noopener'; td.append(a); tr.append(td)
      const pct = v => Number.isFinite(v) ? amount(v) + '%' : '—'
      for (const value of [amount(Number(s.eps_change)), result ? result.buy ? '买入' : '不买 · 对照' : '待验收',
        result?.entry ?? '—',result?.exit ?? '—',pct(result?.stock_gross_pct),pct(result?.pool_gross_pct),amount(result?.excess_pct)]) {
        tr.append(element('td', value))
      }
      find('filing-rows').append(tr)
    }
    find('filing-next').textContent = r ? '预定扩样覆盖同四家公司2016—2018年的48个财季，先核对当时可得的公告，再与全部公告比较。当前结果只计一次事件检验；现金账户净利和回撤尚未计算。' : ''
    const x = events.expansion
    find('filing-expansion').hidden = !x
    if (x) {
      const pct = b => amount(b / 100) + '%'
      const pp = b => amount(b / 100) + ' 个百分点'
      find('filing-stage').textContent = '首批 8 次 · 扩样 48 次'
      find('filing-expanded-summary').textContent = `同四家公司又核实了 ${x.priced} 份季度公告，其中 ${x.positive} 份盈利同比增长。每个机会分配相同金额、每次买入扣往返 0.50%，持有 20 个交易日。`
      const metrics = find('filing-expanded-metrics')
      metrics.replaceChildren()
      for (const [title,val] of [['只买盈利增长',pct(x.cost50.filtered_bp)],['每次公告都买',pct(x.cost50.unconditional_bp)],['筛选增加的收益',pp(x.cost50.increment_bp)]]) {
        const pair=element('div'); pair.append(element('dt',title),element('dd',val));metrics.append(pair)
      }
      find('filing-expanded-compare').textContent = `增长组相对同日股票池的毛差为 ${pp(x.positive_peer_bp)}，其余公告为 ${pp(x.other_peer_bp)}。扣往返 0.50% 后，增长组相对股票池为 ${pp(x.positive_peer_bp - 50)}；去掉表现最好的一次则为 ${pp(x.leave_best_peer_bp - 50)}。但跳过其他公告会持有现金；在全部机会中，过滤后${x.cost50.increment_bp<0?'少赚':'多赚'} ${Math.abs(x.cost50.increment_bp / 100).toFixed(2)} 个百分点。`
      const rows=find('filing-expanded-rows');rows.replaceChildren()
      for (const y of x.years) {
        const row=element('tr')
        for(const t of [String(y.year),y.positive+' / '+y.priced,pct(y.filtered_bp),pct(y.unconditional_bp),pp(y.increment_bp)]) row.append(element('td',t))
        rows.append(row)
      }
      find('filing-expanded-limits').textContent=`四家公司都在后来的股票样本中，不能代表全部美股。不同公告的持有期最多同时有 ${x.overlap} 笔；这里没有按有限现金、整数股与换汇重建资金流水，不是账户收益。首批 8 次与这 48 次分开列示。`
      find('filing-next').textContent='新增48个财季与首批八次公告均来自训练期历史，不能据此认定稳定盈利。'
    }
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
        if (row.measure === 'gross_rights') period.append(element('span', `前组−同池 ${row.top_excess_bp > 0 ? '+' : ''}${row.top_excess_bp.toFixed(2)} bp/期（毛权益）`))
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
  function renderEvidenceUpdates(data) {
    const updates = data.evidence_updates
    find('evidence-updates').hidden = !updates
    if (!updates) return
    const q = updates.sgov_qii, f = updates.forward_evaluation
    find('qii-summary').textContent = `${q.ticker} · ${q.source_events}笔发行人QII分类已核。`
    find('qii-years').replaceChildren()
    for (const [i, r] of q.annual.entries()) {
      if (i) find('qii-years').append(document.createTextNode('；'))
      const link = element('a', `${r.year}：${Number(r.weighted_qii_percent) === 100 ? '100' : Number(r.weighted_qii_percent).toFixed(4)}%`)
      link.href = r.source_url; link.target = '_blank'; link.rel = 'noopener'; link.title = `${r.year}年发行人QII原表PDF`
      find('qii-years').append(link)
    }
    find('qii-years').append(document.createTextNode('。'))
    find('qii-note').textContent = q.note
    find('qii-limits').textContent = q.limitation
    find('forward-accepted').textContent = `描述性协议接受：${f.accepted_at_hkt} HKT；保留两套原T0和${f.existing_arms_reported}臂。`
    find('forward-note').textContent = f.note
    find('forward-limits').textContent = f.limitation
    find('forward-method-badge').textContent = f.layered_measurement ? '正式统计推断未启用' : '稳定性统计方法未冻结'
    const cash = updates.hk_cash_2024
    find('hk-cash-update').hidden = !cash
    if (cash) {
      find('hk-cash-summary').textContent = cash.summary
      find('hk-cash-limits').textContent = cash.limitation
      find('hk-cash-accepted').textContent = `局部来源接受：${dateText(cash.accepted_at_utc)} HKT；原收益、空值和试验计数不变。`
    }
    const wrapper = updates.hk_usd_cash_wrapper
    find('hk-usd-cash-update').hidden = !wrapper
    if (wrapper) {
      find('hk-usd-cash-summary').textContent = wrapper.summary
      find('hk-usd-cash-note').textContent = wrapper.note
      find('hk-usd-cash-limits').textContent = wrapper.limitation
      find('hk-usd-cash-source').href = wrapper.source_url
    }
    const activity = updates.hk_usd_activity
    find('hk-usd-activity-update').hidden = !activity
    if (activity) {
      find('hk-usd-activity-summary').textContent = activity.summary
      const label = `全年246个会话：有成交记录21天（深色），零成交记录225天（浅色）。这是日线成交记录，不是开盘可成交深度。`
      find('hk-usd-activity-meter').setAttribute('aria-label',label)
      find('hk-usd-activity-positive').style.width = `${activity.positive_volume_sessions/activity.year_sessions*100}%`
      find('hk-usd-activity-count').textContent = label
      find('hk-usd-activity-limits').textContent = activity.limitation
    }
  }
  function renderPortfolio(data) {
    const research = data.portfolio_research
    find('portfolio-progress').hidden = !research
    if (!research) return
    find('portfolio-title').textContent = research.name
    find('portfolio-badge').textContent = research.status_label ?? 'A段待独立验收'
    find('portfolio-summary').textContent = `${research.period}。${research.summary}`
    find('portfolio-status').textContent = research.progress
    find('portfolio-limits').textContent = research.limitations
    find('portfolio-fee-boundary').textContent = research.fee_boundary ?? ''
    find('portfolio-comparison').textContent = research.comparison ?? ''
    find('portfolio-payment').textContent = research.payment_sensitivity ?? ''
    find('portfolio-separation-note').textContent = research.separation_note ?? ''
    find('portfolio-segment-table').hidden = !research.segment_rows
    find('portfolio-segment-rows').replaceChildren()
    for (const segment of research.segment_rows ?? []) {
      const row = element('tr'), pending = segment.status === 'awaiting_root_review'
      for (const value of [`${segment.stage} · ${segment.period}`, money(segment.base_net_hkd), money(segment.net_hkd),
        pending ? '待核' : `${segment.risk_pct.toFixed(4)}%`, pending ? '待核' : `${segment.negative_months}/${segment.months}`]) row.append(element('td', value))
      find('portfolio-segment-rows').append(row)
    }
    find('portfolio-curve-note').textContent = research.curve_note
    find('portfolio-chart-link').hidden = !research.chart
    if (research.chart) { find('portfolio-chart-link').href = research.chart; find('portfolio-chart').src = research.chart }
    find('portfolio-table').hidden = !research.cases
    find('portfolio-capital-details').hidden = !research.cases
    find('portfolio-capital-label').textContent = `查看${research.C_cases ? 'A/B/C' : research.B_cases ? 'A/B' : 'A'}各本金的基础/压力情景`
    find('portfolio-rows').replaceChildren()
    const groups = research.cases ? [['A', research.cases], ...(research.B_cases ? [['B', research.B_cases]] : []), ...(research.C_cases ? [['C', research.C_cases]] : [])] : []
    for (const [stage, cases] of groups) for (const capital of [10000, 20000, 30000]) {
      const base = cases.find(c => c.capital_hkd === capital && c.cost === 'base')
      const pressure = cases.find(c => c.capital_hkd === capital && c.cost === 'pressure'), row = element('tr')
      for (const value of [stage, capital.toLocaleString('zh-HK'), money(base.net_hkd), money(pressure.net_hkd), `${pressure.risk_pct.toFixed(4)}%`, `${pressure.negative_months}/${pressure.months}`]) row.append(element('td', value))
      find('portfolio-rows').append(row)
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
  function renderTipHistory(data) {
    const h = data.tip_history, accepted = h?.status === 'accepted_conditional_A'
    const hasB = data.tip_continuation?.status === 'accepted_rejected_B'
    find('tip-history').hidden = !accepted
    if (!accepted) { find('tip-history-chart').removeAttribute('src'); return }
    find('tip-history-note').textContent = h.note
    find('tip-history-limits').textContent = h.limitations
    find('tip-history-badge').textContent = hasB ? 'A段原条件历史记录' : 'A段条件历史 · 后段未检验'
    find('tip-history-source').textContent = (hasB ? 'A原验收时的说明（B最新独立结论见上方）：' : '') + h.source_note
    find('tip-history-concentration').textContent = `${h.concentration_formula} = ${exactMoney(h.concentration_without_best_year_W_hkd)} 港币。仅为固定算术诊断，不是删掉2019后的完整回测。${hasB ? 'A原值保留；B后段已有独立检验，见上方' : h.B_status}。`
    find('tip-history-chart').src = h.chart
    find('tip-history-link').href = h.chart
    find('tip-history-rows').replaceChildren()
    for (const capital of [10000, 20000, 30000]) {
      const base = h.cases.find(c => c.capital_hkd === capital && c.cost === 'base')
      const pressure = h.cases.find(c => c.capital_hkd === capital && c.cost === 'pressure')
      const tr = element('tr')
      for (const text of [new Intl.NumberFormat('zh-HK').format(capital), exactMoney(base.net_W_hkd), exactMoney(pressure.net_W_hkd),
        `${pressure.risk_pct.toFixed(2)}%`, `${pressure.negative_years}／5`, `${pressure.negative_months}／60`, exactMoney(pressure.net_distributions_usd)]) {
        tr.append(element('td', text))
      }
      find('tip-history-rows').append(tr)
    }
  }
  function renderTipContinuation(data) {
    const h = data.tip_continuation, accepted = h?.status === 'accepted_rejected_B'
    find('tip-continuation').hidden = !accepted
    if (!accepted) { find('tip-continuation-chart').removeAttribute('src'); return }
    for (const [id, text] of [['conclusion', h.conclusion], ['note', h.note], ['limits', h.limitations], ['source', h.source_note]]) {
      find(`tip-continuation-${id}`).textContent = text
    }
    find('tip-continuation-chart').src = h.chart
    find('tip-continuation-link').href = h.chart
    find('tip-continuation-rows').replaceChildren()
    for (const capital of [10000, 20000, 30000]) {
      const base = h.cases.find(c => c.capital_hkd === capital && c.cost === 'base')
      const pressure = h.cases.find(c => c.capital_hkd === capital && c.cost === 'pressure'), tr = element('tr')
      for (const text of [new Intl.NumberFormat('zh-HK').format(capital), exactMoney(base.net_W_hkd), exactMoney(pressure.net_W_hkd),
        `${pressure.risk_pct.toFixed(2)}%`, `${pressure.negative_years}／5`, `${pressure.negative_months}／60`, exactMoney(pressure.net_distributions_usd)]) {
        tr.append(element('td', text))
      }
      find('tip-continuation-rows').append(tr)
    }
  }
  function renderCards(data) {
    find('cards').replaceChildren()
    for (const card of data.cards) {
      const article = element('article', undefined, 'study')
      const head = element('div', undefined, 'study-head')
      const originalA = card.id === 'us-tip-history-A' && data.tip_continuation?.status === 'accepted_rejected_B'
      head.append(element('h3', card.name), element('span', originalA ? 'A原验收记录 · 当时后段未检验' : card.status_label, `badge ${card.status}`))
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
      article.append(element('p', card.conclusion), element('p', originalA ? `原验收时下一步：${card.next} 最新B独立检验已在上方展示。` : card.next, 'next'))
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
    const hk = data.paper, intent = hk.recorded_intents?.at(-1)
    const observation = hk.last_observation ? `最近实际观察 ${hk.last_observation}；源日线核对至 ${hk.source_quote_through}。` : ''
    const intentNote = intent ? `最近登记意向 ${intent.date} · ${intent.eligible ? '已及时' : '未及时'}；${hk.recorded_intents.some(i => i.date > hk.last_observation) ? '后续登记以原记录为准' : '未见后续会话预登记，不倒填'}。` : ''
    find('paper-note').textContent = `${hk.note} 起点：${dateText(hk.activation_utc)} HKT；${observation}${intentNote}状态核对：${dateText(hk.checked_at)} HKT。研究系统下单数 ${hk.orders_sent}。`
    find('paper-rows').replaceChildren()
    for (const account of data.paper.accounts) {
      const row = element('tr')
      for (const value of [names[account.id] ?? account.id, money(account.nav_hkd).replace(/^\+/, ''), money(account.change_hkd), account.quantity, account.closed_rounds]) row.append(element('td', value))
      find('paper-rows').append(row)
    }
    const sgov = data.sgov_paper
    find('sgov-paper-note').textContent = sgov ? sgov.activated
      ? `${sgov.note} 起点：${dateText(sgov.activation_utc)} HKT；首个可观察会话 ${sgov.first_session}、最近实际观察 ${sgov.accounts.map(a => a.last_observation).filter(Boolean).sort().at(-1) ?? '尚无'}、源日线核对至 ${sgov.source_quote_through}（均为纽约交易日）。状态核对 ${dateText(sgov.checked_at)} HKT。系统下单数 ${sgov.orders_sent}。`
      : sgov.note : 'SGOV纸面状态尚未随此快照提供。'
    find('sgov-paper-table').hidden = !sgov?.activated
    find('sgov-last-success-header').hidden = sgov?.valuation_current !== false
    find('sgov-paper-rows').replaceChildren()
    for (const account of sgov?.accounts ?? []) {
      const row = element('tr'), unknown = account.status !== 'ACTIVE'
      for (const value of [`${account.capital_hkd.toLocaleString('zh-HK')} · ${account.cost === 'base' ? '基础' : '压力'}`,
        unknown ? '本次未知' : money(account.nav_hkd).replace(/^\+/, ''), unknown ? '本次未知' : money(account.change_hkd), account.quantity ?? '未知', account.observations]) row.append(element('td', value))
      if (sgov.valuation_current === false) {
        const old = account.last_successful
        row.append(element('td', `${old.observation}：${money(old.nav_hkd).replace(/^\+/, '')}／${money(old.change_hkd)}；${old.quantity}份（旧值）`))
      }
      find('sgov-paper-rows').append(row)
    }
    renderDiversifiedPaper(data)
  }
  function renderDiversifiedPaper(data) {
    const p = data.diversified_paper
    find('diversified-paper').hidden = !p
    if (!p) return
    const shown = v => v === null ? '—' : String(v)
    const time = v => v === null ? '—' : `${dateText(v)} HKT`
    find('diversified-paper-status').textContent = p.status_label
    find('diversified-paper-status').className = `badge ${p.activated ? 'paper' : 'review'}`
    find('diversified-paper-note').textContent = `${p.TEST_ONLY ? 'TEST_ONLY · 模拟渲染，非实际接续。 ' : ''}${p.note}`
    find('diversified-paper-note').classList.toggle('test-only', p.TEST_ONLY === true)
    find('diversified-origin').textContent = time(p.activation_utc)
    find('diversified-source').textContent = p.activated ? `${p.first_session} / ${p.source_through}` : '— / —'
    find('diversified-observation').textContent = p.activated ? `${p.observations}会话；最近 ${shown(p.last_observation)}` : '—'
    const intentStatus = p.intent.timely === true ? '已及时固化' : p.intent.timely === false ? '未及时' : '尚无'
    find('diversified-intent').textContent = p.activated ? `${shown(p.intent.date)} · ${intentStatus}；${time(p.intent.completed_utc)}` : '—'
    find('diversified-orders').textContent = `实际订单 ${p.actual_orders}；纸面证券成交 ${shown(p.security_trades)}。`
    const costs = data.nov18_cost_attribution ?? []
    find('nov18-cost').hidden = !costs.length
    find('nov18-rows').replaceChildren()
    for (const c of costs) {
      const tr = element('tr')
      for (const val of [c.capital + ' · ' + c.cost, c.fx, c.move, c.slip, c.fee, c.net]) tr.append(element('td',val))
      find('nov18-rows').append(tr)
    }
    find('diversified-paper-rows').replaceChildren()
    for (const arm of p.arms) {
      const row = element('tr'), unknown = arm.status === 'UNKNOWN'
      const name = `${arm.capital_hkd.toLocaleString('zh-HK')} · ${arm.cost === 'base' ? '基础' : '压力'} · ${arm.policy === 'annual' ? '年度再平衡' : '一次持有'}`
      const state = { ACTIVE: '接续中', MISSED: '已漏首单', UNKNOWN: '未知 · 旧前缀', NOT_ACTIVATED: '未激活' }[arm.status]
      const values = [name, unknown ? '无法完整评估' : exactMoney(arm.nav_hkd), unknown ? '无法完整评估' : exactMoney(arm.net_hkd),
        exactMoney(arm.settled_cash_usd), ...['US.SGOV', 'US.VTI', 'US.GLD'].map(t => shown(arm.shares[t])), state]
      for (const [index, value] of values.entries()) row.append(element('td', value, index === 2 && arm.net_hkd?.startsWith('-') ? 'negative-amount' : undefined))
      row.dataset.arm = arm.id
      find('diversified-paper-rows').append(row)
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
      item.append(element('small', stage.detail ?? names[stage.status] ?? stage.status)); find('stages').append(item)
    }
    renderWork(data); renderMerger(data); renderForm4(data); renderFiling(data); renderPortfolio(data); renderFactors(data); renderEvidenceUpdates(data); renderSgovHistory(data); renderTipHistory(data); renderTipContinuation(data); renderCards(data); renderPaper(data); renderRecords()
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
