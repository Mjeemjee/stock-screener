import type { ReactNode } from 'react'
import { Link, useLocation } from 'react-router'

const NAV = [
  { to: '/', label: '选股' },
  { to: '/backtest', label: '回测' },
  { to: '/holdings', label: '持仓' },
  { to: '/guide', label: '指南' },
]

/** 全站统一外壳：毛玻璃吸顶导航 + 品牌标识 + 页面副标题 */
export default function AppShell({
  title,
  subtitle,
  children,
}: {
  title: string
  subtitle?: ReactNode
  children: ReactNode
}) {
  const { pathname } = useLocation()
  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-40 border-b border-border/60 bg-background/75 backdrop-blur-md">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 py-3 space-y-2">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="h-7 w-7 shrink-0 rounded-lg bg-gradient-to-br from-rose-500 to-amber-500 shadow-[0_0_20px_-4px] shadow-rose-500/60" />
              <h1 className="text-base sm:text-lg font-semibold tracking-tight truncate">
                {title}
              </h1>
            </div>
            <nav className="flex shrink-0 gap-0.5 rounded-full border border-border/60 bg-card/60 p-1 text-sm">
              {NAV.map((n) => {
                const active = pathname === n.to
                return (
                  <Link
                    key={n.to}
                    to={n.to}
                    className={
                      active
                        ? 'rounded-full bg-primary px-3 py-1 font-medium text-primary-foreground shadow-sm'
                        : 'rounded-full px-3 py-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground'
                    }
                  >
                    {n.label}
                  </Link>
                )
              })}
            </nav>
          </div>
          {subtitle != null && (
            <p className="text-xs leading-relaxed text-muted-foreground">{subtitle}</p>
          )}
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 sm:px-6 py-5 sm:py-7">{children}</main>
    </div>
  )
}
