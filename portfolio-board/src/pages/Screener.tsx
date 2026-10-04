import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import AppShell from '@/components/AppShell'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type { ScreenHit, ScreenerResults, StrategyResult } from '@/types/screener'

const STATUS_STYLE: Record<string, { label: string; variant: 'default' | 'secondary' | 'outline' }> = {
  active: { label: '启用中', variant: 'default' },
  watch: { label: '观察中', variant: 'secondary' },
  paused: { label: '已暂停', variant: 'outline' },
}

function mktOf(code: string) {
  return code.startsWith('US.') ? 'US' : code.startsWith('HK.') ? 'HK' : '?'
}

function fmtMv(v?: number) {
  if (v == null) return '-'
  if (v >= 1e12) return (v / 1e12).toFixed(2) + 'T'
  if (v >= 1e9) return (v / 1e9).toFixed(1) + 'B'
  return (v / 1e6).toFixed(0) + 'M'
}

function ChangeText({ value }: { value?: number }) {
  if (value == null) return <span>-</span>
  return (
    <span className={value >= 0 ? 'text-red-500' : 'text-emerald-500'}>
      {value >= 0 ? '+' : ''}
      {value.toFixed(2)}%
    </span>
  )
}

function StrategyCard({ r }: { r: StrategyResult }) {
  const s = STATUS_STYLE[r.meta.status] ?? STATUS_STYLE.watch
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2 flex-wrap">
          {r.meta.name}
          <Badge variant={s.variant}>{s.label}</Badge>
          {r.meta.markets.map((m) => (
            <Badge key={m} variant="outline">{m}</Badge>
          ))}
          <span className="sm:ml-auto text-sm font-normal text-muted-foreground">
            {r.meta.error ? '执行出错' : `${r.meta.hit_count} 只命中`}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="text-sm space-y-2">
        <p className="text-muted-foreground">{r.meta.principle}</p>
        <p className="text-xs text-muted-foreground">来源：{r.meta.source}</p>
        {r.meta.cloud_note && (
          <p className="text-xs text-sky-400">云端版说明：{r.meta.cloud_note}</p>
        )}
        <details className="text-xs">
          <summary className="cursor-pointer text-muted-foreground hover:text-foreground">参数与风险</summary>
          <pre className="mt-1 rounded bg-muted p-2 overflow-x-auto">{JSON.stringify(r.meta.params, null, 2)}</pre>
          <p className="mt-1 text-amber-400">{r.meta.risk}</p>
        </details>
      </CardContent>
    </Card>
  )
}

/** 手机端：一张卡片 = 一只标的，免横向滚动 */
function HitCardList({ hits }: { hits: ScreenHit[] }) {
  return (
    <div className="divide-y">
      {hits.map((h) => (
        <div key={h.code} className="px-4 py-3 space-y-1">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-2 min-w-0">
              <Badge variant={mktOf(h.code) === 'US' ? 'default' : 'secondary'} className="shrink-0">
                {mktOf(h.code)}
              </Badge>
              <div className="min-w-0">
                <div className="font-medium leading-tight truncate">{h.name}</div>
                <div className="text-xs text-muted-foreground">{h.code}</div>
              </div>
            </div>
            <div className="text-right shrink-0">
              <div className="font-medium leading-tight tnum">{h.last_price?.toFixed(2)}</div>
              <div className="text-xs tnum">
                <ChangeText value={h.change_rate} />
              </div>
            </div>
          </div>
          <p className="text-xs text-muted-foreground leading-relaxed">
            市值 {fmtMv(h.circular_market_val)} · {h.reason}
          </p>
        </div>
      ))}
    </div>
  )
}

/** 桌面端：完整表格 */
function HitTable({ hits }: { hits: ScreenHit[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>标的</TableHead>
          <TableHead className="text-right">最新价</TableHead>
          <TableHead className="text-right">当日涨跌</TableHead>
          <TableHead className="text-right">市值</TableHead>
          <TableHead>命中原因</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {hits.map((h) => (
          <TableRow key={h.code}>
            <TableCell>
              <div className="flex items-center gap-2">
                <Badge variant={mktOf(h.code) === 'US' ? 'default' : 'secondary'}>{mktOf(h.code)}</Badge>
                <div>
                  <div className="font-medium">{h.name}</div>
                  <div className="text-xs text-muted-foreground">{h.code}</div>
                </div>
              </div>
            </TableCell>
            <TableCell className="text-right tnum">{h.last_price?.toFixed(2)}</TableCell>
            <TableCell className="text-right tnum">
              <ChangeText value={h.change_rate} />
            </TableCell>
            <TableCell className="text-right tnum">{fmtMv(h.circular_market_val)}</TableCell>
            <TableCell className="text-xs text-muted-foreground max-w-[280px]">{h.reason}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

function HitList({ r }: { r: StrategyResult }) {
  if (r.meta.error)
    return <p className="p-4 text-sm text-red-500">策略执行出错：{r.meta.error}</p>
  if (r.hits.length === 0)
    return (
      <p className="p-4 text-sm text-muted-foreground">
        本期无命中标的。
        {r.meta.cloud_note && <span className="block mt-1 text-sky-400">{r.meta.cloud_note}</span>}
      </p>
    )
  return (
    <>
      <div className="md:hidden">
        <HitCardList hits={r.hits} />
      </div>
      <div className="hidden md:block">
        <HitTable hits={r.hits} />
      </div>
    </>
  )
}

export default function Screener() {
  const [data, setData] = useState<ScreenerResults | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('./data/screener_results.json')
      .then((r) => {
        if (!r.ok) throw new Error('screener_results.json 加载失败')
        return r.json()
      })
      .then(setData)
      .catch((e: Error) => setError(e.message))
  }, [])

  if (error)
    return (
      <div className="p-10 text-center">
        <p className="text-red-500 mb-2">选股数据加载失败：{error}</p>
        <p className="text-muted-foreground text-sm">请先运行 <code>python -m screener.cloud_engine</code>（详见 <Link to="/guide" className="underline">策略进化指南</Link>）</p>
      </div>
    )
  if (!data) return <div className="p-10 text-center text-muted-foreground">数据加载中…</div>

  const active = data.strategies.filter((s) => s.meta.status !== 'paused')

  return (
    <AppShell
      title="港美股选股台"
      subtitle={
        <>
          全市场 {data.universe_total.toLocaleString()} 只 → 过滤后 {data.universe_after_filter.toLocaleString()} 只
          <span className="hidden sm:inline">｜</span>
          <br className="sm:hidden" />
          扫描于 {data.generated_at}
        </>
      }
    >
      <div className="space-y-8">
        <section>
          <h2 className="text-base sm:text-lg font-semibold mb-3">策略库（{data.strategies.length} 个策略，持续进化中）</h2>
          <div className="grid md:grid-cols-2 gap-4">
            {data.strategies.map((r) => (
              <StrategyCard key={r.meta.id} r={r} />
            ))}
          </div>
          <p className="mt-3 text-xs text-muted-foreground leading-relaxed">
            看到有意思的策略想加进来？把思路发给我即可——分析适用性 → 写成模块 → 先标「观察中」验证 → 你确认后启用。详见
            <Link to="/guide" className="underline ml-1">策略进化指南</Link>。
          </p>
        </section>

        <section>
          <h2 className="text-base sm:text-lg font-semibold mb-3">最新筛选结果</h2>
          <Tabs defaultValue={active[0]?.meta.id}>
            <TabsList className="flex flex-wrap h-auto w-full sm:w-fit gap-1">
              {active.map((r) => (
                <TabsTrigger key={r.meta.id} value={r.meta.id} className="flex-none">
                  {r.meta.name}（{r.meta.hit_count}）
                </TabsTrigger>
              ))}
            </TabsList>
            {active.map((r) => (
              <TabsContent key={r.meta.id} value={r.meta.id}>
                <Card>
                  <CardContent className="p-0">
                    <HitList r={r} />
                  </CardContent>
                </Card>
                <p className="mt-2 text-xs text-amber-400/90 leading-relaxed">风险提示：{r.meta.risk}</p>
              </TabsContent>
            ))}
          </Tabs>
        </section>

        <p className="text-center text-xs text-muted-foreground pb-6 leading-relaxed">
          筛选结果仅为量化初筛，不构成投资建议；红涨绿跌。
          数据源：{data.data_source ?? '富途 OpenAPI 全市场快照'}。
        </p>
      </div>
    </AppShell>
  )
}
