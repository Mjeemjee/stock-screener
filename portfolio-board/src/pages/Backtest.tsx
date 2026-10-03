import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { runBacktest } from '@/backtest/engine'
import { STRATEGIES } from '@/backtest/strategies'
import type {
  BacktestResult,
  Bar,
  HistoryFile,
  IndexFile,
  ParamSpec,
  RawBar,
  StockSeries,
} from '@/backtest/types'

type MarketKey = 'US' | 'HK'

interface MarketData {
  stocks: StockSeries[]
  generatedAt: string
  note: string
  minDate: number
  maxDate: number
}

const dataCache: Partial<Record<MarketKey, MarketData>> = {}
let benchCache: Record<'US' | 'HK', Bar[] | undefined> | null = null

const rawToBar = (b: RawBar): Bar => ({ d: b[0], o: b[1], h: b[2], l: b[3], c: b[4], v: b[5] })

async function loadMarket(m: MarketKey): Promise<MarketData> {
  const hit = dataCache[m]
  if (hit) return hit
  const r = await fetch(`./data/history/${m.toLowerCase()}.json`)
  if (!r.ok) throw new Error(`${m} 历史数据加载失败（HTTP ${r.status}）`)
  const j = (await r.json()) as HistoryFile
  const stocks: StockSeries[] = j.stocks.map((s) => ({
    code: s.code,
    name: s.name,
    bars: s.bars.map(rawToBar),
  }))
  let minDate = Infinity
  let maxDate = 0
  for (const s of stocks)
    for (const b of s.bars) {
      if (b.d < minDate) minDate = b.d
      if (b.d > maxDate) maxDate = b.d
    }
  const md: MarketData = { stocks, generatedAt: j.generated_at, note: j.survivorship_note, minDate, maxDate }
  dataCache[m] = md
  return md
}

async function loadBench(m: MarketKey): Promise<Bar[] | undefined> {
  if (!benchCache) {
    benchCache = { US: undefined, HK: undefined }
    try {
      const r = await fetch('./data/history/index.json')
      if (r.ok) {
        const j = (await r.json()) as IndexFile
        if (j.indexes.SPX) benchCache.US = j.indexes.SPX.bars.map(rawToBar)
        if (j.indexes.HSI) benchCache.HK = j.indexes.HSI.bars.map(rawToBar)
      }
    } catch {
      // 基准缺失不阻塞回测
    }
  }
  return benchCache[m]
}

const toIso = (d: number) => {
  const s = String(d)
  return `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`
}
const toYmd = (iso: string) => Number(iso.replaceAll('-', ''))
const fmtD = (d: number) => toIso(d)
const fmtPct = (v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`

function defaultsOf(specs: ParamSpec[]) {
  const out: Record<string, number> = {}
  for (const s of specs) out[s.key] = s.default
  return out
}

function Pct({ v }: { v: number }) {
  return <span className={v >= 0 ? 'text-red-500' : 'text-emerald-500'}>{fmtPct(v)}</span>
}

/** 手机端交易明细：一卡一笔 */
function TradeCards({ trades }: { trades: BacktestResult['trades'] }) {
  return (
    <div className="divide-y">
      {trades.map((t, i) => (
        <div key={`${t.code}-${t.exitDate}-${i}`} className="px-4 py-3 space-y-1">
          <div className="flex items-baseline justify-between gap-2">
            <div className="min-w-0">
              <span className="font-medium">{t.name}</span>
              <span className="ml-1.5 text-xs text-muted-foreground">{t.code}</span>
            </div>
            <Pct v={t.pnlPct} />
          </div>
          <p className="text-xs text-muted-foreground">
            {fmtD(t.entryDate)} 买 {t.entryPrice} → {fmtD(t.exitDate)} 卖 {t.exitPrice}
            ｜持 {t.holdingDays} 根K线｜{t.reason}
          </p>
        </div>
      ))}
    </div>
  )
}

function TradeTable({ trades }: { trades: BacktestResult['trades'] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>标的</TableHead>
          <TableHead className="text-right">买入</TableHead>
          <TableHead className="text-right">卖出</TableHead>
          <TableHead className="text-right">收益</TableHead>
          <TableHead className="text-right">持有</TableHead>
          <TableHead>出场原因</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {trades.map((t, i) => (
          <TableRow key={`${t.code}-${t.exitDate}-${i}`}>
            <TableCell>
              <div className="font-medium">{t.name}</div>
              <div className="text-xs text-muted-foreground">{t.code}</div>
            </TableCell>
            <TableCell className="text-right">
              {t.entryPrice}
              <div className="text-xs text-muted-foreground">{fmtD(t.entryDate)}</div>
            </TableCell>
            <TableCell className="text-right">
              {t.exitPrice}
              <div className="text-xs text-muted-foreground">{fmtD(t.exitDate)}</div>
            </TableCell>
            <TableCell className="text-right">
              <Pct v={t.pnlPct} />
            </TableCell>
            <TableCell className="text-right">{t.holdingDays} 根</TableCell>
            <TableCell className="text-muted-foreground">{t.reason}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

export default function Backtest() {
  const [market, setMarket] = useState<MarketKey>('US')
  const [strategyId, setStrategyId] = useState(STRATEGIES[0]?.id ?? '')
  const strategy = STRATEGIES.find((s) => s.id === strategyId) ?? STRATEGIES[0]
  const [params, setParams] = useState<Record<string, number>>(() =>
    defaultsOf(strategy?.params ?? []),
  )
  const [initialCash, setInitialCash] = useState(1000000)
  const [maxPositions, setMaxPositions] = useState(10)
  const [costPct, setCostPct] = useState(0.15)
  const [stopLoss, setStopLoss] = useState(0)
  const [takeProfit, setTakeProfit] = useState(0)
  const [maxHold, setMaxHold] = useState(0)
  const [startIso, setStartIso] = useState('')
  const [endIso, setEndIso] = useState('')
  const [md, setMd] = useState<MarketData | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<BacktestResult | null>(null)
  const resultRef = useRef<HTMLDivElement>(null)

  // 切换市场 → 懒加载该市场数据
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setLoadError(null)
    setResult(null)
    loadMarket(market)
      .then((d) => {
        if (cancelled) return
        setMd(d)
        setStartIso(toIso(d.minDate))
        setEndIso(toIso(d.maxDate))
      })
      .catch((e: Error) => !cancelled && setLoadError(e.message))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [market])

  const changeStrategy = useCallback(
    (id: string) => {
      setStrategyId(id)
      const s = STRATEGIES.find((x) => x.id === id)
      if (s) setParams(defaultsOf(s.params))
    },
    [setStrategyId],
  )

  function handleRun() {
    if (!md || !strategy) return
    setRunning(true)
    const opts = {
      initialCash,
      maxPositions,
      costPct,
      startDate: startIso ? toYmd(startIso) : undefined,
      endDate: endIso ? toYmd(endIso) : undefined,
      stopLossPct: stopLoss,
      takeProfitPct: takeProfit,
      maxHoldDays: maxHold,
    }
    // 让出一帧渲染 loading，再跑计算
    setTimeout(() => {
      void loadBench(market)
        .then((bench) => runBacktest(md.stocks, strategy, params, opts, bench))
        .then((res) => {
          setResult(res)
          setTimeout(() => resultRef.current?.scrollIntoView({ behavior: 'smooth' }), 80)
        })
        .catch((e: Error) => setLoadError(`回测运行失败：${e.message}`))
        .finally(() => setRunning(false))
    }, 60)
  }

  const m = result?.metrics
  const metricCards = m
    ? [
        { label: '总收益', node: <Pct v={m.totalReturnPct} /> },
        { label: '年化收益', node: <Pct v={m.cagrPct} /> },
        { label: '最大回撤', node: <span className="text-emerald-500">{m.maxDrawdownPct.toFixed(2)}%</span> },
        { label: '夏普比率', node: <span>{m.sharpe.toFixed(2)}</span> },
        { label: '胜率', node: <span>{m.winRatePct.toFixed(1)}%</span> },
        { label: '交易次数', node: <span>{m.tradeCount}</span> },
      ]
    : []

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 py-4 space-y-1.5">
          <div className="flex items-center justify-between gap-2">
            <h1 className="text-lg sm:text-xl font-bold">策略回测实验室</h1>
            <nav className="flex gap-3 sm:gap-4 text-sm shrink-0">
              <Link to="/" className="text-muted-foreground hover:text-foreground">选股</Link>
              <span className="font-medium">回测</span>
              <Link to="/holdings" className="text-muted-foreground hover:text-foreground">持仓</Link>
              <Link to="/guide" className="text-muted-foreground hover:text-foreground">指南</Link>
            </nav>
          </div>
          <p className="text-xs text-muted-foreground leading-relaxed">
            选策略 → 调参数 → 一键跑历史回测，全部在你的浏览器里完成
            {md && (
              <>
                <span className="hidden sm:inline">｜</span>
                <br className="sm:hidden" />
                {market === 'US' ? '美股' : '港股'}池 {md.stocks.length} 只 · 数据更新于 {md.generatedAt}
              </>
            )}
          </p>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 sm:px-6 py-5 sm:py-6 space-y-6">
        {/* 控制区 */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">回测设置</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="space-y-1.5">
                <Label>市场</Label>
                <Select value={market} onValueChange={(v) => setMarket(v as MarketKey)}>
                  <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="US">美股（标普500 基准）</SelectItem>
                    <SelectItem value="HK">港股（恒生指数 基准）</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5 col-span-2 md:col-span-1">
                <Label>策略模块</Label>
                <Select value={strategyId} onValueChange={changeStrategy}>
                  <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {STRATEGIES.map((s) => (
                      <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>开始日期</Label>
                <Input type="date" value={startIso} onChange={(e) => setStartIso(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label>结束日期</Label>
                <Input type="date" value={endIso} onChange={(e) => setEndIso(e.target.value)} />
              </div>
            </div>

            {strategy && (
              <p className="text-xs text-muted-foreground leading-relaxed border-l-2 border-muted pl-3">
                {strategy.description}
              </p>
            )}

            {/* 策略参数（schema 自动生成） */}
            {strategy && strategy.params.length > 0 && (
              <div>
                <p className="text-sm font-medium mb-2">策略参数</p>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {strategy.params.map((spec) => (
                    <div key={spec.key} className="space-y-1.5">
                      <Label title={spec.description}>
                        {spec.label}
                        <span className="ml-1 text-xs text-muted-foreground">({spec.min}~{spec.max})</span>
                      </Label>
                      <Input
                        type="number"
                        min={spec.min}
                        max={spec.max}
                        step={spec.step}
                        value={params[spec.key] ?? spec.default}
                        onChange={(e) => {
                          const v = Number(e.target.value)
                          if (Number.isNaN(v)) return
                          setParams((prev) => ({
                            ...prev,
                            [spec.key]: Math.min(spec.max, Math.max(spec.min, v)),
                          }))
                        }}
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 全局参数 */}
            <div>
              <p className="text-sm font-medium mb-2">交易规则（0 = 关闭该项）</p>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                <div className="space-y-1.5">
                  <Label>初始资金</Label>
                  <Input type="number" min={10000} step={10000} value={initialCash}
                    onChange={(e) => setInitialCash(Math.max(10000, Number(e.target.value) || 10000))} />
                </div>
                <div className="space-y-1.5">
                  <Label>最大持仓只数</Label>
                  <Input type="number" min={1} max={50} value={maxPositions}
                    onChange={(e) => setMaxPositions(Math.min(50, Math.max(1, Math.round(Number(e.target.value) || 1))))} />
                </div>
                <div className="space-y-1.5">
                  <Label>单边成本 %（佣金+滑点）</Label>
                  <Input type="number" min={0} max={2} step={0.05} value={costPct}
                    onChange={(e) => setCostPct(Math.min(2, Math.max(0, Number(e.target.value) || 0)))} />
                </div>
                <div className="space-y-1.5">
                  <Label>止损 %</Label>
                  <Input type="number" min={0} max={50} step={1} value={stopLoss}
                    onChange={(e) => setStopLoss(Math.min(50, Math.max(0, Number(e.target.value) || 0)))} />
                </div>
                <div className="space-y-1.5">
                  <Label>止盈 %</Label>
                  <Input type="number" min={0} max={200} step={5} value={takeProfit}
                    onChange={(e) => setTakeProfit(Math.min(200, Math.max(0, Number(e.target.value) || 0)))} />
                </div>
                <div className="space-y-1.5">
                  <Label>最大持有 K 线数</Label>
                  <Input type="number" min={0} max={500} step={5} value={maxHold}
                    onChange={(e) => setMaxHold(Math.min(500, Math.max(0, Math.round(Number(e.target.value) || 0))))} />
                </div>
              </div>
            </div>

            <div className="flex items-center gap-3 flex-wrap">
              <Button onClick={handleRun} disabled={loading || running || !md} className="min-w-28">
                {loading ? '数据加载中…' : running ? '回测运行中…' : '运行回测'}
              </Button>
              {result && (
                <span className="text-xs text-muted-foreground">
                  本次用时 {result.elapsedMs}ms · 覆盖 {result.stockCount} 只股票
                </span>
              )}
            </div>
            {loadError && <p className="text-sm text-red-500">{loadError}</p>}
          </CardContent>
        </Card>

        {/* 结果区 */}
        {result && m && (
          <div ref={resultRef} className="space-y-6">
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
              {metricCards.map((c) => (
                <Card key={c.label}>
                  <CardContent className="p-3 sm:p-4">
                    <p className="text-xs text-muted-foreground">{c.label}</p>
                    <p className="text-lg sm:text-xl font-semibold mt-0.5">{c.node}</p>
                  </CardContent>
                </Card>
              ))}
            </div>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center gap-2 flex-wrap">
                  净值曲线（起点 = 1）
                  <Badge variant="outline">{result.strategyId}</Badge>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-64 sm:h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={result.equity} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
                      <CartesianGrid strokeDasharray="3 3" opacity={0.4} />
                      <XAxis dataKey="d" tickFormatter={(d: number) => toIso(d).slice(0, 7)}
                        tick={{ fontSize: 11 }} minTickGap={48} />
                      <YAxis tickFormatter={(v: number) => v.toFixed(2)} tick={{ fontSize: 11 }} domain={['auto', 'auto']} />
                      <Tooltip
                        labelFormatter={(d) => fmtD(Number(d))}
                        formatter={(value: number | string, name: string) => [
                          typeof value === 'number' ? value.toFixed(3) : value,
                          name,
                        ]}
                      />
                      <Legend />
                      <Line type="monotone" dataKey="v" name="策略净值" stroke="#dc2626"
                        dot={false} strokeWidth={1.8} />
                      <Line type="monotone" dataKey="bench" name="基准（指数）" stroke="#9ca3af"
                        dot={false} strokeWidth={1.2} strokeDasharray="4 3" connectNulls />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">回撤（%）</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-40 sm:h-48">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={result.drawdown} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
                      <CartesianGrid strokeDasharray="3 3" opacity={0.4} />
                      <XAxis dataKey="d" tickFormatter={(d: number) => toIso(d).slice(0, 7)}
                        tick={{ fontSize: 11 }} minTickGap={48} />
                      <YAxis tickFormatter={(v: number) => v.toFixed(0)} tick={{ fontSize: 11 }} />
                      <Tooltip labelFormatter={(d) => fmtD(Number(d))}
                        formatter={(value: number | string) => [
                          `${typeof value === 'number' ? value.toFixed(2) : value}%`, '回撤']}/>
                      <Area type="monotone" dataKey="dd" stroke="#f59e0b" fill="#f59e0b33" strokeWidth={1.2} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">
                  交易明细
                  <span className="ml-2 text-sm font-normal text-muted-foreground">
                    共 {result.trades.length} 笔{result.trades.length > 30 ? '，按出场时间显示最近 30 笔' : ''}
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0 sm:p-0">
                <div className="md:hidden">
                  <TradeCards trades={result.trades.slice(0, 30)} />
                </div>
                <div className="hidden md:block">
                  <TradeTable trades={result.trades.slice(0, 30)} />
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        <div className="text-xs text-muted-foreground leading-relaxed space-y-1 pb-6">
          <p>口径说明：前复权日K；信号当日收盘产生、次日开盘成交（T+1）；等权分仓、允许零碎股；单边成本含佣金与滑点。</p>
          <p className="text-amber-600">
            {md?.note ?? '股票池按当日成交额选取，回测存在幸存者偏差，结果偏乐观。'}
            历史回测不代表未来收益，结果仅供研究，不构成投资建议。
          </p>
        </div>
      </main>
    </div>
  )
}
