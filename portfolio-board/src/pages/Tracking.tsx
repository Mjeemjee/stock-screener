import { useMemo, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import AppShell from '@/components/AppShell'
import { Button } from '@/components/ui/button'
import { useTracking } from '@/hooks/useTracking'
import { formatNumber, scanTimeInfo } from '@/lib/screener'

const percent = (value: number | null | undefined) => value == null ? '-' : `${value > 0 ? '+' : ''}${formatNumber(value)}%`
const dateLabel = (value?: number) => value ? `${String(value).slice(0, 4)}-${String(value).slice(4, 6)}-${String(value).slice(6, 8)}` : '-'

export default function Tracking() {
  const { data, error, loading, retry } = useTracking()
  const [market, setMarket] = useState('US')
  const [horizon, setHorizon] = useState(20)
  const [strategy, setStrategy] = useState('ALL')
  const archives = useMemo(() => new Map(data?.archives.map(record => [record.id, record]) ?? []), [data])
  const rows = data?.evaluations.filter(row => row.market === market && row.horizon === horizon &&
    (strategy === 'ALL' || row.strategy_id === strategy)) ?? []
  const summary = data?.summary.filter(row => row.market === market && row.horizon === horizon &&
    (strategy === 'ALL' || row.strategy_id === strategy)) ?? []
  const names = new Map(data?.evaluations.map(row => [row.strategy_id, row.strategy_name]) ?? [])
  return <AppShell title="选股效果追踪" subtitle="每日冻结名单 · 原排序与最终排序对照">
    <div className="flex flex-wrap items-center justify-between gap-3 border-b pb-4">
      <div className="text-sm text-muted-foreground">
        {data ? `${data.archives.filter(row => row.provenance === 'prospective').length} 份前瞻档案 · ${data.archives.filter(row => row.provenance === 'historical_import').length} 份历史导入` : '选股档案'}
      </div>
      <Button variant="outline" size="icon" aria-label="刷新追踪数据" title="刷新追踪数据" disabled={loading} onClick={retry}><RefreshCw /></Button>
    </div>
    {loading && !data && <p role="status" className="py-8 text-sm text-muted-foreground">读取追踪数据...</p>}
    {error && <p role="alert" className="py-4 text-sm text-destructive">{error}</p>}
    {data && <div className="space-y-6 pt-4">
      <div className="flex flex-wrap items-center gap-3">
        <div role="group" aria-label="追踪市场" className="flex rounded-md border p-0.5">
          {['US', 'HK'].map(value => <button key={value} type="button" aria-pressed={market === value} onClick={() => setMarket(value)} className={`rounded-sm px-4 py-1.5 text-sm ${market === value ? 'bg-primary text-primary-foreground' : 'text-muted-foreground'}`}>{value === 'US' ? '美股' : '港股'}</button>)}
        </div>
        <label className="flex items-center gap-2 text-xs text-muted-foreground">持有期
          <select aria-label="追踪持有期" value={horizon} onChange={event => setHorizon(Number(event.target.value))} className="h-9 rounded-md border bg-background px-2 text-sm text-foreground">
            {[5, 20, 60].map(value => <option key={value} value={value}>{value} 交易日</option>)}
          </select>
        </label>
        <select aria-label="追踪策略" value={strategy} onChange={event => setStrategy(event.target.value)} className="h-9 max-w-full rounded-md border bg-background px-2 text-sm">
          <option value="ALL">全部策略</option>{[...names].map(([id, name]) => <option key={id} value={id}>{name}</option>)}
        </select>
      </div>
      <p className="text-xs leading-relaxed text-muted-foreground">每市场取前 {data.protocol.top_n} 只等权，冻结后的下一次市场开盘进入，持有期结束开盘退出；每边费用 {data.protocol.cost_bps_per_side} bp。指数为价格基准，不扣交易费。</p>
      <section aria-label="前瞻配对统计" className="space-y-3">
        <h2 className="text-sm font-semibold">前瞻配对统计</h2>
        {summary.length === 0 ? <p className="border-y py-6 text-sm text-muted-foreground">暂无前瞻样本。历史导入不参与此统计。</p> : <div className="overflow-x-auto">
          <table className="w-full text-left text-xs"><thead className="border-b text-muted-foreground"><tr>{['策略 / 版本', '到期 / 总期数', '最终排序', '原排序', '指数', '配对差值'].map(label => <th key={label} className="whitespace-nowrap p-2 font-normal">{label}</th>)}</tr></thead>
            <tbody>{summary.map(row => <tr key={`${row.strategy_id}-${row.strategy_version}`} className="border-b"><td className="p-2">{names.get(row.strategy_id) ?? row.strategy_id}<span className="block font-mono text-[10px] text-muted-foreground">{row.strategy_version.slice(0, 10)}</span></td><td className="p-2 tnum">{row.matured_pairs} / {row.cohorts}</td><td className="p-2 tnum">{percent(row.mean_selected_pct)}</td><td className="p-2 tnum">{percent(row.mean_original_pct)}</td><td className="p-2 tnum">{percent(row.mean_benchmark_pct)}</td><td className="p-2 tnum">{row.mean_delta_pp == null ? '-' : `${formatNumber(row.mean_delta_pp)} pp`}</td></tr>)}</tbody>
          </table>
        </div>}
        <p className="text-xs leading-relaxed text-muted-foreground">仅比较两种名单和基准价格均完整的同一期；重叠持有期展示平均单期收益，不复合为组合净值。缺价格不会重新分配给其他股票。</p>
        <p className="text-xs text-muted-foreground">仅美股动量候选使用因子重排，其他策略保留原排序。</p>
        <p className="text-xs text-muted-foreground">同一入场日与版本仅计最早冻结的一份名单，周末或手动重复扫描不增加样本数。</p>
      </section>
      <section className="space-y-3">
        <h2 className="text-sm font-semibold">逐期结果</h2>
        {rows.length === 0 ? <p className="py-6 text-sm text-muted-foreground">当前市场和策略暂无记录。</p> : <div className="overflow-x-auto">
          <table className="w-full text-left text-xs"><thead className="border-b text-muted-foreground"><tr>{['冻结时间', '策略', '状态', '最终排序', '原排序', '指数'].map(label => <th key={label} className="whitespace-nowrap p-2 font-normal">{label}</th>)}</tr></thead>
            <tbody>{[...rows].reverse().map(row => {
              const archive = archives.get(row.snapshot_id)
              const selected = row.baskets.selected
              const status = !row.prospective ? '历史导入' : !row.exit_date ? '未到期' :
                !selected.complete || !row.baskets.original?.complete ? '缺价格' : row.benchmark_pct == null ? '基准缺价' : '已到期'
              return <tr key={`${row.snapshot_id}-${row.strategy_id}`} className="border-b"><td className="whitespace-nowrap p-2">{archive ? scanTimeInfo(archive.frozen_at).display : '-'}</td><td className="min-w-28 p-2">{row.strategy_name}</td><td className="whitespace-nowrap p-2">{status}<span className="block text-[10px] text-muted-foreground">{status === '未到期' ? `预计 ${dateLabel(row.scheduled_exit_date)}` : `价格 ${selected.known_count}/${selected.count}`}</span></td><td className="p-2 tnum">{percent(selected.return_pct)}</td><td className="p-2 tnum">{percent(row.baskets.original?.return_pct)}</td><td className="p-2 tnum">{percent(row.benchmark_pct)}</td></tr>
            })}</tbody>
          </table>
        </div>}
      </section>
      <details className="border-t pt-4 text-xs">
        <summary className="cursor-pointer font-medium">归档记录（{data.archives.length}）</summary>
        <div className="mt-3 divide-y">{[...data.archives].reverse().map(record => <div key={record.id} className="flex flex-wrap gap-x-4 gap-y-1 py-3 text-muted-foreground"><span>{scanTimeInfo(record.frozen_at).display}</span><span>{record.provenance === 'prospective' ? '前瞻冻结' : '历史导入'}</span><span>{record.candidate_count} 条候选 · {record.complete_candidates ? '完整名单' : '部分名单'}</span><span className="font-mono">{record.strategy_version.slice(0, 10)}</span></div>)}</div>
      </details>
      {(data.history_refresh.failed.length > 0 || data.history_refresh.budget_excluded > 0) && <p className="text-xs text-amber-700">待补充历史价格 {data.history_refresh.needed} 只，本轮取数失败 {data.history_refresh.failed.length} 只，未请求 {data.history_refresh.budget_excluded} 只。</p>}
    </div>}
  </AppShell>
}
