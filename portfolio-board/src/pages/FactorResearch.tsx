import { useState } from 'react'
import { Link } from 'react-router'
import { Bar, BarChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Check, Download, ExternalLink, FlaskConical, RefreshCw, Search, X } from 'lucide-react'
import AppShell from '@/components/AppShell'
import LabTabs from '@/components/LabTabs'
import ResearchProposal from '@/components/ResearchProposal'
import ModelResearch, { modelConnection } from '@/components/ModelResearch'
import { Button } from '@/components/ui/button'
import { useResearch } from '@/hooks/useResearch'
import { downloadJson, formula } from '@/lib/research'
import { scanTimeInfo } from '@/lib/screener'
import type { ResearchData, ResearchProgram } from '@/types/research'

const STATUS = { testing: '前瞻跟踪中', review: '待审核', approved: '已审核（纸面）', paused: '已暂停', rejected: '已淘汰' }
const GATES: Record<string, string> = { coverage: '配对完整率', signal_rate: '有效信号比例', independent: '非重叠样本', improvement: '相对父策略改善',
  uncertainty: '修正后的改善下界', benchmark: '扣费后基准超额', stress_cost: '高成本压力测试', risk: '最差单期', novelty: '因子重复性' }
const metric = (value: number | null | undefined, suffix = '') => value == null ? '-' : `${value.toFixed(2)}${suffix}`
const day = (v: number) => String(v).replace(/^(\d{4})(\d{2})(\d{2})$/, '$1-$2-$3')
const control = 'h-9 max-w-full rounded-md border bg-background px-2 text-sm'

function Detail({ program: p, data }: { program: ResearchProgram; data: ResearchData }) {
  const [tab, setTab] = useState('forward')
  const own = data.observations.filter(r => r.trial_id === p.id)
  const chart = own.filter(r => r.due && r.branch.complete && r.parent.complete && r.branch.return_pct != null && r.parent.return_pct != null)
    .slice(-40).map(r => ({ date: day(r.entry_date).slice(5), delta: r.branch.return_pct! - r.parent.return_pct! }))
  const latest = p.assessments.at(-1)
  const parent = data.programs.find(row => row.id === p.parent_id)
  const m = p.metrics
  const name = (code: string) => data.universes.flatMap(u => u.members).find(member => member.code === code)?.name ?? code
  return <section aria-label="研究详情" className="min-w-0 border-t pt-5">
    <div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><h2 className="text-base font-semibold break-words">{p.name}</h2>
      <p className="mt-1 text-xs text-muted-foreground">{p.market} · 第 {p.generation} 代 · {parent ? `父策略：${parent.name}` : '独立家族 · 同期研究池等权对照'}</p></div>
      <span className={`text-xs ${p.status === 'review' ? 'text-amber-800' : p.status === 'rejected' ? 'text-rose-700' : 'text-emerald-800'}`}>{STATUS[p.status]}</span></div>
    <div className="my-4 flex flex-wrap gap-1 border-b" role="group" aria-label="研究详情视图">{[['forward', '前瞻跟踪'], ['history', '历史诊断'], ['hypothesis', '研究依据']].map(([key, label]) =>
      <button key={key} onClick={() => setTab(key)} aria-pressed={tab === key} className={`border-b-2 px-3 py-2 text-sm ${tab === key ? 'border-primary text-primary' : 'border-transparent text-muted-foreground'}`}>{label}</button>)}</div>
    {tab === 'forward' && <div className="space-y-5">
      <dl className="grid grid-cols-2 gap-x-4 gap-y-4 md:grid-cols-4">
        {[['到期 / 完整配对', `${m?.due ?? 0} / ${m?.paired ?? 0}`], ['平均扣费收益', metric(m?.mean_return_pct, '%')],
          ['相对父策略改善', metric(m?.mean_delta_pp, ' pp')], ['相对基准超额', metric(m?.mean_excess_pp, ' pp')],
          ['高成本超额', metric(m?.stress_excess_pp, ' pp')], ['最差单期', metric(m?.worst_period_pct, '%')],
          ['Rank IC', metric(m?.rank_ic)], ['最大平均相关性', metric(m?.novelty)]].map(([label, value]) => <div key={label}>
          <dt className="text-xs text-muted-foreground">{label}</dt><dd className="mt-1 text-base tabular-nums">{value}</dd></div>)}
      </dl>
      <div><h3 className="text-sm font-semibold">逐期收益改善</h3>{chart.length ? <div className="mt-3 h-48 min-w-0" aria-label="前瞻改善图表">
        <ResponsiveContainer width="100%" height="100%"><BarChart data={chart}><XAxis dataKey="date" tick={{ fontSize: 10 }} /><YAxis width={40} tick={{ fontSize: 10 }} />
          <Tooltip formatter={v => [metric(Number(v), ' pp'), '策略减同期对照']} /><ReferenceLine y={0} stroke="#64748b" /><Bar dataKey="delta" fill="#207d72" maxBarSize={24} /></BarChart></ResponsiveContainer>
      </div> : <p className="border-b py-7 text-sm text-muted-foreground">尚无到期的完整配对结果。</p>}</div>
      <div><h3 className="text-sm font-semibold">当前研究名单 <span className="ml-2 font-normal text-muted-foreground">{p.latest_selection.length} 只</span></h3>
        <p className="mt-1 text-xs text-muted-foreground">{p.latest_frozen_at ? `决策冻结于 ${scanTimeInfo(p.latest_frozen_at).display}` : '尚无可用的创建后决策快照'}</p>
        {p.latest_selection.length ? <div className="mt-3 overflow-x-auto"><table className="w-full min-w-[360px] text-left text-xs"><thead className="border-b text-muted-foreground"><tr><th className="p-2">股票</th><th className="p-2">因子得分</th><th className="p-2">因子观测</th></tr></thead>
          <tbody>{p.latest_selection.map(h => <tr key={h.code} className="border-b"><td className="p-2"><Link to={`/stock/${encodeURIComponent(h.code)}`} className="text-primary">{name(h.code)}<span className="block text-[10px] text-muted-foreground">{h.code}</span></Link></td>
            <td className="p-2 tabular-nums">{metric(h.score)}</td><td className="p-2"><details><summary className="cursor-pointer">查看观测值</summary><dl className="mt-2 space-y-1">{Object.entries(h.features).map(([key, value]) => <div key={key}>{data.features[key]?.name ?? key}：{metric(value)}</div>)}</dl></details></td></tr>)}</tbody></table></div>
          : <p className="py-4 text-sm text-muted-foreground">{p.latest_frozen_at ? '本期没有符合条件的股票，按现金观察。' : '等待研究池行情和首个决策快照。'}</p>}
      </div>
      <div className="border-t pt-4"><h3 className="text-sm font-semibold">固定关卡 {latest ? `· ${latest.checkpoint} 期` : `· 等待 ${data.policy.checkpoints[0]} 期`}</h3>
        {latest && <ul className="mt-3 grid gap-2 text-xs sm:grid-cols-2">{Object.entries(latest.gates).map(([key, passed]) => <li key={key} className="flex items-center gap-2">{passed ? <Check className="h-4 w-4 text-emerald-700" /> : <X className="h-4 w-4 text-rose-700" />}{GATES[key] ?? key}</li>)}</ul>}
        {['testing', 'review', 'approved'].includes(p.status) && <div className="mt-4 flex flex-wrap items-center gap-3"><Button variant="outline" onClick={() => downloadJson({ program_id: p.id,
          decision: p.status === 'review' ? 'approve' : 'pause', evidence_hash: latest?.hash ?? p.definition_hash,
          definition_hash: p.definition_hash, policy_hash: data.policy_hash }, `${p.id}-review.json`)}><Download className="mr-2 h-4 w-4" />{p.status === 'review' ? '下载审核申请' : '下载暂停申请'}</Button>
          <a className="inline-flex items-center gap-1 text-sm text-primary" href={data.review_workflow.startsWith('https://github.com/Mjeemjee/stock-screener/') ? data.review_workflow : '#'} target="_blank" rel="noreferrer">仓库权限审核<ExternalLink className="h-3 w-3" /></a></div>}
      </div>
      <details className="border-t pt-3 text-xs"><summary className="cursor-pointer font-semibold">逐期结果与缺价</summary><div className="mt-3 overflow-x-auto"><table className="w-full min-w-[580px] text-left"><thead><tr>{['入场', '退出', '状态', '策略收益', '同期对照', '基准', 'Rank IC'].map(v => <th key={v} className="p-2">{v}</th>)}</tr></thead>
        <tbody>{own.slice().reverse().map(r => <tr key={r.entry_date} className="border-t"><td className="p-2">{day(r.entry_date)}</td><td className="p-2">{day(r.exit_date)}</td><td className="p-2">{!r.due ? '未到期' : r.branch.complete && r.parent.complete && r.benchmark_pct != null ? '完整' : '到期缺价'}</td>
          <td className="p-2">{metric(r.branch.return_pct, '%')}</td><td className="p-2">{metric(r.parent.return_pct, '%')}</td><td className="p-2">{metric(r.benchmark_pct, '%')}</td><td className="p-2">{metric(r.rank_ic)}</td></tr>)}</tbody></table></div></details>
    </div>}
    {tab === 'history' && <div className="space-y-4"><p className="border-l-2 border-amber-500 pl-3 text-xs leading-relaxed text-amber-900">{p.historical.note}</p>
      <h3 className="text-sm font-semibold">按时间分段的测试折</h3>
      {p.historical.status === 'insufficient_data' && <p className="text-sm text-muted-foreground">部分测试折数据不足，保留缺失状态。</p>}
      {p.historical.folds.some(f => f.rank_ic != null) && <div className="h-48 min-w-0" aria-label="历史分折IC图表"><ResponsiveContainer width="100%" height="100%">
        <BarChart data={p.historical.folds.map((f, i) => ({ ...f, fold: `折 ${i + 1}` }))}><XAxis dataKey="fold" /><YAxis width={45} /><Tooltip formatter={v => metric(Number(v))} /><ReferenceLine y={0} stroke="#64748b" />
          <Bar dataKey="train_rank_ic" name="训练段 Rank IC" fill="#94a3b8" maxBarSize={32} /><Bar dataKey="rank_ic" name="测试段 Rank IC" fill="#207d72" maxBarSize={32} /></BarChart></ResponsiveContainer></div>}
      <div className="overflow-x-auto"><table className="w-full min-w-[780px] text-left text-xs"><thead className="border-b text-muted-foreground"><tr>{['训练区间', '测试区间', '完整期数', 'Rank / Pearson IC', 'ICIR', 'IC 95%区间', 'Q5-Q1', '策略减研究池'].map(v => <th key={v} className="p-2 font-normal">{v}</th>)}</tr></thead>
        <tbody>{p.historical.folds.map(f => <tr key={f.test_start} className="border-b"><td className="p-2">{day(f.train_start)}<br />{day(f.train_end)}</td><td className="p-2">{day(f.test_start)}<br />{day(f.test_end)}</td><td className="p-2">{f.complete} / {f.test_periods}</td>
          <td className="p-2">{metric(f.rank_ic)} / {metric(f.pearson_ic)}</td><td className="p-2">{metric(f.icir)}</td><td className="p-2">{metric(f.ic_lower)} 至 {metric(f.ic_upper)}</td><td className="p-2">{metric(f.q5_q1_pp, ' pp')}</td><td className="p-2">{metric(f.mean_delta_pp, ' pp')}</td></tr>)}</tbody></table></div>
      <p className="text-xs text-muted-foreground">训练末端剔除 {p.historical.folds[0]?.purged ?? 5} 个标签重叠期，再隔离 {p.historical.folds[0]?.embargo ?? 5} 个交易日。IC 区间为历史诊断的近似区块重采样区间。</p>
    </div>}
    {tab === 'hypothesis' && <div className="space-y-4 text-sm leading-relaxed">
      <p>{p.hypothesis}</p><dl className="grid gap-4 sm:grid-cols-2"><div><dt className="text-xs text-muted-foreground">本次改动</dt><dd className="mt-1 break-words">{p.change}</dd></div><div><dt className="text-xs text-muted-foreground">待验证目标</dt><dd className="mt-1">{p.expected}</dd></div></dl>
      <div className="border-y py-3"><p className="text-xs text-muted-foreground">因子公式</p><p className="mt-1 break-words">{formula(p.expression, data.features)}</p>
        <ul className="mt-2 space-y-1 text-xs text-muted-foreground">{p.filters.map((f, i) => <li key={i}>{data.features[f.feature]?.name ?? f.feature}{f.gte != null ? ` >= ${f.gte}` : ''}{f.lte != null ? ` <= ${f.lte}` : ''}</li>)}</ul></div>
      <p className="text-xs text-muted-foreground">来源：{({ predeclared: '预先声明的研究假设', automatic_research: '到期样本驱动的公式研究', owner_proposal: '仓库所有者提交' } as Record<string, string>)[p.discovery.kind] ?? p.discovery.kind} · 创建于 {scanTimeInfo(p.created_at).display}</p>
      {p.discovery.note && <p className="text-xs text-amber-900">{p.discovery.note}{p.discovery.last_label_date ? `，探索标签截至 ${day(p.discovery.last_label_date)}` : ''}</p>}
      <details className="text-xs"><summary className="cursor-pointer">公式、定义与数据版本</summary><pre className="mt-2 max-w-full overflow-x-auto rounded border p-3">{JSON.stringify({ expression: p.expression, filters: p.filters, definition_hash: p.definition_hash, universe_hash: p.universe_hash, engine_version: p.engine_version }, null, 2)}</pre></details>
      <div className="border-t pt-4"><h3 className="font-semibold">决策记录</h3><ol className="mt-3 space-y-3 text-xs">{data.events.filter(e => e.program_id === p.id).map((e, i) => <li key={i} className="border-l-2 pl-3"><span className="text-muted-foreground">{scanTimeInfo(e.at).display}</span><p>{({ created: '创建实验', assessed: '固定关卡评估', paused: '版本变化暂停', pause: '人工暂停', reject: '人工拒绝', approve: '人工审核通过', research_completed: '完成新公式研究', started_by_owner: '人工启动实验' } as Record<string, string>)[e.action] ?? e.action}{e.reason ? ` · ${e.reason}` : ''}{e.actor ? ` · ${e.actor}` : ''}</p></li>)}</ol></div>
    </div>}
  </section>
}

export default function FactorResearch() {
  const { data, loading, error, retry } = useResearch()
  const [tab, setTab] = useState('experiments')
  const [market, setMarket] = useState('ALL')
  const [status, setStatus] = useState('ALL')
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState<string | null>(null)
  const programs = data?.programs.filter(p => (market === 'ALL' || p.market === market) && (status === 'ALL' || p.status === status)
    && `${p.name} ${p.id} ${p.hypothesis}`.toLowerCase().includes(query.trim().toLowerCase())) ?? []
  const chosen = programs.find(p => p.id === selected) ?? programs[0]
  return <AppShell title="因子研究实验室" subtitle="固定研究池 · 独立策略家族 · 未来样本验证"><LabTabs />
    <div className="flex flex-wrap items-center justify-between gap-3 border-b pb-4"><div className="flex flex-wrap gap-x-5 gap-y-2 text-sm">
      <span>研究实验 <strong>{data?.programs.length ?? 0} / {data?.policy.max_programs ?? '-'}</strong></span>
      <span>公式研究 <strong>{data?.searches.length ?? 0} / {data?.policy.max_searches ?? '-'}</strong></span>
      <span>待审核 <strong>{data?.programs.filter(p => p.status === 'review').length ?? 0}</strong></span></div>
      <Button variant="outline" size="icon" onClick={retry} disabled={loading} aria-label="刷新因子研究" title="刷新因子研究"><RefreshCw /></Button></div>
    {loading && !data && <p role="status" className="py-8 text-sm text-muted-foreground">读取研究档案...</p>}
    {error && <div role="alert" className="flex flex-wrap items-center gap-3 py-5 text-sm text-destructive">{error}<Button variant="outline" onClick={retry}><RefreshCw className="mr-2 h-4 w-4" />重试</Button></div>}
    {data && <div className="space-y-5 pt-4">
      <div className="flex flex-wrap gap-x-5 gap-y-2 text-xs text-muted-foreground"><span>{scanTimeInfo(data.generated_at).display}</span>
        <span>自动公式研究：{data.searches.length >= data.policy.max_searches ? '研究轮次已用完' : `等待 / 检查 ${data.policy.discovery_after} 期完整样本`}</span><span>{modelConnection(data)}</span></div>
      <div className="flex flex-wrap gap-1 border-b" role="group" aria-label="因子研究视图">{[['experiments', '研究实验'], ['proposals', '研究提案'], ['universe', '数据与股票池'], ['features', '因子库']].map(([key, label]) => <button key={key} onClick={() => setTab(key)} aria-pressed={tab === key}
        className={`border-b-2 px-3 py-2 text-sm ${tab === key ? 'border-primary font-semibold text-primary' : 'border-transparent text-muted-foreground'}`}>{label}</button>)}</div>
      {tab === 'experiments' && <>
        <div className="flex flex-wrap items-center gap-2"><select aria-label="研究市场" className={control} value={market} onChange={e => setMarket(e.target.value)}><option value="ALL">全部市场</option><option value="US">美股</option><option value="HK">港股</option></select>
          <select aria-label="研究状态" className={control} value={status} onChange={e => setStatus(e.target.value)}><option value="ALL">全部状态</option>{Object.entries(STATUS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select>
          <label className="relative min-w-0 basis-full sm:flex-1 sm:basis-auto sm:max-w-xs"><Search className="pointer-events-none absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" /><input aria-label="搜索研究" value={query} onChange={e => setQuery(e.target.value)} className={`${control} w-full pl-8`} placeholder="搜索研究" /></label></div>
        {!programs.length ? <p className="py-8 text-sm text-muted-foreground">{data.programs.length ? '当前条件下没有研究实验。' : '尚未建立研究实验，等待首次可用的行情池。'}</p> : <div className="overflow-x-auto"><table className="w-full min-w-[690px] text-left text-xs"><thead className="border-b text-muted-foreground"><tr>{['研究 / 家族', '市场', '状态', '本期股票', '到期 / 配对', '配对改善', '重复性'].map(v => <th key={v} className="p-2 font-normal">{v}</th>)}</tr></thead>
          <tbody>{programs.map(p => <tr key={p.id} className={`border-b ${p.id === chosen?.id ? 'bg-muted/40' : ''}`}><td className="p-2"><button className="text-left text-primary hover:underline" aria-label={`查看研究 ${p.id}`} onClick={() => setSelected(p.id)}><span className="flex items-center gap-1"><FlaskConical className="h-3 w-3" />{p.name}</span><span className="mt-1 block text-[10px] text-muted-foreground">第 {p.generation} 代 · {p.discovery.kind === 'automatic_research' ? '新公式研究' : p.parent_id ? '扩展研究' : '独立家族'}</span></button></td>
            <td className="p-2">{p.market}</td><td className="p-2">{STATUS[p.status]}</td><td className="p-2">{p.latest_selection.length}</td><td className="p-2">{p.metrics?.due ?? 0} / {p.metrics?.paired ?? 0}</td><td className="p-2">{metric(p.metrics?.mean_delta_pp, ' pp')}</td><td className="p-2">{metric(p.metrics?.novelty)}</td></tr>)}</tbody></table></div>}
        {chosen && <Detail key={chosen.id} program={chosen} data={data} />}
      </>}
      {tab === 'proposals' && <><ModelResearch data={data} /><ResearchProposal data={data} /><section className="border-t pt-5"><h2 className="text-sm font-semibold">自动研究记录</h2>
        {!data.searches.length ? <p className="py-6 text-sm text-muted-foreground">尚无完成的公式研究轮次。首次触发需要 {data.policy.discovery_after} 期完整结果。</p> : <div className="mt-3 divide-y">{data.searches.slice().reverse().map(search => <details key={search.hash} className="py-3"><summary className="cursor-pointer text-sm">{scanTimeInfo(search.at).display} · {search.market} · {search.candidates.length} 个候选 / {search.candidates.filter(c => c.qualified).length} 个通过探索检查</summary>
          <p className="mt-2 text-xs text-amber-900">探索样本 {search.cohort_count} 期，标签截至 {day(search.last_label_date)}。探索成绩不计入新实验的前瞻成绩。</p>
          <div className="mt-3 overflow-x-auto"><table className="w-full min-w-[620px] text-left text-xs"><thead><tr>{['候选改动', '探索改善', 'Rank IC', '重复性', '信号比例', '探索结果'].map(v => <th className="p-2" key={v}>{v}</th>)}</tr></thead><tbody>{search.candidates.map((c, i) => <tr key={i} className="border-t"><td className="p-2">{c.spec.change}</td><td className="p-2">{metric(c.mean_delta_pp, ' pp')}</td><td className="p-2">{metric(c.rank_ic)}</td><td className="p-2">{metric(c.novelty)}</td><td className="p-2">{metric(c.signal_rate * 100, '%')}</td><td className="p-2">{c.duplicate ? '重复公式' : c.qualified ? '通过探索检查' : '未通过'}</td></tr>)}</tbody></table></div>
        </details>)}</div>}</section></>}
      {tab === 'universe' && <div className="space-y-6">{data.universes.map(u => { const q = data.quality.find(row => row.market === u.market); return <section key={u.market}>
        <div className="flex flex-wrap justify-between gap-2"><h2 className="text-sm font-semibold">{u.market === 'US' ? '美股' : '港股'}固定研究池 · {u.members.length} 只</h2><span className={`text-xs ${q?.status === 'ready' ? 'text-emerald-800' : 'text-amber-800'}`}>有效行情 {q?.valid ?? 0} / {q?.total ?? u.members.length}</span></div>
        <p className="mt-2 text-xs leading-relaxed text-muted-foreground">建立于 {scanTimeInfo(u.created_at).display} · {u.basis}</p><p className="mt-1 text-xs text-muted-foreground">{q ? `最近完成交易日 ${day(q.session)} · ${q.status === 'ready' ? '行情覆盖达标' : '行情覆盖不足，暂停新信号'}` : '等待行情检查'}</p>
        <div className="mt-3 grid grid-cols-1 gap-x-5 divide-y border-y sm:grid-cols-2 lg:grid-cols-3">{u.members.map(m => <div key={m.code} className="min-w-0 py-2 text-xs"><Link className="break-words text-primary" to={`/stock/${encodeURIComponent(m.code)}`}>{m.name}</Link><span className="ml-2 text-muted-foreground">{m.code}</span>{q?.missing[m.code] && <span className="mt-1 block text-amber-800">{q.missing[m.code]}</span>}</div>)}</div>
        <details className="mt-3 text-xs"><summary className="cursor-pointer">研究池版本</summary><code className="mt-2 block break-all">{u.hash}</code></details>
      </section>})}</div>}
      {tab === 'features' && <section><h2 className="text-sm font-semibold">可研究因子与对照因子</h2><div className="mt-3 divide-y border-y">{Object.entries(data.features).map(([key, f]) => <div key={key} className="grid gap-2 py-3 sm:grid-cols-[180px_1fr]"><div className="text-sm">{f.name}<span className="mt-1 block text-[10px] text-muted-foreground">{f.family === 'control' ? '原有趋势对照' : '研究输入'} · {key}</span></div><code className="break-all text-xs text-muted-foreground">{f.formula}</code></div>)}</div></section>}
      <details className="border-t pt-4 text-xs leading-relaxed text-muted-foreground"><summary className="cursor-pointer font-semibold text-foreground">研究预算与评估口径</summary><div className="mt-3 space-y-2">
        <p>固定研究池独立于原策略命中名单。主周期 {data.policy.horizon} 个交易日，决策冻结后的下一开盘入场；每边 {data.policy.cost_bps} bp，压力成本 {data.policy.stress_cost_bps} bp。缺价保持未知，空名单按现金计算。</p>
        <p>最多 {data.policy.max_programs} 个实验、{data.policy.max_searches} 轮公式研究，预留 {data.policy.comparison_budget} 次比较。固定 {data.policy.checkpoints.join(' / ')} 期关卡。已有因子的平均绝对秩相关达到 {data.policy.max_correlation} 时，不通过新增信息检查。</p>
        <p>历史回溯使用当前成员与调整后行情，存在幸存者和复权修订偏差。最差单期不是账户最大回撤，重叠收益不复合为净值。审核通过保留为纸面研究策略。</p>
      </div></details>
    </div>}
  </AppShell>
}
