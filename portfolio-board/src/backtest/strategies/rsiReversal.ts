import { rsi } from '../engine'
import type { StrategyModule } from '../types'

/** RSI 超卖反转：RSI 从超卖区下方上穿回场内时买入博反弹，回升到中枢离场。
 * 逆向策略，胜率通常较高但单次盈利小，怕单边下跌（接飞刀）。 */
export const strategy: StrategyModule = {
  id: 'rsi-reversal',
  name: 'RSI超卖反转',
  description:
    'RSI 跌破超卖线后重新上穿时买入博反弹，回升到中枢位离场。逆向策略：胜率往往不错、单次盈利小；最大风险是单边下跌中「接飞刀」，建议配合止损参数使用。',
  params: [
    { key: 'period', label: 'RSI 周期', default: 14, min: 5, max: 30, step: 1 },
    { key: 'oversold', label: '超卖阈值', description: 'RSI 低于此值视为超卖', default: 30, min: 10, max: 45, step: 1 },
    { key: 'exitLevel', label: '离场水平', description: 'RSI 回升到此值以上离场', default: 55, min: 40, max: 80, step: 1 },
  ],
  prepare(bars, p) {
    const closes = bars.map((b) => b.c)
    const r = rsi(closes, Math.round(p.period))
    const entries = new Array<boolean>(bars.length).fill(false)
    const exits = new Array<boolean>(bars.length).fill(false)
    for (let i = 1; i < bars.length; i++) {
      if (r[i] != null && r[i - 1] != null)
        entries[i] = r[i - 1]! < p.oversold && r[i]! >= p.oversold
      if (r[i] != null) exits[i] = r[i]! >= p.exitLevel
    }
    return { entries, exits }
  },
}
