import { useState } from 'react'
import LabTabs from '@/components/LabTabs'
import { Link } from 'react-router'
import { Check, Clock3, Download, ExternalLink, GitFork, RefreshCw, X } from 'lucide-react'
import { Bar, BarChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import AppShell from '@/components/AppShell'
import { Button } from '@/components/ui/button'
import { useLab } from '@/hooks/useLab'
import { formatNumber, scanTimeInfo } from '@/lib/screener'
import type { LabData, LabTrial } from '@/types/lab'

const STATUS = { testing: '验证中', review: '待晋级审核', rejected: '已淘汰', approved: '已批准', paused: '已暂停' }
const GATES: Record<string, string> = { coverage: '配对覆盖率', signal_rate: '有效信号比例', independent: '非重叠样本',
  improvement: '相对母策略改善', uncertainty: '修正后的区间下界', benchmark: '扣费后跑赢基准', stress_cost: '高成本压力测试', risk: '最差单期损失' }
const PARAMETERS: Record<string, string> = { near_high_pct: '距年内高点上限', near_low_pct: '距年内低点上限',
  min_turnover: '最低成交额', min_market_val: '最低市值', pe_ttm_max: 'PE 上限', dividend_min: '最低股息率' }
const metric = (value: number | null | undefined, unit = ' pp') => value == null ? '-' : formatNumber(value) + unit

function requestReview(trial: LabTrial, policyHash: string) {
  const evidence = trial.assessments.at(-1)
  const blob = new Blob([JSON.stringify({ trial_id: trial.id, evidence_hash: evidence?.hash ?? trial.definition_hash,
    policy_hash: policyHash, definition_hash: trial.definition_hash }, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `${trial.id}-review.json`
  anchor.click()
  URL.revokeObjectURL(url)
}

function Detail({ trial, data }: { trial: LabTrial; data: LabData }) {
  const assessment = trial.assessments.at(-1)
  const values = trial.metrics
  const chart = data.observations.filter(row => row.trial_id === trial.id && row.due && row.branch.complete && row.parent.complete)
    .map(row => ({ date: String(row.entry_date).slice(4), delta: (row.branch.return_pct ?? 0) - (row.parent.return_pct ?? 0) }))
  const parent = data.trials.find(row => row.id === trial.parent_id)?.name ?? data.parents.find(row => row.id === trial.parent_id)?.name ?? trial.root_id
  return <section aria-label="实验详情" className="min-w-0 border-t pt-5">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0"><h2 className="flex items-center gap-2 text-base font-semibold"><GitFork className="h-4 w-4 shrink-0" />{trial.name}</h2>
        <p className="mt-1 break-all font-mono text-[11px] text-muted-foreground">{trial.id}</p></div>
      <span className="text-xs font-medium text-primary">{STATUS[trial.status]}</span>
    </div>
    <p className="mt-3 break-words text-sm">{parent} / 第 {trial.generation} 代 / {trial.market === 'US' ? '美股' : '港股'}</p>
    <p className="mt-2 text-xs text-muted-foreground">创建于 {scanTimeInfo(trial.created_at).display}</p>
    <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
      <div><dt className="text-xs text-muted-foreground">唯一改动</dt><dd className="mt-1 break-words">{PARAMETERS[trial.change.parameter] ?? trial.change.parameter}：{formatNumber(trial.change.from)} → {formatNumber(trial.change.to)}</dd></div>
      <div><dt className="text-xs text-muted-foreground">已配对 / 已到期</dt><dd className="mt-1 tnum">{values?.paired ?? 0} / {values?.due ?? 0}</dd></div>
      <div><dt className="text-xs text-muted-foreground">平均配对改善</dt><dd className="mt-1 tnum">{metric(values?.mean_delta_pp)}</dd></div>
      <div><dt className="text-xs text-muted-foreground">高成本下相对基准</dt><dd className="mt-1 tnum">{metric(values?.stress_excess_pp)}</dd></div>
      <div><dt className="text-xs text-muted-foreground">最差单期收益</dt><dd className="mt-1 tnum">{metric(values?.worst_period_pct, '%')}</dd></div>
      <div><dt className="text-xs text-muted-foreground">非重叠配对样本</dt><dd className="mt-1 tnum">{values?.independent ?? 0}</dd></div>
    </dl>
    <p className="mt-4 text-sm leading-relaxed">{trial.hypothesis}</p>
    <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{trial.expected}</p>
    <div className="mt-5">
      <h3 className="text-sm font-semibold">逐期配对差值</h3>
      {chart.length ? <div className="mt-3 h-48 min-w-0" aria-label="配对差值图表"><ResponsiveContainer width="100%" height="100%">
        <BarChart data={chart}><XAxis dataKey="date" tick={{ fontSize: 10 }} /><YAxis width={36} tick={{ fontSize: 10 }} />
          <Tooltip formatter={value => [metric(Number(value)), '分支减母策略']} /><ReferenceLine y={0} stroke="#64748b" />
          <Bar dataKey="delta" fill="#207d72" maxBarSize={24} /></BarChart>
      </ResponsiveContainer></div> : <p className="py-6 text-sm text-muted-foreground">尚无到期配对数据。</p>}
    </div>
    <div className="border-t pt-4">
      <h3 className="text-sm font-semibold">晋级检查{assessment ? ` · ${assessment.checkpoint} 期关卡` : ''}</h3>
      {!assessment ? <p className="mt-2 text-xs text-muted-foreground">等待首个 {data.policy.checkpoints[0]} 期固定关卡。</p> : <ul className="mt-3 grid gap-2 text-xs sm:grid-cols-2">{Object.entries(assessment.gates).map(([key, passed]) => <li key={key} className="flex items-center gap-2">
        {passed ? <Check className="h-4 w-4 text-emerald-700" /> : <X className="h-4 w-4 text-rose-700" />}{GATES[key] ?? key}</li>)}</ul>}
      {(trial.status === 'review' || trial.status === 'testing') && <div className="mt-4 flex flex-wrap items-center gap-2">
        <Button variant="outline" onClick={() => requestReview(trial, data.policy_hash)}><Download className="mr-2 h-4 w-4" />{trial.status === 'review' ? '下载审核申请' : '下载暂停申请'}</Button>
        <a href={data.review_workflow.startsWith('https://github.com/Mjeemjee/stock-screener/') ? data.review_workflow : '#'} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sm text-primary">仓库权限审核<ExternalLink className="h-3 w-3" /></a>
        <code className="w-full break-all text-[10px] text-muted-foreground">{assessment?.hash ?? trial.definition_hash}</code>
      </div>}
    </div>
    <details className="mt-5 border-t pt-4 text-xs"><summary className="cursor-pointer font-medium">完整参数与版本</summary>
      <pre className="mt-3 max-w-full overflow-x-auto rounded border bg-muted/30 p-3 text-[11px]">{JSON.stringify(trial.params, null, 2)}</pre>
      <p className="mt-2 break-all font-mono text-muted-foreground">定义 {trial.definition_hash}</p></details>
    <div className="mt-5 border-t pt-4"><h3 className="text-sm font-semibold">决策记录</h3>
      <ol className="mt-3 space-y-3 text-xs">{data.events.filter(row => row.trial_id === trial.id).map((row, index) => <li key={index} className="border-l-2 border-border pl-3">
        <span className="text-muted-foreground">{scanTimeInfo(row.at).display}</span><p className="mt-1">{({ created: '创建分支', assessed: '到期评估', paused: '暂停验证', approve: '人工批准', reject: '人工拒绝' } as Record<string, string>)[row.action] ?? row.action}{row.checkpoint ? ` · ${row.checkpoint} 期` : ''}{row.reason ? ` · ${row.reason}` : ''}{row.actor ? ` · ${row.actor}` : ''}</p></li>)}</ol>
    </div>
  </section>
}

export default function StrategyLab() {
  const { data, error, loading, retry } = useLab()
  const [market, setMarket] = useState('ALL')
  const [status, setStatus] = useState('ALL')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const trials = data?.trials.filter(row => (market === 'ALL' || row.market === market) && (status === 'ALL' || row.status === status)) ?? []
  const selectedTrial = trials.find(row => row.id === selectedId) ?? trials[0]
  return <AppShell title="策略进化实验室" subtitle="独立前瞻验证 · 有限分支 · 人工晋级">
    <LabTabs />
    <div className="flex flex-wrap items-center justify-between gap-3 border-b pb-4">
      <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm"><span>累计试验 <strong>{data?.trials.length ?? 0} / {data?.policy.max_trials ?? '-'}</strong></span><span>待审核 <strong>{data?.trials.filter(row => row.status === 'review').length ?? 0}</strong></span><span>正式批准 <strong>{data?.trials.filter(row => row.status === 'approved').length ?? 0}</strong></span></div>
      <Button variant="outline" size="icon" aria-label="刷新实验室数据" title="刷新实验室数据" onClick={retry} disabled={loading}><RefreshCw /></Button>
    </div>
    {loading && !data && <p role="status" className="py-8 text-sm text-muted-foreground">读取实验档案...</p>}
    {error && <div role="alert" className="flex flex-wrap items-center gap-3 py-5 text-sm text-destructive">{error}<Button variant="outline" onClick={retry}><RefreshCw className="mr-2 h-4 w-4" />重试</Button></div>}
    {data && <div className="space-y-6 pt-5">
      <div className="flex flex-wrap items-center gap-3">
        <div role="group" aria-label="实验市场" className="flex rounded-md border p-0.5">{[['ALL', '全部'], ['US', '美股'], ['HK', '港股']].map(([value, label]) => <button key={value} type="button" aria-pressed={market === value} onClick={() => setMarket(value)} className={`rounded-sm px-3 py-1.5 text-sm ${market === value ? 'bg-primary text-primary-foreground' : 'text-muted-foreground'}`}>{label}</button>)}</div>
        <select aria-label="实验状态" value={status} onChange={e => setStatus(e.target.value)} className="h-9 max-w-full rounded-md border bg-background px-2 text-sm"><option value="ALL">全部状态</option>{Object.entries(STATUS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
        <span className="text-xs text-muted-foreground">{scanTimeInfo(data.generated_at).display}</span>
      </div>
      <section aria-label="母策略进度"><h2 className="text-sm font-semibold">母策略准备情况</h2>
        <div className="mt-3 divide-y border-y">{data.parents.filter(row => market === 'ALL' || row.market === market).map(parent => <div key={parent.id} className="grid min-w-0 gap-2 py-3 sm:grid-cols-[1fr_180px_120px] sm:items-center">
          <div className="min-w-0 text-sm">{parent.name}<span className="ml-2 text-xs text-muted-foreground">{parent.market}</span><span className="mt-1 block font-mono text-[10px] text-muted-foreground">{parent.source_version.slice(0, 10)}</span></div>
          <div><progress aria-label={`${parent.name} ${parent.market} 到期进度`} value={Math.min(parent.matured, data.policy.spawn_after)} max={data.policy.spawn_after} className="h-1.5 w-full accent-emerald-700" /><span className="block text-[11px] text-muted-foreground">可评估期数 {parent.matured} / {data.policy.spawn_after}</span></div>
          <span className="flex items-center gap-1 text-xs text-muted-foreground"><Clock3 className="h-3 w-3 shrink-0" />{!parent.supported ? '暂无分支模板' : parent.matured < data.policy.spawn_after ? '等待样本到期' : '等待调度 / 已派生'}</span>
        </div>)}</div>
      </section>
      <section><h2 className="text-sm font-semibold">实验分支</h2>
        {!trials.length ? <div className="border-b py-8 text-sm text-muted-foreground">{data.trials.length ? '当前条件下没有实验。' : '尚未生成分支。母策略达到探索门槛后，下一轮自动创建实验。'}<Link to="/tracking" className="ml-2 text-primary underline underline-offset-4">查看收益追踪</Link></div> : <div className="mt-3 overflow-x-auto"><table className="w-full min-w-[600px] text-left text-xs"><thead className="border-b text-muted-foreground"><tr>{['分支 / 世代', '市场', '状态', '到期 / 配对', '配对改善', '最差单期'].map(label => <th key={label} className="whitespace-nowrap p-2 font-normal">{label}</th>)}</tr></thead><tbody>{trials.map(trial => <tr key={trial.id} className={`border-b ${trial.id === selectedTrial?.id ? 'bg-muted/50' : ''}`}><td className="p-2"><button onClick={() => setSelectedId(trial.id)} aria-label={`查看实验 ${trial.id}`} className="text-left text-primary hover:underline"><span className="flex items-center gap-1"><GitFork className="h-3 w-3" />{trial.name}</span><span className="mt-1 block text-[10px] text-muted-foreground">第 {trial.generation} 代 · {trial.id.slice(-6)}</span></button></td><td className="p-2">{trial.market}</td><td className="whitespace-nowrap p-2">{STATUS[trial.status]}</td><td className="p-2 tnum">{trial.metrics?.due ?? 0} / {trial.metrics?.paired ?? 0}</td><td className="whitespace-nowrap p-2 tnum">{metric(trial.metrics?.mean_delta_pp)}</td><td className="whitespace-nowrap p-2 tnum">{metric(trial.metrics?.worst_period_pct, '%')}</td></tr>)}</tbody></table></div>}
      </section>
      {selectedTrial && <Detail trial={selectedTrial} data={data} />}
      <details className="border-t pt-4 text-xs leading-relaxed"><summary className="cursor-pointer font-semibold">研究规则与晋级条件</summary><div className="mt-3 space-y-2 text-muted-foreground">
        <p>只收紧母策略条件并继承排名；每个分支只改一个参数。每代最多 {data.policy.children_per_parent} 个分支，最多 {data.policy.max_generations} 代、{data.policy.max_trials} 个累计试验、{data.policy.max_active} 个并行观察分支。</p>
        <p>主周期 {data.policy.horizon} 交易日；固定在 {data.policy.checkpoints.join(' / ')} 个到期样本评估。买卖每边 {data.policy.cost_bps} bp，压力测试 {data.policy.stress_cost_bps} bp。配对覆盖率至少 {data.policy.min_coverage * 100}%，非重叠样本至少 {data.policy.min_independent_periods} 期；区间下界采用多试验与固定关卡修正。</p>
        <p>未到期和缺价不是失败或零收益。失败记录不删除。最差单期不是组合最大回撤，重叠收益不复合为净值；待审核也不代表已经证明未来有效。</p>
        <p>正式晋级需要仓库权限、当前证据哈希和未改变的母策略版本。批准后在后续扫描生效，不自动下单。</p>
      </div></details>
    </div>}
  </AppShell>
}
