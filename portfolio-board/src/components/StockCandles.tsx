import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router'
import { CandlestickSeries, ColorType, createChart, createSeriesMarkers, HistogramSeries } from 'lightweight-charts'
import type { IChartApi, Time } from 'lightweight-charts'
import { useCandles } from '@/hooks/useCandles'
import { chartPeriods, dayLabel, tradeMarkers } from '@/lib/candles'
import type { Bar, TradeMarker } from '@/lib/candles'
import { currencyOf, formatNumber } from '@/lib/screener'
import type { Evaluation } from '@/types/tracking'
import { Button } from '@/components/ui/button'

const UP = '#b82c3a'
const DOWN = '#138064'
const price = (v: number | undefined) => v == null ? '暂无' : formatNumber(v, 3)
const statusLabel: Record<string, string> = { pending: '持有中或等待开盘', matured: '已到期', missing_entry: '缺买入价格', missing_exit: '缺卖出价格', no_trade: '当日无成交，保留现金' }

function CandleCanvas({ code, bars, markers, sessions }: { code: string; bars: Bar[]; markers: TradeMarker[]; sessions: number }) {
  const container = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const [hovered, setHovered] = useState<Bar | null>(null)
  const [chartError, setChartError] = useState(false)
  const active = hovered ?? bars.at(-1)
  useEffect(() => {
    if (!container.current || bars.length === 0) return
    setChartError(false)
    setHovered(null)
    let chart: IChartApi | undefined
    try {
      chart = createChart(container.current, {
        autoSize: true, height: 360,
        layout: { background: { type: ColorType.Solid, color: '#ffffff' }, textColor: '#626c7e', fontSize: 11, attributionLogo: true },
        grid: { vertLines: { color: '#f0f2f5' }, horzLines: { color: '#edf0f4' } },
        rightPriceScale: { borderColor: '#dfe3e8', scaleMargins: { top: 0.14, bottom: 0.08 } },
        timeScale: { borderColor: '#dfe3e8', rightOffset: 4, timeVisible: false },
        localization: { locale: 'zh-CN', dateFormat: 'yyyy-MM-dd' },
        handleScroll: { vertTouchDrag: false },
      })
      chartRef.current = chart
      const candle = chart.addSeries(CandlestickSeries, { upColor: UP, downColor: DOWN, borderUpColor: UP, borderDownColor: DOWN, wickUpColor: UP, wickDownColor: DOWN,
        priceFormat: { type: 'price', precision: 3, minMove: 0.001 } })
      const volume = chart.addSeries(HistogramSeries, { priceFormat: { type: 'volume' }, lastValueVisible: false, priceLineVisible: false }, 1)
      volume.priceScale().applyOptions({ scaleMargins: { top: 0.15, bottom: 0 } })
      chart.panes()[1].setHeight(80)
      candle.setData(bars.map(([day, open, high, low, close]) => ({ time: dayLabel(day), open, high, low, close })))
      volume.setData(bars.map(([day, open, , , close, value]) => ({ time: dayLabel(day), value, color: close >= open ? '#b82c3a77' : '#13806477' })))
      createSeriesMarkers(candle, markers.map(m => ({ time: m.time as Time, position: m.kind === 'buy' ? 'belowBar' : 'aboveBar', color: m.kind === 'buy' ? '#1959a6' : '#a85610',
        shape: m.kind === 'buy' ? 'arrowUp' : 'arrowDown', text: m.kind === 'buy' ? '模拟买入' : '模拟卖出' })))
      const byDay = new Map(bars.map(b => [dayLabel(b[0]), b]))
      chart.subscribeCrosshairMove(event => {
        const time = event.time
        const key = typeof time === 'string' ? time : time && typeof time === 'object' ? `${time.year}-${String(time.month).padStart(2, '0')}-${String(time.day).padStart(2, '0')}` : ''
        setHovered(byDay.get(key) ?? null)
      })
      chart.timeScale().setVisibleLogicalRange({ from: Math.max(0, bars.length - sessions), to: bars.length + 3 })
    } catch {
      chart?.remove()
      chartRef.current = null
      setChartError(true)
    }
    return () => { if (chartRef.current === chart) { chart?.remove(); chartRef.current = null } }
  }, [bars, markers, sessions])
  return <div className="min-w-0 rounded-md border bg-white">
    <div className="flex flex-wrap items-center justify-between gap-2 border-b px-3 py-2 text-xs"><span className="tnum">{active ? dayLabel(active[0]) : '—'} · {currencyOf(code)}</span><span className="text-muted-foreground">红涨绿跌（收盘对比开盘）</span></div>
    {active && <dl aria-label="日K价格明细" className="grid grid-cols-3 gap-x-3 gap-y-2 px-3 py-3 text-xs sm:grid-cols-6">{[['开盘', price(active[1])], ['最高', price(active[2])], ['最低', price(active[3])], ['收盘', price(active[4])], ['开盘至收盘涨跌', `${((active[4] / active[1] - 1) * 100).toFixed(2)}%`], ['成交量（源单位）', formatNumber(active[5], 0)]].map(([label, value]) => <div key={label}><dt className="text-muted-foreground">{label}</dt><dd className="mt-1 break-all font-medium tnum">{value}</dd></div>)}</dl>}
    {chartError && <p role="alert" className="px-3 py-8 text-sm text-destructive">图表暂时无法显示，可展开下方日线表格查看价格。</p>}
    <div ref={container} className={`h-[360px] min-w-0 w-full ${chartError ? 'hidden' : ''}`} role="img" aria-label={`${code} 日K线与成交量，蓝色为模拟买入，棕色为模拟卖出`} />
    <div className="flex flex-wrap items-center gap-2 border-t px-3 py-2">
      <Button size="sm" variant="outline" aria-label="放大K线" onClick={() => { const t = chartRef.current?.timeScale(); const r = t?.getVisibleLogicalRange(); if (r) t?.setVisibleLogicalRange({ from: r.to - (r.to - r.from) * 0.75, to: r.to }) }}>放大</Button>
      <Button size="sm" variant="outline" aria-label="缩小K线" onClick={() => { const t = chartRef.current?.timeScale(); const r = t?.getVisibleLogicalRange(); if (r) t?.setVisibleLogicalRange({ from: r.to - (r.to - r.from) * 1.3, to: r.to }) }}>缩小</Button>
      <Button size="sm" variant="ghost" onClick={() => chartRef.current?.timeScale().fitContent()}>显示全部</Button>
      <span className="text-[11px] text-muted-foreground">拖动看历史，滑动或双指缩放；点按查看当天价格。</span>
    </div>
  </div>
}

export default function StockCandles({ code, evaluations }: { code: string; evaluations: Evaluation[] }) {
  const { data, error, loading, retry } = useCandles(code)
  const [params, setParams] = useSearchParams()
  const [sessions, setSessions] = useState(60)
  const periods = useMemo(() => chartPeriods(evaluations, code), [evaluations, code])
  const period = periods.find(p => p.id === params.get('period')) ?? periods[0]
  const bars = data?.bars
  const { markers, warnings } = useMemo(() => tradeMarkers(period, code, bars ?? []), [period, code, bars])
  const holding = period?.row.baskets[period.mode]?.holdings.find(h => h.code === code)
  return <section className="min-w-0 space-y-3" aria-label="股票日K线">
    <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="text-sm font-semibold">日K线与成交量</h2><Button variant="ghost" size="sm" disabled={loading} onClick={retry}>刷新K线</Button></div>
    <div className="flex flex-wrap gap-1" role="group" aria-label="K线显示范围">{[[20, '1个月'], [60, '3个月'], [120, '6个月'], [260, '12个月']].map(([n, label]) => <button key={n} type="button" aria-pressed={sessions === n} onClick={() => setSessions(Number(n))} className={`rounded border px-3 py-1.5 text-xs ${sessions === n ? 'border-primary bg-primary text-primary-foreground' : 'bg-white'}`}>{label}</button>)}</div>
    <p className="text-xs leading-relaxed text-muted-foreground">范围按约 20／60／120／260 个交易日显示，以已取得的数据为限。仅显示已收盘日线，不是实时行情。</p>
    {periods.length > 0 ? <div className="space-y-2 rounded-md border bg-muted/30 p-3">
      <label className="block space-y-2 text-xs"><span className="font-medium">查看哪一期模拟跟踪</span><select aria-label="K线跟踪期" className="h-10 w-full min-w-0 rounded border bg-white px-2" value={period?.id ?? ''} onChange={e => { const next = new URLSearchParams(params); next.set('period', e.target.value); setParams(next, { replace: true }) }}>{periods.map(p => <option key={p.id} value={p.id}>{p.row.scheduled_entry_date ? dayLabel(p.row.scheduled_entry_date) : '未定日期'} · {p.row.strategy_name} · {p.row.horizon}交易日 · {p.mode === 'selected' ? '最终排序' : '原排序'} · {p.row.prospective ? '前瞻' : '历史导入'}</option>)}</select></label>
      {holding && period && <div className="flex flex-wrap gap-x-5 gap-y-2 text-xs tnum"><span>状态：{statusLabel[holding.status] ?? holding.status}</span><span>模拟买入：{period.row.entry_date ? dayLabel(period.row.entry_date) : '等待开盘'} · {price(period.row.entry_date ? holding.entry_price : undefined)}</span><span>模拟卖出：{period.row.exit_date ? dayLabel(period.row.exit_date) : `预计 ${period.row.scheduled_exit_date ? dayLabel(period.row.scheduled_exit_date) : '待定'}`} · {price(period.row.exit_date ? holding.exit_price : undefined)}</span><span>扣费收益：{holding.return_pct == null || !['matured', 'no_trade'].includes(holding.status) ? '待定' : `${formatNumber(holding.return_pct)}%`}</span></div>}
      <p className="text-[11px] leading-relaxed text-muted-foreground">蓝色箭头为模拟买入日，棕色为模拟卖出日；价格以此处记录为准。预计日期不画成已成交，模拟记录不代表真实下单。</p>
    </div> : <p className="text-xs text-muted-foreground">该股尚未进入跟踪组合，取得日线后可看走势；暂无模拟买卖标记。</p>}
    {loading && <p role="status" className="py-12 text-center text-sm text-muted-foreground">正在读取日K线…</p>}
    {error && <div role="alert" className="rounded border p-4 text-sm"><p>{error}</p><Button className="mt-3" variant="outline" size="sm" onClick={retry}>重试日K线</Button></div>}
    {data && !data.bars.length && <p className="border-y py-12 text-center text-sm text-muted-foreground">暂无完整的开、高、低、收和成交量数据，暂不绘制K线。</p>}
    {bars && bars.length > 0 && <>
      <p className="text-xs text-muted-foreground">日线截至 {dayLabel(data!.as_of!)} · 已取得 {bars.length} 根 · {currencyOf(code)} · {markers.length} 个模拟买卖标记</p>
      {data!.rejected_rows > 0 && <p className="text-xs leading-relaxed text-amber-800">原始历史中有 {data!.rejected_rows} 条异常日线已排除，缺失位置不补画K线。</p>}
      {data!.source === 'chart_history' && <p className="text-xs leading-relaxed text-muted-foreground">使用图表专用补充日线；这份补充数据只用于展示。</p>}
      <CandleCanvas code={code} bars={bars} markers={markers} sessions={sessions} />
      {warnings.map(w => <p key={w} className="text-xs leading-relaxed text-amber-800">{w}</p>)}
      <details className="text-xs"><summary className="cursor-pointer py-2 font-medium">日线价格表（支持不用图表查看）</summary><div className="max-h-80 overflow-auto"><table className="w-full text-right text-xs tnum"><thead className="sticky top-0 bg-white"><tr>{['日期', '开盘', '最高', '最低', '收盘', '成交量（源单位）'].map(x => <th key={x} className="whitespace-nowrap border-b p-2 font-normal">{x}</th>)}</tr></thead><tbody>{[...bars].reverse().map(b => <tr key={b[0]} className="border-b">{b.map((v, i) => <td key={i} className="whitespace-nowrap p-2">{i === 0 ? dayLabel(v) : i === 5 ? formatNumber(v, 0) : price(v)}</td>)}</tr>)}</tbody></table></div></details>
    </>}
    <p className="text-[11px] leading-relaxed text-muted-foreground">沿用跟踪历史源的复权 OHLC，价格不是当时未复权成交报价。成交量保留源单位，不同来源可能用股或手，不作跨来源比较。复权或来源变化时，买卖价核对不通过的标记会隐藏。</p>
    <p className="text-[10px] text-muted-foreground">图表使用 <a href="https://www.tradingview.com/" target="_blank" rel="noreferrer" className="underline">TradingView Lightweight Charts™</a>，Copyright © 2025 TradingView, Inc.</p>
  </section>
}
