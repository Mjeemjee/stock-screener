import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router'
import { dataUrl } from '@/lib/dataSource'
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
import AppShell from '@/components/AppShell'
import { runBacktestCore } from '@/backtest/engine'
import { STRATEGIES } from '@/backtest/strategies'
import {
  DEFAULT_COMBO,
  comboLabel,
  combineSignals,
  parseStack,
  serializeStack,
  type EntryMode,
  type ExitMode,
  type StackConfig,
  type StrategyBlock,
} from '@/backtest/combo'
import type {
  BacktestResult,
  Bar,
  HistoryFile,
  IndexFile,
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
  const r = await fetch(dataUrl(`history/${m.toLowerCase()}.json`))
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
      const r = await fetch(dataUrl('history/index.json'))
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

/** 拼图块的强调色（按在组合中的位置循环） */
const BLOCK_COLORS = ['#e11d48', '#2563eb', '#d97706', '#059669', '#7c3aed', '#0891b2']

const resolveStrategy = (id: string) => STRATEGIES.find((s) => s.id === id)

function defaultsOf(specs: { key: string; default: number }[]) {
  const out: Record<string, number> = {}
  for (const s of specs) out[s.key] = s.default
  return out
}

function mkBlock(strategyId: string): StrategyBlock | null {
  const m = resolveStrategy(strategyId)
  if (!m) return null
  return { strategyId, enabled: true, weight: 1, params: defaultsOf(m.params) }
}

function Pct({ v }: { v: number }) {
  return (
    <span className={`tnum ${v >= 0 ? 'text-rose-600' : 'text-emerald-600'}`}>{fmtPct(v)}</span>
  )
}

/** 手机端交易明细：一卡一笔 */
function TradeCards({ trades }: { trades: BacktestResult['trades'] }) {
  return (
    <div className="divide-y divide-border/60">
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
            <TableCell className="text-right tnum">
              {t.entryPrice}
              <div className="text-xs text-muted-foreground">{fmtD(t.entryDate)}</div>
            </TableCell>
            <TableCell className="text-right tnum">
              {t.exitPrice}
              <div className="text-xs text-muted-foreground">{fmtD(t.exitDate)}</div>
            </TableCell>
            <TableCell className="text-right">
              <Pct v={t.pnlPct} />
            </TableCell>
            <TableCell className="text-right tnum">{t.holdingDays} 根</TableCell>
            <TableCell className="text-muted-foreground">{t.reason}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

const TOOLTIP_STYLE = {
  background: 'hsl(0 0% 100%)',
  border: '1px solid hsl(220 16% 88%)',
  borderRadius: 10,
  fontSize: 12,
  boxShadow: '0 8px 24px -12px rgb(16 24 40 / 0.25)',
} as const

/** 拼图块：一个策略实例卡片 */
function BlockCard({
  block,
  color,
  onChange,
  onRemove,
}: {
  block: StrategyBlock
  color: string
  onChange: (patch: Partial<StrategyBlock>) => void
  onRemove: () => void
}) {
  const mod = resolveStrategy(block.strategyId)
  if (!mod) return null
  return (
    <div
      className={`relative rounded-xl border border-border/70 bg-secondary/40 p-3.5 pl-4 transition-opacity ${
        block.enabled ? '' : 'opacity-55'
      }`}
    >
      <span
        className="absolute left-0 top-3 bottom-3 w-1 rounded-full"
        style={{ background: color }}
      />
      <div className="flex items-center gap-2.5 flex-wrap">
        <span className="font-medium text-sm">{mod.name}</span>
        <span className="text-[11px] text-muted-foreground">{mod.id}</span>
        <div className="ml-auto flex items-center gap-2">
          <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
            权重
            <Input
              type="number"
              min={0}
              max={10}
              step={0.5}
              value={block.weight}
              onChange={(e) => {
                const v = Number(e.target.value)
                if (Number.isFinite(v)) onChange({ weight: Math.min(10, Math.max(0, v)) })
              }}
              className="h-7 w-16 px-2 text-xs tnum"
            />
          </label>
          {/* 启用开关（原生按钮实现，避免新增依赖） */}
          <button
            type="button"
            role="switch"
            aria-checked={block.enabled}
            aria-label={block.enabled ? '停用该策略块' : '启用该策略块'}
            onClick={() => onChange({ enabled: !block.enabled })}
            className={`relative h-6 w-11 shrink-0 rounded-full transition-colors ${
              block.enabled ? 'bg-primary' : 'bg-muted'
            }`}
          >
            <span
              className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${
                block.enabled ? 'translate-x-[22px]' : 'translate-x-0.5'
              }`}
            />
          </button>
          <button
            type="button"
            onClick={onRemove}
            aria-label="移除该策略块"
            className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-destructive/15 hover:text-destructive"
          >
            ✕
          </button>
        </div>
      </div>
      <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground line-clamp-2">
        {mod.description}
      </p>
      {mod.params.length > 0 && (
        <div className="mt-2.5 grid grid-cols-2 sm:grid-cols-3 gap-2">
          {mod.params.map((spec) => (
            <label key={spec.key} className="space-y-1 block" title={spec.description}>
              <span className="block text-[11px] text-muted-foreground">
                {spec.label}
                <span className="ml-1 opacity-70">
                  {spec.min}~{spec.max}
                </span>
              </span>
              <Input
                type="number"
                min={spec.min}
                max={spec.max}
                step={spec.step}
                value={block.params[spec.key] ?? spec.default}
                disabled={!block.enabled}
                onChange={(e) => {
                  const v = Number(e.target.value)
                  if (Number.isNaN(v)) return
                  onChange({
                    params: {
                      ...block.params,
                      [spec.key]: Math.min(spec.max, Math.max(spec.min, v)),
                    },
                  })
                }}
                className="h-8 px-2 text-xs tnum"
              />
            </label>
          ))}
        </div>
      )}
    </div>
  )
}

export default function Backtest() {
  const [market, setMarket] = useState<MarketKey>('US')
  const [stack, setStack] = useState<StackConfig>(() => ({
    combo: { ...DEFAULT_COMBO },
    blocks: [mkBlock('ma-cross'), mkBlock('breakout')].filter((b): b is StrategyBlock => b != null),
  }))
  const [codeMode, setCodeMode] = useState(false)
  const [codeText, setCodeText] = useState('')
  const [codeErrors, setCodeErrors] = useState<string[]>([])
  const [codeMsg, setCodeMsg] = useState<string | null>(null)
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
  const [costStress, setCostStress] = useState(true)
  const [stress, setStress] = useState<{ mult: number; ret: number; sharpe: number }[] | null>(null)
  const resultRef = useRef<HTMLDivElement>(null)

  // 切换市场 → 懒加载该市场数据
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setLoadError(null)
    setResult(null)
    setStress(null)
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

  const updateBlock = useCallback((idx: number, patch: Partial<StrategyBlock>) => {
    setStack((prev) => ({
      ...prev,
      blocks: prev.blocks.map((b, i) => (i === idx ? { ...b, ...patch } : b)),
    }))
  }, [])

  const removeBlock = useCallback((idx: number) => {
    setStack((prev) => ({ ...prev, blocks: prev.blocks.filter((_, i) => i !== idx) }))
  }, [])

  const addBlock = useCallback((strategyId: string) => {
    const b = mkBlock(strategyId)
    if (b) setStack((prev) => ({ ...prev, blocks: [...prev.blocks, b] }))
  }, [])

  const availableToAdd = useMemo(
    () => STRATEGIES.filter((s) => !stack.blocks.some((b) => b.strategyId === s.id)),
    [stack.blocks],
  )

  const activeCount = stack.blocks.filter((b) => b.enabled && b.weight > 0).length

  // 进入代码模式：序列化当前组合；退出时不强制应用（避免丢失未应用的编辑由用户决定）
  const enterCodeMode = () => {
    setCodeText(serializeStack(stack))
    setCodeErrors([])
    setCodeMsg(null)
    setCodeMode(true)
  }
  const applyCode = () => {
    const r = parseStack(codeText, resolveStrategy)
    if (r.ok) {
      setStack(r.stack)
      setCodeErrors([])
      setCodeMsg('已应用：表单与组合已同步')
    } else {
      setCodeErrors(r.errors)
      setCodeMsg(null)
    }
  }

  function handleRun() {
    if (!md) return
    setRunning(true)
    setLoadError(null)
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
        .then(async (bench) => {
          const provider = combineSignals(stack, resolveStrategy)
          const res = runBacktestCore(md.stocks, provider, opts, bench, comboLabel(stack))
          if (costStress) {
            // 成本压力：同一组合在 2×/3× 成本下重跑，检验策略对交易成本的敏感度
            const rows = [{ mult: 1, ret: res.metrics.totalReturnPct, sharpe: res.metrics.sharpe }]
            for (const mult of [2, 3]) {
              const r = runBacktestCore(
                md.stocks,
                combineSignals(stack, resolveStrategy),
                { ...opts, costPct: costPct * mult },
                bench,
                comboLabel(stack),
              )
              rows.push({ mult, ret: r.metrics.totalReturnPct, sharpe: r.metrics.sharpe })
            }
            setStress(rows)
          } else {
            setStress(null)
          }
          return res
        })
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
        {
          label: '最大回撤',
          node: <span className="tnum text-amber-600">{m.maxDrawdownPct.toFixed(2)}%</span>,
        },
        { label: '夏普比率', node: <span className="tnum">{m.sharpe.toFixed(2)}</span> },
        { label: '胜率', node: <span className="tnum">{m.winRatePct.toFixed(1)}%</span> },
        { label: '交易次数', node: <span className="tnum">{m.tradeCount}</span> },
      ]
    : []

  return (
    <AppShell
      title="策略回测实验室"
      subtitle={
        <>
          像拼图一样组合多个策略模块 → 调参数（或用代码）→ 一键跑历史回测，全部在你的浏览器里完成
          {md && (
            <>
              <span className="hidden sm:inline">｜</span>
              <br className="sm:hidden" />
              {market === 'US' ? '美股' : '港股'}池 {md.stocks.length} 只 · 数据更新于 {md.generatedAt}
            </>
          )}
        </>
      }
    >
      <div className="space-y-5 sm:space-y-6">
        {/* ① 策略拼图 */}
        <Card>
          <CardHeader className="pb-1">
            <CardTitle className="flex items-center gap-2.5 text-base flex-wrap">
              策略拼图
              <Badge variant="outline" className="tnum">
                {activeCount} 块生效
              </Badge>
              <Link
                to="/learn"
                className="text-xs font-normal text-muted-foreground underline-offset-4 hover:text-primary hover:underline"
              >
                各策略的底层逻辑 →
              </Link>
              <div className="ml-auto flex rounded-full border border-border/60 bg-card/60 p-0.5 text-xs">
                {(['visual', 'code'] as const).map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    onClick={() => (mode === 'code' ? enterCodeMode() : setCodeMode(false))}
                    className={`rounded-full px-3 py-1 transition-colors ${
                      (codeMode ? 'code' : 'visual') === mode
                        ? 'bg-primary font-medium text-primary-foreground'
                        : 'text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    {mode === 'visual' ? '可视化' : '代码'}
                  </button>
                ))}
              </div>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {codeMode ? (
              /* —— 代码模式：组合 JSON 直编 —— */
              <div className="space-y-2.5">
                <textarea
                  value={codeText}
                  onChange={(e) => {
                    setCodeText(e.target.value)
                    setCodeMsg(null)
                  }}
                  spellCheck={false}
                  rows={18}
                  className="code-editor w-full resize-y rounded-xl border border-border/70 bg-background/70 p-3.5 text-xs leading-relaxed outline-none focus:border-primary/60 focus:ring-2 focus:ring-primary/20"
                />
                <div className="flex items-center gap-2.5 flex-wrap">
                  <Button size="sm" onClick={applyCode}>
                    应用代码
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setCodeText(serializeStack(stack))
                      setCodeErrors([])
                      setCodeMsg('已还原为当前组合')
                    }}
                  >
                    还原为当前组合
                  </Button>
                  {codeMsg && <span className="text-xs text-emerald-600">{codeMsg}</span>}
                </div>
                {codeErrors.length > 0 && (
                  <div className="rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-xs text-rose-700 space-y-1">
                    {codeErrors.map((e, i) => (
                      <p key={i}>· {e}</p>
                    ))}
                  </div>
                )}
                <p className="text-[11px] leading-relaxed text-muted-foreground">
                  字段说明：strategy=策略 id（{STRATEGIES.map((s) => s.id).join(' / ')}）；
                  entryMode：all 全部同意 / any 任一同意 / vote 加权投票（配合 voteThresholdPct）；
                  exitMode：any 任一块出信号即卖 / all 全部块出信号才卖；weight=投票权重；params 越界自动收敛到合法范围。
                </p>
              </div>
            ) : (
              /* —— 可视化模式：拼图块 —— */
              <>
                {/* 可添加的策略模块 */}
                {availableToAdd.length > 0 && (
                  <div>
                    <p className="mb-2 text-xs text-muted-foreground">点击添加策略块：</p>
                    <div className="flex flex-wrap gap-2">
                      {availableToAdd.map((s) => (
                        <button
                          key={s.id}
                          type="button"
                          onClick={() => addBlock(s.id)}
                          title={s.description}
                          className="rounded-full border border-dashed border-border bg-secondary/30 px-3.5 py-1.5 text-xs text-muted-foreground transition-colors hover:border-primary/60 hover:bg-primary/10 hover:text-foreground"
                        >
                          ＋ {s.name}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* 组合中的块 */}
                <div className="space-y-2.5">
                  {stack.blocks.length === 0 && (
                    <p className="rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
                      组合为空——从上方添加至少一个策略块
                    </p>
                  )}
                  {stack.blocks.map((b, i) => (
                    <BlockCard
                      key={`${b.strategyId}-${i}`}
                      block={b}
                      color={BLOCK_COLORS[i % BLOCK_COLORS.length]}
                      onChange={(patch) => updateBlock(i, patch)}
                      onRemove={() => removeBlock(i)}
                    />
                  ))}
                </div>

                {/* 组合逻辑 */}
                <div className="rounded-xl border border-border/60 bg-secondary/30 p-3.5 space-y-3">
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div className="space-y-1.5">
                      <Label>买入逻辑（多块如何表决）</Label>
                      <Select
                        value={stack.combo.entryMode}
                        onValueChange={(v) =>
                          setStack((prev) => ({
                            ...prev,
                            combo: { ...prev.combo, entryMode: v as EntryMode },
                          }))
                        }
                      >
                        <SelectTrigger className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="all">全部同意才买（最严）</SelectItem>
                          <SelectItem value="any">任一同意即买（最松）</SelectItem>
                          <SelectItem value="vote">加权投票（按权重）</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    {stack.combo.entryMode === 'vote' && (
                      <div className="space-y-1.5">
                        <Label>
                          投票阈值
                          <span className="ml-1.5 tnum text-primary">{stack.combo.voteThresholdPct}%</span>
                        </Label>
                        <input
                          type="range"
                          min={1}
                          max={100}
                          step={1}
                          value={stack.combo.voteThresholdPct}
                          onChange={(e) =>
                            setStack((prev) => ({
                              ...prev,
                              combo: { ...prev.combo, voteThresholdPct: Number(e.target.value) },
                            }))
                          }
                          className="mt-2.5 w-full"
                        />
                      </div>
                    )}
                    <div className="space-y-1.5">
                      <Label>卖出逻辑</Label>
                      <Select
                        value={stack.combo.exitMode}
                        onValueChange={(v) =>
                          setStack((prev) => ({
                            ...prev,
                            combo: { ...prev.combo, exitMode: v as ExitMode },
                          }))
                        }
                      >
                        <SelectTrigger className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="any">任一块说出场就卖（风控优先）</SelectItem>
                          <SelectItem value="all">全部块说出场才卖（拿得更久）</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  <p className="text-[11px] leading-relaxed text-muted-foreground">
                    {stack.combo.entryMode === 'all' &&
                      '所有启用的策略块在同一天都出买入信号，才会买入——信号更少但更稳。'}
                    {stack.combo.entryMode === 'any' &&
                      '任何一个启用的策略块出买入信号就买入——信号更多但更杂。'}
                    {stack.combo.entryMode === 'vote' &&
                      `按权重计票：同意买入的块权重之和 ÷ 启用块总权重 ≥ ${stack.combo.voteThresholdPct}% 才买入。给更信任的策略块加大权重。`}
                    停用或权重为 0 的块不参与表决。
                  </p>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        {/* ② 运行条件 */}
        <Card>
          <CardHeader className="pb-1">
            <CardTitle className="text-base">运行条件</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="space-y-1.5">
                <Label>市场</Label>
                <Select value={market} onValueChange={(v) => setMarket(v as MarketKey)}>
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="US">美股（标普500 基准）</SelectItem>
                    <SelectItem value="HK">港股（恒生指数 基准）</SelectItem>
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
              <div className="space-y-1.5">
                <Label>初始资金</Label>
                <Input
                  type="number"
                  min={10000}
                  step={10000}
                  value={initialCash}
                  onChange={(e) => setInitialCash(Math.max(10000, Number(e.target.value) || 10000))}
                  className="tnum"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              <div className="space-y-1.5">
                <Label>最大持仓只数</Label>
                <Input
                  type="number"
                  min={1}
                  max={50}
                  value={maxPositions}
                  onChange={(e) =>
                    setMaxPositions(Math.min(50, Math.max(1, Math.round(Number(e.target.value) || 1))))
                  }
                  className="tnum"
                />
              </div>
              <div className="space-y-1.5">
                <Label>单边成本 %</Label>
                <Input
                  type="number"
                  min={0}
                  max={2}
                  step={0.05}
                  value={costPct}
                  onChange={(e) => setCostPct(Math.min(2, Math.max(0, Number(e.target.value) || 0)))}
                  className="tnum"
                />
              </div>
              <div className="space-y-1.5">
                <Label>止损 %（0=关）</Label>
                <Input
                  type="number"
                  min={0}
                  max={50}
                  step={1}
                  value={stopLoss}
                  onChange={(e) => setStopLoss(Math.min(50, Math.max(0, Number(e.target.value) || 0)))}
                  className="tnum"
                />
              </div>
              <div className="space-y-1.5">
                <Label>止盈 %（0=关）</Label>
                <Input
                  type="number"
                  min={0}
                  max={200}
                  step={5}
                  value={takeProfit}
                  onChange={(e) => setTakeProfit(Math.min(200, Math.max(0, Number(e.target.value) || 0)))}
                  className="tnum"
                />
              </div>
              <div className="space-y-1.5">
                <Label>最大持有 K 线（0=关）</Label>
                <Input
                  type="number"
                  min={0}
                  max={500}
                  step={5}
                  value={maxHold}
                  onChange={(e) => setMaxHold(Math.min(500, Math.max(0, Math.round(Number(e.target.value) || 0))))}
                  className="tnum"
                />
              </div>
            </div>
            <div className="flex items-center gap-3 flex-wrap pt-1">
              <Button
                onClick={handleRun}
                disabled={loading || running || !md || activeCount === 0}
                className="min-w-32 shadow-sm"
              >
                {loading ? '数据加载中…' : running ? '回测运行中…' : `运行回测（${activeCount} 块）`}
              </Button>
              <label className="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={costStress}
                  onChange={(e) => setCostStress(e.target.checked)}
                  className="accent-[hsl(var(--primary))] w-4 h-4"
                />
                成本压力测试（同参数 1×/2×/3× 成本各跑一次）
              </label>
              {result && (
                <span className="text-xs text-muted-foreground tnum">
                  本次用时 {result.elapsedMs}ms · 覆盖 {result.stockCount} 只股票
                </span>
              )}
              {activeCount === 0 && (
                <span className="text-xs text-amber-600">至少启用 1 个权重 &gt; 0 的策略块</span>
              )}
            </div>
            {loadError && <p className="text-sm text-rose-600">{loadError}</p>}
          </CardContent>
        </Card>

        {/* ③ 结果区 */}
        {result && m && (
          <div ref={resultRef} className="space-y-5 sm:space-y-6">
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
              {metricCards.map((c) => (
                <div
                  key={c.label}
                  className="rounded-xl border border-border bg-card p-3.5 sm:p-4 shadow-[0_1px_2px_rgb(16_24_40/0.05),0_8px_24px_-16px_rgb(16_24_40/0.12)]"
                >
                  <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
                    {c.label}
                  </p>
                  <p className="mt-1 text-xl sm:text-2xl font-semibold">{c.node}</p>
                </div>
              ))}
            </div>

            {stress && (
              <div className="rounded-xl border border-border bg-card px-4 py-3.5 shadow-[0_1px_2px_rgb(16_24_40/0.05),0_8px_24px_-16px_rgb(16_24_40/0.12)]">
                <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
                  成本压力 · 总收益 / 夏普 随成本倍数变化
                </p>
                <div className="mt-2 flex items-center gap-4 sm:gap-8 flex-wrap">
                  {stress.map((s) => (
                    <div key={s.mult} className="flex items-baseline gap-2">
                      <span className="text-xs text-muted-foreground tnum">{s.mult}×</span>
                      <span className="text-lg font-semibold tnum">
                        <Pct v={s.ret} />
                      </span>
                      <span className="text-xs text-muted-foreground tnum">夏普 {s.sharpe}</span>
                    </div>
                  ))}
                  <span className="text-xs text-muted-foreground">
                    {stress[2].ret <= 0
                      ? '成本翻倍即吞噬全部收益——策略对成本高度敏感，审慎对待'
                      : stress[0].ret - stress[2].ret > stress[0].ret * 0.5
                        ? '成本敏感度偏高，收益过半依赖低摩擦环境'
                        : '成本敏感度可控'}
                  </span>
                </div>
              </div>
            )}

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 flex-wrap text-base">
                  净值曲线（起点 = 1）
                  <Badge variant="outline">{result.label ?? result.strategyId}</Badge>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-64 sm:h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={result.equity} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(220 16% 90%)" opacity={0.8} />
                      <XAxis
                        dataKey="d"
                        tickFormatter={(d: number) => toIso(d).slice(0, 7)}
                        tick={{ fontSize: 11, fill: 'hsl(220 12% 42%)' }}
                        minTickGap={48}
                      />
                      <YAxis
                        tickFormatter={(v: number) => v.toFixed(2)}
                        tick={{ fontSize: 11, fill: 'hsl(220 12% 42%)' }}
                        domain={['auto', 'auto']}
                      />
                      <Tooltip
                        contentStyle={TOOLTIP_STYLE}
                        labelStyle={{ color: 'hsl(213 31% 91%)' }}
                        labelFormatter={(d) => fmtD(Number(d))}
                        formatter={(value: number | string, name: string) => [
                          typeof value === 'number' ? value.toFixed(3) : value,
                          name,
                        ]}
                      />
                      <Legend />
                      <Line
                        type="monotone"
                        dataKey="v"
                        name="策略净值"
                        stroke="#e11d48"
                        dot={false}
                        strokeWidth={2}
                      />
                      <Line
                        type="monotone"
                        dataKey="bench"
                        name="基准（指数）"
                        stroke="#64748b"
                        dot={false}
                        strokeWidth={1.2}
                        strokeDasharray="4 3"
                        connectNulls
                      />
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
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(220 16% 90%)" opacity={0.8} />
                      <XAxis
                        dataKey="d"
                        tickFormatter={(d: number) => toIso(d).slice(0, 7)}
                        tick={{ fontSize: 11, fill: 'hsl(220 12% 42%)' }}
                        minTickGap={48}
                      />
                      <YAxis
                        tickFormatter={(v: number) => v.toFixed(0)}
                        tick={{ fontSize: 11, fill: 'hsl(220 12% 42%)' }}
                      />
                      <Tooltip
                        contentStyle={TOOLTIP_STYLE}
                        labelStyle={{ color: 'hsl(213 31% 91%)' }}
                        labelFormatter={(d) => fmtD(Number(d))}
                        formatter={(value: number | string) => [
                          `${typeof value === 'number' ? value.toFixed(2) : value}%`,
                          '回撤',
                        ]}
                      />
                      <Area type="monotone" dataKey="dd" stroke="#d97706" fill="#d9770622" strokeWidth={1.4} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">
                  交易明细
                  <span className="ml-2 text-sm font-normal text-muted-foreground tnum">
                    共 {result.trades.length} 笔
                    {result.trades.length > 30 ? '，按出场时间显示最近 30 笔' : ''}
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

        {/* 首次使用引导 */}
        {!result && !loading && (
          <Card>
            <CardContent className="py-8 text-center space-y-3">
              <p className="text-gradient text-lg font-semibold">三步上手</p>
              <div className="mx-auto grid max-w-2xl grid-cols-1 sm:grid-cols-3 gap-3 text-left">
                {[
                  ['① 拼策略', '从上方点击添加策略块，可以只留一个，也可以多个组合'],
                  ['② 调规则', '可视化拖数字，或切到「代码」模式直接改 JSON'],
                  ['③ 跑回测', '点「运行回测」，看净值曲线有没有跑赢基准指数'],
                ].map(([t, d]) => (
                  <div key={t} className="rounded-xl border border-border/60 bg-secondary/30 p-3.5">
                    <p className="text-sm font-medium">{t}</p>
                    <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{d}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        <div className="space-y-1 pb-6 text-xs leading-relaxed text-muted-foreground">
          <p>
            口径说明：前复权日K；信号当日收盘产生、次日开盘成交（T+1）；等权分仓、允许零碎股；单边成本含佣金与滑点。
          </p>
          <p className="text-amber-600">
            {md?.note ?? '股票池按当日成交额选取，回测存在幸存者偏差，结果偏乐观。'}
            历史回测不代表未来收益，结果仅供研究，不构成投资建议。
          </p>
        </div>
      </div>
    </AppShell>
  )
}
