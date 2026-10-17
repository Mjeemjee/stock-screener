import { useEffect, useState } from 'react'
import { dataUrl } from '@/lib/dataSource'
import type { LabData } from '@/types/lab'
import { isLabData } from '@/lib/lab'

export function useLab() {
  const [data, setData] = useState<LabData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    let disposed = false
    const timer = window.setTimeout(() => controller.abort(), 20_000)
    setLoading(true)
    setError(null)
    fetch(dataUrl('lab.json'), { signal: controller.signal, cache: 'no-cache' })
      .then(async response => {
        if (!response.ok) throw new Error(response.status === 404 ? '实验室数据尚未发布' : `读取失败（HTTP ${response.status}）`)
        const value = await response.json()
        if (!isLabData(value)) throw new Error('实验室数据格式不完整')
        if (!disposed) setData(value)
      })
      .catch(reason => { if (!disposed) setError(reason instanceof Error ? reason.message : '读取失败') })
      .finally(() => { clearTimeout(timer); if (!disposed) setLoading(false) })
    return () => { disposed = true; clearTimeout(timer); controller.abort() }
  }, [attempt])
  return { data, error, loading, retry: () => setAttempt(value => value + 1) }
}
