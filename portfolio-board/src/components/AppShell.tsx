import type { ReactNode } from 'react'
import { Link, useLocation } from 'react-router'

const NAV = [
  { to: '/', label: '选股' },
  { to: '/backtest', label: '回测' },
  { to: '/learn', label: '学习' },
  { to: '/holdings', label: '持仓' },
  { to: '/guide', label: '指南' },
]

/** 全站统一外壳：浅色机构风——白色吸顶导航 + 衬线品牌标识 + 页面副标题 */
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
      {/* 顶部机构蓝细规 */}
      <div className="h-0.5 w-full bg-primary" />
      <header className="sticky top-0 z-40 border-b border-border bg-card/90 backdrop-blur-md">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 py-3 space-y-2">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="h-7 w-7 shrink-0 rounded-md bg-primary shadow-sm flex items-center justify-center">
                <span className="font-display text-primary-foreground text-sm leading-none font-bold">
                  量
                </span>
              </div>
              <h1 className="font-display text-lg sm:text-xl font-bold tracking-tight truncate">
                {title}
              </h1>
            </div>
            <nav className="flex shrink-0 gap-0.5 rounded-full border border-border bg-secondary/70 p-1 text-sm">
              {NAV.map((n) => {
                const active = pathname === n.to
                return (
                  <Link
                    key={n.to}
                    to={n.to}
                    className={
                      active
                        ? 'rounded-full bg-primary px-3 py-1 font-medium text-primary-foreground shadow-sm'
                        : 'rounded-full px-3 py-1 text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground'
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
      <footer className="border-t border-border mt-6">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 py-4 text-xs text-muted-foreground flex items-center justify-between gap-3 flex-wrap">
          <span className="font-display font-semibold text-foreground/80">港美股选股台</span>
          <span>数据每日自动更新 · 仅供研究筛选，不构成投资建议</span>
        </div>
      </footer>
    </div>
  )
}
