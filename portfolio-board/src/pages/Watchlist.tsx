import { useState } from 'react'
import { Link } from 'react-router'
import { Plus, Search } from 'lucide-react'
import AppShell from '@/components/AppShell'
import WatchButton from '@/components/WatchButton'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useWatchlist } from '@/hooks/useWatchlist'
import { useTracking } from '@/hooks/useTracking'
import { currencyOf, formatNumber } from '@/lib/screener'

export default function Watchlist() {
  const { items, toggle, error } = useWatchlist()
  const { data } = useTracking()
  const [query, setQuery] = useState('')
  const code = query.trim().toUpperCase()
  const valid = /^(US|HK)\.[A-Z0-9.-]+$/.test(code) && !items.some(item => item.code === code)
  const candidates = query.trim() ? Object.values(data?.securities ?? {}).filter(security =>
    security.code.toLowerCase().includes(query.trim().toLowerCase()) || security.name.toLowerCase().includes(query.trim().toLowerCase())).slice(0, 8) : []
  const add = () => { if (valid) { toggle({ code, name: data?.securities[code]?.name ?? code }); setQuery('') } }
  return <AppShell title="观察名单" subtitle={`${items.length} 只标的 · 保存在当前浏览器`}>
    <div className="flex items-center gap-2 border-b pb-4"><div className="relative min-w-0 flex-1"><Search className="pointer-events-none absolute left-3 top-2.5 size-4 text-muted-foreground" /><Input aria-label="添加观察标的" placeholder="US.AAPL 或 HK.00700" value={query} onChange={event => setQuery(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') add() }} className="pl-9" /></div><Button size="icon" variant="outline" aria-label="添加代码到观察名单" title="添加代码到观察名单" disabled={!valid} onClick={add}><Plus /></Button></div>
    {error && <p role="alert" className="py-3 text-sm text-destructive">{error}</p>}
    {candidates.length > 0 && <div className="divide-y border-b">{candidates.map(security => <div key={security.code} className="flex items-center justify-between gap-3 py-3"><Link className="min-w-0 break-words text-sm hover:text-primary" to={`/stock/${encodeURIComponent(security.code)}`}>{security.name}<span className="ml-2 text-xs text-muted-foreground">{security.code}</span></Link><WatchButton code={security.code} name={security.name} /></div>)}</div>}
    {items.length === 0 ? <p className="py-12 text-center text-sm text-muted-foreground">观察名单为空。</p> : <div className="divide-y">{items.map(item => {
      const security = data?.securities[item.code]
      return <div key={item.code} className="flex items-center justify-between gap-3 py-4"><Link to={`/stock/${encodeURIComponent(item.code)}`} className="min-w-0 hover:text-primary"><p className="break-words text-sm font-medium">{security?.name ?? item.name}</p><p className="mt-1 text-xs text-muted-foreground">{item.code}</p></Link><div className="ml-auto text-right text-sm tnum">{formatNumber(security?.last_price)}<p className="text-xs text-muted-foreground">{currencyOf(item.code)}</p></div><WatchButton code={item.code} name={item.name} /></div>
    })}</div>}
  </AppShell>
}
