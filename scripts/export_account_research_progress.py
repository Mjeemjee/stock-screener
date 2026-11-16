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

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--activity',choices=['preparing','checking','waiting','done'],required=True)
    parser.add_argument('--phase',choices=['development','later'],default='development')
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
    registry=[]
    for i,line in enumerate((TEAM/'README.md').read_text(encoding='utf-8').splitlines()):
        if not line.startswith('| `/root'):continue
        cells=[clean(v) for v in line.split('|')[1:-1]]
        if len(cells)!=4:continue
        version=re.search(r'V\d+[A-Z]?',cells[1])
        registry.append(dict(id=f'team-{i}',version=version.group() if version else '研究汇总',name=cells[1],
              category='recent',conclusion=cells[2],source_date=now[:10],source='工作台记录同步'))
    archived=ROOT/'sites/hk-quant-research-hub/dist/data/catalog.json'
    archive=read(archived) if archived.exists() else None
    if archive:
        for r in archive['strategies']:
            registry.append(dict(id='archive-'+r['id'],version='早期归档',name=r['name'],category='archive',
                 conclusion=clean(str(r.get('short_conclusion') or r.get('conclusion') or r['summary']))[:800],
                 source_date='2026-11-03',source='旧快照，结论日期保留'))
    stage_status=['done','done','done','active','pending','pending']
    if latest['status']!='pending':stage_status=['done','done','done','done','pending' if latest['status']=='candidate' else 'not_opened','pending' if latest['status']=='candidate' else 'not_opened']
    if args.phase=='later' and latest['status']=='candidate':stage_status=['done','done','done','done','active','pending']
    if later_review.exists():stage_status=['done','done','done','done','done','pending' if latest['status']=='candidate' else 'not_opened']
    if args.activity not in ['preparing','checking']:stage_status=['pending' if s=='active' else s for s in stage_status]
    activity_active=args.activity in ['preparing','checking'] and latest['status'] in ['pending','candidate']
    activity_text={'preparing':'准备固定开发检验','checking':'账户计算与独立复算','waiting':'等待下一项真实证据','done':'本轮检验已验收'}[args.activity]
    if args.phase=='later' and args.activity in ['preparing','checking']:activity_text='固定后续段与连续账户检验'
    source_paths={'nasdaq':'v103-review/FINAL-REVIEW-v1.json','dividend':'v102-review/FINAL-REVIEW-v1.json','sp500_source':'v106-sp500-development-source/SOURCE-QUALIFICATION-v1.json'}
    if accepted.exists():source_paths['sp500_accepted']=str(accepted.relative_to(TEAM))
    payload=dict(schema_version=1,updated_at=now,market_data_through=paper['verified_data_through'],
      activity=dict(status=args.activity,active_at_snapshot=activity_active,focus='03195 · 1万港币账户',
                    text=activity_text,
                    snapshot_only=True,fresh_for_minutes=15),
      stages=[dict(name=n,status=s) for n,s in zip(['规则固定','原价与事件','现金与成本','开发检验','后续历史段','真实日期纸面'],stage_status)],
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
    print(json.dumps(dict(updated_at=now,records=len(registry),latest_status=latest['status'],paper_closed_rounds=payload['paper']['closed_rounds'],orders_sent=0),ensure_ascii=False))

if __name__=='__main__':main()
