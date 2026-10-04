import { RollingSr, nearestBelow, atrSeries } from '../srLevels'
import { sma } from '../engine'
import type { StrategyModule } from '../types'

/** 支撑回踩企稳：价格回落至成交量密集支撑区、出现企稳迹象时买入，跌破支撑失效离场。
 * 均值回复类策略——关键位由体积守恒成交量剖面与 ZigZag 摆动点共同确认，
 * 触及次数与陈旧度决定可靠度；震荡市胜率高，单边下跌市会连续失效。 */
export const strategy: StrategyModule = {
  id: 'srBounce',
  name: '支撑回踩企稳',
  description:
    '以成交量剖面与摆动点识别支撑区：价格回踩区带且企稳（连续 N 日收盘走高）时买入；收盘跌破支撑位下方缓冲（ATR 倍数）即认输出场。震荡市的均值回复策略，单边下跌市中支撑会连续失效。',
  params: [
    { key: 'windowDays', label: '关键位观察窗口', description: '成交量剖面与摆动点的回溯交易日数', default: 120, min: 60, max: 240, step: 10 },
    { key: 'zigzagAtrMult', label: '摆动灵敏度', description: 'ZigZag 反转确认阈值（ATR 倍数），越大关键位越少越粗', default: 2, min: 1, max: 4, step: 0.5 },
    { key: 'confirmDays', label: '企稳确认天数', description: '连续多少日收盘高于前一日才算企稳，0=不要求', default: 1, min: 0, max: 3, step: 1 },
    { key: 'exitBufferAtr', label: '离场缓冲', description: '收盘跌破支撑位下方多少 ATR 离场', default: 0.3, min: 0, max: 1.5, step: 0.1 },
    { key: 'refreshEvery', label: '关键位刷新间隔', description: '每多少根 K 线重算关键位（性能与灵敏度折中）', default: 5, min: 3, max: 20, step: 1 },
  ],
  prepare(bars, p) {
    const n = bars.length
    const sr = new RollingSr(
      bars,
      { windowDays: Math.round(p.windowDays), zigzagAtrMult: p.zigzagAtrMult, maxPerSide: 3, minDistAtr: 0.3, maxDistAtr: 5 },
      Math.round(p.refreshEvery),
    )
    const atr = atrSeries(bars)
    const vols = bars.map((b) => b.v)
    const avgV = sma(vols, 20)
    const entries = new Array<boolean>(n).fill(false)
    const exits = new Array<boolean>(n).fill(false)
    const confirm = Math.round(p.confirmDays)
    for (let i = 1; i < n; i++) {
      const levels = sr.at(i)
      if (levels.length === 0) continue
      const b = bars[i]
      const a = atr[i] ?? atr[i - 1]
      if (a == null) continue
      // 入场：最低价探入支撑区带，收盘仍在区带下沿之上，且满足企稳确认
      let entry = false
      for (const l of levels) {
        if (l.kind !== 'support') continue
        const touched = b.l <= l.upper && b.c >= l.lower
        if (!touched) continue
        let ok = true
        for (let k = 0; k < confirm; k++) {
          if (i - k < 1 || bars[i - k].c <= bars[i - k - 1].c) { ok = false; break }
        }
        // 缩量回踩更优：若均量可用，要求成交量不高于均量的 1.5 倍（放量下杀不接）
        if (ok && avgV[i] != null && vols[i] > avgV[i]! * 1.5) ok = false
        if (ok) { entry = true; break }
      }
      entries[i] = entry
      // 出场：收盘跌破最近下方支撑位（缓冲 exitBufferAtr × ATR）
      const below = nearestBelow(levels, b.c)
      if (below && b.c < below.price - p.exitBufferAtr * a) exits[i] = true
    }
    return { entries, exits }
  },
}
