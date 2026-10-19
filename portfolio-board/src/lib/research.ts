import type { Expression, Proposal, ResearchData } from '../types/research'

const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v)
const text = (v: unknown): v is string => typeof v === 'string' && v.length > 0
const number = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)
const nullable = (v: unknown) => v === null || number(v)
const array = (v: unknown, predicate: (item: unknown) => boolean) => Array.isArray(v) && v.every(predicate)
const keys = (v: Record<string, unknown>, allowed: string[]) => Object.keys(v).every(k => allowed.includes(k))

export function validExpression(v: unknown, features: string[], depth = 0): v is Expression {
  if (!object(v) || depth > 4) return false
  if (v.op === 'feature') return keys(v, ['op', 'name']) && text(v.name) && features.includes(v.name)
  if (v.op === 'neg') return keys(v, ['op', 'arg']) && validExpression(v.arg, features, depth + 1)
  return ['mean', 'product'].includes(String(v.op)) && keys(v, ['op', 'args']) && Array.isArray(v.args)
    && v.args.length >= 2 && v.args.length <= 3 && v.args.every(a => validExpression(a, features, depth + 1))
}

function spec(v: unknown, features: string[]) {
  return object(v) && ['name', 'op_type', 'hypothesis', 'change', 'expected'].every(k => text(v[k]))
    && validExpression(v.expression, features) && Array.isArray(v.filters) && v.filters.length <= 5 && v.filters.every(f =>
      object(f) && text(f.feature) && features.includes(f.feature) && keys(f, ['feature', 'gte', 'lte'])
      && ('gte' in f || 'lte' in f) && ['gte', 'lte'].every(k => !(k in f) || number(f[k]) && Math.abs(f[k]) <= 1e6)
      && !(number(f.gte) && number(f.lte) && f.gte > f.lte))
}

export function parseProposal(raw: string, data: Pick<ResearchData, 'features' | 'programs' | 'universes'>): Proposal {
  if (raw.length > 16000) throw new Error('提案超过长度限制')
  let value: unknown
  try { value = JSON.parse(raw) } catch { throw new Error('提案 JSON 格式无效') }
  if (!object(value) || !keys(value, ['name', 'op_type', 'hypothesis', 'change', 'expected', 'expression', 'filters', 'market', 'parent_id'])
      || !spec(value, Object.keys(data.features))) throw new Error('提案字段、因子或公式不符合研究规则')
  for (const key of ['name', 'op_type', 'hypothesis', 'change', 'expected']) {
    if (!text(value[key]) || !value[key].trim() || value[key].length > (key === 'name' ? 60 : 400)) throw new Error('名称或研究依据为空、超长')
  }
  if (!data.universes.some(u => u.market === value.market)) throw new Error('该市场尚未建立研究池')
  if (value.parent_id != null && !data.programs.some(p => p.id === value.parent_id && p.market === value.market)) throw new Error('父策略不存在或市场不一致')
  return value as unknown as Proposal
}

export function formula(expr: Expression, features: ResearchData['features']): string {
  if (expr.op === 'feature') return features[expr.name]?.name ?? expr.name
  if (expr.op === 'neg') return `负向(${formula(expr.arg, features)})`
  return `${expr.op === 'mean' ? '均值' : '交互'}(${expr.args.map(a => formula(a, features)).join('，')})`
}

export function isResearchData(v: unknown): v is ResearchData {
  if (!object(v) || v.schema_version !== 1 || !['generated_at', 'policy_hash', 'engine_version', 'review_workflow', 'generator'].every(k => text(v[k]))
      || typeof v.model_connected !== 'boolean' || !object(v.policy) || !object(v.features) || !Object.keys(v.features).length) return false
  if (!Object.values(v.features).every(f => object(f) && ['name', 'formula', 'family'].every(k => text(f[k])))) return false
  const names = Object.keys(v.features), policy = v.policy
  if (!['horizon', 'max_programs', 'max_searches', 'max_active', 'comparison_budget', 'discovery_after', 'max_correlation', 'cost_bps', 'stress_cost_bps'].every(k => number(policy[k]))
      || !Array.isArray(policy.checkpoints) || !policy.checkpoints.length || !policy.checkpoints.every(number)) return false
  if (!array(v.universes, u => object(u) && ['market', 'hash', 'created_at', 'basis'].every(k => text(u[k]))
      && array(u.members, m => object(m) && text(m.code) && text(m.name)))) return false
  if (!array(v.quality, q => object(q) && text(q.market) && text(q.status) && object(q.missing)
      && Object.values(q.missing).every(text) && ['session', 'valid', 'total', 'coverage'].every(k => number(q[k])))) return false
  const metrics = (m: unknown) => object(m) && ['due', 'paired', 'coverage', 'signal_rate', 'independent'].every(k => number(m[k]))
    && ['mean_delta_pp', 'lower_delta_pp', 'mean_return_pct', 'mean_excess_pp', 'stress_excess_pp', 'worst_period_pct', 'rank_ic', 'pearson_ic', 'novelty'].every(k => nullable(m[k]))
  if (!array(v.programs, p => object(p) && spec(p, names) && ['id', 'family', 'market', 'created_at', 'definition_hash', 'engine_version'].every(k => text(p[k]))
      && number(p.generation) && ['testing', 'review', 'approved', 'paused', 'rejected'].includes(String(p.status))
      && object(p.discovery) && text(p.discovery.kind) && (p.metrics === undefined || metrics(p.metrics))
      && array(p.assessments, a => object(a) && number(a.checkpoint) && text(a.hash) && object(a.gates) && Object.values(a.gates).every(g => typeof g === 'boolean'))
      && array(p.latest_selection, h => object(h) && text(h.code) && number(h.score) && object(h.features) && Object.values(h.features).every(number))
      && (p.latest_frozen_at === null || text(p.latest_frozen_at))
      && object(p.historical) && text(p.historical.status) && text(p.historical.note)
      && array(p.historical.folds, f => object(f) && ['train_start', 'train_end', 'test_start', 'test_end', 'test_periods', 'complete', 'purged', 'embargo'].every(k => number(f[k]))
        && ['rank_ic', 'train_rank_ic', 'pearson_ic', 'mean_delta_pp', 'coverage', 'icir', 'ic_lower', 'ic_upper', 'q5_q1_pp', 'degradation'].every(k => nullable(f[k]))))) return false
  if (!array(v.observations, r => object(r) && text(r.trial_id) && number(r.entry_date) && number(r.exit_date) && typeof r.due === 'boolean'
      && nullable(r.rank_ic) && nullable(r.pearson_ic) && nullable(r.benchmark_pct)
      && ['branch', 'parent', 'pool'].every(k => object(r[k]) && typeof r[k].complete === 'boolean' && nullable(r[k].return_pct))
      && object(r.branch) && number(r.branch.count) && array(r.branch.holdings, h => object(h) && text(h.code) && text(h.status) && nullable(h.return_pct)))) return false
  if (!array(v.events, e => object(e) && text(e.action) && text(e.at))) return false
  if (v.model_research !== undefined) {
    const m = v.model_research
    if (!object(m) || !['provider', 'model', 'connection', 'checked_at'].every(k => text(m[k]))
        || m.mode !== 'owner_review' || !number(m.max_calls) || !number(m.min_cohorts)
        || !array(m.calls, c => object(c) && ['id', 'at', 'parent_id', 'status'].every(k => text(c[k]))
          && number(c.rejected_count) && object(c.usage) && Object.values(c.usage).every(number)
          && array(c.proposals, p => object(p) && spec(p.proposal, names) && object(p.proposal)
            && text(p.proposal.market) && text(p.proposal.parent_id)
            && (p.started_program_id === null || text(p.started_program_id))))) return false
  }
  return array(v.searches, s => object(s) && ['hash', 'at', 'parent_id', 'market'].every(k => text(s[k])) && number(s.cohort_count) && number(s.last_label_date)
    && array(s.candidates, c => object(c) && spec(c.spec, names) && nullable(c.rank_ic) && nullable(c.novelty) && number(c.mean_delta_pp) && number(c.signal_rate)
      && typeof c.qualified === 'boolean' && typeof c.duplicate === 'boolean'))
}

export function downloadJson(value: unknown, name: string) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' }))
  const anchor = document.createElement('a')
  anchor.href = url; anchor.download = name; anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
