import { RollingSr, nearestBelow } from '../srLevels'
import { sma } from '../engine'
import type { StrategyModule } from '../types'

/** 阻力放量突破：收盘价放量上破阻力区带上沿时追入，回落失守原阻力位（已翻转为支撑）离场。
 * 动量类策略——与「N日新高突破」的差别在于突破目标由成交量剖面与摆动点确认，
 * 是市场真实博弈出的关键位，而非简单的窗口极值。 */
export const strategy: StrategyModule = {
  id: 'srBreakout',
  name: '阻力放量突破',
  description:
    '以成交量剖面与摆动点识别阻力区：收盘价放量上破区带上沿时追入；回落跌破原阻力位（突破后翻转为支撑）离场。与 N 日新高突破同属动量，但突破目标来自市场博弈出的密集成交区，假突破过滤能力更强。',
  params: [
    { key: 'windowDays', label: '关键位观察窗口', description: '成交量剖面与摆动点的回溯交易日数', default: 120, min: 60, max: 240, step: 10 },
    { key: 'zigzagAtrMult', label: '摆动灵敏度', description: 'ZigZag 反转确认阈值（ATR 倍数），越大关键位越少越粗', default: 2, min: 1, max: 4, step: 0.5 },
    { key: 'volMult', label: '放量倍数', description: '成交量 ≥ 20日均量 × 此倍数才确认突破', default: 1.5, min: 1, max: 4, step: 0.1 },
    { key: 'refreshEvery', label: '关键位刷新间隔', description: '每多少根 K 线重算关键位（性能与灵敏度折中）', default: 5, min: 3, max: 20, step: 1 },
  ],
  prepare(bars, p) {
    const n = bars.length
    const sr = new RollingSr(
      bars,
      { windowDays: Math.round(p.windowDays), zigzagAtrMult: p.zigzagAtrMult, maxPerSide: 3, minDistAtr: 0.3, maxDistAtr: 5 },
      Math.round(p.refreshEvery),
    )
    const vols = bars.map((b) => b.v)
    const avgV = sma(vols, 20)
    const entries = new Array<boolean>(n).fill(false)
    const exits = new Array<boolean>(n).fill(false)
    for (let i = 1; i < n; i++) {
      const levels = sr.at(i)
      if (levels.length === 0) continue
      const b = bars[i]
      const pc = bars[i - 1].c
      // 入场：昨日收盘 ≤ 区带上沿、今日收盘 > 区带上沿（上穿），且放量
      let entry = false
      for (const l of levels) {
        if (l.kind !== 'resistance') continue
        if (pc <= l.upper && b.c > l.upper) {
          if (avgV[i] == null || vols[i] > avgV[i]! * p.volMult) { entry = true; break }
        }
      }
      entries[i] = entry
      // 出场：回落失守最近下方支撑（突破后的原阻力位已翻转为支撑）
      const below = nearestBelow(levels, b.c)
      if (below && b.c < below.price) exits[i] = true
    }
    return { entries, exits }
  },
}
