import { Link, useParams } from 'react-router'
import { ArrowLeft, RefreshCw } from 'lucide-react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import AppShell from '@/components/AppShell'
import WatchButton from '@/components/WatchButton'
import { Button } from '@/components/ui/button'
import { useTracking } from '@/hooks/useTracking'
import { currencyOf, formatNumber, isFiniteNumber, scanTimeInfo } from '@/lib/screener'

export default function StockDetail() {
  const { code = '' } = useParams()
  const { data, error, loading, retry } = useTracking()
  const security = data?.securities[code]
  const observations = data?.appearances[code] ?? []
  const history = security?.history?.map(([date, close]) => ({ date: String(date), close })) ?? []
  const metrics = [
    ['最新价', security ? `${formatNumber(security.last_price)} ${currencyOf(code)}` : '-'],
    ['20 日年化波动', isFiniteNumber(security?.volatility_20d_pct) ? `${formatNumber(security.volatility_20d_pct)}%` : '暂无'],
    [`${security?.risk_window_sessions ?? 120} 日最大回撤`, isFiniteNumber(security?.drawdown_120d_pct) ? `${formatNumber(security.drawdown_120d_pct)}%` : '暂无'],
    ['20 日成交额中位数估算', isFiniteNumber(security?.median_turnover_20d) ? `${formatNumber(security.median_turnover_20d / 1e6)}M ${currencyOf(code)}` : '暂无'],
  ]
  return <AppShell title={security?.name ?? code} subtitle={code}>
    <div className="flex items-center justify-between gap-3 border-b pb-3">
      <Button asChild variant="ghost" size="sm"><Link to="/"><ArrowLeft />选股结果</Link></Button>
      <div className="flex items-center gap-2"><WatchButton code={code} name={security?.name ?? code} /><Button variant="ghost" size="icon" aria-label="刷新个股数据" title="刷新个股数据" onClick={retry} disabled={loading}><RefreshCw /></Button></div>
    </div>
    {error && <p role="alert" className="py-4 text-sm text-destructive">{error}</p>}
    {loading && !data && <p role="status" className="py-8 text-sm text-muted-foreground">读取个股数据...</p>}
    {data && !security && <p className="py-8 text-sm text-muted-foreground">当前档案没有该标的的行情或入选记录。</p>}
    {security && <div className="space-y-6 pt-5">
      <dl className="grid grid-cols-2 gap-4 md:grid-cols-4">{metrics.map(([label, value]) => <div key={label} className="min-w-0 border-b pb-3"><dt className="text-xs leading-relaxed text-muted-foreground">{label}</dt><dd className="mt-2 break-words text-base font-semibold tnum">{value}</dd></div>)}</dl>
      <div className="flex flex-wrap gap-x-6 gap-y-2 text-xs text-muted-foreground"><span>行业：{security.industry || security.sector || '暂无分类'}</span><span>财报日期：{security.earnings_date || '暂无可靠数据'}</span><span>风险数据截至：{security.risk_as_of || '暂无'}</span><span className="break-all">行情时间：{security.quote_time || '源未提供'}</span></div>
      <p className="text-xs leading-relaxed text-muted-foreground">成交额中位数以日收盘价 × 成交股数估算；复权与成交量口径可能影响数值。风险数据仅采用已完成日线。</p>
      <section className="space-y-3">
        <div className="flex flex-wrap items-baseline justify-between gap-2"><h2 className="text-sm font-semibold">近期价格</h2><span className="text-xs text-muted-foreground">{currencyOf(code)} · 日线收盘</span></div>
        {history.length > 1 ? <div className="h-[280px] min-w-0 w-full" aria-label={`${code} 历史价格走势图`}><ResponsiveContainer width="100%" height="100%"><LineChart data={history} margin={{ left: 0, right: 12, top: 12, bottom: 0 }}><CartesianGrid strokeDasharray="3 3" stroke="#dfe3e8" /><XAxis dataKey="date" tickFormatter={value => `${String(value).slice(4, 6)}/${String(value).slice(6, 8)}`} minTickGap={35} tick={{ fontSize: 11 }} /><YAxis domain={['auto', 'auto']} width={55} tick={{ fontSize: 11 }} /><Tooltip formatter={value => [formatNumber(Number(value)), currencyOf(code)]} labelFormatter={value => String(value)} /><Line dataKey="close" type="linear" stroke="#1959a6" strokeWidth={2} dot={false} isAnimationActive={false} /></LineChart></ResponsiveContainer></div> : <p className="border-y py-12 text-center text-sm text-muted-foreground">暂无足够历史日线。</p>}
      </section>
      <section className="space-y-3"><h2 className="text-sm font-semibold">入选原因</h2><p className="text-sm leading-relaxed">{security.reason}</p>{security.factor_note && <p className="break-words text-xs leading-relaxed text-muted-foreground">{security.factor_note}</p>}<p className="text-xs text-muted-foreground">最近入选：{security.last_seen ? scanTimeInfo(security.last_seen).display : '-'}</p></section>
      <section className="space-y-3"><h2 className="text-sm font-semibold">历次入选（{observations.length}）</h2><div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead className="border-b text-muted-foreground"><tr>{['扫描时间', '策略', '原排序', '最终排序', '因子分', '来源'].map(label => <th key={label} className="whitespace-nowrap p-2 font-normal">{label}</th>)}</tr></thead><tbody>{[...observations].reverse().map((row, index) => <tr key={`${row.snapshot_id}-${index}`} className="border-b"><td className="whitespace-nowrap p-2">{scanTimeInfo(row.generated_at).display}</td><td className="min-w-28 p-2">{row.strategy_name}</td><td className="p-2 tnum">{row.original_market_rank ?? '-'}</td><td className="p-2 tnum">{row.selection_market_rank ?? '-'}</td><td className="p-2 tnum">{formatNumber(row.factor_score)}</td><td className="whitespace-nowrap p-2">{row.provenance === 'prospective' ? '前瞻冻结' : '历史导入'}</td></tr>)}</tbody></table></div></section>
    </div>}
  </AppShell>
}
