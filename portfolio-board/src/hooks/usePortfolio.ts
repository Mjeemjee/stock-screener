import { useEffect, useState } from 'react'
import { dataUrl } from '@/lib/dataSource'
import type { HoldingRow, PositionsFile, QuotesFile } from '@/types/portfolio'

export const USDHKD = 7.8 // 估算汇率，仅用于跨币种权重折算

interface PortfolioState {
  loading: boolean
  error: string | null
  positions: PositionsFile | null
  quotes: QuotesFile | null
  rows: HoldingRow[]
}

export function usePortfolio(): PortfolioState {
  const [state, setState] = useState<PortfolioState>({
    loading: true,
    error: null,
    positions: null,
    quotes: null,
    rows: [],
  })

  useEffect(() => {
    Promise.all([
      fetch(dataUrl('positions.json')).then((r) => {
        if (!r.ok) throw new Error('positions.json 加载失败')
        return r.json() as Promise<PositionsFile>
      }),
      fetch(dataUrl('quotes.json')).then((r) => {
        if (!r.ok) throw new Error('quotes.json 加载失败')
        return r.json() as Promise<QuotesFile>
      }),
    ])
      .then(([positions, quotes]) => {
        const quoteMap = new Map(quotes.snapshot.map((q) => [q.code, q]))
        const rows: HoldingRow[] = (positions.positions ?? []).map((p) => {
          const q = quoteMap.get(p.code)
          const last = q?.last_price ?? p.nominal_price ?? 0
          const prev = q?.prev_close_price ?? last
          const market = p.code.startsWith('US.') ? 'US' : p.code.startsWith('HK.') ? 'HK' : 'OTHER'
          return {
            ...p,
            last_price: last,
            prev_close_price: prev,
            day_pl: (last - prev) * p.qty,
            market,
          }
        })
        setState({ loading: false, error: null, positions, quotes, rows })
      })
      .catch((e: Error) =>
        setState({ loading: false, error: e.message, positions: null, quotes: null, rows: [] }),
      )
  }, [])

  return state
}

export function toHKD(value: number, currency: string): number {
  return currency === 'USD' ? value * USDHKD : value
}

export function fmt(n: number, digits = 2): string {
  return n.toLocaleString('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}
