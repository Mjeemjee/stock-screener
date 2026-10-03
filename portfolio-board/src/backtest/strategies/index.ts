import type { StrategyModule } from '../types'

/**
 * 策略模块注册表：构建期自动发现本目录下所有导出 `strategy` 的模块。
 * 新增策略 = 新建一个 .ts 文件并 `export const strategy: StrategyModule`，
 * 重新构建后无需改动任何其他代码即出现在回测页下拉框（AC-402）。
 */
const modules = import.meta.glob('./*.ts', { eager: true }) as Record<
  string,
  { strategy?: StrategyModule }
>

export const STRATEGIES: StrategyModule[] = Object.entries(modules)
  .filter(([path, m]) => !path.endsWith('index.ts') && m.strategy != null)
  .map(([, m]) => m.strategy as StrategyModule)
  .sort((a, b) => a.id.localeCompare(b.id))
