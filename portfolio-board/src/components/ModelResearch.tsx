import { Download, ExternalLink } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { downloadJson, formula } from '@/lib/research'
import { scanTimeInfo } from '@/lib/screener'
import type { ResearchData } from '@/types/research'

const CONNECTION: Record<string, string> = {
  missing_key: '待配置密钥', verified: '连接已验证', authentication_failed: '认证失败',
  unavailable: '连接暂不可用', model_unavailable: '账户未开放此模型',
}
const RESULT: Record<string, string> = {
  completed: '已完成', interrupted: '调用中断，额度已保留', http_error: '服务请求失败',
  network_error: '网络失败', invalid_response: '响应格式无效', invalid_proposals: '提案校验失败',
  response_limit: '响应超出限制', input_too_large: '输入超出限制', incomplete: '输出未完成',
}

export function modelConnection(data: ResearchData) {
  const m = data.model_research
  return m ? `DeepSeek Flash：${CONNECTION[m.connection] ?? '状态未知'}` : '模型研究尚未配置'
}

export default function ModelResearch({ data }: { data: ResearchData }) {
  const m = data.model_research
  if (!m) return null
  return <section aria-label="DeepSeek 研究提案" className="space-y-3 border-b pb-5">
    <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="text-base font-semibold">DeepSeek Flash 研究提案</h2>
      <span className="text-xs text-muted-foreground">研究轮次 {m.calls.length} / {m.max_calls}</span></div>
    <p className="text-xs text-muted-foreground">{modelConnection(data)} · {scanTimeInfo(m.checked_at).display}</p>
    {!m.calls.length && <p className="py-3 text-sm text-muted-foreground">尚无模型提案 · 研究触发条件：{m.min_cohorts} 期完整前瞻结果</p>}
    {m.calls.slice().reverse().map(call => <div key={call.id} className="space-y-3 border-t pt-3">
      <p className="text-xs text-muted-foreground">{scanTimeInfo(call.at).display} · {RESULT[call.status] ?? '状态未知'} · 拦截 {call.rejected_count} 项</p>
      {call.proposals.map((item, i) => <div key={i} className="space-y-2 border-l-2 pl-3">
        <h3 className="break-words text-sm font-semibold">{item.proposal.name} · {item.proposal.market}</h3>
        <p className="text-xs leading-relaxed">{item.proposal.hypothesis}</p>
        {item.proposal.research_card ? <dl className="space-y-2 text-xs leading-relaxed">{[
          ['依据', item.proposal.research_card.evidence], ['失败条件', item.proposal.research_card.failure_condition], ['数据与执行限制', item.proposal.research_card.data_risks],
        ].map(([label, value]) => <div key={label}><dt className="text-muted-foreground">{label}</dt><dd className="mt-1 break-words">{value}</dd></div>)}</dl>
          : <p className="text-xs text-amber-800">旧提案未冻结假设卡，启动新实验前需在提案编辑器补充。</p>}
        <p className="break-words text-xs text-muted-foreground">{formula(item.proposal.expression, data.features)}</p>
        <p className="text-xs text-amber-800">{item.started_program_id ? `已启动实验 ${item.started_program_id}` : '格式校验通过 · 收益未经验证 · 待人工审核'}</p>
        <Button variant="outline" disabled={!!item.started_program_id} onClick={() => downloadJson(item.proposal, `deepseek-proposal-${call.id.slice(0, 8)}-${i + 1}.json`)}>
          <Download className="mr-2 h-4 w-4" />下载模型提案</Button>
      </div>)}
      {call.status === 'completed' && !call.proposals.length && <p className="text-xs text-muted-foreground">本轮没有可提交的新提案</p>}
    </div>)}
    <a className="inline-flex items-center gap-1 text-sm text-primary" href="https://github.com/Mjeemjee/stock-screener/actions/workflows/review-factor-research.yml" target="_blank" rel="noreferrer">
      仓库研究审核<ExternalLink className="h-3 w-3" /></a>
  </section>
}
