/**
 * 偏移动量（Bias Momentum）：衡量"当前价格相对于均线的偏移动能"。
 *
 * 原理（於三水 ETF 三因子轮动中的 bias 因子，权重 0.3）：
 *   1. bias = close / MA(close, 25)（当日价格偏离 25 日均线的比例）
 *   2. 取最近 25 天 bias 序列，除以该窗口的第一个值做归一化
 *   3. 归一化后的序列做线性回归，斜率 × 10000 = 偏移动量得分
 * 正值 = bias 加速偏离均线（趋势增强），负值 = bias 回退（动能衰减）。
 *
 * 数学实现见 ../threeFactors.ts（与「横截面轮动」共用同一份因子代码，
 * 保证单标的模式与轮动模式口径完全一致）。
 *
 * 本模块将其适配为单标的回测策略：
 *   - 买入：偏移动量 > 阈值（趋势正在加速）
 *   - 卖出：偏移动量 ≤ 阈值（动能在衰减）
 * 注意：原始策略用于 4 只 ETF 横截面轮动，通用到个股时阈值需要按市场调整。
 */
import { biasScore } from '../threeFactors'
import type { StrategyModule } from '../types'

export const strategy: StrategyModule = {
  id: 'bias-momentum',
  name: '偏移动量（Bias 斜率）',
  description:
    '收盘价相对 25 日均线的偏离率（bias），对最近 25 天归一化 bias 做线性回归取斜率。斜率 > 0 买入（bias 加速偏离=趋势增强），斜率 ≤ 0 卖出。出自 ETF 三因子轮动策略的 bias 因子，单标的使用时在趋势启动阶段表现好，横盘震荡时假信号较多。',
  params: [
    { key: 'biasN', label: 'Bias 周期', description: '计算 bias 的 MA 天数', default: 25, min: 10, max: 60, step: 1 },
    { key: 'momN', label: '回归窗口', description: '最近多少天 bias 做线性回归', default: 25, min: 10, max: 50, step: 5 },
    { key: 'threshold', label: '信号阈值', description: '斜率 × 10000 超过此值触发买入', default: 0, min: -100, max: 100, step: 1 },
  ],
  prepare(bars, p) {
    const score = biasScore(
      bars.map((b) => b.c),
      Math.round(p.biasN),
      Math.round(p.momN),
    )

    const entries = new Array<boolean>(bars.length).fill(false)
    const exits = new Array<boolean>(bars.length).fill(false)
    for (let i = 0; i < bars.length; i++) {
      if (score[i] == null || !isFinite(score[i]!)) continue
      entries[i] = score[i]! > p.threshold
      exits[i] = score[i]! <= p.threshold
    }
    return { entries, exits }
  },
}