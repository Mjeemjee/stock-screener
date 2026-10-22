import { Check, CircleHelp, Download, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { downloadJson } from '@/lib/research'
import type { ResearchData, ResearchProgram } from '@/types/research'

const metric = (value: number | null, suffix = '') => value == null ? '未知' : `${value.toFixed(2)}${suffix}`

export default function ResearchReview({ program, data }: { program: ResearchProgram; data: ResearchData }) {
  const review = data.research_review?.programs.find(r => r.program_id === program.id && r.definition_hash === program.definition_hash)
  if (!review) return <p role="status" className="py-5 text-sm text-muted-foreground">这份档案尚无研究复核记录，原跟踪成绩仍然保留。</p>
  const s = review.summary
  const baseline = program.parent_id ? '父策略' : '研究池等权'
  return <div aria-label="研究复核" className="min-w-0 space-y-5">
    <div className="flex flex-wrap items-start justify-between gap-3 border-b pb-4">
      <div className="min-w-0 flex-1"><h3 className="text-sm font-semibold">{review.headline}</h3>
        <p className="mt-2 text-xs text-muted-foreground">辅助复核 · 原审批与记分规则不变</p></div>
      <Button size="icon" variant="outline" title="下载研究复核记录" aria-label="下载研究复核记录" onClick={() => downloadJson({
        ...review, review_version: data.research_review?.version, source_generated_at: data.generated_at,
        engine_version: data.engine_version, policy_hash: data.policy_hash, policy: data.policy,
      }, `${program.id}-research-review.json`)}><Download /></Button>
    </div>
    <section className="space-y-3" aria-label="白话复盘"><h3 className="text-sm font-semibold">结果出来了多少</h3>
      <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">{[
        ['未到期', s.pending], ['到期缺完整配对', s.missing], ['完整配对', s.paired], ['不重叠时段', s.independent],
        ['扣费后赚钱', s.wins], ['扣费后亏钱', s.losses], ['跑赢同期指数', s.beat_benchmark], [`跑赢同期${baseline}`, s.beat_parent],
      ].map(([label, value]) => <div key={label}><dt className="text-xs text-muted-foreground">{label}</dt><dd className="mt-1 text-lg tabular-nums">{value}<span className="ml-1 text-xs text-muted-foreground">期</span></dd></div>)}</dl>
      <p className="text-xs text-muted-foreground">盈亏和跑赢次数均只计完整配对。持平 {s.flat} 期，其中空名单留现金 {s.cash} 期。重叠期次不能当成独立考试。</p>
      <dl className="grid grid-cols-2 gap-4 border-y py-3 sm:grid-cols-4">{[
        ['平均扣费收益', metric(s.mean_return_pct, '%')], ['平均领先指数', metric(s.mean_excess_pp, ' 个百分点')],
        [`平均领先${baseline}`, metric(s.mean_delta_pp, ' 个百分点')], ['高成本下领先指数', metric(s.stress_excess_pp, ' 个百分点')],
      ].map(([label, value]) => <div key={label}><dt className="text-xs text-muted-foreground">{label}</dt><dd className="mt-1 break-words text-sm tabular-nums">{value}</dd></div>)}</dl>
    </section>
    <section className="space-y-3" aria-label="压力检查"><h3 className="text-sm font-semibold">证据与压力检查</h3>
      <p className="text-xs text-muted-foreground">单边基础成本 {data.policy.cost_bps} 基点，高成本 {data.policy.stress_cost_bps} 基点；包含费用与成交摩擦的简化假设，不代表真实成交保证。</p>
      <ul className="divide-y">{review.checks.map(check => <li key={check.id} className="flex items-start gap-3 py-3">
        {check.status === 'pass' ? <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-700" /> : check.status === 'fail' ? <X className="mt-0.5 h-4 w-4 shrink-0 text-rose-700" /> : <CircleHelp className="mt-0.5 h-4 w-4 shrink-0 text-amber-700" />}
        <div className="min-w-0"><p className="text-sm">{check.label}<span className="ml-2 text-xs text-muted-foreground">{({ pass: '当前满足', fail: '当前未满足', pending: '待验证' })[check.status]}</span></p>
          <p className="mt-1 break-words text-xs leading-relaxed text-muted-foreground">{check.detail}</p></div>
      </li>)}</ul>
    </section>
    <section className="space-y-3 border-t pt-4" aria-label="假设卡"><h3 className="text-sm font-semibold">研究假设卡 <span className="ml-2 text-xs font-normal text-muted-foreground">{review.card.origin === 'frozen' ? '创建时已冻结' : '原始说明 · 未单独冻结假设卡'}</span></h3>
      <dl className="space-y-3 text-sm leading-relaxed">{[
        ['为什么值得试', review.card.hypothesis], ['这次改变什么', review.card.change], ['依据是什么', review.card.evidence],
        ['什么情况说明想法失败', review.card.failure_condition], ['数据与执行有什么限制', review.card.data_risks],
        ['等待验证的目标', review.card.expected],
      ].map(([label, value]) => <div key={label}><dt className="text-xs text-muted-foreground">{label}</dt><dd className="mt-1 break-words">{value}</dd></div>)}</dl>
      <p className="text-xs text-muted-foreground">所需登记因子：{review.card.features.map(f => data.features[f]?.name ?? f).join('、')}。固定关卡：{data.policy.checkpoints.join(' / ')} 期。文字说明不能修改原失败与审批门槛。</p>
    </section>
  </div>
}
