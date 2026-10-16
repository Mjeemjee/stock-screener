import { Star } from 'lucide-react'
import { useWatchlist } from '@/hooks/useWatchlist'
import { Button } from '@/components/ui/button'

export default function WatchButton({ code, name }: { code: string; name: string }) {
  const { items, toggle, error } = useWatchlist()
  const selected = items.some(item => item.code === code)
  return <span className="inline-flex items-center gap-1">
    <Button variant="ghost" size="icon" className="size-8 shrink-0" aria-pressed={selected}
      aria-label={`${selected ? '移出' : '加入'}观察名单 ${code}`} title={selected ? '移出观察名单' : '加入观察名单'}
      onClick={() => toggle({ code, name })}>
      <Star className={selected ? 'fill-amber-400 text-amber-600' : 'text-muted-foreground'} />
    </Button>
    {error && <span role="alert" className="text-xs text-destructive">{error}</span>}
  </span>
}
