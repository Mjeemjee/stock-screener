import { useEffect, useState } from 'react'
import { dataUrl } from '@/lib/dataSource'
import { isCandleData, validCode } from '@/lib/candles'
import type { CandleData } from '@/lib/candles'

export function useCandles(code: string) {
  const [state, setState] = useState<{ code: string; data: CandleData | null; error: string | null; loading: boolean }>({ code, data: null, error: null, loading: true })
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    let disposed = false
    const timer = window.setTimeout(() => controller.abort(), 20_000)
    setState({ code, data: null, error: null, loading: true })
    const fetchData = async () => {
      if (!validCode(code)) throw new Error('股票代码格式不正确')
      const response = await fetch(dataUrl(`candles/${encodeURIComponent(code)}.json`), { signal: controller.signal, cache: 'no-cache' })
      if (!response.ok) throw new Error(response.status === 404 ? '该股票暂无公开日K线，下一次数据更新后可重试。' : `日K线读取失败（HTTP ${response.status}）`)
      const value: unknown = await response.json()
      if (!isCandleData(value, code)) throw new Error('日K线格式或价格不完整，已停止绘图。')
      if (!disposed) setState({ code, data: value, error: null, loading: false })
    }
    fetchData().catch(reason => {
      if (!disposed) setState({ code, data: null, error: reason?.name === 'AbortError' ? '日K线读取超时，请重试。' : reason instanceof Error ? reason.message : '日K线读取失败', loading: false })
    }).finally(() => window.clearTimeout(timer))
    return () => { disposed = true; window.clearTimeout(timer); controller.abort() }
  }, [code, attempt])
  return { ...(state.code === code ? state : { data: null, error: null, loading: true }), retry: () => setAttempt(value => value + 1) }
}
