import { useMemo, useState } from 'react'
import { Link } from 'react-router'
import { ArrowRight, RefreshCw } from 'lucide-react'
import AppShell from '@/components/AppShell'
import { Button } from '@/components/ui/button'
import { useTracking } from '@/hooks/useTracking'
import { scanTimeInfo } from '@/lib/screener'
import { dateLabel, fundingSlots, validationGroups } from '@/lib/validation'
import type { PeriodStats } from '@/lib/validation'

const focus = 'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring'
const percent = (value: number | null) => value === null ? '待定' : `${value > 0 ? '+' : ''}${value.toFixed(2)}%`
const points = (value: number | null) => value === null ? '待定' : `${value > 0 ? '+' : ''}${value.toFixed(2)} 个百分点`
const field = `h-10 min-w-0 max-w-full rounded-md border bg-card px-3 text-sm ${focus}`

function OverlapLesson() {
  const [separated, setSeparated] = useState(false)
  const entries = separated ? [1, 6, 11] : [1, 2, 3]
  const x = (day: number) => 110 + (day - 1) * 40
  return <section aria-labelledby="overlap-title" className="space-y-5">
    <div className="max-w-2xl space-y-3">
      <p className="text-xs font-semibold tracking-widest text-primary">看懂策略验证</p>
      <h2 id="overlap-title" className="font-display text-2xl font-bold leading-snug sm:text-3xl">每天一份成绩，<br className="sm:hidden" />不等于每天一次新验证。</h2>
      <p className="text-sm leading-7 text-muted-foreground">假设每次持有五个交易日。周一和周二选出的股票，接下来会经历很多相同的行情。切换下面的时间线，看看怎样把持有时间错开。</p>
    </div>
    <div className="overflow-hidden rounded-lg border bg-card">
      <div role="group" aria-label="时间线模式" className="flex flex-wrap gap-2 border-b px-4 py-3 sm:px-6">
        {[false, true].map(value => <button key={String(value)} type="button" aria-pressed={separated === value}
          onClick={() => setSeparated(value)} className={`rounded-md px-3 py-2 text-sm font-medium ${focus} ${separated === value ? 'bg-primary text-primary-foreground' : 'bg-secondary text-secondary-foreground hover:bg-accent'}`}>
          {value ? '结束后再开始' : '每天开始一期'}
        </button>)}
      </div>
      <div className="grid lg:grid-cols-[minmax(0,1fr)_230px]">
        <figure className="min-w-0 px-4 py-5 sm:px-6">
          <div className={`overflow-x-auto rounded-sm ${focus}`} tabIndex={0} role="region" aria-label="可横向滚动的持有期示意">
            <svg viewBox="0 0 780 235" className="min-w-[580px] w-full" role="img" aria-labelledby="timeline-title" aria-describedby="timeline-desc">
              <title id="timeline-title">{separated ? '三期持有时间不重叠' : '三期持有时间重叠'}</title>
              <desc id="timeline-desc">{entries.map((day, i) => `第${i + 1}期：第${day}个交易日开盘买入，第${day + 5}个交易日开盘卖出`).join('；')}。均为概念示意，不是真实收益。</desc>
              {!separated && <rect x={x(3)} y="37" width={120} height={158} fill="#b45309" fillOpacity="0.09" />}
              {[1, 6, 11, 16].map(day => <g key={day}>
                <line x1={x(day)} x2={x(day)} y1="35" y2="195" stroke="#dbe0e8" strokeDasharray="3 5" />
                <text x={x(day)} y="22" textAnchor="middle" fontSize="13" fill="#606a7c">第 {day} 日</text>
              </g>)}
              {entries.map((day, i) => <g key={i}>
                <text x="12" y={69 + i * 54} fontSize="14" fill="#152036">第 {i + 1} 期</text>
                <rect x={x(day)} y={47 + i * 54} width={200} height="34" rx="6" fill={separated ? '#1456a4' : '#edf3fc'} stroke="#1456a4" />
                <circle cx={x(day)} cy={64 + i * 54} r="4" fill={separated ? 'white' : '#1456a4'} />
                <text x={x(day) + 100} y={69 + i * 54} textAnchor="middle" fontSize="13" fill={separated ? 'white' : '#1456a4'}>第 {day} 日买 → 第 {day + 5} 日卖</text>
              </g>)}
              <text x="110" y="224" fontSize="12" fill="#606a7c">横轴是交易日；每次都在开盘进入和退出。</text>
            </svg>
          </div>
          <figcaption className="mt-2 text-xs text-muted-foreground">手机可左右滑动。示意中的下一份名单已在买入前确定。</figcaption>
        </figure>
        <div className={`flex flex-col justify-center gap-3 border-t px-5 py-5 lg:border-l lg:border-t-0 ${separated ? 'bg-accent/60' : 'bg-amber-50/60'}`} aria-live="polite">
          <p className="font-semibold">{separated ? '三段不同的持有时间' : '三期共享一段行情'}</p>
          <p className="text-sm leading-6 text-muted-foreground">{separated ? '上一期退出，下一期才进入。时间不重叠，重复使用行情的问题就少了。' : '这三期共同经历了第 3 日到第 6 日开盘之间的涨跌。不能把它们当作三次独立考试。'}</p>
          <p className="text-xs leading-5 text-muted-foreground">不重叠也可能遇到同一轮牛市或熊市，仍需更长时间的验证。</p>
        </div>
      </div>
    </div>
  </section>
}

function Score({ title, stats, separated }: { title: string; stats: PeriodStats; separated?: boolean }) {
  return <article className={`rounded-lg border p-4 sm:p-5 ${separated ? 'border-primary/30 bg-accent/40' : 'bg-card'}`}>
    <h4 className="text-sm font-semibold">{title}</h4>
    <div className="my-3 flex items-baseline gap-2"><span className="tnum text-3xl font-semibold">{stats.complete}</span><span className="text-sm text-muted-foreground">{separated ? '段完整持有期' : '期完整成绩'}</span></div>
    <p className="mb-4 text-xs text-muted-foreground">{stats.pending} 期未到期 · {stats.missing} 期缺价格</p>
    <dl className="space-y-2 text-sm tnum">
      <div className="flex flex-wrap justify-between gap-2"><dt className="text-muted-foreground">平均单期净收益</dt><dd>{percent(stats.net)}</dd></div>
      <div className="flex flex-wrap justify-between gap-2"><dt className="text-muted-foreground">同期指数</dt><dd>{percent(stats.benchmark)}</dd></div>
      <div className="flex flex-wrap justify-between gap-2 border-t pt-2"><dt className="text-muted-foreground">比指数多赚 / 少赚</dt><dd className="font-medium">{points(stats.excess)}</dd></div>
    </dl>
    <p className="mt-4 text-xs leading-5 text-muted-foreground">{separated ? (stats.missing ? '抽取的到期期次中有缺价，整体均值保持待定，不用其他期次替补。' : '仅统计按日期抽取的已完成期次。更多新行情仍在等待。') : '仅用最终排序、原排序、指数都有完整价格的期次；可能共享行情。'}</p>
  </article>
}

function FundingLesson() {
  const [day, setDay] = useState(1)
  const slots = fundingSlots(day, 10000)
  const invested = slots.filter(slot => slot.start !== null).length * 2000
  return <section aria-labelledby="funding-title" className="space-y-4 border-t pt-7">
    <div className="max-w-2xl space-y-2">
      <p className="text-xs font-semibold text-primary">如果每天都想参与</p>
      <h2 id="funding-title" className="font-display text-xl font-semibold">一笔本金，分五份轮流使用</h2>
      <p className="text-sm leading-7 text-muted-foreground">假设本金 10,000 元，每天用一份 2,000 元，持有五个交易日。第六日第一份退出，再用这份资金进入下一期。每天新增一期，也要受到总本金限制。</p>
    </div>
    <div className="rounded-lg border bg-card p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <label htmlFor="funding-day" className="text-sm font-semibold">查看第 <span className="tnum">{day}</span> 个交易日</label>
        <span className="text-xs text-muted-foreground">概念演示 · 不代表账户收益</span>
      </div>
      <input id="funding-day" aria-label="资金轮转交易日" className={`my-5 w-full ${focus}`} type="range" min="1" max="11" step="1" value={day} onChange={e => setDay(Number(e.target.value))} />
      <div className="grid gap-2 sm:grid-cols-5" aria-live="polite">
        {slots.map(slot => <div key={slot.slot} className={`rounded-md border p-3 ${slot.entering ? 'border-primary bg-accent' : slot.start === null ? 'bg-secondary/50' : 'bg-card'}`}>
          <p className="text-xs text-muted-foreground">第 {slot.slot} 份</p><p className="my-2 tnum text-lg font-semibold">2,000 <span className="text-xs font-normal">元</span></p>
          <p className="text-xs font-medium">{slot.start === null ? '现金等待' : slot.renewed ? '退出后再次投入' : slot.entering ? '今天投入' : '继续持有'}</p>
          <p className="mt-1 text-xs text-muted-foreground">{slot.start === null ? `第 ${slot.slot} 日开始` : `第 ${slot.start} → ${slot.exit} 日`}</p>
        </div>)}
      </div>
      <p className="mt-4 text-sm tnum" data-testid="funding-total">投入本金 {invested.toLocaleString('en-US')} 元 ＋ 等待现金 {(10000 - invested).toLocaleString('en-US')} 元 ＝ 10,000 元</p>
      <p className="mt-2 text-xs leading-5 text-muted-foreground">本图假设价格不变、忽略费用，并允许退出后立即复用资金。真实模拟还要处理涨跌、交易费、滑点、资金到账和重复持仓；当前没有据此计算实际账户净值。</p>
    </div>
  </section>
}

export default function Validation() {
  const { data, loading, error, retry } = useTracking()
  const [market, setMarket] = useState('US')
  const [horizon, setHorizon] = useState(5)
  const [strategy, setStrategy] = useState('oversold_watch')
  const [version, setVersion] = useState('')
  const [showAll, setShowAll] = useState(false)
  const result = useMemo(() => data ? validationGroups(data) : { groups: [], invalid: 0 }, [data])
  const matching = result.groups.filter(g => g.market === market && g.horizon === horizon)
  const versions = [...new Set(matching.map(g => g.version))]
  const chosenVersion = versions.includes(version) ? version : versions[0]
  const choices = matching.filter(g => g.version === chosenVersion)
  const group = choices.find(g => g.strategy === strategy) ?? choices[0]
  const periods = group ? (showAll ? group.periods : group.periods.slice(0, 20)) : []
  return <AppShell title="策略验证" subtitle="看懂期数重叠 · 用真实跟踪记录检查证据">
    <div className="space-y-8">
      <OverlapLesson />
      <section aria-labelledby="actual-title" className="space-y-4 border-t pt-7">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-2"><h2 id="actual-title" className="font-display text-xl font-semibold">你的真实跟踪，积累了多少证据？</h2>
            <p className="text-sm text-muted-foreground">同一策略、市场、持有期和版本，分别看全部完整成绩与不重叠的日期对照。</p></div>
          <Button size="icon" variant="outline" disabled={loading} aria-label="刷新验证数据" onClick={retry}><RefreshCw className="h-4 w-4" /></Button>
        </div>
        {loading && !data && <p role="status" className="rounded-md border p-5 text-sm text-muted-foreground">正在读取真实跟踪记录…</p>}
        {error && <div role="alert" className="rounded-md border border-destructive/30 p-4 text-sm text-destructive">{error}。请点击刷新验证数据重试。{data && '下方保留上次读取的记录，请核对更新时间。'}</div>}
        {data && <>
          <p className="text-xs text-muted-foreground">数据更新：{scanTimeInfo(data.generated_at).display}。{loading && '正在刷新…'}</p>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <label className="flex min-w-0 flex-col gap-1.5 text-xs text-muted-foreground" htmlFor="validation-market">市场<select id="validation-market" aria-label="市场" className={field} value={market} onChange={e => setMarket(e.target.value)}><option value="US">美股</option><option value="HK">港股</option></select></label>
            <label className="flex min-w-0 flex-col gap-1.5 text-xs text-muted-foreground" htmlFor="validation-horizon">持有期<select id="validation-horizon" aria-label="持有期" className={field} value={horizon} onChange={e => setHorizon(Number(e.target.value))}>{[5, 20, 60].map(v => <option key={v} value={v}>{v} 个交易日</option>)}</select></label>
            <label className="flex min-w-0 flex-col gap-1.5 text-xs text-muted-foreground" htmlFor="validation-version">规则版本<select id="validation-version" aria-label="规则版本" className={field} disabled={!versions.length} value={chosenVersion ?? ''} onChange={e => setVersion(e.target.value)}>{!versions.length && <option value="">暂无版本</option>}{versions.map((v, i) => <option key={v} value={v}>{i === 0 ? '最近版本' : '历史版本'} · {v.slice(0, 10)}</option>)}</select></label>
            <label className="flex min-w-0 flex-col gap-1.5 text-xs text-muted-foreground" htmlFor="validation-strategy">选股策略<select id="validation-strategy" aria-label="选股策略" className={field} disabled={!choices.length} value={group?.strategy ?? ''} onChange={e => setStrategy(e.target.value)}>{!choices.length && <option value="">暂无策略</option>}{choices.map(g => <option key={g.strategy} value={g.strategy}>{g.name}</option>)}</select></label>
          </div>
          {result.invalid > 0 && <p role="status" className="text-xs text-amber-800">全档案中有 {result.invalid} 条记录缺少可核对的日期或版本，未纳入对照。请核查数据后重新刷新。</p>}
          {!group ? <p className="rounded-md border p-5 text-sm text-muted-foreground">当前筛选下暂无可比较的前瞻记录。历史导入不参与这项统计。</p> : <div className="space-y-4" data-testid="actual-evidence">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm"><h3 className="font-semibold">{group.name}</h3><span className="text-xs text-muted-foreground">{group.periods.length} 个不同入场日 · 已合并 {group.duplicates} 次重复扫描</span></div>
            <div className="grid gap-3 md:grid-cols-2"><Score title="每天观察 · 全部完整期次" stats={group.all} /><Score title="日期对照 · 不重叠期次" stats={group.separated} separated /></div>
            <div className="rounded-md border-l-4 border-primary bg-card px-4 py-3 text-sm leading-6">
              <p className="font-medium">{group.separated.complete === 0 ? '目前还没有完整的不重叠持有期。' : `目前有 ${group.separated.complete} 段完整、不重叠的持有期。`}</p>
              <p className="text-muted-foreground">这些数字说明证据积累到了哪里，不会自动给策略贴上“成熟”标签。还要看新的行情、增加费用后的表现，以及亏损能否承受。</p>
            </div>
            <p className="text-xs leading-6 text-muted-foreground">两栏均为平均单期收益，不是账户累计收益。沿用每边 {data.protocol.cost_bps_per_side / 100}% 的费用；{market === 'US' ? '标普 500' : '恒生指数'}为同期价格参照，不扣交易费。缺价不填零、不重新分配权重。</p>
            <details className="rounded-md border bg-card p-4" open>
              <summary className={`cursor-pointer text-sm font-medium ${focus}`}>逐期核对：哪些计入日期对照？</summary>
              <p className="my-3 text-xs leading-6 text-muted-foreground">从本版本最早的入场日开始，上一期预计结束后再取下一期。先按日期选定位置，再看收益；缺价的期次仍占据原来的位置。这是已有记录的对照分析，新一轮正式验证仍需事先固定起点与规则。</p>
              <div className={`overflow-x-auto ${focus}`} role="region" aria-label="逐期不重叠对照" tabIndex={0}>
                <table className="w-full min-w-[670px] text-left text-xs tnum">
                  <caption className="sr-only">{group.name}，{horizon} 个交易日，不同入场日的日期对照与收益</caption>
                  <thead><tr className="border-b text-muted-foreground">{['计划买入 → 卖出', '日期对照', '数据状态', '组合净收益', '同期指数'].map(s => <th key={s} scope="col" className="p-2 font-medium">{s}</th>)}</tr></thead>
                  <tbody>{periods.map(p => <tr key={p.row.snapshot_id} className={`border-b last:border-0 ${p.separated ? 'bg-accent/40' : ''}`}>
                    <td className="whitespace-nowrap p-2">{dateLabel(p.entry)} → {dateLabel(p.exit)}</td>
                    <td className="p-2">{p.separated ? '计入对照' : '与前期重叠'}</td>
                    <td className="p-2">{p.state === 'complete' ? '价格完整' : p.state === 'missing' ? '缺价格，保留位置' : '未到期'}</td>
                    <td className="p-2">{p.state === 'complete' ? percent(p.row.baskets.selected.return_pct) : '待定'}</td>
                    <td className="p-2">{p.state === 'complete' ? percent(p.row.benchmark_pct) : '待定'}</td>
                  </tr>)}</tbody>
                </table>
              </div>
              {group.periods.length > 20 && <button type="button" onClick={() => setShowAll(v => !v)} className={`mt-3 text-sm text-primary underline ${focus}`}>{showAll ? '收起较长期次' : `查看全部 ${group.periods.length} 期`}</button>}
            </details>
          </div>}
        </>}
        <div className="flex flex-wrap gap-x-5 gap-y-3 text-sm"><Link className={`inline-flex items-center gap-1 text-primary underline underline-offset-4 ${focus}`} to="/tracking">查看股票与逐期跟踪 <ArrowRight className="h-3 w-3" /></Link><Link className={`text-primary underline underline-offset-4 ${focus}`} to="/lab/research">查看因子研究的验收条件</Link></div>
      </section>
      <FundingLesson />
      <section aria-labelledby="next-title" className="border-t pt-7">
        <h2 id="next-title" className="font-display text-xl font-semibold">接下来，怎样积累更可靠的证据？</h2>
        <ol className="mt-4 grid gap-4 text-sm sm:grid-cols-3">
          {[['先固定规则', '提前确定起点、持有期和成本。规则改了，就另开版本，保留旧成绩。'], ['继续接收新成绩', '每天记录，同时关注不重叠的时段。不能看到结果以后再挑赚钱的期次。'], ['再复核是否稳定', '检查不同起点、不同市场阶段、费用和亏损。时间不重叠，也不保证完全独立。']].map(([title, text], i) => <li key={title} className="border-t-2 border-primary/30 pt-3"><p className="font-semibold"><span className="mr-2 tnum text-primary">{i + 1}.</span>{title}</p><p className="mt-2 leading-6 text-muted-foreground">{text}</p></li>)}
        </ol>
      </section>
    </div>
  </AppShell>
}
