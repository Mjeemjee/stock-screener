import { useMemo, useState, useSyncExternalStore } from 'react'

const KEY = 'screener.watchlist.v1'
const EVENT = 'screener-watchlist'
export interface WatchItem { code: string; name: string; added_at: string }

export function parseWatchlist(raw: string): WatchItem[] {
  try {
    const rows: unknown = JSON.parse(raw)
    if (!Array.isArray(rows)) return []
    const seen = new Set<string>()
    return rows.filter((item): item is WatchItem => {
      if (!item || typeof item.code !== 'string' || !/^(US|HK)\.[A-Za-z0-9.-]+$/.test(item.code) ||
        typeof item.name !== 'string' || typeof item.added_at !== 'string' || seen.has(item.code)) return false
      seen.add(item.code)
      return true
    })
  } catch { return [] }
}

function read() {
  try { return localStorage.getItem(KEY) ?? '[]' } catch { return '[]' }
}

function subscribe(listener: () => void) {
  window.addEventListener(EVENT, listener)
  window.addEventListener('storage', listener)
  return () => { window.removeEventListener(EVENT, listener); window.removeEventListener('storage', listener) }
}

export function useWatchlist() {
  const raw = useSyncExternalStore(subscribe, read, () => '[]')
  const items = useMemo(() => parseWatchlist(raw), [raw])
  const [error, setError] = useState<string | null>(null)
  const toggle = (item: { code: string; name: string }) => {
    const current = parseWatchlist(read())
    const next = current.some(row => row.code === item.code)
      ? current.filter(row => row.code !== item.code)
      : [...current, { ...item, added_at: new Date().toISOString() }]
    try {
      localStorage.setItem(KEY, JSON.stringify(next))
      setError(null)
      window.dispatchEvent(new Event(EVENT))
    } catch { setError('浏览器未允许保存观察名单') }
  }
  return { items, toggle, error }
}
