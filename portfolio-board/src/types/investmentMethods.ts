export interface InvestmentMethod {
  id: string
  version: string
  people: string[]
  name: string
  style: string
  targetMarkets: string[]
  representation: 'reference_only' | 'institutional_reference' | 'quantitative_approximation'
  evidenceStatus: string
  summary: string
  sources: { title: string; url: string; sourceType: string; checkedOn: string; supports: string; limitations: string }[]
  requiredData: string[]
  quantitativeRules: { origin: 'project' | 'source'; rule: string; implementation?: string }[]
  projectAddedRules: string[]
  limitations: string[]
  executionBinding: { screenerId: string | null; backtestId: string | null; learningId: string | null }
  initialParams?: Record<string, number>
  validationEvidence: string[]
}
