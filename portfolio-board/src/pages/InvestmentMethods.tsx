import { useState } from 'react'
import { Link, useParams } from 'react-router'
import AppShell from '@/components/AppShell'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { INVESTMENT_METHODS } from '@/content/investmentMethods'
import { filterInvestmentMethods, getInvestmentMethod, REPRESENTATIONS } from '@/lib/investmentMethods'
import type { InvestmentMethod } from '@/types/investmentMethods'

const SOURCE_TYPES: Record<string, string> = {
  author_original: '作者原文', author_affiliated: '作者关联网站', book_introduction: '书目介绍',
  related_institution: '相关机构说明', participant_archive: '参与者历史档案',
}

function MethodDetail({ method }: { method: InvestmentMethod }) {
  const canBacktest = !!method.executionBinding.backtestId
  return <div className="mx-auto max-w-3xl space-y-6" data-testid="method-detail">
    <Link className="text-sm text-primary underline underline-offset-4" to="/methods">返回全部方法</Link>
    <header className="space-y-3 border-b pb-5">
      <p className="text-sm text-muted-foreground">{method.people.join(' / ')} · {method.style}</p>
      <h2 className="font-display text-2xl font-semibold leading-snug">{method.name}</h2>
      <div className="flex flex-wrap gap-2"><Badge variant="secondary">{REPRESENTATIONS[method.representation]}</Badge><Badge variant="outline">{canBacktest ? '可回测简化版' : '待补规则或数据'}</Badge></div>
      <p className="text-sm leading-7">{method.summary}</p>
      <p className="text-xs text-muted-foreground">研究目标市场：{method.targetMarkets.join(' / ')}；表示研究范围，实际执行能力以下方工具为准。方法版本 {method.version}。</p>
    </header>
    <section className="space-y-3" aria-label="工具与结果">
      <h3 className="font-medium">工具与结果</h3>
      {canBacktest ? <><Button asChild><Link to={`/backtest?method=${encodeURIComponent(method.id)}`}>回测简化版</Link></Button><p className="text-sm leading-6 text-muted-foreground">复用现有突破模块，进入回测页后检查数据是否加载成功。改变参数或增加其他模块后，显示为自定义配置；组合权重代表信号票数。</p></>
        : <p className="rounded-md border bg-muted/30 p-4 text-sm leading-6 text-muted-foreground">尚未接入可运行的回测模块。需先核对完整规则并补齐下方数据；当前只提供方法与出处参考。</p>}
      <div className="grid gap-3 text-sm sm:grid-cols-2">
        <div className="rounded-md border p-4"><p className="font-medium">选股结果</p>{method.executionBinding.screenerId ? <Link to="/" className="text-primary underline">查看选股</Link> : <p className="mt-2 text-muted-foreground">暂无绑定的选股策略，不借用其他策略名单。</p>}</div>
        <div className="rounded-md border p-4"><p className="font-medium">验证与追踪</p><p className="mt-2 text-muted-foreground">暂无对应策略版本的收益验证记录。</p><Link to="/tracking" className="mt-2 inline-block text-xs text-primary underline">查看站内选股追踪</Link></div>
      </div>
      {method.validationEvidence.map(note => <p key={note} className="text-xs leading-6 text-muted-foreground">{note}</p>)}
    </section>
    <section className="space-y-3">
      <h3 className="font-medium">量化规则与原方法的差异</h3>
      {method.quantitativeRules.length ? <ul className="list-disc space-y-2 pl-5 text-sm leading-7">{method.quantitativeRules.map(rule => <li key={rule.rule}><span className="mr-2 text-xs text-muted-foreground">{rule.origin === 'project' ? '项目规则' : '原文规则'}</span>{rule.rule}</li>)}</ul>
        : <p className="text-sm leading-7 text-muted-foreground">尚未冻结可执行的数值规则。下方来源支持方法概念，不代表已经核对完整阈值或复现作者的投资过程。</p>}
      {method.initialParams && <p className="text-sm leading-7">项目初始参数：突破窗口 {method.initialParams.lookback} 日、放量倍数 {method.initialParams.volMult}、退出窗口 {method.initialParams.exitLookback} 日。参数沿用站内模块，不称为完整原版配置。</p>}
      {method.projectAddedRules.length > 0 && <p className="text-sm leading-7 text-muted-foreground">项目自行采用：{method.projectAddedRules.join('、')}。</p>}
      <ul className="list-disc space-y-2 pl-5 text-sm leading-7 text-amber-800">{method.limitations.map(note => <li key={note}>{note}</li>)}</ul>
    </section>
    <section className="space-y-3"><h3 className="font-medium">需要的数据与判断</h3><ul className="list-disc space-y-2 pl-5 text-sm leading-6">{method.requiredData.map(field => <li key={field}>{field}</li>)}</ul><p className="text-xs leading-6 text-muted-foreground">这些是方法需求，不代表已经接入。历史财报应按公告可用时点和当时披露版本截断，报告期末不能代替公告日。</p></section>
    <section className="space-y-3"><h3 className="font-medium">可追溯的出处</h3>{method.sources.map(source => <article key={source.url} className="space-y-2 rounded-md border p-4 text-sm leading-6"><a className="break-words font-medium text-primary underline underline-offset-4" href={source.url} target="_blank" rel="noreferrer">{source.title}</a><p className="text-xs text-muted-foreground">{SOURCE_TYPES[source.sourceType] ?? source.sourceType} · 查阅 {source.checkedOn}</p><p>支持范围：{source.supports}</p><p className="text-muted-foreground">局限：{source.limitations}</p></article>)}<p className="text-xs text-muted-foreground">查阅日期仅表示来源核对时间，不是财报发布或收益验证日期。</p></section>
  </div>
}

export default function InvestmentMethods() {
  const { id } = useParams()
  const [query, setQuery] = useState('')
  const [style, setStyle] = useState('ALL')
  const [market, setMarket] = useState('ALL')
  const [capability, setCapability] = useState('ALL')
  const method = id ? getInvestmentMethod(id) : null
  const filtered = filterInvestmentMethods(query, style, market, capability)
  const selectClass = 'h-10 min-w-0 rounded-md border bg-background px-3 text-sm'
  return <AppShell title="投资方法库" subtitle="从公开出处理解方法，再检查规则、数据和验证证据。人物理念的量化近似需要单独验证。">
    {id ? method ? <MethodDetail method={method} /> : <div className="space-y-4 py-12 text-center"><p role="alert">未找到该投资方法。</p><Link to="/methods" className="text-primary underline">返回方法库</Link></div> : <>
      <div className="mb-6 space-y-4 border-b pb-5">
        <div className="flex flex-wrap items-baseline justify-between gap-2"><h2 className="font-display text-xl font-semibold">六组方法，一个研究入口</h2><p className="text-xs text-muted-foreground">{filtered.length} / {INVESTMENT_METHODS.length} 组 · {INVESTMENT_METHODS.filter(m => m.executionBinding.backtestId).length} 组已接入简化版回测</p></div>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4"><Input aria-label="搜索人物或投资方法" placeholder="搜索人物或方法" value={query} onChange={e => setQuery(e.target.value)} /><select aria-label="方法流派" value={style} onChange={e => setStyle(e.target.value)} className={selectClass}><option value="ALL">全部流派</option>{[...new Set(INVESTMENT_METHODS.map(m => m.style))].map(s => <option key={s}>{s}</option>)}</select><select aria-label="研究目标市场" value={market} onChange={e => setMarket(e.target.value)} className={selectClass}><option value="ALL">全部研究市场</option><option value="US">美股</option><option value="HK">港股</option></select><select aria-label="工具能力" value={capability} onChange={e => setCapability(e.target.value)} className={selectClass}><option value="ALL">全部能力</option><option value="backtest">可回测简化版</option><option value="reference">待补规则或数据</option></select></div>
        {(query || style !== 'ALL' || market !== 'ALL' || capability !== 'ALL') && <Button variant="outline" size="sm" onClick={() => { setQuery(''); setStyle('ALL'); setMarket('ALL'); setCapability('ALL') }}>清除筛选</Button>}
      </div>
      <div className="grid gap-4 md:grid-cols-2">{filtered.map(m => <article key={m.id} data-testid="method-card" className="flex flex-col gap-4 rounded-lg border bg-card p-5"><div><p className="mb-2 text-xs text-muted-foreground">{m.people.join(' / ')} · {m.style}</p><h3 className="font-display text-lg font-semibold"><Link to={`/methods/${m.id}`} className="hover:text-primary">{m.name}</Link></h3></div><p className="text-sm leading-7 text-muted-foreground">{m.summary}</p><div className="flex flex-wrap gap-2"><Badge variant="secondary">{REPRESENTATIONS[m.representation]}</Badge><Badge variant="outline">{m.executionBinding.backtestId ? '可回测简化版' : '待补规则或数据'}</Badge></div><p className="text-xs leading-6 text-muted-foreground">{m.limitations[0]}</p><Link className="mt-auto text-sm font-medium text-primary underline underline-offset-4" to={`/methods/${m.id}`}>查看规则与出处</Link></article>)}</div>
      {!filtered.length && <p role="status" className="py-14 text-center text-sm text-muted-foreground">没有符合当前条件的方法，请调整或清除筛选。</p>}
    </>}
  </AppShell>
}
