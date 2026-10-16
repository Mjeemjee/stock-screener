import { useEffect, useState } from 'react'
import { dataUrl } from '@/lib/dataSource'
import type { TrackingData } from '@/types/tracking'

export function useTracking() {
  const [data, setData] = useState<TrackingData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    let disposed = false
    const timer = window.setTimeout(() => controller.abort(), 20_000)
    setLoading(true)
    setError(null)
    fetch(dataUrl('tracking.json'), { signal: controller.signal, cache: 'no-cache' })
      .then(async response => {
        if (!response.ok) throw new Error(response.status === 404 ? '暂未提供追踪档案' : `读取失败（HTTP ${response.status}）`)
        const value = await response.json()
        if (value?.schema_version !== 1 || !Array.isArray(value.archives) || !Array.isArray(value.evaluations) ||
          !Array.isArray(value.summary) || !value.securities || !value.appearances) throw new Error('追踪数据格式不完整')
        if (!disposed) setData(value)
      })
      .catch(reason => { if (!disposed) setError(reason instanceof Error ? reason.message : '读取失败') })
      .finally(() => { window.clearTimeout(timer); if (!disposed) setLoading(false) })
    return () => { disposed = true; window.clearTimeout(timer); controller.abort() }
  }, [attempt])
  return { data, error, loading, retry: () => setAttempt(value => value + 1) }
}
