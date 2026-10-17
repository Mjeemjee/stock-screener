import { INVESTMENT_METHODS } from '../content/investmentMethods'
import type { InvestmentMethod } from '../types/investmentMethods'
import { DEFAULT_COMBO, parseStack, type ResolveStrategy, type StackConfig } from '../backtest/combo'

export const REPRESENTATIONS: Record<InvestmentMethod['representation'], string> = {
  reference_only: '理念参考', institutional_reference: '机构参考版', quantitative_approximation: '量化近似',
}

export const getInvestmentMethod = (id: string) => INVESTMENT_METHODS.find(method => method.id === id)

export function filterInvestmentMethods(query: string, style: string, market: string, capability: string) {
  const keyword = query.trim().toLocaleLowerCase()
  return INVESTMENT_METHODS.filter(method =>
    (!keyword || [method.name, ...method.people, method.id, method.style].join(' ').toLocaleLowerCase().includes(keyword)) &&
    (style === 'ALL' || method.style === style) &&
    (market === 'ALL' || method.targetMarkets.includes(market)) &&
    (capability === 'ALL' || (capability === 'backtest' ? !!method.executionBinding.backtestId : !method.executionBinding.backtestId)),
  )
}

export function investmentMethodPreset(id: string | null, resolve: ResolveStrategy): {
  method: InvestmentMethod | null; stack: StackConfig | null; error: string | null
} {
  if (!id) return { method: null, stack: null, error: null }
  const method = getInvestmentMethod(id)
  if (!method) return { method: null, stack: null, error: '未找到该投资方法，请返回方法库选择。' }
  const moduleId = method.executionBinding.backtestId
  if (!moduleId || !resolve(moduleId)) return { method, stack: null, error: '该方法尚未接入可运行的回测模块。' }
  const parsed = parseStack(JSON.stringify({ combo: DEFAULT_COMBO,
    blocks: [{ strategy: moduleId, enabled: true, weight: 1, params: method.initialParams ?? {} }] }), resolve)
  return parsed.ok ? { method, stack: parsed.stack, error: null }
    : { method, stack: null, error: parsed.errors.join('；') }
}
