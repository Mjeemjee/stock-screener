/** 策略拼图组合：多块策略信号的合成逻辑 + JSON 序列化/校验。
 *
 * 组合语义：
 *  - 买入：all=全部启用块同时出信号；any=任一块出信号；vote=同意块权重和/总权重 ≥ 阈值
 *  - 卖出：any=任一块出出场信号即卖（默认，风控优先）；all=全部块出信号才卖
 *  - 停用（enabled=false）或权重为 0 的块不参与合成
 *  - 只有 1 个启用块时，三种买入逻辑等价于单策略
 *
 * 策略解析用依赖注入（resolve），避免依赖 import.meta.glob 的注册表，
 * 使本模块可在纯 Node 环境回归（scripts/validate-backtest.cjs）。
 */
import type { Bar, SignalProvider, StrategyModule } from './types'

export type EntryMode = 'all' | 'any' | 'vote'
export type ExitMode = 'any' | 'all'

export interface ComboConfig {
  entryMode: EntryMode
  /** 加权投票阈值（0~100），仅 entryMode=vote 生效 */
  voteThresholdPct: number
  exitMode: ExitMode
}

export interface StrategyBlock {
  strategyId: string
  enabled: boolean
  weight: number
  params: Record<string, number>
}

export interface StackConfig {
  combo: ComboConfig
  blocks: StrategyBlock[]
}

export const DEFAULT_COMBO: ComboConfig = {
  entryMode: 'vote',
  voteThresholdPct: 50,
  exitMode: 'any',
}

export type ResolveStrategy = (id: string) => StrategyModule | undefined

/** 参与合成的块：启用且权重 > 0 */
export function activeBlocks(stack: StackConfig): StrategyBlock[] {
  return stack.blocks.filter((b) => b.enabled && b.weight > 0)
}

/** 把组合编译成信号提供者（引擎统一入口） */
export function combineSignals(stack: StackConfig, resolve: ResolveStrategy): SignalProvider {
  const act = activeBlocks(stack)
  if (act.length === 0) throw new Error('组合为空：至少启用 1 个权重 > 0 的策略块')
  const mods = act.map((b) => {
    const m = resolve(b.strategyId)
    if (!m) throw new Error(`未知策略模块：${b.strategyId}`)
    return { m, w: b.weight, params: b.params }
  })
  const totalW = mods.reduce((a, x) => a + x.w, 0)
  const combo = stack.combo
  return {
    id: 'combo:' + mods.map((x) => x.m.id).join('+'),
    prepare(bars: Bar[]) {
      const sigs = mods.map((x) => x.m.prepare(bars, x.params))
      const n = bars.length
      const entries = new Array<boolean>(n).fill(false)
      const exits = new Array<boolean>(n).fill(false)
      for (let i = 0; i < n; i++) {
        if (combo.entryMode === 'all') {
          entries[i] = sigs.every((s) => s.entries[i])
        } else if (combo.entryMode === 'any') {
          entries[i] = sigs.some((s) => s.entries[i])
        } else {
          let w = 0
          for (let k = 0; k < sigs.length; k++) if (sigs[k].entries[i]) w += mods[k].w
          entries[i] = (w / totalW) * 100 >= combo.voteThresholdPct - 1e-9
        }
        exits[i] =
          combo.exitMode === 'all' ? sigs.every((s) => s.exits[i]) : sigs.some((s) => s.exits[i])
      }
      return { entries, exits }
    },
  }
}

const MODE_TEXT: Record<EntryMode, string> = {
  all: '全部同意',
  any: '任一同意',
  vote: '加权投票',
}

export function comboLabel(stack: StackConfig): string {
  const n = activeBlocks(stack).length
  const entry =
    stack.combo.entryMode === 'vote'
      ? `${MODE_TEXT.vote}≥${stack.combo.voteThresholdPct}%`
      : MODE_TEXT[stack.combo.entryMode]
  return n <= 1
    ? `单策略`
    : `拼图组合 · ${n} 块 · ${entry} / 出场${stack.combo.exitMode === 'any' ? '任一' : '全部'}`
}

// ---------------------------------------------------------------- JSON 代码模式

/** 序列化为代码模式 JSON（字段名面向用户，保持稳定） */
export function serializeStack(stack: StackConfig): string {
  return JSON.stringify(
    {
      combo: {
        entryMode: stack.combo.entryMode,
        voteThresholdPct: stack.combo.voteThresholdPct,
        exitMode: stack.combo.exitMode,
      },
      blocks: stack.blocks.map((b) => ({
        strategy: b.strategyId,
        enabled: b.enabled,
        weight: b.weight,
        params: b.params,
      })),
    },
    null,
    2,
  )
}

type ParseOk = { ok: true; stack: StackConfig }
type ParseErr = { ok: false; errors: string[] }

/** 解析并校验代码模式 JSON；参数越界自动收敛到 min/max，缺省补默认值 */
export function parseStack(json: string, resolve: ResolveStrategy): ParseOk | ParseErr {
  const errors: string[] = []
  let raw: unknown
  try {
    raw = JSON.parse(json)
  } catch (e) {
    return { ok: false, errors: [`JSON 语法错误：${(e as Error).message}`] }
  }
  if (typeof raw !== 'object' || raw == null) return { ok: false, errors: ['顶层必须是对象'] }
  const obj = raw as Record<string, unknown>

  // combo
  const c = (obj.combo ?? {}) as Record<string, unknown>
  const entryMode = c.entryMode ?? DEFAULT_COMBO.entryMode
  const exitMode = c.exitMode ?? DEFAULT_COMBO.exitMode
  if (entryMode !== 'all' && entryMode !== 'any' && entryMode !== 'vote')
    errors.push(`combo.entryMode 只能是 all / any / vote（收到 ${JSON.stringify(entryMode)}）`)
  if (exitMode !== 'any' && exitMode !== 'all')
    errors.push(`combo.exitMode 只能是 any / all（收到 ${JSON.stringify(exitMode)}）`)
  let voteThresholdPct = Number(c.voteThresholdPct ?? DEFAULT_COMBO.voteThresholdPct)
  if (!Number.isFinite(voteThresholdPct)) {
    errors.push('combo.voteThresholdPct 必须是数字')
    voteThresholdPct = DEFAULT_COMBO.voteThresholdPct
  }
  voteThresholdPct = Math.min(100, Math.max(1, voteThresholdPct))

  // blocks
  if (!Array.isArray(obj.blocks) || obj.blocks.length === 0) {
    errors.push('blocks 必须是非空数组')
    return { ok: false, errors }
  }
  const blocks: StrategyBlock[] = []
  ;(obj.blocks as unknown[]).forEach((item, idx) => {
    const where = `blocks[${idx}]`
    if (typeof item !== 'object' || item == null) {
      errors.push(`${where} 必须是对象`)
      return
    }
    const b = item as Record<string, unknown>
    const id = String(b.strategy ?? '')
    const mod = resolve(id)
    if (!mod) {
      errors.push(`${where}.strategy 未知：${JSON.stringify(b.strategy)}`)
      return
    }
    let weight = Number(b.weight ?? 1)
    if (!Number.isFinite(weight) || weight < 0) {
      errors.push(`${where}.weight 必须是 ≥0 的数字`)
      weight = 1
    }
    const params: Record<string, number> = {}
    const given = (b.params ?? {}) as Record<string, unknown>
    for (const spec of mod.params) {
      const v = Number(given[spec.key] ?? spec.default)
      params[spec.key] = Number.isFinite(v)
        ? Math.min(spec.max, Math.max(spec.min, v))
        : spec.default
    }
    blocks.push({ strategyId: id, enabled: b.enabled !== false, weight, params })
  })

  if (errors.length > 0) return { ok: false, errors }
  return {
    ok: true,
    stack: {
      combo: {
        entryMode: entryMode as EntryMode,
        voteThresholdPct,
        exitMode: exitMode as ExitMode,
      },
      blocks,
    },
  }
}
