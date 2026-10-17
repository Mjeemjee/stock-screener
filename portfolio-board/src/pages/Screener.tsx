import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router'
import { AlertTriangle, ArrowDownWideNarrow, ArrowUpNarrowWide, Download, Loader2, RefreshCw, Search, X } from 'lucide-react'
import { dataUrl } from '@/lib/dataSource'
import {
  currencyOf, filterAndSortHits, formatNumber, hitsToCsv, isFiniteNumber,
  isScreenerResults, marketOf, marketValue, scanTimeInfo,
  type MarketFilter, type SortDirection, type SortKey,
} from '@/lib/screener'
import AppShell from '@/components/AppShell'
import WatchButton from '@/components/WatchButton'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import type { ScreenHit, ScreenerResults, StrategyResult } from '@/types/screener'

const STATUS_STYLE: Record<string, { label: string; variant: 'default' | 'secondary' | 'outline' }> = {
  active: { label: '启用中', variant: 'default' },
  watch: { label: '观察中', variant: 'secondary' },
  paused: { label: '已暂停', variant: 'outline' },
}

const FACTOR_STATUS: Record<string, string> = {
  unsupported_scope: '不在评分范围',
  budget_excluded: '未纳入本轮计算',
  history_unavailable: '历史数据不可用',
  stale_history: '历史数据不同步',
  insufficient_sample: '有效样本不足',
}

function fmtMv(value: unknown) {
  if (!isFiniteNumber(value)) return '-'
  if (value >= 1e12) return (value / 1e12).toFixed(2) + 'T'
  if (value >= 1e9) return (value / 1e9).toFixed(1) + 'B'
  return (value / 1e6).toFixed(1) + 'M'
}

function ChangeText({ value }: { value?: number | null }) {
  if (!isFiniteNumber(value)) return <span className="text-muted-foreground">-</span>
  return <span className={value > 0 ? 'text-red-600' : value < 0 ? 'text-emerald-600' : 'text-muted-foreground'}>
    {value > 0 ? '+' : ''}{value.toFixed(2)}%
  </span>
}

function FactorValue({ hit }: { hit: ScreenHit }) {
  if (!isFiniteNumber(hit.factor_score)) {
    return <span className="text-muted-foreground">{FACTOR_STATUS[hit.factor_status ?? ''] ?? '暂无评分'}</span>
  }
  return <span title={hit.factor_note}>
    {isFiniteNumber(hit.factor_rank) && <span className="mr-2 text-primary">#{hit.factor_rank}</span>}
    {formatNumber(hit.factor_score)}
    {hit.factor_as_of && <span className="block text-[11px] text-muted-foreground">{hit.factor_as_of}</span>}
  </span>
}

function StrategyDetails({ result }: { result: StrategyResult }) {
  const status = STATUS_STYLE[result.meta.status] ?? STATUS_STYLE.watch
  return <details className="border-b py-4">
    <summary className="cursor-pointer text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring">
      {result.meta.name}
      <Badge variant={status.variant} className="ml-2">{status.label}</Badge>
      <span className="ml-2 text-xs font-normal text-muted-foreground">{result.meta.markets.join(' / ')}</span>
    </summary>
    <div className="mt-3 space-y-2 text-sm leading-relaxed">
      <p>{result.meta.principle}</p>
      <p className="text-xs text-muted-foreground break-words">来源：{result.meta.source}</p>
      {result.meta.cloud_note && <p className="text-xs text-sky-700">{result.meta.cloud_note}</p>}
      {result.meta.fundamentals && <p className="text-xs text-muted-foreground">财务数据：{result.meta.fundamentals.source}；匹配 {result.meta.fundamentals.matched_count}/{result.meta.fundamentals.requested_count}，价格核对通过 {result.meta.fundamentals.verified_count}，股息可用 {result.meta.fundamentals.dividend_available_count}。{result.meta.fundamentals.error && '本期数据源请求失败。'}采集时间 {scanTimeInfo(result.meta.fundamentals.fetched_at).display}，不是财报公告时间。</p>}
      {result.meta.market_params && <div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead><tr className="border-b text-muted-foreground"><th className="p-2">市场</th><th className="p-2">市值下限</th><th className="p-2">成交额下限</th><th className="p-2">20 日中位数过滤</th></tr></thead><tbody>{Object.entries(result.meta.market_params).map(([market, params]) => <tr key={market} className="border-b"><td className="p-2">{market}</td><td className="whitespace-nowrap p-2">{fmtMv(params.min_market_val)} {market === 'US' ? 'USD' : 'HKD'}</td><td className="whitespace-nowrap p-2">{fmtMv(params.min_turnover)} {market === 'US' ? 'USD' : 'HKD'}</td><td className="p-2">{params.use_median_liquidity ? fmtMv(params.min_median_turnover_20d) : '未启用'}</td></tr>)}</tbody></table><p className="mt-2 text-xs text-muted-foreground">市场配置 {result.meta.policy_version}；港币门槛以固定 7.8 比例作规模对齐，属于初始参数，未声称已优化收益。</p></div>}
      <pre className="max-w-full overflow-x-auto rounded-md bg-muted p-3 text-xs">{JSON.stringify(result.meta.params, null, 2)}</pre>
      <p className="text-xs text-amber-700">{result.meta.risk}</p>
    </div>
  </details>
}

function HitRows({ hits }: { hits: ScreenHit[] }) {
  return <>
    <div className="divide-y md:hidden">
      {hits.map((hit) => <article key={hit.code} className="space-y-2 py-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-start gap-2">
              <Badge variant={marketOf(hit.code) === 'US' ? 'default' : 'secondary'} className="shrink-0">{marketOf(hit.code)}</Badge>
              <Link to={`/stock/${encodeURIComponent(hit.code)}`} className="break-words text-sm font-medium hover:text-primary">{hit.name}</Link>
            </div>
            <div className="mt-1 flex items-center gap-1"><p className="text-xs text-muted-foreground">{hit.code}</p><WatchButton code={hit.code} name={hit.name} /></div>
          </div>
          <div className="shrink-0 text-right text-sm tnum">
            <p className="font-medium">{formatNumber(hit.last_price)} <span className="text-[10px] font-normal text-muted-foreground">{currencyOf(hit.code)}</span></p>
            <ChangeText value={hit.change_rate} />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs tnum">
          <div><span className="text-muted-foreground">{hit.market_cap_basis === 'hk_listed' ? '港股市值' : '市值'} </span>{fmtMv(marketValue(hit))} {currencyOf(hit.code)}</div>
          <div className="text-right"><span className="text-muted-foreground">因子 </span><FactorValue hit={hit} /></div>
        </div>
        <p className="break-words text-xs leading-relaxed text-muted-foreground">{hit.reason}</p>
      </article>)}
    </div>
    <div className="hidden md:block">
      <Table className="table-fixed">
        <TableHeader><TableRow>
          <TableHead className="w-[23%]">标的</TableHead>
          <TableHead className="text-right">最新价</TableHead>
          <TableHead className="text-right">当日涨跌</TableHead>
          <TableHead className="text-right">市值</TableHead>
          <TableHead className="w-[29%]">命中原因</TableHead>
          <TableHead className="text-right">因子评分</TableHead>
        </TableRow></TableHeader>
        <TableBody>{hits.map((hit) => <TableRow key={hit.code}>
          <TableCell className="whitespace-normal break-words"><div className="flex items-start gap-2">
            <Badge variant={marketOf(hit.code) === 'US' ? 'default' : 'secondary'} className="shrink-0">{marketOf(hit.code)}</Badge>
            <div className="min-w-0"><Link to={`/stock/${encodeURIComponent(hit.code)}`} className="break-words font-medium hover:text-primary">{hit.name}</Link><div className="text-xs text-muted-foreground">{hit.code}</div></div><WatchButton code={hit.code} name={hit.name} />
          </div></TableCell>
          <TableCell className="text-right tnum">{formatNumber(hit.last_price)}<div className="text-[10px] text-muted-foreground">{currencyOf(hit.code)}</div></TableCell>
          <TableCell className="text-right tnum"><ChangeText value={hit.change_rate} /></TableCell>
          <TableCell className="text-right tnum">{fmtMv(marketValue(hit))}<div className="text-[10px] text-muted-foreground">{currencyOf(hit.code)}{hit.market_cap_basis === 'hk_listed' ? ' · 港股市值' : ''}</div></TableCell>
          <TableCell className="whitespace-normal break-words text-xs leading-relaxed text-muted-foreground">{hit.reason}</TableCell>
          <TableCell className="whitespace-normal break-words text-right text-xs tnum"><FactorValue hit={hit} /></TableCell>
        </TableRow>)}</TableBody>
      </Table>
    </div>
  </>
}

function FactorSummary({ data }: { data: ScreenerResults }) {
  const factor = data.factor_rank
  if (!factor) return <p className="text-xs text-muted-foreground">本期未提供因子计算记录。</p>
  if (!factor.scope && factor.reason) return <p className="text-xs text-amber-700">本期未执行因子排名：{factor.reason}</p>
  if (!factor.scope) return <p className="text-xs text-amber-700">本期为旧版因子结果，未记录评分范围与样本覆盖；历史评分仅供参考。</p>
  return <div className="space-y-1 text-xs leading-relaxed text-muted-foreground">
    <details>
    <summary className="cursor-pointer">
      因子范围：{factor.scope === 'US momentum_breakout' ? '美股动量突破' : factor.scope}
      {' · '}已评分 {factor.ranked} / {factor.candidates ?? '-'} 只
      {isFiniteNumber(factor.coverage) && `（${(factor.coverage * 100).toFixed(0)}%）`}
    </summary>
    <p className="mt-1">历史数据失败 {factor.failures} 只。评分是本轮候选中的相对排序，未评分不等于低分；历史相关性不代表未来收益。</p>
    </details>
    {factor.reason && <p className="text-amber-700">{factor.reason}</p>}
  </div>
}

export default function Screener() {
  const [data, setData] = useState<ScreenerResults | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [request, setRequest] = useState(0)
  const [strategyId, setStrategyId] = useState('')
  const [query, setQuery] = useState('')
  const [market, setMarket] = useState<MarketFilter>('ALL')
  const [sort, setSort] = useState<SortKey>('strategy')
  const [direction, setDirection] = useState<SortDirection>('desc')

  useEffect(() => {
    const controller = new AbortController()
    let timedOut = false
    let disposed = false
    const timeout = window.setTimeout(() => { timedOut = true; controller.abort() }, 20_000)
    setLoading(true)
    setError(null)
    fetch(dataUrl('screener_results.json'), { signal: controller.signal, cache: 'no-cache' })
      .then(async (response) => {
        if (!response.ok) throw new Error(`数据文件无法读取（HTTP ${response.status}）`)
        const value: unknown = await response.json()
        if (!isScreenerResults(value)) throw new Error('数据格式不完整，请等待下一次扫描后重试')
        if (!disposed) setData(value)
      })
      .catch((reason: unknown) => {
        if (!disposed) setError(timedOut ? '读取超时，请重试' : reason instanceof Error ? reason.message : '网络连接失败，请重试')
      })
      .finally(() => { window.clearTimeout(timeout); if (!disposed) setLoading(false) })
    return () => { disposed = true; window.clearTimeout(timeout); controller.abort() }
  }, [request])

  const active = data?.strategies.filter((strategy) => strategy.meta.status !== 'paused') ?? []
  const selected = active.find((strategy) => strategy.meta.id === strategyId) ?? active[0]
  const hits = useMemo(() => filterAndSortHits(selected?.hits ?? [], query, market, sort, direction), [selected, query, market, sort, direction])
  const scan = data ? scanTimeInfo(data.generated_at) : null
  const filtersActive = query !== '' || market !== 'ALL' || sort !== 'strategy'
  const sectorCounts = hits.reduce<Record<string, number>>((counts, hit) => {
    const sector = hit.sector || '未分类'
    counts[sector] = (counts[sector] ?? 0) + 1
    return counts
  }, {})
  const resetFilters = () => { setQuery(''); setMarket('ALL'); setSort('strategy'); setDirection('desc') }
  const exportCsv = () => {
    if (!selected || !data || hits.length === 0) return
    const blob = new Blob([hitsToCsv(hits, selected.meta.name, data.generated_at)], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `screener-${selected.meta.id.replace(/[^a-z0-9_-]/gi, '_')}-${market.toLowerCase()}.csv`
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    window.setTimeout(() => URL.revokeObjectURL(url), 1_000)
  }

  return <AppShell title="港美股选股台" subtitle={data ? `全市场 ${data.universe_total.toLocaleString()} 只 · 基础过滤后 ${data.universe_after_filter.toLocaleString()} 只` : '港股与美股策略筛选'}>
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-3 border-b pb-4">
        <div className="min-w-0 space-y-1">
          <h2 className="text-lg font-semibold">最新筛选结果</h2>
          {scan && <p className="break-words text-xs leading-relaxed text-muted-foreground">
            扫描时间：{scan.display}{scan.ageHours === null ? '（时区未标注，时效待核对）' : '（香港时间）'}
          </p>}
          {scan?.stale && <p role="status" className="flex items-start gap-1.5 text-xs text-amber-700"><AlertTriangle className="mt-0.5 size-3.5 shrink-0" />扫描已超过 72 小时，当前展示为历史快照。</p>}
          {scan?.future && <p role="status" className="text-xs text-amber-700">扫描时间晚于当前时间，请核对数据时间。</p>}
        </div>
        <Button variant="outline" size="icon" disabled={loading} aria-label="重新读取选股数据" title="重新读取选股数据" onClick={() => setRequest((value) => value + 1)}>
          {loading ? <Loader2 className="animate-spin motion-reduce:animate-none" /> : <RefreshCw />}
        </Button>
      </div>

      {error && <div role="alert" className="space-y-3 border-l-2 border-destructive bg-destructive/5 p-4">
        <p className="text-sm text-destructive">选股数据加载失败：{error}</p>
        {data && <p className="text-xs text-muted-foreground">当前保留上一次成功读取的结果。</p>}
        <Button variant="outline" size="sm" disabled={loading} onClick={() => setRequest((value) => value + 1)}><RefreshCw />重试</Button>
      </div>}

      {loading && !data && <div role="status" className="flex min-h-48 items-center justify-center gap-2 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin motion-reduce:animate-none" />正在读取选股数据</div>}

      {data && <>
        <section aria-label="数据覆盖" className="space-y-2">
          <FactorSummary data={data} />
          {isFiniteNumber(data.data_quality?.coverage_pct) && data.data_quality.coverage_pct < 99.9 && <p className="text-xs leading-relaxed text-amber-700">行情覆盖 {data.data_quality.coverage_pct.toFixed(1)}%，部分请求未返回快照；本期命中范围受限。</p>}
        </section>
        {active.length === 0 ? <p className="py-10 text-sm text-muted-foreground">本期没有启用或观察中的策略。</p> : <Tabs value={selected?.meta.id} onValueChange={setStrategyId}>
          <TabsList aria-label="选股策略" className="flex h-auto w-full justify-start gap-1 overflow-x-auto sm:flex-wrap">
            {active.map((strategy) => <TabsTrigger key={strategy.meta.id} value={strategy.meta.id} className="min-h-9 shrink-0 justify-between gap-2 whitespace-nowrap text-left">
              <span>{strategy.meta.name}</span><span className="tnum">{strategy.meta.error ? '异常' : strategy.meta.execution_status === 'unavailable' ? '数据缺失' : strategy.meta.hit_count}</span>
            </TabsTrigger>)}
          </TabsList>
          {selected && <TabsContent value={selected.meta.id} className="space-y-4 pt-2">
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <Badge variant={STATUS_STYLE[selected.meta.status].variant}>{STATUS_STYLE[selected.meta.status].label}</Badge>
              <span>{selected.meta.hit_count} 只命中 · 载入 {selected.hits.length} 只</span>
              {(selected.meta.truncated || selected.meta.hit_count > selected.hits.length) && <span className="text-amber-700">本期仅提供部分命中结果</span>}
            </div>
            {selected.meta.cloud_note && <p className="text-xs leading-relaxed text-sky-700">{selected.meta.cloud_note}</p>}
            {!!selected.meta.unavailable_count && selected.meta.execution_status !== 'unavailable' && <p className="text-xs text-amber-700">{selected.meta.unavailable_count} 只标的因字段缺失未参与该策略判断。</p>}

            <div className="flex flex-wrap items-center gap-2 border-y py-3">
              <div className="relative w-full sm:min-w-56 sm:flex-1">
                <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-2.5 size-4 text-muted-foreground" />
                <Input aria-label="搜索代码或名称" placeholder="代码或名称" value={query} onChange={(event) => setQuery(event.target.value)} className="h-9 pl-9 pr-9" />
                {query && <button type="button" className="absolute right-1 top-0.5 flex size-8 items-center justify-center rounded-sm text-muted-foreground hover:text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring" aria-label="清空搜索" title="清空搜索" onClick={() => setQuery('')}><X className="size-4" /></button>}
              </div>
              <div role="group" aria-label="市场筛选" className="flex h-9 shrink-0 items-center rounded-md border bg-secondary/70 p-0.5">
                {([['ALL', '全部'], ['US', '美股'], ['HK', '港股']] as const).map(([value, label]) => <button key={value} type="button" aria-pressed={market === value} onClick={() => setMarket(value)} className={`h-7 rounded-sm px-3 text-xs font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring ${market === value ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-accent'}`}>{label}</button>)}
              </div>
              <div className="flex min-w-[150px] flex-1 items-center gap-1 sm:flex-none">
                <select aria-label="排序字段" value={sort} onChange={(event) => setSort(event.target.value as SortKey)} className="h-9 min-w-0 flex-1 rounded-md border border-input bg-background px-2 text-xs focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring sm:w-36">
                  <option value="strategy">策略原始顺序</option><option value="factor_score">因子评分</option><option value="change_rate">当日涨跌</option><option value="circular_market_val">市值（原币）</option><option value="last_price">价格（原币）</option><option value="code">股票代码</option>
                </select>
                <Button variant="ghost" size="icon" disabled={sort === 'strategy'} aria-label={direction === 'desc' ? '当前降序，切换升序' : '当前升序，切换降序'} title={direction === 'desc' ? '降序，点击切换' : '升序，点击切换'} onClick={() => setDirection((value) => value === 'desc' ? 'asc' : 'desc')}>{direction === 'desc' ? <ArrowDownWideNarrow /> : <ArrowUpNarrowWide />}</Button>
              </div>
              <Button variant="outline" size="icon" disabled={hits.length === 0 || !!selected.meta.error} aria-label="导出当前结果 CSV" title="导出当前结果 CSV" onClick={exportCsv}><Download /></Button>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
              <p role="status" aria-live="polite">当前 {hits.length} / {selected.hits.length} 只 · 已评分 {hits.filter((hit) => isFiniteNumber(hit.factor_score)).length} 只</p>
              {filtersActive && <Button variant="ghost" size="sm" onClick={resetFilters}><X />清除筛选</Button>}
            </div>
            {selected.meta.error ? <p role="alert" className="py-6 text-sm text-destructive">本期策略执行失败：{selected.meta.error}</p>
              : selected.meta.execution_status === 'unavailable' ? <p role="status" className="py-6 text-sm text-amber-700">{selected.meta.data_note ?? '本期数据缺少策略所需字段，暂时无法执行筛选。'}</p>
              : hits.length > 0 ? <HitRows hits={hits} />
              : <div className="space-y-3 py-10 text-center text-sm text-muted-foreground"><p>{selected.hits.length > 0 ? '没有符合当前条件的标的。' : '本期策略没有命中标的。'}</p>{filtersActive && <Button variant="outline" size="sm" onClick={resetFilters}><X />清除筛选</Button>}</div>}
            <p className="text-xs leading-relaxed text-muted-foreground">价格与市值为各市场原币；红涨绿跌。评分缺失的标的在评分排序中置后。</p>
            {hits.length > 0 && <details className="text-xs text-muted-foreground"><summary className="cursor-pointer">当前显示名单的行业分布</summary><div className="mt-2 flex flex-wrap gap-x-4 gap-y-2">{Object.entries(sectorCounts).sort((a, b) => b[1] - a[1]).map(([sector, count]) => <span key={sector}>{sector} {count} / {hits.length}（{(count / hits.length * 100).toFixed(0)}%）</span>)}</div></details>}
            <p className="text-xs leading-relaxed text-amber-700">{selected.meta.risk}</p>
          </TabsContent>}
        </Tabs>}

        <section aria-label="数据来源" className="space-y-2 border-t pt-4">
          <p className="break-words text-xs leading-relaxed text-muted-foreground">数据源：{data.data_source ?? '富途 OpenAPI 全市场快照'}。扫描时间不等于每只股票的成交时间。</p>
        </section>

        <section className="border-t pt-4">
          <div className="flex items-baseline justify-between gap-3"><h2 className="text-sm font-semibold">策略与参数</h2><Link to="/guide" className="text-xs text-primary underline underline-offset-4">策略指南</Link></div>
          {data.strategies.map((strategy) => <StrategyDetails key={strategy.meta.id} result={strategy} />)}
        </section>
      </>}
    </div>
  </AppShell>
}
