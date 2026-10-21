import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { Download, RefreshCw } from 'lucide-react'
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import AppShell from '@/components/AppShell'
import LabTabs from '@/components/LabTabs'
import { Button } from '@/components/ui/button'
import { dataUrl } from '@/lib/dataSource'
import { downloadJson } from '@/lib/research'
import { scanTimeInfo } from '@/lib/screener'
import { isLongReport, type LongReport } from '@/lib/longResearch'

const names: Record<string, string> = { combined: '两因子组合', momentum: '纯长期动量', liquidity: '纯流动性' }
const pct = (v: number | null | undefined, suffix = '%') => v == null ? '-' : `${v.toFixed(2)}${suffix}`
const day = (v: number) => String(v).replace(/^(\d{4})(\d{2})(\d{2})$/, '$1-$2-$3')

export default function LongHorizon() {
  const [data, setData] = useState<LongReport | null>(null)
  const [error, setError] = useState('')
  const [refresh, setRefresh] = useState(0)
  const [market, setMarket] = useState('US')
  const [tab, setTab] = useState('forward')
  useEffect(() => {
    const abort = new AbortController()
    setError('')
    fetch(dataUrl('long_research.json'), { signal: abort.signal }).then(r => { if (!r.ok) throw new Error('长期研究数据暂不可用'); return r.json() })
      .then(v => { if (!isLongReport(v)) throw new Error('长期研究数据不完整'); setData(v) })
      .catch(e => { if (!abort.signal.aborted) setError(e instanceof Error ? e.message : '读取失败') })
    return () => abort.abort()
  }, [refresh])
  const m = data?.markets.find(x => x.market === market)
  const rows = data?.cohorts.filter(x => x.market === market) ?? []
  return <AppShell title="流动性与长期动量" subtitle="独立研究 · 21 交易日周期"><LabTabs />
    <div className="flex flex-wrap items-center justify-between gap-3 border-b pb-3"><div className="flex gap-1" role="group" aria-label="长期研究市场">
      {['US', 'HK'].map(key => <button key={key} aria-pressed={market === key} className={`rounded px-3 py-2 text-sm ${market === key ? 'bg-primary text-primary-foreground' : 'bg-muted'}`} onClick={() => setMarket(key)}>{key === 'US' ? '美股' : '港股'}</button>)}</div>
      <Button variant="outline" size="icon" aria-label="刷新长期研究" title="刷新长期研究" onClick={() => setRefresh(x => x + 1)}><RefreshCw /></Button></div>
    {error && <div role="alert" className="flex flex-wrap items-center gap-3 py-5 text-sm text-destructive">{error}<Button variant="outline" onClick={() => setRefresh(x => x + 1)}>重试</Button></div>}
    {!data && !error && <p role="status" className="py-6 text-sm">读取研究档案...</p>}
    {data && m && <div className="space-y-5 pt-4">
      <p className="text-xs text-muted-foreground">{scanTimeInfo(data.generated_at).display} · 数据覆盖 {m.quality.valid} / {m.quality.total} · 最近完成交易日 {day(m.quality.session)}</p>
      {m.quality.status !== 'ready' && <p className="border-l-2 border-amber-500 pl-3 text-sm text-amber-900">行情不足，暂停生成新信号；已冻结的研究期仍保留。</p>}
      <div className="grid grid-cols-2 gap-x-5 gap-y-4 border-y py-4 sm:grid-cols-4">
        {[['完整 / 到期', `${m.metrics.paired} / ${m.metrics.due}`], ['扣费平均收益', pct(m.metrics.mean_net_pct)], ['相对纯动量', pct(m.metrics.mean_delta_pp, ' pp')], ['验证阶段', m.metrics.stage]].map(([label, value]) => <div key={label} className="min-w-0"><span className="text-xs text-muted-foreground">{label}</span><p className="mt-1 break-words text-base font-semibold">{value}</p></div>)}
      </div>
      <div className="flex flex-wrap gap-4 border-b text-sm" role="group" aria-label="长期研究视图">{[['forward', '前瞻记录'], ['history', '历史诊断'], ['protocol', '验证进度']].map(([key, label]) => <button key={key} aria-pressed={tab === key} className={`border-b-2 pb-2 ${tab === key ? 'border-primary font-semibold text-primary' : 'border-transparent'}`} onClick={() => setTab(key)}>{label}</button>)}</div>
      {tab === 'forward' && <section className="space-y-4"><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-sm font-semibold">真实创建后的独立研究期</h2><Button variant="outline" disabled={!rows.length} onClick={() => downloadJson(rows, `long-horizon-${market}.json`)}><Download className="mr-2 h-4 w-4" />导出研究期</Button></div>
        {!rows.length ? <p className="py-5 text-sm text-muted-foreground">尚无行情覆盖达标的新研究期</p> : <div className="overflow-x-auto"><table className="w-full min-w-[650px] text-left text-xs"><thead><tr>{['冻结时间', '计划入场', '计划退出', '组合扣费', '纯动量', '纯流动性', '状态'].map(v => <th key={v} className="p-2 font-normal text-muted-foreground">{v}</th>)}</tr></thead><tbody>{rows.slice().reverse().map(r => <tr key={r.id} className="border-t"><td className="p-2">{scanTimeInfo(r.frozen_at).display}</td><td className="p-2">{day(r.entry_date)}</td><td className="p-2">{day(r.exit_date)}</td>{['combined', 'momentum', 'liquidity'].map(k => <td key={k} className="p-2">{pct(r.baskets[k].return_pct)}</td>)}<td className="p-2">{!r.due ? '等待到期' : r.baskets.combined.complete ? '已到期' : '缺价，保持未知'}</td></tr>)}</tbody></table></div>}
        {m.latest && <div className="border-t pt-4"><h3 className="text-sm font-semibold">最新冻结名单 · {m.latest.baskets.combined.count} 只</h3><div className="mt-3 grid grid-cols-2 gap-x-5 gap-y-2 text-xs sm:grid-cols-4 lg:grid-cols-6">{m.latest.baskets.combined.holdings.map(h => <Link className="break-all text-primary hover:underline" key={h.code} to={`/stock/${encodeURIComponent(h.code)}`}>{h.code}</Link>)}</div></div>}
      </section>}
      {tab === 'history' && <section className="space-y-3"><h2 className="text-sm font-semibold">修正口径后的历史回放</h2><p className="text-xs leading-relaxed text-amber-900">{data.historical?.note ?? '尚无历史诊断'} 历史数字不计入前瞻进度。</p>
        <div className="h-56 w-full" aria-label="完整历史期平均扣费收益图"><ResponsiveContainer><BarChart data={data.historical?.summary.filter(h => h.market === market).map(h => ({ name: names[h.variant] ?? h.variant, value: h.mean_net_pct }))} margin={{ left: 0, right: 10, bottom: 5 }}><XAxis dataKey="name" tick={{ fontSize: 11 }} /><YAxis tick={{ fontSize: 11 }} unit="%" /><Tooltip formatter={v => pct(Number(v))} /><Bar dataKey="value" name="完整期平均扣费收益" fill="#267f78" isAnimationActive={false} /></BarChart></ResponsiveContainer></div>
        <div className="overflow-x-auto"><table className="w-full min-w-[550px] text-left text-xs"><thead><tr>{['配置', '完整 / 总期数', '覆盖率', '完整期平均扣费收益', '组合相对该对照'].map(v => <th key={v} className="p-2 font-normal text-muted-foreground">{v}</th>)}</tr></thead><tbody>{data.historical?.summary.filter(h => h.market === market).map(h => <tr className="border-t" key={h.variant}><td className="p-2">{names[h.variant] ?? h.variant}</td><td className="p-2">{h.complete} / {h.due}</td><td className="p-2">{pct(h.coverage * 100)}</td><td className="p-2">{pct(h.mean_net_pct)}</td><td className="p-2">{pct(h.mean_combo_improvement_pp, ' pp')}</td></tr>)}</tbody></table></div>
        <p className="text-xs text-muted-foreground">完整期均值是条件统计；缺失期仍然存在，因此不展示完整策略的年化收益或净值。</p></section>}
      {tab === 'protocol' && <section className="space-y-4 text-sm"><h2 className="font-semibold">按不重叠样本验收</h2>
        <div className="divide-y border-y">{data.policy.checkpoints.map((n, i) => <div key={n} className="flex flex-wrap items-center justify-between gap-2 py-3"><span>{n} 期 · 约 {n} 个月 · {['初步观察', '持续验证', '正式人工复核'][i]}</span><span>{Math.min(m.metrics.paired, n)} / {n}</span></div>)}</div>
        <p className="text-xs leading-relaxed text-muted-foreground">持有 {data.policy.horizon} 个交易日，下一期开盘不早于上一期退出。完整配对要求组合、纯动量、纯流动性和基准全部可评估。单边 {data.policy.cost_bps} bp，压力成本 {data.policy.stress_cost_bps} bp。</p>
        <p className="text-xs leading-relaxed text-muted-foreground">新信号保存实际冻结时间和 {data.policy.lookback} 个交易日输入。缺价不换股、不重新分配权重。以最先到期的 24 期做固定验收，检查多重比较修正后的改善下界；样本数量达标仍不保证有效。</p>
        <p className="text-xs leading-relaxed text-muted-foreground">历史股票池存在幸存者偏差，成交额使用复权价与成交量代理；交易冲击、税费和公司行动仍有模型误差。此页为独立的仅做多研究，旧多空账本保留为历史演示。</p>
        <details className="text-xs"><summary className="cursor-pointer">研究定义版本</summary><code className="mt-2 block break-all">{data.definition_hash}</code></details>
      </section>}
    </div>}
  </AppShell>
}
