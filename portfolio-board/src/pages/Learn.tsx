import { Link } from 'react-router'
import AppShell from '@/components/AppShell'
import { Badge } from '@/components/ui/badge'
import { CHAPTERS } from '@/content/learn'

const TAG_STYLE: Record<string, string> = {
  方法论: 'border-sky-400/40 text-sky-300',
  趋势: 'border-emerald-400/40 text-emerald-300',
  动量: 'border-amber-400/40 text-amber-300',
  反转: 'border-rose-400/40 text-rose-300',
  关键位: 'border-violet-400/40 text-violet-300',
}

/** 学习板块：每个策略的底层逻辑与回测方法论，面向零基础但行文不降格 */
export default function Learn() {
  return (
    <AppShell
      title="学习"
      subtitle="理解策略，先于使用策略。本板块逐一拆解站内每个策略的构造原理、数学形式与失效条件，不预设任何金融背景。全部内容仅作方法论说明，不构成投资建议。"
    >
      {/* 目录 */}
      <nav className="mb-6 flex flex-wrap gap-2">
        {CHAPTERS.map((c) => (
          <a
            key={c.id}
            href={`#${c.id}`}
            className="rounded-full border border-border/60 bg-card/60 px-3 py-1 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          >
            {c.no.replace(' · ', ' ')}{' '}{c.title}
          </a>
        ))}
      </nav>

      <div className="space-y-5 sm:space-y-7">
        {CHAPTERS.map((c) => (
          <article
            key={c.id}
            id={c.id}
            className="scroll-mt-24 rounded-2xl border border-border/70 bg-card/80 p-5 sm:p-7 shadow-[0_12px_40px_-16px_rgb(0_0_0/0.65)] backdrop-blur-sm"
          >
            <header className="mb-4 flex items-center gap-3 flex-wrap">
              <span className="text-xs tracking-widest text-muted-foreground">{c.no}</span>
              <h2 className="text-lg sm:text-xl font-semibold tracking-tight">{c.title}</h2>
              <Badge variant="outline" className={TAG_STYLE[c.tag]}>
                {c.tag}
              </Badge>
            </header>
            <div className="space-y-5">
              {c.sections.map((s) => (
                <section key={s.h}>
                  <h3 className="mb-2 text-sm font-medium text-foreground/90 border-l-2 border-primary/60 pl-2.5">
                    {s.h}
                  </h3>
                  <div className="space-y-2.5 pl-3.5">
                    {s.paras.map((p, i) => (
                      <p key={i} className="text-sm leading-7 text-muted-foreground">
                        {p}
                      </p>
                    ))}
                  </div>
                </section>
              ))}
            </div>
          </article>
        ))}

        {/* 收尾 */}
        <div className="rounded-2xl border border-primary/30 bg-primary/5 p-5 sm:p-6 text-sm leading-7 text-muted-foreground">
          建议的阅读次序：先读「回测如何运作」建立规则意识，再任选一个策略篇章，
          随后到<Link to="/backtest" className="text-primary hover:underline mx-1">回测页</Link>
          亲手运行该策略，对照篇章中的「适用与失效」检验结果是否吻合。最后读「组合表决机制」，
          理解多块策略如何相互制衡。回测页与选股台的每个策略块，都可以通过篇章目录回到这里。
        </div>
      </div>
    </AppShell>
  )
}
