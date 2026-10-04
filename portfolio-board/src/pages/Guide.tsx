import { Link } from 'react-router'
import AppShell from '@/components/AppShell'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

function Code({ children }: { children: string }) {
  return (
    <pre className="mt-2 rounded-md bg-muted px-3 py-2 text-xs overflow-x-auto select-all">{children}</pre>
  )
}

export default function Guide() {
  return (
    <AppShell title="策略进化指南" subtitle="策略库如何长大、回测拼图怎么玩、以及这个网站的边界">
      <div className="mx-auto max-w-3xl space-y-4">
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-base">这个网站的核心：策略库会不断长大</CardTitle></CardHeader>
          <CardContent className="text-sm text-muted-foreground space-y-2">
            <p>选股不是一套死规则。每个策略是 <code>screener/strategies/</code> 下的一个独立文件，自带原理、来源、适用市场、参数和风险提示。看到任何有意思的策略——一篇文章、一个研报观点、甚至一句话思路——直接发给我，剩下的我来。</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-base">提出策略后，我会做的事</CardTitle></CardHeader>
          <CardContent className="text-sm text-muted-foreground space-y-2">
            <p><b>① 识别与拆解</b>：把策略的核心逻辑提炼成可执行的筛选条件（什么算低估、什么算突破、阈值多少）。</p>
            <p><b>② 适用性分析</b>：对照美股/港股的市场结构逐条核对——数据拿不拿得到、流动性差异、做空机制、小盘股质量、策略在什么行情下会失效。</p>
            <p><b>③ 落地入库</b>：写成策略模块，状态先标 <Badge variant="secondary">观察中</Badge>，跑真实数据验证输出是否合理。</p>
            <p><b>④ 由你拍板</b>：网站策略库里能看到所有策略（含观察中），你认可后调为 <Badge>启用中</Badge>，不合适就 <Badge variant="outline">暂停</Badge>。</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-base">数据从哪里来（云端免挂机）</CardTitle></CardHeader>
          <CardContent className="text-sm text-muted-foreground space-y-2">
            <p>每天北京时间 21:22，GitHub Actions 自动完成一次全市场扫描并更新本网站，你的电脑不需要开机：</p>
            <Code>{`港股宇宙：港交所官方证券列表（普通股 2,700+ 只）
美股宇宙：NASDAQ 官方 screener（NYSE/NASDAQ/AMEX 6,600+ 只）
行情快照：腾讯 qt.gtimg.cn 批量接口（价格/涨跌/PE/市值/52周高低）
回测历史K线：腾讯 fqkline（港股前复权）+ 东方财富（美股前复权）+ 雅虎（兜底）
回测基准：标普500 / 恒生指数；股票池 = 当日成交额 Top 300/市场`}</Code>
            <p>全部为免费公开数据源，无需任何密钥。想在本地手跑一次：</p>
            <Code>python -m screener.cloud_engine</Code>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-base">回测拼图：多个策略组合着用</CardTitle></CardHeader>
          <CardContent className="text-sm text-muted-foreground space-y-2">
            <p>回测页的策略不再是单选——点「＋」把多个策略块拼在一起，每块有自己的参数和权重：</p>
            <p><b>买入表决三选一</b>：全部同意才买（信号少而稳）/ 任一同意即买（信号多而杂）/ 加权投票（同意的块权重占比 ≥ 阈值才买，信任哪个策略就给它加大权重）。</p>
            <p><b>卖出</b>：默认任一块发出出场信号就卖（风控优先），也可切成全部块同意才卖。</p>
            <p><b>代码模式</b>：点「代码」切换到 JSON 视图，直接改数字、整块复制粘贴都行，点「应用代码」即生效——参数写超范围会自动收敛回合法区间，写错了会告诉你哪一行有问题。</p>
            <p>一个好用的起手组合：<Badge variant="secondary">均线交叉</Badge> + <Badge variant="secondary">N日新高突破</Badge> 加权投票 ≥50%——趋势与突破互相确认，比单用一个信号更耐震荡。</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-base">常见问题</CardTitle></CardHeader>
          <CardContent className="text-sm text-muted-foreground space-y-3">
            <div>
              <p className="font-medium text-foreground">某期某策略命中为 0，是坏了吗？</p>
              <p>通常不是。策略本就是过滤器，行情极端时命中很少甚至为 0 是正常信号（比如大盘普跌日「动量突破」命中骤减，本身就是市场温度）。若策略卡片上有「云端版说明」，则是该策略所需字段云端数据源暂未覆盖。</p>
            </div>
            <div>
              <p className="font-medium text-foreground">筛出来的股票能直接买吗？</p>
              <p>不能。这是量化初筛名单，每个策略卡片下方都写着它的失效场景，买入前务必人工复核基本面。</p>
            </div>
            <div>
              <p className="font-medium text-foreground">我想调整某个策略的参数/阈值？</p>
              <p>选股策略的参数直接告诉我即可（如「把动量突破的市值门槛提到 50 亿」），我会改参数并重新扫描；回测策略的参数在<Link to="/backtest" className="underline">回测页</Link>自己拖数字（或切「代码」模式改 JSON）就能实时重跑。</p>
            </div>
            <div>
              <p className="font-medium text-foreground">回测结果可信吗？</p>
              <p>回测用于「快速排除明显没用的想法」，不是收益承诺。已知的系统性偏差都写在回测页底部：股票池按今日成交额选取（幸存者偏差，结果偏乐观）、前复权口径、T+1 成交、允许零碎股。策略真要用，先过回测、再过人工复核。</p>
            </div>
            <div>
              <p className="font-medium text-foreground">云端版和本机版有什么区别？</p>
              <p>云端版免挂机但字段较少（无 PB/股息率/换手率）；本机版连富途 OpenD 字段最全（PB、股息率 TTM、换手率、振幅都有），「低估值高股息」策略只在本机版产出。</p>
            </div>
          </CardContent>
        </Card>

        <p className="text-center text-xs text-muted-foreground pb-6">本工具仅作研究筛选，不构成投资建议。</p>
      </div>
    </AppShell>
  )
}
