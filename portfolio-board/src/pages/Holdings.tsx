import AppShell from '@/components/AppShell'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { fmt, toHKD, usePortfolio } from '@/hooks/usePortfolio'

function PnlText({ value, suffix = '' }: { value: number; suffix?: string }) {
  const cls = value > 0 ? 'text-rose-400' : value < 0 ? 'text-emerald-400' : 'text-muted-foreground'
  const sign = value > 0 ? '+' : ''
  return (
    <span className={`tnum ${cls}`}>
      {sign}
      {fmt(value)}
      {suffix}
    </span>
  )
}

export default function Holdings() {
  const { loading, error, positions, rows } = usePortfolio()

  if (loading) return <div className="p-10 text-center text-muted-foreground">数据加载中…</div>
  if (error || !positions)
    return (
      <div className="p-10 text-center">
        <p className="text-rose-400 mb-2">持仓数据加载失败：{error}</p>
        <p className="text-muted-foreground text-sm max-w-md mx-auto">
          持仓页只在本机版可用（需富途 OpenD 运行并在项目根目录执行 <code>refresh_data.py</code>）。
          云端部署的网页不含持仓数据——这是刻意的：持仓是隐私，不该上公网。
        </p>
      </div>
    )

  const funds = positions.funds?.[0]
  const totalHKD = rows.reduce((s, r) => s + toHKD(r.market_val, r.currency), 0)
  const dayPlHKD = rows.reduce((s, r) => s + toHKD(r.day_pl, r.currency), 0)
  const dayPlUSD = rows.filter((r) => r.currency === 'USD').reduce((s, r) => s + r.day_pl, 0)
  const usHKD = rows.filter((r) => r.market === 'US').reduce((s, r) => s + toHKD(r.market_val, r.currency), 0)
  const usPct = totalHKD > 0 ? (usHKD / totalHKD) * 100 : 0

  return (
    <AppShell
      title="我的持仓"
      subtitle={`数据更新于 ${positions.fetched_at}（本地数据，刷新请运行 refresh_data.py）`}
    >
      <div className="space-y-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">总资产</CardTitle></CardHeader>
            <CardContent><p className="text-2xl font-bold tnum">{funds ? fmt(funds.total_assets) : '-'} <span className="text-sm font-normal text-muted-foreground">{funds?.currency}</span></p></CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">持仓市值</CardTitle></CardHeader>
            <CardContent><p className="text-2xl font-bold tnum">{funds ? fmt(funds.market_val) : '-'} <span className="text-sm font-normal text-muted-foreground">{funds?.currency}</span></p></CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">可用现金</CardTitle></CardHeader>
            <CardContent><p className="text-2xl font-bold tnum">{funds ? fmt(funds.cash) : '-'} <span className="text-sm font-normal text-muted-foreground">{funds?.currency}</span></p></CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">当日参考盈亏（按昨收估算）</CardTitle></CardHeader>
            <CardContent>
              <p className="text-2xl font-bold"><PnlText value={dayPlHKD} /> <span className="text-sm font-normal text-muted-foreground">HKD 折算</span></p>
              <p className="text-xs text-muted-foreground mt-1">其中美股部分 <PnlText value={dayPlUSD} suffix=" USD" /></p>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">市场分布（按市值折算港币）</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex h-3 w-full overflow-hidden rounded-full bg-muted">
              <div className="bg-blue-500" style={{ width: `${usPct}%` }} />
              <div className="bg-amber-500" style={{ width: `${100 - usPct}%` }} />
            </div>
            <div className="mt-2 flex gap-6 text-xs text-muted-foreground">
              <span><span className="inline-block w-2 h-2 rounded-full bg-blue-500 mr-1" />美股 {fmt(usPct, 1)}%</span>
              <span><span className="inline-block w-2 h-2 rounded-full bg-amber-500 mr-1" />港股 {fmt(100 - usPct, 1)}%</span>
              <span className="ml-auto">汇率按 1 USD ≈ 7.8 HKD 估算</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">持仓明细</CardTitle></CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>标的</TableHead>
                  <TableHead className="text-right">数量</TableHead>
                  <TableHead className="text-right">成本价</TableHead>
                  <TableHead className="text-right">最新价</TableHead>
                  <TableHead className="text-right">市值</TableHead>
                  <TableHead className="text-right">浮动盈亏</TableHead>
                  <TableHead className="text-right">权重</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((r) => (
                  <TableRow key={r.code}>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Badge variant={r.market === 'US' ? 'default' : 'secondary'}>{r.market}</Badge>
                        <div>
                          <div className="font-medium">{r.stock_name}</div>
                          <div className="text-xs text-muted-foreground">{r.code}</div>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="text-right tnum">{r.qty}</TableCell>
                    <TableCell className="text-right tnum">{fmt(r.cost_price)}</TableCell>
                    <TableCell className="text-right tnum">{fmt(r.last_price)}</TableCell>
                    <TableCell className="text-right tnum">{fmt(r.market_val)} <span className="text-xs text-muted-foreground">{r.currency}</span></TableCell>
                    <TableCell className="text-right">
                      <PnlText value={r.pl_val} />
                      <div className="text-xs"><PnlText value={r.pl_ratio} suffix="%" /></div>
                    </TableCell>
                    <TableCell className="text-right tnum">{totalHKD > 0 ? fmt((toHKD(r.market_val, r.currency) / totalHKD) * 100, 1) : '-'}%</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <p className="text-center text-xs text-muted-foreground pb-6">
          本看板仅为个人持仓信息展示，不构成投资建议。红涨绿跌。
        </p>
      </div>
    </AppShell>
  )
}
