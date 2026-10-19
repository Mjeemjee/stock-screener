import { useRef, useState } from 'react'
import { Download, ExternalLink, Save, Upload } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { downloadJson, formula, parseProposal } from '@/lib/research'
import type { Expression, Proposal, ResearchData } from '@/types/research'

const STORAGE = 'factor-research-proposal-v1'
const field = 'w-full min-w-0 rounded-md border bg-background px-3 py-2 text-sm'

export default function ResearchProposal({ data }: { data: ResearchData }) {
  const [market, setMarket] = useState(data.universes[0]?.market ?? 'US')
  const [parentId, setParentId] = useState('')
  const [name, setName] = useState('')
  const [hypothesis, setHypothesis] = useState('')
  const [factor, setFactor] = useState('relative_volume')
  const [second, setSecond] = useState('recovery')
  const [op, setOp] = useState('mean')
  const [mode, setMode] = useState<'form' | 'json'>(() => { try { return localStorage.getItem(STORAGE) ? 'json' : 'form' } catch { return 'form' } })
  const [raw, setRaw] = useState(() => { try { return localStorage.getItem(STORAGE) ?? '' } catch { return '' } })
  const [notice, setNotice] = useState('')
  const input = useRef<HTMLInputElement>(null)
  const parent = data.programs.find(p => p.id === parentId && p.market === market)
  const first: Expression = parent?.expression ?? { op: 'feature', name: factor }
  const extra: Expression = { op: 'feature', name: parent ? factor : second }
  const expression: Expression = op === 'single' ? { op: 'feature', name: factor } : op === 'neg' ? { op: 'neg', arg: first }
    : { op: op === 'mean' ? 'mean' : 'product', args: [first, extra] }
  const draft: Proposal = { name, market, parent_id: parent?.id ?? null, hypothesis,
    op_type: op === 'product' ? 'feature_interaction' : op === 'neg' ? 'negate_signal' : parent ? 'add_feature' : 'new_factor_family', change: formula(expression, data.features),
    expected: '仅使用创建后的未来样本，验证五日扣费收益增量及因子重复性', expression,
    filters: parent?.filters ?? [] }
  const source = mode === 'json' ? raw : JSON.stringify(draft, null, 2)
  let valid: Proposal | null = null, error = ''
  try { valid = parseProposal(source, data) } catch (reason) { error = reason instanceof Error ? reason.message : '提案无效' }
  const safeLink = data.review_workflow.startsWith('https://github.com/Mjeemjee/stock-screener/') ? data.review_workflow : '#'
  return <section aria-label="研究提案编辑器" className="space-y-5">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h2 className="text-base font-semibold">新研究提案</h2><p className="mt-1 text-xs text-muted-foreground">本机草稿 · 尚未启动实验</p></div>
      <div className="flex gap-1 rounded-md border p-0.5" role="group" aria-label="提案编辑方式">
        <button className={`rounded-sm px-3 py-1.5 text-sm ${mode === 'form' ? 'bg-secondary' : ''}`} aria-pressed={mode === 'form'} onClick={() => setMode('form')}>组合因子</button>
        <button className={`rounded-sm px-3 py-1.5 text-sm ${mode === 'json' ? 'bg-secondary' : ''}`} aria-pressed={mode === 'json'} onClick={() => { if (!raw) setRaw(source); setMode('json') }}>JSON</button>
      </div>
    </div>
    {mode === 'form' ? <div className="grid gap-4 sm:grid-cols-2">
      <label className="space-y-1 text-xs">研究名称<input className={field} value={name} maxLength={60} onChange={e => setName(e.target.value)} /></label>
      <label className="space-y-1 text-xs">市场<select className={field} value={market} onChange={e => { setMarket(e.target.value); setParentId('') }}>
        {data.universes.map(u => <option key={u.market} value={u.market}>{u.market === 'US' ? '美股' : '港股'}</option>)}</select></label>
      <label className="space-y-1 text-xs">研究起点<select className={field} value={parentId} onChange={e => setParentId(e.target.value)}><option value="">独立新策略</option>
        {data.programs.filter(p => p.market === market).map(p => <option key={p.id} value={p.id}>{p.name} · 第{p.generation}代</option>)}</select></label>
      <label className="space-y-1 text-xs">组合方式<select className={field} value={op} onChange={e => setOp(e.target.value)}>
        <option value="mean">等权组合</option><option value="product">交互因子</option><option value="single">单因子</option><option value="neg">反向因子</option></select></label>
      <label className="space-y-1 text-xs">{parent ? '新增因子' : '首个因子'}<select className={field} disabled={!!parent && op === 'neg'} value={factor} onChange={e => setFactor(e.target.value)}>
        {Object.entries(data.features).map(([key, f]) => <option key={key} value={key}>{f.name}</option>)}</select></label>
      {!parent && ['mean', 'product'].includes(op) && <label className="space-y-1 text-xs">第二个因子<select className={field} value={second} onChange={e => setSecond(e.target.value)}>
        {Object.entries(data.features).map(([key, f]) => <option key={key} value={key}>{f.name}</option>)}</select></label>}
      <label className="space-y-1 text-xs sm:col-span-2">研究假设<textarea aria-label="研究假设" className={`${field} min-h-24`} value={hypothesis} maxLength={400} onChange={e => setHypothesis(e.target.value)} /></label>
      <div className="border-y py-3 text-sm leading-relaxed sm:col-span-2"><span className="text-xs text-muted-foreground">候选公式</span><p className="mt-1 break-words">{formula(expression, data.features)}</p>
        {parent && <p className="mt-2 text-xs text-muted-foreground">继承父策略的 {parent.filters.length} 项原始因子条件</p>}</div>
    </div> : <label className="block text-xs">提案 JSON<textarea aria-label="提案 JSON" className={`${field} mt-2 min-h-80 font-mono text-xs`} spellCheck={false} value={raw} maxLength={16000} onChange={e => setRaw(e.target.value)} /></label>}
    {error && <p role="status" className="text-xs text-amber-800">{error}</p>}
    <div className="flex flex-wrap gap-2">
      <Button variant="outline" disabled={!valid} onClick={() => { try { localStorage.setItem(STORAGE, source); setRaw(source); setNotice('草稿已保存到本机，尚未提交云端') } catch { setNotice('浏览器未允许保存草稿') } }}><Save className="mr-2 h-4 w-4" />保存草稿</Button>
      <Button disabled={!valid} onClick={() => { downloadJson(valid, 'factor-research-proposal.json'); setNotice('提案已导出，实验尚未启动') }}><Download className="mr-2 h-4 w-4" />导出提案</Button>
      <Button variant="outline" onClick={() => input.current?.click()}><Upload className="mr-2 h-4 w-4" />导入提案</Button>
      <input className="hidden" ref={input} aria-label="导入提案文件" type="file" accept="application/json,.json" onChange={async e => {
        const file = e.target.files?.[0]
        if (!file) return
        if (file.size > 64000) { setNotice('提案文件过大'); return }
        try { const content = await file.text(); parseProposal(content, data); setRaw(content); setMode('json'); setNotice('已导入本机草稿，尚未启动实验') }
        catch (reason) { setNotice(reason instanceof Error ? reason.message : '导入失败') }
        e.target.value = ''
      }} />
      <a href={safeLink} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 px-2 text-sm text-primary">仓库研究任务<ExternalLink className="h-3 w-3" /></a>
    </div>
    {notice && <p role="status" className="text-sm text-muted-foreground">{notice}</p>}
  </section>
}
