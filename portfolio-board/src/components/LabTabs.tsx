import { Link, useLocation } from 'react-router'

export default function LabTabs() {
  const { pathname } = useLocation()
  return <nav aria-label="实验室分类" className="mb-5 flex flex-wrap gap-x-5 border-b text-sm">
    {[['/lab', '参数分支'], ['/lab/research', '因子研究'], ['/lab/long-horizon', '长期验证']].map(([to, label]) => <Link key={to} to={to}
      aria-current={pathname === to ? 'page' : undefined}
      className={`border-b-2 py-3 ${pathname === to ? 'border-primary font-semibold text-primary' : 'border-transparent text-muted-foreground hover:text-foreground'}`}>{label}</Link>)}
  </nav>
}
