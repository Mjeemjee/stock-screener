"""Project accepted account research into the public progress snapshot.

Run in the research workspace; no new price requests, signals or trades. Activity
is supplied by the owning conversation after an actual progress observation.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import argparse, hashlib, json, math, re, shutil, subprocess, sys

ROOT=Path(__file__).resolve().parents[1]
TEAM=ROOT/'reports/hk-strategy-team-20261112'
OUT=ROOT/'portfolio-board/public/research-progress'
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def clean(text):return re.sub(r'\[([^\]]+)\]\([^)]+\)',r'\1',text).replace('`','').replace('**','').strip()

def accepted_card(card,accepted,later=None,study_only=False):
    if not accepted.exists():return card
    result=read(accepted);cases=result['cases']
    assert len(cases)==2 and {v['cost'] for v in cases}=={'base','pressure'}
    complete=all(type(v.get('net_hkd')) in (int,float) and math.isfinite(v['net_hkd']) and type(v.get('quote_drawdown_pct')) in (int,float) and math.isfinite(v['quote_drawdown_pct']) and not v.get('unknowns') for v in cases)
    card['period']=' — '.join(result['period'])
    if not complete:
        assert result.get('complete_economics_evaluable') is False or any(v.get('unknowns') for v in cases),'Invalid result must not be silently hidden'
        card.update(status='unknown',status_label='必要执行资料不足',basis='完整收益和风险无法评估，已知前缀不代替终点',
            results=[dict(cost=k,net_hkd=None,cagr_pct=None,risk_pct=None) for k in ['base','pressure']],
            conclusion=(f"{result['source_failure_date']} 必要退出 {result['required_exit_quantity']} 份缺可靠成交资料。" if result.get('source_failure_date') and result.get('required_exit_quantity') else '必要输入未知，完整经济结果保持未知。'),
            next='本轮已归档，后续条件案未运行；其他候选继续独立研究。')
        return card
    positive=all(v['net_hkd']>0 and v['quote_drawdown_pct']<=20 for v in cases)
    status='review' if positive and study_only else 'candidate' if positive else 'closed'
    card.update(status=status,status_label='旧史诊断有条件正额' if status=='review' else ('后续段通过，保留候选' if later and later.exists() else '开发通过，待后段') if positive else '固定版本已关闭',
        basis=result.get('site_basis','已见历史单独起账，净应收不当作可用现金' if study_only else '已独立复算，含开放持仓估值'),
        results=[dict(cost=v['cost'],net_hkd=v['net_hkd'],cagr_pct=None,risk_pct=v['quote_drawdown_pct'],closed_net_hkd=v.get('closed_net_hkd'),open_contribution_hkd=v.get('open_contribution_hkd'),open_quantity=v.get('open_quantity')) for v in cases],
        conclusion=result.get('site_conclusion','旧历史诊断正额不等于通过采用标准或取得独立验证。' if study_only and positive else '固定两成本净正，样本及执行限制保留。' if positive else '固定检验未通过，保留原结果。'),
        next='下一步由原协议和证据决定，不调整参数救结果。' if positive else '原失败保留，不打开后段补救。')
    return card

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--activity',choices=['preparing','checking','waiting','done'],required=True)
    parser.add_argument('--phase',choices=['source','implementation','development','later'],default='development')
    parser.add_argument('--focus',choices=['sp500','small-nasdaq','hsi-hold','gold','ipo'],default='sp500')
    args=parser.parse_args();now=datetime.now(timezone(timedelta(hours=8))).isoformat()
    nasdaq=read(TEAM/'v103-review/DESCRIPTIVE-ACCOUNTS-v1.json')
    negative=read(TEAM/'v102-review/FINAL-REVIEW-v1.json')
    quality=read(TEAM/'v106-sp500-development-source/SOURCE-QUALIFICATION-v1.json')
    baseline=read(TEAM/'v103-review/FINAL-REVIEW-v1.json')
    # This existing entry point is read-only and makes no new source request.
    paper_run=subprocess.run([sys.executable,'-B','-X','utf8',str(TEAM/'candidate-packet/forward.py'),'status'],
                             cwd=ROOT,capture_output=True,text=True,encoding='utf-8',check=True,timeout=20)
    paper= json.loads(paper_run.stdout)
    assert paper['actual_orders']==0
    monthly=[v for v in nasdaq['metrics'] if v['role']=='monthly']
    cards=[dict(id='nasdaq-monthly',name='03086 · 每月趋势复核',status='paper',status_label='保留纸面验证',capital_hkd=30000,
                period='2020-01-02 — 2026-11-13',basis='历史收盘标记，含开放持仓',
                results=[dict(cost=v['cost'],net_hkd=v['marked_change_hkd'],cagr_pct=v['calendar_cagr_pct'],risk_pct=v['quote_drawdown_pct']) for v in monthly],
                conclusion='历史正收益；降低回撤的取舍有依据，稳定超额收益尚未建立。只有5笔已闭合、1笔开放。',
                next='按冻结规则接续真实日期的纸面记录。'),
           dict(id='dividend-03110',name='03110 · 高股息月度趋势',status='closed',status_label='固定版本已关闭',capital_hkd=30000,
                period='2021-01-01 — 2023-12-29',basis='各4笔已闭合，期末全现金',
                results=[dict(cost=v['cost'],net_hkd=v['net_hkd'],cagr_pct=None,risk_pct=v['quote_drawdown_pct']) for v in negative['cases']],
                conclusion='两档成本均亏损。价格变化加毛分派也为负，关闭这版并保留结果。',next='未打开2024年后数据补救。')]
    development_review=TEAM/'v106-review/FINAL-REVIEW-v1.json'
    later_review=TEAM/'v106c-review/FINAL-REVIEW-v1.json'
    accepted=later_review if later_review.exists() else development_review
    latest=dict(id='sp500-03195',name='03195 · 小资金月度趋势',status='pending',status_label='开发结果待验收',capital_hkd=10000,
                period='2025-02-01 — 2025-12-31',basis='预先固定两档成本，当前不显示未验收收益',
                results=[dict(cost=k,net_hkd=None,cagr_pct=None,risk_pct=None) for k in ['base','pressure']],
                conclusion=f"已核{quality['actual_sessions']}个实际交易日；开收盘价和成交量两源一致。实际零分派窗口另有官方公告支持。",
                next='完成两案和独立现金复算；任一净额非正便关闭此版。')
    if accepted.exists():
        result=read(accepted);cases=result['cases']
        assert len(cases)==2 and {v['cost'] for v in cases}=={'base','pressure'}
        assert all(math.isfinite(v['net_hkd']) and math.isfinite(v['quote_drawdown_pct']) for v in cases)
        positive=all(v['net_hkd']>0 and v['quote_drawdown_pct']<=20 for v in cases)
        latest.update(status='candidate' if positive else 'closed',status_label='开发通过，待后段' if positive else '固定版本已关闭',
            period=' — '.join(result['period']),
            basis='已独立复算的后续段，各案重新起账' if later_review.exists() else '已独立复算的开发期结果，含开放持仓估值',
            results=[dict(cost=v['cost'],net_hkd=v['net_hkd'],cagr_pct=None,risk_pct=v['quote_drawdown_pct'],closed_net_hkd=v['closed_net_hkd'],open_contribution_hkd=v['open_contribution_hkd'],open_quantity=v['open_quantity']) for v in cases],
             conclusion=('固定后续段两成本净正，样本仍有限。' if later_review.exists() else '两成本开发净正，统计样本仍有限。') if positive else '固定检验门槛未通过，原结果保留。',
            next='继续核连续账户、资金差异与被动参考。' if positive and later_review.exists() else '按预先协议核后续历史段。' if positive else '不以修改参数或打开后段补救此版。')
        if not later_review.exists() and positive and args.phase=='later':latest['status_label']='开发通过，后段待验收'
        if later_review.exists() and positive:latest['status_label']='后续段通过，保留候选'
    cards.insert(0,latest)
    small_review=TEAM/'v108-review/FINAL-REVIEW-v1.json'
    small_later=TEAM/'v108c-review/FINAL-REVIEW-v1.json'
    small_accepted=small_later if small_later.exists() else small_review
    small=dict(id='nasdaq-03034',name='03034 · 小资金纳指月度趋势',status='pending',status_label='来源与代码准备',capital_hkd=10000,
        period='2024-11-01 — 2025-12-31',basis='固定开发期；当前没有已验收账户结果',
        results=[dict(cost=k,net_hkd=None,cagr_pct=None,risk_pct=None) for k in ['base','pressure']],
        conclusion='已找到年度财务报告与目标切换首日整手原件；现金口径正在独立复核。',
        next='来源通过后，一次执行固定两成本开发检验。')
    small=accepted_card(small,small_accepted,small_later)
    if not small_accepted.exists() and (TEAM/'v108-small-nasdaq-development-source/ROOT-SOURCE-ACCEPTANCE-v1.json').exists():
        small.update(status_label='开发检验，待独立验收',conclusion='现金与起点整手条件已核；492日原价已取齐，零成交量和报价异常保留。',next='完成固定两成本账户及独立复算，必要执行资料未知时不展示完整收益。')
    if (TEAM/'V108-SMALL-NASDAQ-PROTOCOL-20261117.md').exists():
        cards=[small,*[v for v in cards if v['id']=='nasdaq-monthly'],*[v for v in cards if v['id']!='nasdaq-monthly']]
    elif args.focus=='small-nasdaq':raise ValueError('03034事前协议不存在')
    hsi_review=TEAM/'v109-review/FINAL-REVIEW-v1.json'
    hsi=dict(id='hsi-02800-longhold',name='02800 · 每月复核取消到期',status='pending',status_label='既有历史单变体诊断',capital_hkd=30000,
        period='2011—2018开发／2019—2023已见后段',basis='各段独立起账；原50%预算，未知支付日股息留净应收',
        results=[dict(cost=k,net_hkd=None,cagr_pct=None,risk_pct=None) for k in ['base','pressure']],
        conclusion='只取消三月到期退出；保留原1tick/15及2tick/30成本、量额资格与现金约束。',next='固定四案和原三月基线比较，不作为全盲验证或真实到账收入。')
    hsi=accepted_card(hsi,hsi_review,study_only=True)
    if (TEAM/'V109-HOLD-DIAGNOSTIC-EXECUTION-20261117.md').exists():cards.insert(0,hsi)
    elif args.focus=='hsi-hold':raise ValueError('02800正式诊断协议不存在')
    gold=dict(id='gold-feasibility',name='黄金 ETF · 小资金可行性预检',status='pending',status_label='来源与整手预检',capital_hkd=30000,
        period='预检阶段，尚无本轮账户结果',basis='同时核对1／2／3万门槛；这里不展示策略收益',
        results=[dict(cost=k,net_hkd=None,cagr_pct=None,risk_pct=None) for k in ['base','pressure']],
        conclusion='核对02840每手1份与03081每手100份的官方来源、现金事件和费用门槛；既有V86黄金规则失败保留。',
        next='源审与可执行性通过后，先固定规则及期间，再决定是否回测。')
    gold_rule=TEAM/'V111-SPDR-LOT1-PREPARATION-20261117.md'
    gold_source=TEAM/'v111-spdr-source/SOURCE-QUALIFICATION-v1.json'
    gold_review=TEAM/'v111-review/FINAL-REVIEW-v1.json'
    if gold_rule.exists():
        gold.update(name='02840 · 单份整手月度趋势',capital_hkd=10000,period='2025-07-01 — 2026-11-16',
            status_label='执行代码准备，待验收',basis='固定新制度诊断；每月复核，40%预算，不设到期',
            conclusion='只在2025-06-30整手5→1后交易；2026零分派为条件推断，不能视为完整现金认证。',
            next='高价ETF价位和独立核算准备通过后，一次运行固定账户；目前没有已验收收益。')
        if gold_source.exists():
            quality_gold=read(gold_source)
            assert quality_gold['status']=='CONDITIONAL_FIXED_REGIME_SOURCE_READY'
            gold['conclusion']=f"{quality_gold['actual_sessions']}实际日开收盘与成交量两源一致，无零量。保留最低价异常、风险代理及2026零分派条件；暂无本轮账户结论。"
        gold=accepted_card(gold,gold_review,study_only=True)
    if (TEAM/'V110-GOLD-PREFLIGHT-20261117.md').exists():cards.insert(0,gold)
    elif args.focus=='gold':raise ValueError('黄金事前预检派单不存在')
    ipo_review=TEAM/'ipo-review-20261117/FINAL-REVIEW-v1.json'
    ipo=dict(status='pending')
    if args.focus=='ipo':
        assert ipo_review.exists() and read(ipo_review)['decision']=='ACCEPT_NEW_OFFER_CONFIRMED_ADMISSION_PENDING'
    current,current_later={'sp500':(latest,later_review),'small-nasdaq':(small,small_later),'hsi-hold':(hsi,None),'gold':(gold,None),'ipo':(ipo,None)}[args.focus]
    registry=[]
    for i,line in enumerate((TEAM/'README.md').read_text(encoding='utf-8').splitlines()):
        if not line.startswith('| `/root'):continue
        cells=[clean(v) for v in line.split('|')[1:-1]]
        if len(cells)!=4:continue
        version=re.search(r'V\d+[A-Z]?',cells[1])
        registry.append(dict(id=f'team-{i}',version=version.group() if version else '研究汇总',name=cells[1],
              category='recent',conclusion=cells[2],source_date=now[:10],source='工作台记录同步'))
    factor_notes=TEAM/'factor-validity/FACTOR-AND-RULE-CONCLUSIONS-v2.json'
    if factor_notes.exists():
        notes=read(factor_notes)
        assert notes['new_factor_IC_computations']==0
        for note in notes['items']:
            registry.append(dict(id='signal-note-'+note['id'],version='信号与规则综述',name=note['name'],category='recent',
                conclusion=note['conclusion'],source_date=now[:10],source='已验账户证据综述；本轮无新增IC'))
    archived=ROOT/'sites/hk-quant-research-hub/dist/data/catalog.json'
    archive=read(archived) if archived.exists() else None
    if archive:
        for r in archive['strategies']:
            registry.append(dict(id='archive-'+r['id'],version='早期归档',name=r['name'],category='archive',
                 conclusion=clean(str(r.get('short_conclusion') or r.get('conclusion') or r['summary']))[:800],
                 source_date='2026-11-03',source='旧快照，结论日期保留'))
    stage_status=['done','done','done','active','pending','pending']
    if current['status']!='pending':stage_status=['done','done','done','done','pending' if current['status']=='candidate' else 'not_opened','pending' if current['status']=='candidate' else 'not_opened']
    if args.phase=='source':stage_status=['done','active','pending','pending','pending','pending']
    if args.phase=='implementation' and current['status']=='pending':stage_status=['done','done','active','pending','pending','pending']
    if args.phase=='later' and current['status']=='candidate':stage_status=['done','done','done','done','active','pending']
    if current_later is not None and current_later.exists():stage_status=['done','done','done','done','done','pending' if current['status']=='candidate' else 'not_opened']
    if current['status']=='unknown':stage_status=['done','done','done','unknown','not_opened','not_opened']
    if args.focus=='ipo':stage_status=['done','active','active','pending','not_opened','not_opened']
    if args.activity not in ['preparing','checking']:stage_status=['pending' if s=='active' else s for s in stage_status]
    activity_active=args.activity in ['preparing','checking'] and current['status'] in ['pending','candidate']
    activity_text={'preparing':'准备固定开发检验','checking':'固定检验执行与独立核算','waiting':'等待下一项真实证据','done':'本轮检验已验收'}[args.activity]
    if args.focus=='hsi-hold' and args.activity in ['preparing','checking']:activity_text='已见历史的固定四案单变体诊断'
    if args.phase=='later' and args.activity in ['preparing','checking']:activity_text='固定后续段与连续账户检验'
    if args.phase=='source' and args.activity in ['preparing','checking']:activity_text='发行人现金事件复核与开发源准备'
    if args.focus=='gold' and args.activity in ['preparing','checking']:activity_text='黄金ETF来源、整手与小资金费用预检'
    if args.phase=='implementation' and args.activity in ['preparing','checking']:activity_text='高价ETF执行、现金与独立核算代码准备'
    if args.focus=='ipo' and args.activity in ['preparing','checking']:activity_text='09941现金路径核对，与新时点完整首日源补证并行；准入及温度仍待核'
    source_paths={'nasdaq':'v103-review/FINAL-REVIEW-v1.json','dividend':'v102-review/FINAL-REVIEW-v1.json','sp500_source':'v106-sp500-development-source/SOURCE-QUALIFICATION-v1.json'}
    if accepted.exists():source_paths['sp500_accepted']=str(accepted.relative_to(TEAM))
    if small_accepted.exists():source_paths['small_nasdaq_accepted']=str(small_accepted.relative_to(TEAM))
    if hsi_review.exists():source_paths['hsi_hold_accepted']=str(hsi_review.relative_to(TEAM))
    if (TEAM/'V108-SMALL-NASDAQ-PROTOCOL-20261117.md').exists():source_paths['small_nasdaq_protocol']='V108-SMALL-NASDAQ-PROTOCOL-20261117.md'
    if (TEAM/'V109-HOLD-DIAGNOSTIC-EXECUTION-20261117.md').exists():source_paths['hsi_hold_protocol']='V109-HOLD-DIAGNOSTIC-EXECUTION-20261117.md'
    if (TEAM/'V110-GOLD-PREFLIGHT-20261117.md').exists():source_paths['gold_preflight_protocol']='V110-GOLD-PREFLIGHT-20261117.md'
    if gold_rule.exists():source_paths['gold_rule']=str(gold_rule.relative_to(TEAM))
    if gold_source.exists():source_paths['gold_window_source']=str(gold_source.relative_to(TEAM))
    if gold_review.exists():source_paths['gold_accepted']=str(gold_review.relative_to(TEAM))
    if ipo_review.exists():source_paths['ipo_primary_accepted']=str(ipo_review.relative_to(TEAM))
    if factor_notes.exists():source_paths['signal_and_rule_notes']=str(factor_notes.relative_to(TEAM))
    payload=dict(schema_version=1,updated_at=now,market_data_through=paper['verified_data_through'],
      activity=dict(status=args.activity,active_at_snapshot=activity_active,focus={'small-nasdaq':'03034 · 1万港币账户','sp500':'03195 · 1万港币账户','hsi-hold':'02800 · 3万港币账户','gold':'黄金 ETF · 来源与小资金预检','ipo':'IPO · 09941前向资料核对'}[args.focus],
                    text=activity_text,
                    snapshot_only=True,fresh_for_minutes=15),
      stages=[dict(name=n,status=s) for n,s in zip(['原前向协议','发售资格与截止','首日源补证','08:30资料固化','分配与资金回流','首日退出证据'] if args.focus=='ipo' else ['规则固定','原价与事件','现金与成本','开发检验','后续历史段','真实日期纸面'],stage_status)],
      cards=cards,registry=registry,
      paper=dict(checked_at=paper['checked_at_hkt'],activation_utc=paper['activation_utc'],first_forward_session=paper['first_forward_session'],
                 account_count=len(paper['summaries']),closed_rounds=paper['summaries']['monthly-only-base']['closed_rounds'],
                 open_quantity=paper['summaries']['monthly-only-base']['open_quantity'],
                 modeled_change_hkd=paper['summaries']['monthly-only-base']['total_marked_change_hkd'],orders_sent=0,
                 primary_account='monthly-only-base',accounts=[dict(id=k,nav_hkd=v['marked_nav_hkd'],change_hkd=v['total_marked_change_hkd'],closed_rounds=v['closed_rounds'],quantity=v['open_quantity']) for k,v in paper['summaries'].items()],
                 note='四组独立纸面假设，每组初始3万港币。历史收益不计入前向账本。'),
      research_note='不同资金、期间与规则的结果不能相加。模型回撤不是未来亏损上限；历史正额不证明稳定副业收入。',
      baseline=dict(monthly_base_net_hkd=11644.34,passive_base_net_hkd=24201.91,monthly_base_risk_pct=12.49025137086156,
                    passive_base_risk_pct=19.548568745437528,independent_alpha_confirmed=False,
                    pressure_passive_note='压力参考首次未买到后保持现金，主市场暴露无法估计。'),
      factor_archive=dict(count=len(archive['factors']) if archive else 0,source_date='2026-11-03',
                          note='旧因子目录快照；本轮没有生成新的IC或采用结论。'),
      source_hashes={k:digest(TEAM/v) for k,v in source_paths.items()})
    OUT.mkdir(exist_ok=True,parents=True);(OUT/'assets').mkdir(exist_ok=True)
    with (OUT/'progress.json').open('w',encoding='utf-8',newline='\n') as f:json.dump(payload,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
    shutil.copyfile(ROOT/'reports/hk-nasdaq-baseline-attribution-owner-20261116-v103/baseline-nav-close-drawdown-v1.png',OUT/'assets/nav-risk.png')
    if later_review.exists():shutil.copyfile(ROOT/'reports/hk-sp500-later-validation-owner-20261117-v106c/C-ONLY-NAV-DRAWDOWN-v2.png',OUT/'assets/sp500-later-risk.png')
    if gold_review.exists():shutil.copyfile(TEAM/'v111-review/C-ONLY-NAV-RISK-v1.png',OUT/'assets/gold-later-risk.png')
    print(json.dumps(dict(updated_at=now,records=len(registry),focus=args.focus,latest_status=current['status'],paper_closed_rounds=payload['paper']['closed_rounds'],orders_sent=0),ensure_ascii=False))

if __name__=='__main__':main()
