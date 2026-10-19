import { useEffect, useState } from 'react'
import { dataUrl } from '@/lib/dataSource'
import { isResearchData } from '@/lib/research'
import type { ResearchData } from '@/types/research'

export function useResearch() {
  const [data, setData] = useState<ResearchData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    let disposed = false
    const timer = window.setTimeout(() => controller.abort(), 30000)
    setLoading(true); setError(null)
    fetch(dataUrl('research.json'), { signal: controller.signal, cache: 'no-cache' })
      .then(async response => {
        if (!response.ok) throw new Error(response.status === 404 ? '因子研究报告尚未发布' : `研究数据读取失败（${response.status}）`)
        const report: unknown = await response.json()
        if (!isResearchData(report)) throw new Error('因子研究数据不完整')
        if (!disposed) setData(report)
      })
      .catch(reason => { if (!disposed) setError(reason instanceof Error ? reason.message : '研究数据读取失败') })
      .finally(() => { clearTimeout(timer); if (!disposed) setLoading(false) })
    return () => { disposed = true; clearTimeout(timer); controller.abort() }
  }, [attempt])
  return { data, error, loading, retry: () => setAttempt(v => v + 1) }
}
