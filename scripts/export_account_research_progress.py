"""Project accepted account research into the public progress snapshot.

Run in the research workspace; no new price requests, signals or trades. Activity
is supplied by the owning conversation after an actual progress observation.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import argparse, hashlib, json, math, re, shutil, subprocess, sys

ROOT=Path(__file__).resolve().parents[1]
TEAM=ROOT/'reports/hk-strategy-team-20261112'
MINING=ROOT/'reports/factor-mining-resume-20261117'
SGOV_PACKET=ROOT/'reports/us-sgov-paper-owner-20261117-v140'
DIVERSIFIED_RECEIPT=MINING/'paper-continuation-20261118-v179/ROOT-CONTINUATION-v1.json'
FORM4_RECEIPT=MINING/'acceptance/FORM4-v219-v220-ROOT-v1.json'
FORM4_ANNUAL_RECEIPT=MINING/'acceptance/FORM4-v222-ROOT-v1.json'
FORM4_AUDIT_RECEIPT=MINING/'acceptance/FORM4-v224-ROOT-v1.json'
FORM4_FINAL_RECEIPT=MINING/'acceptance/FORM4-v226-v227-ROOT-v1.json'
MERGER_RECEIPT=MINING/'acceptance/US-CASH-MERGER-v230-v232-ROOT-v1.json'
CIVITAS_RECEIPT=MINING/'acceptance/US-CASH-MERGER-CIVITAS-NO-OPEN-v1.json'
MERGER_EXECUTION_CHECKS=MINING/'acceptance/US-MERGER-EXECUTION-CHECKS-v1.json'
MERGER_REVIEW_RECEIPT=MINING/'acceptance/US-MERGER-v234-v236-ROOT-v1.json'
MERGER_CLOSEOUT_RECEIPT=MINING/'acceptance/US-MERGER-v242-v244-ROOT-v1.json'
MERGER_STRESS_RECEIPT=MINING/'acceptance/US-MERGER-v247-v249-ROOT-v1.json'
PDBC_PREFLIGHT_RECEIPT=MINING/'acceptance/PDBC-2015-v245-ROOT-v1.json'
IEF_PREFLIGHT_RECEIPT=MINING/'acceptance/IEF-FOMC-v250-v252-ROOT-v1.json'
IEF_RESULT_RECEIPT=MINING/'acceptance/IEF-ACCOUNT-v257-v258-ROOT-v1.json'
SOUTHBOUND_RECEIPT=MINING/'acceptance/HK-SOUTHBOUND-v262-v265-ROOT-v1.json'
SOUTHBOUND_MARCH_RECEIPT=MINING/'acceptance/HK-CONNECT-MARCH-v266-v268-v271-ROOT-v1.json'
ISSUER_TENDER_RECEIPT=MINING/'acceptance/US-ISSUER-TENDER-v269-v270-ROOT-v1.json'
HK_CONTROL_CLOSEOUT=MINING/'acceptance/HK-CONNECT-CONTROL-CLOSEOUT-v272-v276-ROOT-v1.json'
TENDER_CLOSEOUT=MINING/'acceptance/US-ISSUER-TENDER-v274-v275-ROOT-v1.json'
HK_NOV19_RECEIPT=MINING/'paper-nov19-20261119/ROOT-HK-CONTINUATION-v1.json'
TENDER_COVERAGE=MINING/'acceptance/US-ISSUER-TENDER-COVERAGE-v277-v279-ROOT-v1.json'
TENDER_EXECUTION=MINING/'acceptance/US-ISSUER-TENDER-EXECUTION-v279-ROOT-v1.json'
TENDER_BROKER=MINING/'acceptance/US-ISSUER-TENDER-BROKER-FIRST-v283-ROOT-v1.json'
OUT=ROOT/'portfolio-board/public/research-progress'
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def clean(text):return re.sub(r'\[([^\]]+)\]\([^)]+\)',r'\1',text).replace('`','').replace('**','').strip()


def merger_projection():
    if not MERGER_RECEIPT.exists():
        return None
    accepted=read(MERGER_RECEIPT)
    assert accepted['pins']
    for name,sha in accepted['pins'].items():
        path=(ROOT/name).resolve()
        assert path.is_relative_to(ROOT) and digest(path)==sha,name
    result=accepted['site_merger']
    assert result['state']=='SOURCE_SCREEN_INCOMPLETE' and result['return_tests']==0
    assert result['q4_proxy']+result['q1_proxy']==result['proxy_roster']
    assert result['proxy_classified']+result['proxy_open']==result['proxy_roster']
    assert result['proxy_roster']==result['proxy_available']
    assert result['vote_union_docs']>=result['vote_union_accessions']
    assert result['vote_union_docs']<=result['vote_merger_docs']+result['vote_acquisition_docs']
    assert all(re.fullmatch(r'https://www\.sec\.gov/[^\s]+',url) for url in result.get('links',{}).values())
    return result


def civitas_projection():
    if not CIVITAS_RECEIPT.exists():
        return None
    accepted=read(CIVITAS_RECEIPT)
    assert accepted['decision']=='CONFIRMED_NO_NEXT_REGULAR_OPEN_CIVITAS_SOLUTIONS'
    assert accepted['economic_tests']==0 and accepted['pins']
    for name,sha in accepted['pins'].items():
        path=(ROOT/name).resolve()
        assert path.is_relative_to(ROOT) and digest(path)==sha,name
    return {key:accepted[key] for key in ('symbol','public_shareholder_approval_date',
        'next_scheduled_open','proof_exchange_source')}


def merger_cost_projection():
    if not MERGER_EXECUTION_CHECKS.exists():
        return None
    record=read(MERGER_EXECUTION_CHECKS)
    assert record['decision']=='ACCEPT_MERGER_EXECUTION_CHECKS_ONLY' and record['pins']
    for name,expected in record['pins'].items():
        path=(ROOT/name).resolve()
        assert path.is_relative_to(ROOT) and digest(path)==expected,name
    result=record['site_merger_execution']
    assert result['substantive_exchange_exhibits']+result['placeholder_exhibits']==result['ordinary_terminal_filings']
    assert result['full_backtests']==0
    assert [r['hkd'] for r in result['tiers']]==[10000,20000,30000]
    return result


def merger_review_projection():
    if not MERGER_REVIEW_RECEIPT.exists():
        return None
    record=read(MERGER_REVIEW_RECEIPT)
    assert record['decision']=='ACCEPT_PROXY_CLASSIFICATION_AND_VOTE_RETRIEVAL_PROGRESS_ONLY' and record['pins']
    for name,expected in record['pins'].items():
        path=(ROOT/name).resolve()
        assert path.is_relative_to(ROOT) and digest(path)==expected,name
    keys=('proxy_document_classifications_total','proxy_residual_reviewed','remaining_vote_documents_retrieved',
        'remaining_vote_documents_classified','remaining_vote_only_routed','negative_fee_floor_scenarios',
        'near_zero_positive_fee_floor_scenarios','fee_floor_capital_scenarios')
    result={key:record[key] for key in keys}
    if MERGER_CLOSEOUT_RECEIPT.exists():
        closeout=read(MERGER_CLOSEOUT_RECEIPT)
        assert closeout['decision']=='ENUMERATED_VOTES_RECONCILED_EXECUTION_INCOMPLETE' and closeout['pins']
        for name,expected in closeout['pins'].items():
            path=(ROOT/name).resolve()
            assert path.is_relative_to(ROOT) and digest(path)==expected,name
        assert closeout['portfolio_economic_tests']==0 and closeout['new_qualified_after_v231']==0
        assert closeout['reviewed_inc_v236']+closeout['remaining_in_v236_queue']==result['remaining_vote_documents_retrieved']
        result['remaining_vote_documents_classified']=closeout['reviewed_inc_v236']
        result['remaining_vote_only_routed']=closeout['remaining_in_v236_queue']
        public_fields=('pacb_exit_quote_observations','pacb_ftc_case','idti_open_display_usd','idti_exchange_notice')
        result['closeout']={key:closeout[key] for key in public_fields}
    return result


def pdbc_preflight_projection():
    if not PDBC_PREFLIGHT_RECEIPT.exists():
        return None
    receipt=read(PDBC_PREFLIGHT_RECEIPT)
    assert receipt['decision']=='NO_ADVANCE_UNFILTERED_FULL_EXPOSURE' and receipt['pins']
    for name,expected in receipt['pins'].items():
        path=(ROOT/name).resolve()
        assert path.is_relative_to(ROOT) and digest(path)==expected,name
    assert receipt['account_backtests']==0
    assert [row['capital_hkd'] for row in receipt['tiers']]==[10000,20000,30000]
    return receipt


def merger_stress_projection():
    if not MERGER_STRESS_RECEIPT.exists():
        return None
    receipt=read(MERGER_STRESS_RECEIPT)
    assert receipt['decision']=='REJECT_FULL_EXPOSURE_IN_FAILURE_CONTROL_CONTINUE_OTHER_MECHANISMS' and receipt['pins']
    for path,expected in receipt['pins'].items():
        source=(ROOT/path).resolve()
        assert source.is_relative_to(ROOT) and digest(source)==expected,path
    assert receipt['verified_single_case_scenarios']==36 and receipt['verified_capacity_rows']==216
    assert receipt['portfolio_backtests']==receipt['actual_orders']==0
    stress=receipt['site_merger_stress']
    assert [row['capital'] for row in stress['tier_hkd']]==[10000,20000,30000]
    assert all(len(row['scenario_losses'])==3 for row in stress['tier_hkd'])
    return stress


def ief_result_projection():
    if not IEF_RESULT_RECEIPT.exists():
        return None
    receipt=read(IEF_RESULT_RECEIPT)
    assert receipt['decision']=='REJECT_FIXED_CUT_TIMING_FOR_PROMOTION' and receipt['pins']
    for path,expected in receipt['pins'].items():
        source=(ROOT/path).resolve()
        assert source.is_relative_to(ROOT) and digest(source)==expected,path
    result=receipt['site_ief_account']
    assert result['negative_matched_scenarios']==result['scenario_count']==24
    assert result['matched_pairs']==9 and result['forward_observations']==0
    assert [row['capital'] for row in result['base_and_pressure']]==[10000,20000,30000]
    return result


def southbound_projection():
    if not SOUTHBOUND_RECEIPT.exists():
        return None
    receipt=read(SOUTHBOUND_RECEIPT)
    assert receipt['decision']=='SOURCE_AND_COST_CHECKED_AWAITING_CONTROL' and receipt['pins']
    for name,expected in receipt['pins'].items():
        path=(ROOT/name).resolve()
        assert path.is_relative_to(ROOT) and digest(path)==expected,name
    result=receipt['site_southbound']
    assert result['qualified_pairs']==result['return_tests']==0
    assert [row['code'] for row in result['samples']]==['HK.06603','HK.02661']
    if SOUTHBOUND_MARCH_RECEIPT.exists():
        march=read(SOUTHBOUND_MARCH_RECEIPT)
        assert march['decision']=='FOUR_REMAINING_WITHOUT_POINT_IN_TIME_INDUSTRY_SIZE_FREE_FLOAT'
        assert march['qualified_pairs']==march['return_tests']==0 and march['pins']
        for name,expected in march['pins'].items():
            path=(ROOT/name).resolve()
            assert path.is_relative_to(ROOT) and digest(path)==expected,name
        result['march_controls']={key:march[key] for key in ('initial_candidates','both_routes_buy_unchanged',
            'both_routes_not_buy_unchanged','age_pass','turnover_pass','remaining','turnover')}
    if HK_CONTROL_CLOSEOUT.exists():
        end=read(HK_CONTROL_CLOSEOUT)
        assert end['decision']=='NO_MATCH_AT_FIXED_GATES' and end['qualified_pairs']==end['return_tests']==0
        assert all(digest(ROOT/path)==expected for path,expected in end['pins'].items())
        result['control_closeout']={k:end[k] for k in ('march_classification','september_classification','september_ratio','september_limit')}
    return result


def form4_projection():
    if not FORM4_RECEIPT.exists():
        return None
    accepted=read(FORM4_RECEIPT)
    assert accepted['decision']=='ACCEPT_SOURCE_PILOT_ONLY_NO_ELIGIBLE_PUBLIC_MARKET_BUY' and accepted['pins']
    for name,sha in accepted['pins'].items():
        path=(ROOT/name).resolve()
        assert path.is_relative_to(ROOT) and digest(path)==sha,name
    result=accepted['site_form4']
    assert result['forms_4']+result['amendments']==result['filings']
    assert result['explicit_public_market_purchase_rows']+result['unknown_buy_venue']==result['purchases_coded']
    assert result['explicit_public_market_purchase_rows']==result['actual_return_tests']==0
    if FORM4_ANNUAL_RECEIPT.exists():
        annual=read(FORM4_ANNUAL_RECEIPT)
        assert annual['decision']=='ACCEPT_2018_FORM4_STRUCTURE_ONLY' and annual['pins']
        for name,sha in annual['pins'].items():
            path=(ROOT/name).resolve()
            assert path.is_relative_to(ROOT) and digest(path)==sha,name
        assert annual['form_4']+annual['amendments']==annual['filings']
        assert annual['candidate_venue_unqualified']==annual['structure_rows']
        assert annual['explicit_public_market_footnotes']==annual['actual_return_tests']==0
        result['annual']={k:annual[k] for k in (
            'filings','issuers','structure_rows','structure_filings','structure_issuer_days',
            'dividend_reinvestment_hints','explicit_public_market_footnotes','actual_return_tests')}
        if FORM4_AUDIT_RECEIPT.exists():
            audit=read(FORM4_AUDIT_RECEIPT)
            assert audit['decision']=='ACCEPT_PURPOSIVE_ATTACHMENT_AUDIT_ONLY' and audit['pins']
            for name,sha in audit['pins'].items():
                path=(ROOT/name).resolve()
                assert path.is_relative_to(ROOT) and digest(path)==sha,name
            categories=('automatic_dividend_reinvestment_rows','prearranged_plan_purchase_rows',
                        'direction_conflict_rows','other_paid_acquisition_rows')
            assert sum(audit[key] for key in categories)==audit['rows_reviewed']
            assert audit['explicit_public_market_rows']==audit['actual_return_tests']==0
            result['annual']['attachment_audit']={k:audit[k] for k in (
                'original_filings_reviewed','rows_reviewed',*categories,'explicit_public_market_rows')}
            if FORM4_FINAL_RECEIPT.exists():
                final=read(FORM4_FINAL_RECEIPT)
                assert final['decision']=='SOURCE_INSUFFICIENT_FOR_STRICT_OPEN_MARKET_EVENT_TEST' and final['pins']
                assert final['goal_status']=='ACTIVE' and final['stable_profitability_proven'] is False
                for name,sha in final['pins'].items():
                    path=(ROOT/name).resolve()
                    assert path.is_relative_to(ROOT) and digest(path)==sha,name
                summary=final['site_form4_final']
                assert summary['candidate_filings']==annual['structure_filings']
                assert summary['candidate_rows']==annual['structure_rows']
                assert summary['original_filings_reviewed']+summary['missing_original_filings']==summary['candidate_filings']
                assert summary['rows_reviewed']+summary['missing_original_rows']==summary['candidate_rows']
                assert len(set(final['missing_accessions']))==summary['missing_original_filings']
                assert sum(summary[key] for key in categories)==summary['rows_reviewed']
                assert summary['explicit_public_market_rows']==summary['actual_return_tests']==0
                result['annual']['final_review']=summary
    return result


def filing_event_projection():
    source_path=MINING/'acceptance/FILING-SOURCE-v208-v210-ROOT-v1.json'
    event_path=MINING/'acceptance/FILING-EVENT-v211-ROOT-v1.json'
    if not source_path.exists():return None
    def checked(path,expected):
        record=read(path)
        assert record['decision']==expected and record['pins'] and not record.get('TEST_ONLY')
        for name,h in record['pins'].items():
            local=(ROOT/name).resolve()
            assert local.is_relative_to(ROOT) and digest(local)==h,name
        return record
    source=checked(source_path,'ACCEPT_EIGHT_FIXED_EDGAR_SOURCE_CELLS_ONLY')
    fact_path=ROOT/'reports/us-filing-coverage-20261119-v210/FACTS.json'
    assert fact_path.relative_to(ROOT).as_posix() in source['pins']
    facts=read(fact_path)['facts']
    cells=[{k:r[k] for k in ('issuer','year','accepted_et','official_index','eps_change')} for r in facts]
    assert len(cells)==8 and all(r['official_index'].startswith('https://www.sec.gov/Archives/') for r in cells)
    event=None
    comparison=None
    if event_path.exists():
        review=checked(event_path,'ACCEPT_EIGHT_CELL_EVENT_DIAGNOSTIC_ONLY')
        assert review['goal_status']=='ACTIVE' and review['stable_profitability_proven'] is False
        event=review['site_filing_event']
        assert event['net_account_hkd'] is None and event['real_orders']==0 and event['horizon_sessions']==20
        assert {(r['issuer'],str(r['year'])) for r in event['rows']}=={(r['issuer'],str(r['year'])) for r in cells}
        comparison_path=MINING/'acceptance/FILING-EVENT-v211-EQUAL-OPPORTUNITY.json'
        if comparison_path.exists():
            supplement=read(comparison_path)
            assert supplement['source_sha256']==digest(event_path) and supplement['denominator']==len(cells)
            assert supplement['skip_assumed_cash_return_pct']==0
            comparison=next(r for r in supplement['rows'] if r['round_trip_cost_pct']==.5)
    expansion=None
    expansion_source=MINING/'acceptance/FILING-SOURCE-v212-ROOT-v1.json'
    expansion_review=MINING/'acceptance/FILING-EVENT-v214-ROOT-v1.json'
    if event and expansion_review.exists():
        acceptance=read(expansion_review); source48=read(expansion_source)
        result_path=ROOT/'reports/us-filing-expanded-screen-20261119-v214/RESULT.json'
        assert acceptance['pins'][result_path.relative_to(ROOT).as_posix()]==digest(result_path)
        for pinset in (acceptance['pins'],source48['pins']):
            for name,sha in pinset.items():
                path=(ROOT/name).resolve(); assert path.is_relative_to(ROOT) and digest(path)==sha,name
        assert source48['qualified']==source48['planned']==48 and source48['independent_sample_matches']==source48['independent_sample_size']==8
        result=read(result_path); summary=result['primary']
        assert acceptance['decision']=='REJECT_EPS_GROWTH_ONLY_AS_A_BUY_FILTER_IN_THIS_FOUR_ISSUER_EXPANSION' and all(acceptance[name]==result[name] for name in ('primary','by_year','concentration_positive','overlap_all'))
        assert summary['planned']==summary['stock_priced']==summary['peer_comparable']==48
        assert result['new_account_runs']==result['IC_trials']==result['actual_orders']==0 and result['stable_profitability_proven'] is False
        years=[dict(year=int(y),priced=s['stock_priced'],positive=s['positive_priced'],**s['same_opportunity_costs']['50']) for y,s in sorted(result['by_year'].items())]
        expansion=dict(planned=summary['planned'],priced=summary['stock_priced'],positive=summary['positive_priced'],years=years,
                       cost50=summary['same_opportunity_costs']['50'],positive_peer_bp=summary['positive_mean_excess_bp'],
                       other_peer_bp=summary['nonpositive_mean_excess_bp'],leave_best_peer_bp=result['concentration_positive']['mean_omitting_best_bp'],
                       overlap=result['overlap_all']['max_simultaneous'])
    return dict(sources=cells,expansion=expansion,result=event,equal_opportunity=comparison,event_tests=int(event is not None),
                source_files=source['source_files_verified'],confirmed_first_public_minutes=source['confirmed_first_public_minutes'])


def november18_attribution():
    folder=MINING/'paper-nov18-20261119'
    note=folder/'FIRST-DAY-ATTRIBUTION.md'
    if not note.exists():return []
    arms=read(folder/'ROOT-CONTINUATION-v1.json')['site_diversified_paper']['arms']
    rows=[]
    for line in note.read_text('utf-8').splitlines():
        if not re.match(r'^\| (20000|30000) \|',line):continue
        capital,cost,fx,move,slip,fee,net=[c.strip().replace('**','') for c in line.strip('|').split('|')]
        match=next(a for a in arms if a['capital_hkd']==int(capital) and a['cost']=={'基础':'base','压力':'pressure'}[cost])
        assert match['net_hkd']==net and abs(sum(map(float,[fx,move,slip,fee]))-float(net))<.021
        rows.append(dict(capital=capital,cost=cost,fx=fx,move=move,slip=slip,fee=fee,net=net))
    assert len(rows)==4
    return rows

def accepted_us_factor_reports():
    """Read root-reviewed fixed rejections, including thin-runner outputs."""
    accepted=[]
    specs=[('us-intraday-persistence-owner-20261117-v141','US-INTRADAY-v141-ROOT-REVIEW-v1.json','PROTOCOL-v1.json',False),
           ('us-max-lottery-owner-20261117-v145','MAX-v145-ROOT-REVIEW-v1.json','PROTOCOL-v1.json',False),
           ('us-dividend-yield-owner-20261118-v147','DIVIDEND-YIELD-v147-ROOT-REVIEW-v1.json','PROTOCOL-v1.json',False),
           ('us-next-factor-preparation-owner-20261118-v151','RESIDUAL-v151-ROOT-REVIEW-v1.json','NEXT-PROTOCOL-v1.json',True)]
    for folder,review_name,protocol_name,thin in specs:
        review_path=MINING/'acceptance'/review_name
        if thin and not review_path.exists():continue
        base=ROOT/'reports'/folder;result=read(base/'RESULT-v1.json');protocol=read(base/protocol_name)
        review=read(review_path)
        assert review['decision']=='ACCEPT_FIXED_TRAINING_REJECTION_NOT_GLOBAL_MECHANISM_FAILURE'
        assert not result['validation_or_test_opened']
        if thin:
            manifest=read(base/'OUTPUT-MANIFEST-v1.json')
            assert result['status']=='COMPUTED_PENDING_INDEPENDENT_REVIEW' and result['net_account_profit'] is None
            assert manifest['candidate_signal_trials']==protocol['planned_unique_signals']==1
            assert manifest['fixed_horizon_trials']==len(protocol['horizons'])==2
            assert manifest['files_sha256']['RESULT-v1.json']==digest(base/'RESULT-v1.json')
            assert manifest['files_sha256'][protocol_name]==digest(base/protocol_name)
            assert not manifest['post2019_prices_used'] and not any(manifest['training_gate_pass'].values())
            assert review['sign_or_window_rescues']==0
        else:
            assert result['status']=='FIXED_HYPOTHESIS_NOT_SUPPORTED_BY_TRAINING_SCREEN' and result['account_net_profit'] is None
            assert result['trial_accounting']['unique_signals']==protocol['new_unique_signals']==1
            assert result['trial_accounting']['fixed_horizons']==len(protocol['horizons'])==2
            assert result['trial_accounting']['sign_or_window_rescues']==0
        assert sorted(map(int,result['training']))==sorted(protocol['horizons'])
        assert all(not r['decision']['pass_training_diagnostic'] for r in result['training'].values())
        verification=review['root_executed_verify'] if isinstance(review['root_executed_verify'],dict) else read(MINING/'acceptance'/review['root_executed_verify'])['stdout']
        assert verification['files_written']==0
        if thin:
            assert verification['status']=='REAL_TRAINING_REPRODUCED_WITH_SCOPED_EDGE_CONTRACT_FINDING'
            assert verification['real_training_numeric_review_passed'] and verification['ties']['gate_checks_unchanged']
            assert verification['actual_training_nonfinite_computed_returns']==0
            assert all(not x['fixed_training_rejection_affected'] for x in verification['contract_probes']['edge_contract_findings'])
        else:assert verification['status'].startswith('PASS_READ_ONLY')
        assert verification['result_sha256']==digest(base/'RESULT-v1.json')
        assert verification['protocol_sha256']==digest(base/protocol_name)
        if not thin:assert verification['protocol_sha256']==result['protocol_sha256']
        accepted.append((result,protocol))
    return accepted


def new_factor_research():
    """Project frozen reports; signal counts exclude stages, controls and templates."""
    original=read(MINING/'RESULT-v1.json')
    corrected=read(MINING/'calendar-correction-v2/RESULT.json')
    liquidity=read(ROOT/'reports/hk-liquidity-factor-owner-20261117-v130/RESULT-v1.json')
    anchor=read(ROOT/'reports/us-anchor-factor-owner-20261117-v132/RESULT-v1.json')
    assert corrected['correction_only'] and corrected['h20_rerun'] is False
    assert liquidity['unique_new_signals']==anchor['unique_new_signals']==1
    assert liquidity['maximum_horizon_trials']==anchor['maximum_horizon_trials']==2
    assert anchor['source_integrity']=='FAILED_EXISTING_US_HISTORY_NOT_SPLIT_CONSISTENT'
    assert all(not r['decision']['pass'] for r in liquidity['results']+anchor['results'])

    def fip_row(row,label):
        return dict(horizon=row['horizon'],split=label,period=f"{row['start']} — {row['end']}",
                    rank_ic=row['ic']['mean'],hac_t=row['ic']['t'],p_value=row['ic']['p_two_sided'],
                    p_label='双侧p',top_excess_bp=row['group_means']['top_excess']*10000)
    fip=[fip_row(r,{'train':'训练','validation':'验证'}[r['split']]) for r in original['metrics']
         if r['name']=='sign_persistence_126_skip21' and r['split'] in ['train','validation'] and
         (r['horizon']==5 or r['horizon']==20 and r['split']=='validation')]
    later=next(r for r in corrected['metrics'] if r['name']=='sign_persistence_126_skip21')
    fip.insert(2,fip_row(later,'已见后段 · 日历修正'))

    def trained_rows(result):
        rows=[]
        for r in result['results']:
            ic=r['metrics']['inference']['rank_ic']
            rows.append(dict(horizon=r['horizon'],split='训练',period=' — '.join(r['bounds']),
                             rank_ic=ic['mean'],hac_t=ic['t'],
                             p_value=r['decision']['p_bonferroni_this_batch_only'],p_label='两期限批内p',
                             top_excess_bp=r['metrics']['means']['top_excess']*10000))
        return rows

    report=dict(new_net_account_candidates=0,
        scope='港股和美股个股、普通非杠杆ETF；1万／2万／3万港币分别核验。',
        note='信号与预定期限按已验收来源去重计数；日历修正、来源核验和评价协议不增加因子试验。',
        limitations='各批次股票池、可评价集合和期间不同，不能直接横比IC来断言增量优势。已见历史不是新盲测；批内p校正不覆盖整个研究过程的选择偏差。',
        items=[
            dict(id='sign_persistence_126_skip21',name='港股 · 平滑动量',status='clue',status_label='统计线索，净账户未知',
                horizons=[5,20],formula=read(MINING/'PROTOCOL-v1.json')['formula'],
                diagnostics=fip,account_net_hkd=None,account_max_drawdown_pct=None,
                conclusion='5日已见后段RankIC 0.03354，但最高组相对该因子自身可评价池的毛差只有+0.047bp；2025年IC仅0.00357。20日已在验证段失败，未重新打开。',
                limitation='两停市日已修正；不是556股共同基准。组均值未计整手、费用或分派现金，不能解释为个人净利。',
                next='保留统计线索，暂不优先扩展账户；不调方向或期限救结果。'),
            dict(id=liquidity['candidate'],name='港股 · 异常放量价格压力反转',status='rejected',status_label='两期限训练淘汰',
                horizons=[5,20],formula='−mean(r × max(log(V / 前20日均量), 0), 最近5会话)',
                diagnostics=trained_rows(liquidity),account_net_hkd=None,account_max_drawdown_pct=None,
                conclusion='5日RankIC 0.01358，两期限批内p 0.05050，未过预定门槛；20日也失败。两个期限均在训练停止，未打开验证或后段。',
                limitation='最高组毛差不等于可执行账户利润；换手、整手和最低费用尚未完成账户验证。',
                next='关闭此固定公式，继续不同机制；不改阈值补救接近边界的p值。'),
            dict(id=anchor['candidate'],name='美股 · 252会话收盘高点锚定',status='source_blocked',status_label='源阻断，训练诊断未通过',
                horizons=[20,60],formula='close[T] / max(close[T−251:T]) − 1',
                diagnostics=trained_rows(anchor),account_net_hkd=None,account_max_drawdown_pct=None,
                conclusion='20／60日RankIC 0.01863／0.03772，但HAC t仅0.698／0.979。旧SinaUS缓存保留拆股阶跃，这些仅是存储价格诊断，不能当可靠经济收益。',
                limitation='700只现存池不是历史成分；账户净利润、回撤与本金适配未知。验证与后段未打开。',
                next='先核显式拆股及毛现金字段的小样本源资格，保留本版和旧结果。')])
    metadata={
        'us_intraday_log_strength_20':dict(name='美股 · 20会话日内强度延续',
            conclusion='20／60日RankIC 0.01149／0.02819，HAC t仅0.626／1.585。前组相对同池毛权益差为正，但两个固定期限均未过训练门槛。'),
        'us_negative_max_gross_close_return_20':dict(name='美股 · 低MAX极端收益回避',
            conclusion='20／60日RankIC −0.05701／−0.06330；低MAX前组相对同池毛权益差 −55.47／−105.64bp。h20双侧p过线是反方向关联，不支持冻结的低MAX优先方向。'),
        'us_trailing_gross_cash_yield_252':dict(name='美股 · 252会话毛现金股息率',
            conclusion='20／60日RankIC −0.075076／−0.123738；高股息率前组相对同池毛权益差 −33.38／−107.97bp。双侧显著为反方向，不支持冻结的高者优先方向；净账户未知。'),
        'us_single_proxy_predictive_residual_momentum_252_60':dict(name='美股 · 单代理残差趋势',
            conclusion='20／60日RankIC +0.02325／−0.00186，HAC t仅1.089／−0.067；前组相对同池毛权益差 +24.65／+54.16bp。两个期限均未通过冻结训练闸，毛差不是可执行净利润。')}
    for result,protocol in accepted_us_factor_reports():
        meta=metadata[result['candidate']]
        diagnostics=[]
        for h in protocol['horizons']:
            row=result['training'][str(h)];ic=row['inference']['rank_ic']
            diagnostics.append(dict(horizon=h,split='固定训练 · 毛权益诊断',period=' — '.join(protocol['training']),
                rank_ic=ic['mean'],hac_t=ic['t'],p_value=row['decision']['p_bonferroni_two_horizons_only'],
                p_label='两期限批内p',top_excess_bp=row['means']['top_excess']*10000,measure='gross_rights'))
        item=dict(id=result['candidate'],name=meta['name'],
            status='rejected',status_label='固定方向双期限筛退',horizons=protocol['horizons'],formula=protocol['formula'],
            diagnostics=diagnostics,account_net_hkd=None,account_max_drawdown_pct=None,
            conclusion=meta['conclusion'],
            limitation='只限40只当前大型股便利样本，日截面39—40只；毛除息权益不是可用现金或净账户。没有打开2020+，不代表全球机制失效。',
            next='固定失败保留；不翻方向、改窗口或挑年份补救，账户净利与本金适配仍未知。')
        if result['candidate']=='us_trailing_gross_cash_yield_252':
            audit=read(MINING/'acceptance/DIVIDEND-YIELD-v147-ROOT-REVIEW-v1.json')['precision_audit']
            assert audit['same_top_and_five_group_membership'] and audit['published_frozen_scores_not_rewritten']
            item.update(source_date=protocol['created_hkt'][:10],precision_audit=audit)
            item['limitation']+=f" 精确比率复核发现{audit['exact_ratio_tie_pairs']}对同值被浮点分数轻微拆开；平均IC最大差约{audit['largest_mean_IC_difference']:.2g}，前组及五组成员不变。保留冻结原分数与首个失败核验回执。毛现金指除息应收权利，不是已到账现金。"
        if result['candidate']=='us_single_proxy_predictive_residual_momentum_252_60':
            item['source_date']=protocol['created_hkt'][:10]
            item['limitation']='当前40只大型股便利池，先252会话估计、再60会话形成，需313个连续合格状态。代理为其余股票等权毛收益，不是标准三因子或广义市场中性；与60日价格动量平均秩相关约0.8311。未打开2020+，净账户与本金适配未知。'
            review=read(MINING/'acceptance/RESIDUAL-v151-ROOT-REVIEW-v1.json')
            item['independent_review']=dict(real_training_reproduced=True,edge_findings=review['edge_contract_findings'],fixed_training_rejection_affected=False)
            item['limitation']+=' 独立复算重现本次拒绝。F01为极端溢出输入下的非有限值处理缺陷；实际训练无此输入，不改变本次排名、分组与结论，通用复用前仍须修正。'
        report['items'].append(item)
    downside=accepted_downside_review()
    if downside:
        factor=downside['site_factor']
        assert factor['id']=='us_low_downside_semivariance_126' and factor['horizons']==[20,60]
        assert factor['status']=='rejected' and factor['account_net_hkd'] is None
        report['items'].append(factor)
    intermediate=accepted_intermediate_review()
    if intermediate:report['items'].append(intermediate['site_factor'])
    amihud=accepted_amihud_review()
    if amihud:report['items'].append(amihud['site_factor'])
    peer_delay=accepted_peer_delay_review()
    if peer_delay:report['items'].append(peer_delay['site_factor'])
    ids=[r['id'] for r in report['items']]
    assert len(ids)==len(set(ids)), 'A signal cannot be counted twice'
    report['unique_new_signals']=len(ids)
    report['planned_horizon_trials']=sum(len(set(r['horizons'])) for r in report['items'])
    report['note']=f"已验收筛选记录：{report['unique_new_signals']}个信号、{report['planned_horizon_trials']}个预定期限。日历修正、对照和模板不增加信号数；IC是排序相关系数，不是收益率。"
    return report


def accepted_evidence_updates():
    """Project source classification and evaluation acceptance, not new trials."""
    qii_review_path=MINING/'acceptance/SGOV-QII-v148-ROOT-REVIEW-v1.json'
    qii=read(qii_review_path)
    qii_source=ROOT/'reports/us-cash-tax-fee-source-owner-20261118-v148/SGOV-QII-QUALIFICATION-v2.json'
    qualification=read(qii_source)
    assert qii['decision']=='ACCEPT_ISSUER_CLASSIFICATION_ONLY_NOT_PERSONAL_TAX_FEE_OR_CASH'
    assert qii['classification_is_personal_tax_rate'] is False
    assert qii['actual_broker_withholding_refunds_fees_known'] is False
    assert qii['existing_30pct_tax_and_1_2USD_reserve_scenarios_changed'] is False
    assert qii['paper_rules_or_T0_changed'] is False and qii['stable_profitability_proven'] is False
    assert qii['pins'][qii_source.relative_to(ROOT).as_posix()]==digest(qii_source)
    years=sorted(qualification['annual'],key=lambda r:r['year'])
    findings=(qii_source.parent/'SOURCE-FINDINGS-v1.md').read_text(encoding='utf-8-sig')
    source_urls={int(m[1]):m[2] for line in findings.splitlines()
                 if (m:=re.match(r'\|(\d{4})\|.*?\]\((https://[^)]+)\)',line))}
    assert all(re.match(r'^https://www\.(blackrock|ishares)\.com/.+\.pdf$',source_urls[r['year']]) for r in years)
    assert sum(r['events_in_old_input'] for r in years)==qii['source_events']
    assert all(r['weighted_QII_percent']==qii['constant_one_share_amount_weighted_QII_percent'][str(r['year'])] for r in years)
    forward_path=MINING/'acceptance/FORWARD-EVALUATION-v149-ROOT-ACCEPTANCE-v1.json'
    forward=read(forward_path)
    completion=read(MINING/'acceptance/FORWARD-EVALUATION-v149-ROOT-COMPLETION-v1.json')
    assert forward['status']=='ACCEPTED' and forward['claim_level']=='DESCRIPTIVE_ONLY'
    assert forward['formal_statistical_stability_method_frozen'] is False
    assert forward['original_rules_ledger_T0_capital_unchanged'] and forward['all_existing_arms_reported']==8
    assert forward['automatic_goal_completion'] is False and forward['stable_profitability_proven'] is False
    assert completion['acceptance_sha256']==digest(forward_path) and completion['new_paper_T0'] is False
    assert completion['actual_freeze_utc']==forward['actual_freeze_utc']
    for path,expected in forward['pins'].items():assert digest(ROOT/path)==expected
    accepted_hkt=datetime.fromisoformat(forward['actual_freeze_utc']).astimezone(timezone(timedelta(hours=8)))
    return dict(
        sgov_qii=dict(status='accepted_issuer_classification_only',source_events=qii['source_events'],
            ticker=qii['ticker'],cusip=qii['cusip'],
            annual=[dict(year=r['year'],weighted_qii_percent=r['weighted_QII_percent'],source_url=source_urls[r['year']]) for r in years],
            classification_is_personal_tax_rate=False,actual_broker_withholding_refunds_fees_known=False,
            existing_model_amounts_changed=False,
            note='按每股分派金额加权的发行人QII分类比例，不是用户个人税率、免税资格或实际到账比例。点击年份查看已核发行人原表PDF。',
            limitation='实际预扣、退税时点与服务费用仍未知；原30%税及1／2美元事件储备情景、历史金额与两套纸面规则均未改变。不能因未单列收费认定费用为0，也不将退款当可用现金。'),
        forward_evaluation=dict(status='accepted_descriptive_only',actual_freeze_utc=forward['actual_freeze_utc'],
            accepted_at_hkt=accepted_hkt.strftime('%Y-%m-%d %H:%M:%S'),
            durable_completion_utc=completion['completed_utc'],claim_level=forward['claim_level'],
            formal_statistical_stability_method_frozen=False,existing_arms_reported=forward['all_existing_arms_reported'],
            original_t0s={k:v['original_t0_utc'] for k,v in forward['then_current_heads'].items()},
            primary_reporting_arms=forward['primary_reporting_arms'],new_paper_t0=False,
            stable_profitability_proven=False,automatic_goal_completion=False,
            note='原T0八臂全路径与本金保留；按各市场当地月末固定报告，启动月不足整月。已知现金观察和FX前缀不冒充更早预登记，跨接受时点的会话或月份另标过渡。',
            limitation='这是描述性评价协议的接受时点，不是新纸面T0，也不新增观察或证券交易。正式稳定性统计方法尚未冻结；不得以等待月份、交易笔数、某次正结果或协议接受自动证明稳定盈利。'))


def current_portfolio_research():
    protocol=read(ROOT/'reports/us-diversified-carry-owner-20261117-v144/PROTOCOL-v1.json')
    assert protocol['weights']=={'US.SGOV':'0.60','US.VTI':'0.20','US.GLD':'0.20'}
    assert protocol['windows']['A']==['2021-01-01','2023-12-31']
    pending=dict(id='v144-diversified-carry',name='60% SGOV / 20% VTI / 20% GLD · 条件性账户研究',
        status='implementation_pending_review',period='A · 2021-01-01 — 2023-12-31',net_hkd=None,risk_pct=None,chart=None,
        summary='固定60／20／20权重、年初再平衡、整数股、同一美元钱包；本金1万／2万／3万分别核验。',
        progress='资料已有条件采用；A段模型实现及独立核验中，目前没有已验收账户收益。B/C尚未打开。',
        limitations='VTI 2021四笔支付日来自第三方；2022/2023发行人日历的CUSIP冲突保留。付款日、30%税、费用、固定7.8换汇及T+3卖款均为条件情景，不能称已通过、实际到账或稳定收入。',
        curve_note='A段历史曲线待计算及主会话独立验收，当前不展示收益或曲线。')
    review_path=MINING/'acceptance/DIVERSIFIED-v144-A-ROOT-REVIEW-v2.json'
    if not review_path.exists():return pending
    review=read(review_path)
    assert review['decision']=='ACCEPT_CONDITIONAL_A_ACCOUNT_GATE_NOT_STABLE_PROFIT_PROOF'
    assert not review['stable_profit_proven'] and not review['annual_rebalance_advantage_demonstrated']
    assert not review['B_C_completed'] and review['actual_withdrawn_hkd']==0
    for relative,sha in review['pins'].items():assert digest(ROOT/relative)==sha, 'Accepted A-v2 input changed: '+relative
    folder=ROOT/'reports/us-diversified-carry-owner-20261117-v144/A-v2'
    summaries=read(folder/'ALL-A-SUMMARIES-v2.json')['summaries']
    primary=read(folder/'accounts/A_main_HKD30000_pressure/result.json')
    rows=[]
    for case in review['main_capital_results']:
        source=next(r for r in summaries if r['group']=='main' and r['capital_hkd']==case['capital_hkd'] and r['cost']==case['cost'])
        assert source['net_hkd']==case['net_hkd'] and source['max_observed_drawdown_pct']==case['max_observed_drawdown_pct']
        assert source['monthly_negative_count']==case['monthly_negative_count']
        rows.append(dict(capital_hkd=case['capital_hkd'],cost=case['cost'],net_hkd=float(case['net_hkd']),
            risk_pct=float(case['max_observed_drawdown_pct']),negative_months=case['monthly_negative_count'],months=source['months']))
    assert len(rows)==6 and len(primary['daily'])==756 and len(primary['trades'])==8
    net=float(primary['summary']['net_hkd']);risk=float(primary['summary']['max_observed_drawdown_pct'])
    assert net==float(review['primary_fraction_audit_executed_by_root']['net_hkd'])
    nav=[dict(date=r['date'],nav_hkd=float(r['hkd_nav']),tail=r['tail']) for r in primary['daily']]
    assert all(math.isfinite(p['nav_hkd']) and p['nav_hkd']>0 for p in nav)
    assert all(float(r['identity_residual'])==0 for r in primary['daily'])
    assert nav[-1]['nav_hkd']==float(primary['summary']['final_hkd'])
    pending.update(status='accepted_conditional_A_only',status_label='A段条件门槛通过，B待冻结',net_hkd=net,risk_pct=risk,
        chart='assets/portfolio-A-v2.png',cases=rows,capital_hkd=30000,cost='pressure',nav_series=nav,
        actual_income_certified=False,stable_profitability_proven=False,new_paper_t0=None,B_C_computed=False,
        progress='A段条件账户已验收，主3万压力累计+885.28港币，报价保守回撤约7.8337%，36个月中16个负月。1万在既定压力假设下亏损、未过A段门槛；实际适配仍待真实费用及前向证据。下一步冻结B（2024—2025）继续研究；B/C尚未计算，没有新增组合纸面T0。',
        comparison='同配置不调仓的3万压力对照累计+940.46港币，比年再平衡高55.18；没有建立再平衡优势，不能称独立alpha或稳定收入。',
        payment_sensitivity='2021年VTI四笔第三方付款日延后5个实际会话，六组配对的交易时刻、股数及终值不变，现金余额有20个会话短时不同；这不认证原支付日或实际到账。',
        curve_note='3万港币初始本金，压力费用情景；756个已复核HKD收盘/结算记账点含2024-01-04尾款。保守回撤另含报价高低代理。固定7.8、每方向50bp换汇及单边10bp价格摩擦、双倍佣金平台、30%预扣与每次正分派2美元储备。曲线不是提款或实际收入，报价回撤不是未来亏损上限。')
    pending['limitations']=pending['limitations'].replace('不能称已通过、实际到账或稳定收入。','仅A段条件门槛通过，未认证实际到账或稳定收入。')
    pending['fee_boundary']='每次非零分红基础预留1美元、压力预留2美元，是研究假设，非已确认富途收费；官方未单列也不据此认定0费用。模型保持原假设，没有重算费用救结果。'
    concentration=read(MINING/'acceptance/DIVERSIFIED-v144-A-CONCENTRATION-v1.json')
    assert concentration['source_result']==(folder/'accounts/A_main_HKD30000_pressure/result.json').relative_to(ROOT).as_posix()
    pending['annual_changes_hkd']={year:float(value) for year,value in concentration['annual_changes_hkd'].items()}
    pending['comparison']+=' 净正依赖2023回升，仍有亏损年份：主3万压力2021 +128.59、2022 −1,237.26、2023 +1,993.95港币；剔除最好年后为−1,108.67港币，仅作归因诊断。'
    pending['primary_chart_stage']='A'
    pending['B_accepted']=False;pending['C_accepted']=False
    b_review_path=MINING/'acceptance/DIVERSIFIED-v144-B-ROOT-REVIEW-v1.json'
    if b_review_path.exists():
        b_review=read(b_review_path)
        assert b_review['decision']=='ACCEPT_CONDITIONAL_B_NOT_BLIND_OR_STABLE_PROFIT_PROOF'
        assert b_review['A_pins_unchanged'] and b_review['all12_agent_independent_paths_pass']
        assert not b_review['C_completed'] and not b_review['stable_profit_proven'] and b_review['actual_orders']==0
        for relative,sha in b_review['pins'].items():assert digest(ROOT/relative)==sha, 'Accepted B input changed: '+relative
        b_summaries=read(ROOT/'reports/us-diversified-carry-owner-20261117-v144/B-v1/ALL-B-SUMMARIES-v1.json')['summaries']
        b_cases=[]
        for case in b_review['main_results']:
            source=next(r for r in b_summaries if r['group']=='main' and r['capital_hkd']==case['capital_hkd'] and r['cost']==case['cost'])
            assert source['net_hkd']==case['net_hkd'] and source['max_observed_drawdown_pct']==case['max_observed_drawdown_pct']
            assert source['monthly_negative_count']==case['monthly_negative_count']
            b_cases.append(dict(capital_hkd=case['capital_hkd'],cost=case['cost'],net_hkd=float(case['net_hkd']),risk_pct=float(case['max_observed_drawdown_pct']),
                negative_months=case['monthly_negative_count'],months=source['months']))
        assert len(b_cases)==6
        b_primary=next(r for r in b_cases if r['capital_hkd']==30000 and r['cost']=='pressure')
        assert b_primary['net_hkd']==float(b_review['primary_fraction_audit_executed_by_root']['net_hkd'])
        a_primary=next(r for r in rows if r['capital_hkd']==30000 and r['cost']=='pressure')
        def segment(stage,period,cases,primary):
            base=next(r for r in cases if r['capital_hkd']==30000 and r['cost']=='base')
            return dict(stage=stage,period=period,status='accepted_conditional',capital_hkd=30000,base_net_hkd=base['net_hkd'],net_hkd=primary['net_hkd'],
                risk_pct=primary['risk_pct'],negative_months=primary['negative_months'],months=primary['months'])
        pending.update(status='accepted_conditional_AB_C_pending',status_label='A/B条件历史已验收，C待核',B_accepted=True,B_cases=b_cases,
            period='A 2021—2023 / B 2024—2025；各自新本金',
            segment_rows=[segment('A','2021—2023',rows,a_primary),segment('B','2024—2025',b_cases,b_primary),
                dict(stage='C',period='2021—2025连续账户',status='awaiting_root_review',capital_hkd=30000,base_net_hkd=None,net_hkd=None,risk_pct=None,negative_months=None,months=None)],
            progress='A与B的主3万压力条件历史结果分别+885.28／+6,896.33港币；B报价保守DD约3.1083%，24个月中3个负月。两段各自新本金，不能相加构造连续收益。1万A段在既定压力假设下亏损，B段正额不救回该失败。C连续账户正研究及根审查，结果待核，不预填。',
            separation_note='A、B独立起账，不能相加或当作连续实绩；C必须沿同一钱包、同一起点单独连续核算。均为已见历史，非盲测、实际收入或稳定alpha；没有新增组合纸面T0。',
            B_annual_changes_hkd={year:float(value) for year,value in b_review['annual_changes_hkd'].items()},
            B_contribution_before_FX_usd={key:float(value) for key,value in b_review['net_asset_contributions_before_portfolio_FX_usd'].items()})
        pending['comparison']='同配置不调仓的主3万压力对照：A +940.46港币（高55.18），B +7,277.86港币，均高于各段年再平衡；未建立再平衡收益优势。A净正依赖2023回升，2022仍亏损，剔除最好年余−1,108.67；B的组合换汇前净资产贡献中，GLD为604.68／927.06美元，约65.2%，不能称稳定alpha。'
        pending['limitations']=pending['limitations'].replace('仅A段条件门槛通过，未认证实际到账或稳定收入。','A/B为已见条件历史，未认证实际到账或稳定收入。')
        pending['curve_note']='以下只保留A段3万港币压力曲线。'+pending['curve_note']
        c_review_path=MINING/'acceptance/DIVERSIFIED-v144-C-ROOT-REVIEW-v1.json'
        if c_review_path.exists():
            c_review=read(c_review_path)
            assert c_review['decision']=='ACCEPT_CONDITIONAL_CONTINUOUS_C_NOT_STABLE_PROFIT_PROOF'
            assert c_review['C_completed'] and c_review['all12_agent_independent_paths_pass'] and c_review['A_B_pins_unchanged']
            assert not c_review['stable_profit_proven'] and c_review['actual_orders']==0
            assert len(c_review['exact_A_prefix_rechecked_by_root'])==12
            assert all(r['equal_prefix_counts']['daily']==752 for r in c_review['exact_A_prefix_rechecked_by_root'])
            for relative,sha in c_review['pins'].items():assert digest(ROOT/relative)==sha, 'Accepted C input changed: '+relative
            total=read(ROOT/'reports/us-diversified-carry-owner-20261117-v144/C-v1/ABC-TOTAL-v1.json')
            assert len(total['all_cost_rows'])==18 and len(total['bands'])==9
            assert total['fixed_weights']==protocol['weights'] and not total['engine_changed']
            assert not total['new_paper_started'] and not total['stable_profit_proven'] and total['actual_orders']==0
            assert all(total['A_B_seals'][s]['all_unchanged'] for s in ['A','B'])
            c_cases=[]
            for case in c_review['main_results']:
                source=next(r for r in total['all_cost_rows'] if r['stage']=='C' and r['capital_hkd']==case['capital_hkd'] and r['cost']==case['cost'])
                assert source['main_net_hkd']==case['net_hkd'] and source['main_quote_drawdown_pct']==case['max_observed_drawdown_pct']
                assert source['main_negative_months']==case['monthly_negative_count']
                c_cases.append(dict(capital_hkd=case['capital_hkd'],cost=case['cost'],net_hkd=float(case['net_hkd']),risk_pct=float(case['max_observed_drawdown_pct']),
                    negative_months=case['monthly_negative_count'],months=source['months']))
            assert len(c_cases)==6
            for stage,cases in [('A',rows),('B',b_cases),('C',c_cases)]:
                for case in cases:
                    source=next(r for r in total['all_cost_rows'] if r['stage']==stage and r['capital_hkd']==case['capital_hkd'] and r['cost']==case['cost'])
                    assert float(source['main_net_hkd'])==case['net_hkd'] and float(source['main_quote_drawdown_pct'])==case['risk_pct']
                    assert source['main_negative_months']==case['negative_months'] and source['months']==case['months']
            c_primary=next(r for r in c_cases if r['capital_hkd']==30000 and r['cost']=='pressure')
            assert c_primary['net_hkd']==float(c_review['primary_fraction_audit_executed_by_root']['net_hkd'])
            pending.update(status='accepted_conditional_ABC',status_label='A/B/C条件历史已验收，稳定未证',C_accepted=True,C_cases=c_cases,B_C_computed=True,
                period='A 2021—2023 / B 2024—2025 / C 2021—2025连续账户',C_A_prefix_verified=True,
                progress='C以2021同一初始钱包连续运行，主3万压力五年累计+9,111.40港币，报价保守DD约7.8337%，18/60个月亏损。C的1万／2万压力净额为+1,611.46／+4,798.33；A的1万在既定压力假设下仍亏331.27，不因后段或五年正额救回。没有新增组合纸面T0，稳定盈利尚未证实。',
                separation_note='A/B各自新本金，C沿同一2021钱包连续核算并与A/B重叠，三行不能相加，不是三次独立盲测。A尾款至2024-01-04，B/C尾款至2026-01-06；均为条件历史，不是实际收入。',
                C_annual_changes_hkd={year:float(value) for year,value in c_review['annual_changes_hkd'].items()},
                C_contribution_before_FX_usd={key:float(value) for key,value in c_review['net_asset_contributions_before_portfolio_FX_usd'].items()},
                capital_cost_rows=[dict(stage=r['stage'],capital_hkd=r['capital_hkd'],cost=r['cost'],net_hkd=float(r['main_net_hkd']),
                    risk_pct=float(r['main_quote_drawdown_pct']),negative_months=r['main_negative_months'],months=r['months']) for r in total['all_cost_rows']])
            pending['segment_rows'][2]=segment('C','2021—2025连续账户',c_cases,c_primary)
            pending['comparison']='同配置不调仓的主3万压力对照：A +940.46、B +7,277.86港币，均高于各段年再平衡；C +10,328.63港币、报价保守DD约7.7428%，收益更高且报价回撤略低，年度再平衡未显示增益。A净正依赖2023回升，仍有亏损年份。组合换汇前净资产贡献中，B黄金约65.2%，C黄金约56.98%并受股票贡献，不能称稳定alpha。'
            pending['payment_sensitivity']='既有A段敏感性：'+pending['payment_sensitivity']
            pending['limitations']=pending['limitations'].replace('A/B为已见条件历史','A/B/C为重叠的已见条件历史')
    return pending


def sgov_history():
    path=MINING/'sgov-review/FINAL-REVIEW-v1.json'
    if not path.exists():return None
    result=read(path)
    assert result['decision']=='ACCEPT_CONDITIONAL_CASH_CARRY_FOR_PAPER_20K_30K'
    assert result['independent_cash_review_passed'] and not result['actual_personal_income_certified']
    assert result['independent_alpha_certified'] is False
    assert result['approved_capital_scenarios_hkd']==[20000,30000]
    assert result['excluded_capital_scenarios_hkd']==[10000]
    for relative,sha in result['source_pins'].items():
        assert digest(ROOT/relative)==sha, 'SGOV accepted input changed: '+relative
    cases=result['cases']
    assert len(cases)==18 and all(c['strategy']=='monthly_paid_yield' for c in cases)
    supplied=result['site_card']
    assert supplied['id']=='us-sgov-carry' and supplied['capital_hkd']==30000
    return dict(card=supplied,approved_capital_hkd=[20000,30000],excluded_capital_hkd=[10000],
        actual_personal_income_certified=False,independent_alpha_certified=False,
        cases=[dict(stage=c['stage'],capital_hkd=c['capital_hkd'],cost=c['cost'],start=c['start'],end=c['end'],
                    final_cash_date=c['final_cash_date'],net_hkd=float(c['net_hkd']),
                    risk_pct=float(c['max_quoted_nav_drawdown_pct'])) for c in cases],
        missed_entry_scenarios=result['missed_entry_sensitivity']['cases'],
        rule='每月末以前12个完整上市月内、当时已支付的发行人毛分派×0.70／月末原价判断，严格高于1%才于下个实际会话开盘持有；新仓连同买费不超过前交易净值90%及已结算现金，整股取整，持续持有不重调仓。',
        note='A 2021—2023、B 2024—2025各自起账；C 2021—2025与两段重叠，不可相加。A尾款2024-01-04、B/C尾款2026-01-06。18主策略情景不是18次独立试验。',
        limitations='固定7.8及双向汇兑成本、30%预扣税、每次分派1／2美元服务费储备均是条件情景；发行人付款日不等于券商到账日。单源报价及实际成交未认证。',
        comparison='B段与90%预算简单持有相同；收益来自短债现金carry，未建立独立择时alpha或稳定月收入。漏单敏感性18案中，2万／3万的A/B仍正，不能视为18次独立验证。')


def sgov_paper_status():
    """Call the zero-network status command only after root acceptance exists."""
    packet=SGOV_PACKET
    pending=dict(activated=False,status='awaiting_acceptance',activation_utc=None,first_session=None,
                 accounts=[],orders_sent=0,packet_version='v140',note='SGOV新增固定纸面正在修复时钟边界并独立验收；原包封存不激活。当前没有真实起点，不展示前向收益。')
    if not (packet/'ROOT-ACCEPTANCE-v1.json').exists():return pending
    run=subprocess.run([sys.executable,'-B','-X','utf8',str(packet/'paper.py'),'status'],cwd=ROOT,
                       capture_output=True,text=True,encoding='utf-8',timeout=20)
    result=json.loads(run.stdout)
    assert result['actual_orders']==0 and result['network_calls']==0 and result['files_written']==0
    blocked=None
    if result['status'].startswith('UNKNOWN'):
        # A failed new attempt cannot erase a real T0 or turn an old valuation into a current one.
        accepted=diversified_paper_status();receipt=read(ROOT/accepted['root_receipt'])
        before_refs=[p for p in receipt['pins'] if p.endswith('/BEFORE-v1.json') and 'us-paper-nov18-owner-20261119-v205/' in p]
        run_refs=[p for p in receipt['pins'] if p.endswith('/SGOV-RUN-v1.json') and 'us-paper-nov18-owner-20261119-v205/' in p]
        assert len(before_refs)==len(run_refs)==1,'SGOV source failure needs root-bound last-success and actual attempt evidence'
        before=read(ROOT/before_refs[0])['status_before']['SGOV'];attempt_wrapper=read(ROOT/run_refs[0])
        attempt=json.loads(attempt_wrapper['stdout'])
        assert before['status']=='ACTIVE_PAPER' and attempt['status'].startswith('UNKNOWN')
        blocked=dict(status=result['status'],reason=result['reason'],attempt_date=attempt['date'],attempt_status=attempt['status'],
            recorded_utc=attempt_wrapper['finished_utc'],root_receipt=accepted['root_receipt'],root_receipt_sha256=accepted['root_receipt_sha256'])
        result=before
    if result['status']!='ACTIVE_PAPER':
        pending['status']='review_required' if result['status'].startswith('UNKNOWN') else 'not_activated'
        pending['note']='SGOV固定纸面状态待复核；不展示前向收益。' if pending['status']=='review_required' else 'SGOV纸面程序已验收，尚未创建真实起点；不展示前向收益。'
        return pending
    assert blocked or run.returncode==0
    policy=read(packet/'POLICY-v1.json');arms={a['id']:a for a in policy['arms']}
    assert {a['capital_hkd'] for a in arms.values()}=={20000,30000} and len(arms)==4
    accounts=[]
    for key,s in result['summaries'].items():
        arm=arms[key]
        assert s['actual_orders']==0 and not s['actual_broker_fill'] and not s['stable_income_proven']
        accounts.append(dict(id=key,capital_hkd=arm['capital_hkd'],cost=arm['cost'],status=s['status'],
            nav_hkd=float(s['scenario_nav_hkd']) if s['scenario_nav_hkd'] is not None else None,
            change_hkd=float(s['scenario_net_hkd']) if s['scenario_net_hkd'] is not None else None,
            quantity=s['shares'],observations=s['observations'],last_observation=s['last_observation']))
    assert len(accounts)==4 and set(arms)==set(result['summaries'])
    assumptions=(f"固定USD/HKD {policy['fixed_usdhkd']}；基础／压力的每个方向换汇成本"
                 f"{policy['base']['fx_bps_each_way']}／{policy['pressure']['fx_bps_each_way']}bp，"
                 f"预扣税{float(policy['withholding_scenario'])*100:g}%及每次分派"
                 f"{policy['base']['distribution_service_reserve_usd']}／{policy['pressure']['distribution_service_reserve_usd']}美元服务费储备均为情景；发行人付款日不等于券商到账日。")
    projected=dict(activated=True,status='active_paper',packet_version='v140',activation_utc=result['activation_utc'],
                first_session=result['first_session'],source_quote_through=result['source_quote_through'],
                checked_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),accounts=accounts,orders_sent=0,
                note='SGOV四个独立条件纸面：2万／3万各基础及压力。保持独立T0，不倒填历史。'+
                     ('尚未观察新会话，没有证券成交。' if not any(a['observations'] for a in accounts) else '')+
                     '起点建模美元钱包即计双向换汇估值成本，0证券成交也可呈负增减；这不是实际亏损。'+assumptions)
    if blocked:
        for account in projected['accounts']:
            account['last_successful']=dict(nav_hkd=account['nav_hkd'],change_hkd=account['change_hkd'],quantity=account['quantity'],observation=account['last_observation'])
            account.update(status='UNKNOWN',nav_hkd=None,change_hkd=None,quantity=None)
        projected.update(status='review_required',valuation_current=False,latest_attempt=blocked,
            note=f"SGOV本次{blocked['attempt_date']}接续因旧报价修订而冻结，当前完整估值未知。原T0保留；最近成功旧估值单列，不能当作本次行情或新增收益。"+assumptions)
    return projected


def accepted_downside_review():
    path=MINING/'acceptance/DOWNSIDE-v164-ROOT-REVIEW-v1.json'
    if not path.exists():return None
    review=read(path)
    assert review['decision']=='ACCEPT_FIXED_TRAINING_REJECTION_NOT_GLOBAL_MECHANISM_FAILURE'
    assert review['independent_reproduction_passed'] and review['actual_signal_trials']==1 and review['actual_horizon_trials']==2
    base=ROOT/'reports/us-downside-risk-validation-owner-20261118-v164'
    assert review['result_sha256']==digest(base/'RESULT-v1.json') and review['protocol_sha256']==digest(base/'PROTOCOL-v1.json')
    result=read(base/'RESULT-v1.json')
    assert result['validation_or_test_opened'] is False and result['net_account_profit'] is None
    assert all(not r['decision']['pass_training_diagnostic'] for r in result['training'].values())
    return review


def accepted_diversified_forward():
    path=MINING/'acceptance/DIVERSIFIED-FORWARD-v157-v160-ROOT-REVIEW-v1.json'
    if not path.exists():return None
    result=read(path)
    assert result['decision']=='ACCEPT_CONDITIONAL_FORWARD_IMPLEMENTATION_NOT_PROFITABILITY'
    assert result['stable_profitability_proven'] is False and result['new_paper_t0_created'] is False
    assert result['independent_source_integration_passed'] is True
    return result


def accepted_continuation_review(filename, decision):
    path=MINING/'acceptance'/filename
    if not path.exists():return None
    review=read(path)
    assert review['decision']==decision and review['goal_status']=='ACTIVE'
    assert review['stable_profitability_proven'] is False
    assert not review.get('TEST_ONLY') and isinstance(review.get('pins'),dict) and review['pins']
    for relative,expected in review['pins'].items():
        source=(ROOT/relative).resolve()
        assert source.is_relative_to(ROOT.resolve()) and source.is_file(),relative
        assert isinstance(expected,str) and re.fullmatch('[0-9a-f]{64}',expected),relative
        assert digest(source)==expected,relative
    return review


def accepted_intermediate_review():
    """No author RESULT fallback: a new signal exists here only after root acceptance."""
    review=accepted_continuation_review('INTERMEDIATE-v177-ROOT-REVIEW-v1.json',
        'ACCEPT_FIXED_TRAINING_REJECTION_NOT_GLOBAL_MECHANISM_FAILURE')
    if not review:return None
    assert review['actual_unique_signal_trials']==1 and review['actual_horizon_trials']==2
    factor=review['site_factor']
    assert factor['status']=='rejected' and factor['horizons']==[20,60]
    assert factor['account_net_hkd'] is None and factor['account_max_drawdown_pct'] is None
    assert len(factor['diagnostics'])==2 and {d['horizon'] for d in factor['diagnostics']}=={20,60}
    return review


def accepted_amihud_review():
    """Only the root-reviewed projection can add this signal; never parse author RESULT."""
    review=accepted_continuation_review('AMIHUD-v186-ROOT-REVIEW-v1.json',
        'ACCEPT_FIXED_TRAINING_REJECTION_NOT_GLOBAL_MECHANISM_FAILURE')
    if not review:return None
    assert not review.get('TEST_ONLY') and review['independent_reproduction_passed'] is True
    assert review['actual_unique_signal_trials']==1 and review['actual_horizon_trials']==2
    factor=review['site_factor']
    assert not factor.get('TEST_ONLY') and factor['id']=='us_amihud_gross_illiquidity_252'
    assert factor['status']=='rejected' and factor['horizons']==[20,60]
    assert factor['account_net_hkd'] is None and factor['account_max_drawdown_pct'] is None
    assert len(factor['diagnostics'])==2 and {d['horizon'] for d in factor['diagnostics']}=={20,60}
    return review


def accepted_peer_delay_review():
    review=accepted_continuation_review('PEER-DELAY-v204-v207-ROOT-REVIEW-v1.json',
        'ACCEPT_FIXED_TRAINING_REJECTION_NOT_GLOBAL_MECHANISM_FAILURE')
    if not review:return None
    assert review['independent_reproduction_passed'] is True and review['root_executed_verify'] is True
    assert review['actual_unique_signal_trials']==1 and review['actual_horizon_trials']==2
    factor=review['site_factor']
    assert not factor.get('TEST_ONLY') and factor['status']=='rejected' and factor['horizons']==[20,60]
    assert factor['account_net_hkd'] is None and factor['account_max_drawdown_pct'] is None
    assert len(factor['diagnostics'])==2 and {d['horizon'] for d in factor['diagnostics']}=={20,60}
    return review


def latest_paper_receipt_path():
    """Select only root-owned dated continuation receipts, never an author journal result."""
    candidates=set(MINING.glob('paper-*/ROOT-CONTINUATION-v*.json'))
    if DIVERSIFIED_RECEIPT.exists():candidates.add(DIVERSIFIED_RECEIPT)
    dated=[]
    for path in candidates:
        review=read(path)
        assert review.get('decision')=='ACCEPT_ACTUAL_PAPER_CONTINUATION_NOT_PROFITABILITY' and not review.get('TEST_ONLY'),path
        accepted=datetime.fromisoformat(review['actual_acceptance_utc'].replace('Z','+00:00'))
        assert accepted.utcoffset() is not None,path
        dated.append((accepted,path))
    return max(dated,key=lambda row:(row[0],row[1].as_posix()))[1] if dated else DIVERSIFIED_RECEIPT


def diversified_paper_status():
    """Project only the root-accepted actual journal; never initialize an account."""
    arms=[dict(id=f'HKD{capital}_{cost}_{policy}',capital_hkd=capital,cost=cost,policy=policy,
               nav_hkd=None,net_hkd=None,settled_cash_usd=None,
               shares={ticker:None for ticker in ['US.SGOV','US.VTI','US.GLD']},status='NOT_ACTIVATED')
          for capital in [20000,30000] for cost in ['base','pressure'] for policy in ['annual','once']]
    receipt=latest_paper_receipt_path()
    if not receipt.exists():
        return dict(activated=False,status='NOT_ACTIVATED',status_label='尚未激活 · 无新T0',
            activation_utc=None,first_session=None,last_observation=None,observations=None,
            security_trades=None,actual_orders=0,source_through=None,
            intent=dict(date=None,timely=None,completed_utc=None),arms=arms,
            note='仅预留8个相关情景。尚无root接受的实际接续回执，未创建新钱包、起点、观察或净值；年度再平衡与一次持有并列。')
    review=read(receipt)
    if review.get('TEST_ONLY') or review.get('decision')!='ACCEPT_ACTUAL_PAPER_CONTINUATION_NOT_PROFITABILITY' or \
       review.get('goal_status')!='ACTIVE' or review.get('stable_profitability_proven') is not False:
        raise ValueError('Actual diversified continuation receipt is not accepted; no empty-account fallback.')
    accepted=datetime.fromisoformat(review['actual_acceptance_utc'].replace('Z','+00:00'))
    if accepted.utcoffset() is None:raise ValueError('Continuation acceptance must have an explicit timezone.')
    pins=review.get('pins')
    if not isinstance(pins,dict) or not pins:raise ValueError('Actual continuation has no pinned journal inputs.')
    for relative,expected in pins.items():
        path=ROOT/relative
        if Path(relative).is_absolute() or not path.resolve().is_relative_to(ROOT.resolve()) or \
           not isinstance(expected,str) or not re.fullmatch('[0-9a-f]{64}',expected) or digest(path)!=expected:
            raise ValueError(f'Actual continuation pin mismatch: {relative}')
    paper=review['site_diversified_paper']
    validate_diversified_projection(paper)
    if paper.get('TEST_ONLY') or paper['activated'] is not True:
        raise ValueError('An actual continuation receipt must project an activated, non-test account.')
    original=read(DIVERSIFIED_RECEIPT)['site_diversified_paper']
    for key in ['activation_utc','first_session']:assert paper[key]==original[key],key
    assert paper['observations']>=original['observations']
    identity=lambda p:sorted((a['id'],a['capital_hkd'],a['cost'],a['policy']) for a in p['arms'])
    assert identity(paper)==identity(original),'Continuation cannot reset original capital or arm identities'
    return {**paper,'root_acceptance_utc':review['actual_acceptance_utc'],
            'root_receipt':receipt.relative_to(ROOT).as_posix(),
            'root_receipt_sha256':digest(receipt)}


def validate_diversified_projection(paper):
    """Validate published facts and exact strings; do not calculate financial amounts."""
    def date(value,required=False):
        if value is None and not required:return
        if not isinstance(value,str):raise ValueError('Invalid diversified paper date.')
        datetime.fromisoformat(value.replace('Z','+00:00'))
    def amount(value):
        return value is None or isinstance(value,str) and re.fullmatch(r'-?(?:0|[1-9]\d*)\.\d{2}',value) is not None
    if not isinstance(paper,dict) or type(paper.get('activated')) is not bool or paper.get('actual_orders')!=0:
        raise ValueError('Invalid diversified activation/order status.')
    if not all(isinstance(paper.get(k),str) and paper[k] for k in ['status','status_label','note']):
        raise ValueError('Diversified status and explanation are required.')
    expected={(f'HKD{capital}_{cost}_{policy}',capital,cost,policy)
              for capital in [20000,30000] for cost in ['base','pressure'] for policy in ['annual','once']}
    arms=paper.get('arms')
    if not isinstance(arms,list) or len(arms)!=8 or \
       {(a.get('id'),a.get('capital_hkd'),a.get('cost'),a.get('policy')) for a in arms}!=expected:
        raise ValueError('Diversified paper must keep the eight registered related scenarios.')
    intent=paper.get('intent')
    if not isinstance(intent,dict) or not all(k in intent for k in ['date','timely','completed_utc']):
        raise ValueError('Missing diversified intent facts.')
    for arm in arms:
        if not all(amount(arm.get(k)) for k in ['nav_hkd','net_hkd','settled_cash_usd']):
            raise ValueError('Diversified amounts must be exact two-decimal strings or null.')
        shares=arm.get('shares')
        if not isinstance(shares,dict) or set(shares)!= {'US.SGOV','US.VTI','US.GLD'} or \
           not all(q is None or type(q) is int and 0<=q<=9007199254740991 for q in shares.values()):
            raise ValueError('Diversified share quantities must be explicit integers or null.')
        if paper['activated']:
            if arm.get('status') not in ['ACTIVE','MISSED','UNKNOWN']:
                raise ValueError('Invalid actual diversified arm state.')
            if arm['status']=='UNKNOWN' and any(arm.get(k) is not None for k in ['nav_hkd','net_hkd']):
                raise ValueError('Unknown arms cannot project complete profit.')
        elif arm.get('status')!='NOT_ACTIVATED' or any(arm.get(k) is not None for k in ['nav_hkd','net_hkd','settled_cash_usd']) or any(q is not None for q in shares.values()):
            raise ValueError('Unactivated slots cannot contain financial observations.')
    for key in ['activation_utc','first_session','last_observation','source_through']:
        date(paper.get(key),paper['activated'] and key in ['activation_utc','first_session','source_through'])
    for key in ['observations','security_trades']:
        value=paper.get(key)
        if paper['activated'] and not (type(value) is int and 0<=value<=9007199254740991):
            raise ValueError('Invalid actual diversified observation/trade count.')
    date(intent['date']);date(intent['completed_utc'])
    if intent['timely'] is not None and type(intent['timely']) is not bool:raise ValueError('Invalid timely-intent fact.')
    if not paper['activated'] and (any(paper.get(k) is not None for k in ['activation_utc','first_session','last_observation','source_through','observations','security_trades']) or any(v is not None for v in intent.values())):
        raise ValueError('Unactivated paper must not invent an origin or observation.')
    if paper['activated'] and paper['observations']>0 and paper.get('last_observation') is None:
        raise ValueError('Observed diversified paper requires its actual observation date.')
    return paper


def project_hk_cash_addendum(evidence,current_work,registry):
    review=accepted_continuation_review('HK-CASH-v176-ROOT-REVIEW-v1.json',
        'ACCEPT_2024_NIL_ORDINARY_DISTRIBUTION_ADDENDUM_ONLY')
    if not review:return
    assert review['full_window_upgraded'] is False and review['old_nulls_modified'] is False
    assert review['old_2024_2025_model_and_results_modified'] is False
    summary='03152发行人年报明确支持所覆盖2024年港币ETF无普通股东分派，仅局部补强原2024现金基准的零普通分派条件。'
    limits='2025普通分派完整性、全期整手与价位连续性、非普通行动和个人费用／成交／到账仍未获补齐；旧收益及旧空值不改。'
    evidence['hk_cash_2024']=dict(status='accepted_2024_nil_ordinary_addendum_only',
        accepted_at_utc=review['actual_acceptance_utc'],summary=summary,limitation=limits,
        full_window_upgraded=False,existing_model_amounts_changed=False,new_strategy_trials=0)
    for owner in current_work['owners']:
        if owner['name']=='港币现金资料核查':owner.update(task=summary+' '+limits,status='snapshot')
    registry.append(dict(id='hk-cash-source-v176',version='V176 · 2024局部来源补强',name='03152 · 2024零普通分派年报依据',
        category='recent',record_type='source_qualification_addendum',conclusion=summary+' '+limits,
        source_date='2026-11-18',source='root接受与逐页目视核对；不新增回测、纸面T0或盈利策略'))


def project_hk_usd_cash_source(evidence,current_work,registry):
    review=accepted_continuation_review('HK-USD-CASH-v183-v184-ROOT-REVIEW-v1.json',
        'ACCEPT_DATED_KFS_AND_CURRENT_METADATA_ONLY_NOT_PROFITABILITY')
    if not review:return None
    assert review['candidate']=='HK.03196' and not review.get('TEST_ONLY')
    assert review['new_factor_trials']==review['new_horizon_trials']==review['new_account_return_trials']==0
    assert review['new_T0'] is False and review['actual_orders']==0 and review['old_results_modified'] is False
    assert review['resolved']['distribution_currency']=='USD only'
    receipt=read(ROOT/'reports/hk-usd-cash-wrapper-terms-owner-20261118-v183/G01-RECEIPT.json')
    assert receipt['url'].startswith('https://www.bosera.com.hk/api/infobase/downloadattfile.do?attachmentId=')
    limits='2025全年分派仍未知，当前KFS不是全年现金证明或个人税费认证；后续招募书未完整核阅。休市快照最新价时间为11月17日09:01，成交量0、卖一仅1份且无独立盘口时间，不能证明此刻可成交或3份深度。当前0.05报价档距不是5.55买卖差，也不认证全史价位。大中华银行／企业信用与USD风险保留。'
    fee_note='KFS的0.27%持续收费比率依据2025全年费用；网页0.55%估算分开保留。基金费用已反映NAV，不相加或重扣；没有新增净收益核算。'
    evidence['hk_usd_cash_wrapper']=dict(status='accepted_dated_kfs_current_metadata_only',ticker='HK.03196',
        accepted_at_utc=review['actual_acceptance_utc'],summary=review['site_summary'],
        source_document_date='April 2026',source_url=receipt['url'],note=fee_note,limitation=limits,
        distribution_currency='USD',regular_distribution_guaranteed=False,distribution_2025_certified=False,
        executable_depth_certified=False,existing_model_amounts_changed=False,
        new_factor_trials=0,new_horizon_trials=0,new_account_return_trials=0,new_paper_t0=False)
    current_work['owners'].append(dict(name='03196来源补证',status='snapshot',task=review['site_summary']+' '+limits))
    registry.append(dict(id='hk-usd-cash-source-v183-v184',version='V183–V184 · 当前条款与元数据',
        name='03196 · 上市类KFS与当前报价来源',category='recent',record_type='source_qualification_addendum',
        conclusion=review['site_summary']+' '+fee_note+' '+limits,source_date='2026-11-18',
        source='root接受的发行人KFS与单次公开快照；不是新因子、经济试验、成交或盈利'))
    return review


def project_hk_usd_activity(evidence,current_work,registry):
    review=accepted_continuation_review('HK-USD-ACTIVITY-v190-v191-ROOT-REVIEW-v1.json',
        'ACCEPT_SOURCE_FACTS_FIXED_DATE_EXECUTION_PRESCREEN_NOT_PASSED')
    if not review:return None
    assert review['candidate']=='HK.03196' and review['new_account_return_trials']==0
    assert review['new_factor_trials']==review['new_horizon_trials']==0 and review['new_T0'] is False
    facts=review['activity']
    assert facts['year_sessions']==246 and facts['positive_volume_sessions']==21 and facts['zero_volume_sessions']==225
    assert facts['fixed_entry_volume']==facts['fixed_exit_volume']==0
    evidence['hk_usd_activity']=dict(status='accepted_fixed_date_execution_prescreen_not_passed',
        ticker='HK.03196',year=2024,accepted_at_utc=review['actual_acceptance_utc'],
        **facts,summary=review['site_summary'],limitation=review['site_limitation'],
        net_profit_hkd=None,new_account_return_trials=0,new_factor_trials=0,new_horizon_trials=0,
        new_paper_t0=False,opening_depth_certified=False,whole_fund_invalid=False,
        distribution_2025_certified=False,existing_model_amounts_changed=False)
    current_work['owners'].append(dict(name='03196执行预筛',status='snapshot',task=review['site_summary']))
    registry.append(dict(id='hk-usd-activity-v190-v191',version='V190–V191 · 固定日期执行预筛',
        name='03196 · 2024成交记录与零量买卖日',category='recent',record_type='source_qualification_addendum',
        conclusion=review['site_summary']+' '+review['site_limitation'],source_date='2026-11-18',
        source='公开原始日K、独立复核及root验收；0收益试验，不顺延买卖日'))
    return review


def project_tip_source_work(current_work):
    review=accepted_continuation_review('TIP-PREP-v192-ROOT-REVIEW-v1.json',
        'ACCEPT_STRUCTURE_PREPARATION_SELECT_TIP_SOURCE_ONLY')
    if not review:return None
    team=read(MINING/'TEAM.json')
    active=any(o['status']=='ACTIVE' and any('us-tip-' in p for p in o['write_paths']) for o in team['owners'])
    current_work['owners'].append(dict(name='下一机制：TIP',status='active' if active else 'snapshot',
        task=('正在分别核对发行人分派与公开历史行情。' if active else '来源核查已交回，等待主会话接受并冻结账户协议。')+
             '固定2015—2019窗口，研究通胀挂钩国债及实际利率风险；尚未计算收益或新增纸面起点，不增加因子试验数。'))
    return review


def tip_accepted_file(review,key):
    ref=review[key];path=(ROOT/ref['path']).resolve()
    assert path.is_relative_to(ROOT.resolve()) and path.is_file(),key
    assert re.fullmatch('[0-9a-f]{64}',ref['sha256']) and digest(path)==ref['sha256'],key
    if ref['path'] in review['pins']:assert review['pins'][ref['path']]==ref['sha256'],key
    return path


def project_tip_history(current_work,cards,registry,evidence):
    """Only root-accepted originals supply money; missing acceptance never reads author results."""
    source=accepted_continuation_review('TIP-SOURCE-v193-v195-ROOT-REVIEW-v1.json',
        'ACCEPT_ISSUER_PRIMARY_CONDITIONAL_HISTORY_INPUTS_NOT_STRICT_BUNDLE_UPGRADE')
    account=accepted_continuation_review('TIP-ACCOUNT-v196-v197-ROOT-REVIEW-v1.json',
        'ACCEPT_FIXED_TIP_A_CONDITIONAL_HISTORY_NOT_STABILITY')
    if source:
        registry.append(dict(id='tip-source-v193-v195',version='V193–V195 · TIP源资格',name='TIP · 原价与发行人现金独立核对',
            category='recent',record_type='conditional_source_qualification',source_date=source['actual_acceptance_utc'][:10],
            conclusion='2014年12月至2019年原价／行动与发行人分派已独立核对；2015—2019有37正额／23明确零额日期。主窗正额严格比较均过原0.00001USD独占阈值，但只有6个字面完全相等，差异保留。当前归档、日历代理与真实到账限制仍在；源接受不证明盈利。',
            source='root源接受及原件pins；不是新增因子、收益账户、实际成交或到账'))
    if not account:
        for owner in current_work['owners']:
            if owner['name']=='下一机制：TIP':owner.update(status='snapshot',task='TIP固定A段源已接受；账户独立审计及root接受未完成，不展示作者收益或曲线。B仅来源准备，不是已检验后段。')
        return dict(status='awaiting_root_account_acceptance',chart=None,cases=[],primary_net_W_hkd=None,
            new_factor_trials=0,new_horizon_trials=0,new_paper_T0=False,B_computed=False),source,None
    assert source is not None,'TIP money needs accepted source too'
    result=read(tip_accepted_file(account,'result'));tip_accepted_file(account,'primary_daily')
    assert result['symbol']=='US.TIP' and result['strategy_count']==1 and result['related_scenarios']==12
    assert result['stable_profitability_proven'] is False and result['new_T0'] is False and result['goal_status']=='ACTIVE'
    assert result['new_factor_trials']==0 and len(result['cases'])==12
    from decimal import Decimal as D
    expected={(s,c,k) for s in ['issuer','quote_diagnostic'] for c in [10000,20000,30000] for k in ['base','pressure']}
    assert {(c['amount_source'],c['capital_hkd'],c['cost']) for c in result['cases']}==expected
    cases=[]
    def literal(value):
        assert isinstance(value,str) and re.fullmatch(r'-?(?:0|[1-9]\d*)\.\d{2}',value)
        return value
    for c in result['cases']:
        t=c['terminal'];capital=c['capital_hkd']
        assert D(t['B_hkd'])-D(t['W_hkd'])==D(t['K_hkd'])
        assert D(t['W_hkd'])-capital==D(c['net_W_hkd']) and D(t['B_hkd'])-capital==D(c['net_B_hkd'])
        assert t['is_actual_exit'] is t['is_withdrawable_income'] is False
        assert c['months']==60 and c['years']==5 and c['positive_entitled_gross_events']==c['positive_service_reserve_events']==37
        assert D(c['risk']['conservative_quote_high_low_DD_pct']).is_finite()
        if c['amount_source']=='issuer':
            cases.append(dict(capital_hkd=capital,cost=c['cost'],net_W_hkd=literal(c['net_W_hkd']),net_B_hkd=literal(c['net_B_hkd']),
                B_hkd=literal(t['B_hkd']),W_hkd=literal(t['W_hkd']),K_hkd=literal(t['K_hkd']),
                risk_pct=float(c['risk']['conservative_quote_high_low_DD_pct']),negative_months=c['negative_months'],months=60,
                negative_years=c['negative_years'],years=5,quantity=c['entry']['quantity'],
                net_distributions_usd=literal(c['attribution']['cumulative_rights']['net_usd'])))
    main=next(c for c in result['cases'] if c['amount_source']=='issuer' and c['capital_hkd']==30000 and c['cost']=='pressure')
    yearly=main['periods']['yearly'];assert [y['period'] for y in yearly]==['2015','2016','2017','2018','2019']
    for y in yearly:literal(y['B_change_hkd'])
    cases.sort(key=lambda c:(c['capital_hkd'],c['cost']))
    small=next(c for c in cases if c['capital_hkd']==10000 and c['cost']=='pressure')
    concentration_formula='全期净W − 最佳年度B账面增量'
    assert D(main['net_W_hkd'])-max(D(y['B_change_hkd']) for y in yearly)==D(main['concentration']['arithmetic_W_without_best_year_hkd'])
    history=dict(status='accepted_conditional_A',claim_level='CONDITIONAL_HISTORICAL_MODEL',period='2015—2019 · 累计五年',
        accepted_at_utc=account['actual_acceptance_utc'],receipt_sha256=digest(MINING/'acceptance/TIP-ACCOUNT-v196-v197-ROOT-REVIEW-v1.json'),
        primary_capital_hkd=30000,primary_cost='pressure',primary_net_W_hkd=literal(main['net_W_hkd']),
        primary_B_hkd=literal(main['terminal']['B_hkd']),primary_W_hkd=literal(main['terminal']['W_hkd']),
        primary_K_hkd=literal(main['terminal']['K_hkd']),cases=cases,yearly_B_changes=yearly,
        chart='assets/tip-history-A-v1.png',nav_points=1258,source_amount_scenarios=2,related_scenarios=12,
        actual_income_certified=False,stable_profitability_proven=False,new_paper_T0=False,new_factor_trials=0,new_horizon_trials=0,
        B_computed=False,B_status='来源准备／源资格接续，尚未经济检验',
        concentration_without_best_year_W_hkd=literal(main['concentration']['arithmetic_W_without_best_year_hkd']),
        concentration_formula=concentration_formula,
        note='固定一次买入持有、90%事前预算；表内是原本金上累计五年的模型净W，非年收益、已实现卖出或实际提现。保留初始FX、税费及增量退出储备。',
        limitations=f"2015与2018为亏损年，主3万压力{main['negative_months']}／60负月。1万压力累计分派净现金{small['net_distributions_usd']}USD；整体净W为正不等于稳定派息。2019贡献集中，{concentration_formula}仅为算术诊断，不是删除该年后的替代回测。单源报价／日历代理、当前发行人归档、真实成交及个人税费／到账未知，报价DD不是未来损失上限。",
        source_note='两路金额情景在本批模型分币结果相同，不等于原字面金额全相等；零额Quote0为发行人明确零额的诊断惯例。TIP不是新增IC因子，B段尚未检验，三套纸面原T0不变。')
    selected=lambda k:next(c for c in cases if c['capital_hkd']==30000 and c['cost']==k)
    cards.insert(0,dict(id='us-tip-history-A',name='TIP · 通胀挂钩国债一次持有',status='review',status_label='A段条件历史已接受；后段未检验',
        capital_hkd=30000,period='2015-01-02 — 2019-12-31 · 累计五年',basis='原90%预算、整股、30%税情景／USD1或2正额储备及原费用FX；W另扣增量假设退出成本。',
        results=[dict(cost=k,net_hkd=float(selected(k)['net_W_hkd']),risk_pct=selected(k)['risk_pct'],cagr_pct=None) for k in ['base','pressure']],
        conclusion=f"主3万压力累计模型净W{D(main['net_W_hkd']):+,.2f}港币、报价DD约{selected('pressure')['risk_pct']:.2f}%；{main['negative_years']}亏损年、{main['negative_months']}负月。1万压力仅{D(small['net_W_hkd']):+,.2f}港币，累计分派净现金{small['net_distributions_usd']}USD。不是稳定收入或已提现利润。",
        next='保留A段原式与限制；B段仅准备，未经经济检验。不调费率、窗口或暴露救结果，不新增纸面T0或IC因子。'))
    registry.append(dict(id='tip-history-v196-v197',version='V196–V197 · TIP A段条件历史',name='TIP · 固定2015—2019一次持有净账户',
        category='recent',record_type='conditional_economic_account',source_date=account['actual_acceptance_utc'][:10],
        conclusion=cards[0]['conclusion']+f" 2019年度B变化{D(yearly[-1]['B_change_hkd']):+,.2f}；{concentration_formula}={history['concentration_without_best_year_W_hkd']}港币，仅为算术诊断，不是另一次回测。"+cards[0]['next'],
        source='root接受绑定的作者结果、1258日主账与独立审计；12相关情景不作独立策略样本'))
    for owner in current_work['owners']:
        if owner['name']=='下一机制：TIP':owner.update(status='snapshot',task=f"TIP A段条件历史已独立核对并由root接受，主3万压力五年累计净W{D(main['net_W_hkd']):+,.2f}港币。B段仅来源接续准备，尚未经济检验；稳定盈利未证，0新T0。")
    return history,source,account


def render_tip_history_chart(review):
    """Plot accepted stored B/annual contributions only; never recompute a financial path."""
    import csv
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    result=read(tip_accepted_file(review,'result'))
    main=next(c for c in result['cases'] if c['amount_source']=='issuer' and c['capital_hkd']==30000 and c['cost']=='pressure')
    daily_path=tip_accepted_file(review,'primary_daily')
    with daily_path.open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
    assert len(rows)==1258 and rows[0]['session']=='2015-01-02' and rows[-1]['session']=='2019-12-31'
    dates=[datetime.strptime(r['session'],'%Y-%m-%d') for r in rows];values=[float(r['B_close_hkd']) for r in rows]
    assert all(math.isfinite(v) for v in values)
    yearly=main['periods']['yearly'];changes=[float(y['B_change_hkd']) for y in yearly]
    with plt.rc_context({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False}):
        fig,(ax,annual)=plt.subplots(2,1,figsize=(12.5,7.6),gridspec_kw={'height_ratios':[2,1]},layout='constrained')
        fig.suptitle('TIP | 2015-2019 conditional history | HKD 30,000 pressure',fontsize=14)
        ax.plot(dates,values,color='#176d75',linewidth=1.8,label='Stored close marked wealth B')
        ax.axhline(30000,color='#9e6d28',linestyle='--',linewidth=1,label='Original HKD principal')
        ax.set_ylabel('B wealth (HKD)');ax.legend(loc='upper left',frameon=False)
        ax.xaxis.set_major_locator(mdates.YearLocator());ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'));ax.grid(alpha=.2)
        annual.bar([y['period'] for y in yearly],changes,color=['#aa4e4b' if x<0 else '#176d75' for x in changes],width=.58)
        annual.axhline(0,color='#647480',linewidth=.8);annual.set_ylabel('Annual change in B (HKD)')
        for i,value in enumerate(changes):annual.annotate(f'{value:+,.2f}',(i,value),xytext=(0,-14 if value<0 else 5),textcoords='offset points',ha='center',fontsize=9)
        annual.margins(y=.25);annual.grid(axis='y',alpha=.15)
        fig.supxlabel('Five-year cumulative model evidence. B is marked wealth; W reserves exit cost. Neither is actual withdrawal.',fontsize=10)
        path=OUT/'assets/tip-history-A-v1.png';path.parent.mkdir(parents=True,exist_ok=True)
        fig.savefig(path,dpi=150,metadata={'Software':'Accepted stored TIP B and annual B view; no account recalculation'});plt.close(fig)
    assert digest(daily_path)==review['primary_daily']['sha256']
    return path


def project_tip_continuation(current_work,cards,registry):
    """Project the separate B account only through root-bound source/account receipts."""
    source=accepted_continuation_review('TIP-B-SOURCE-v198-v200-ROOT-REVIEW-v1.json',
        'ACCEPT_ISSUER_PRIMARY_CONDITIONAL_HISTORY_INPUTS_NOT_STRICT_BUNDLE_UPGRADE')
    account=accepted_continuation_review('TIP-B-ACCOUNT-v201-v202-ROOT-REVIEW-v1.json',
        'ACCEPT_FIXED_TIP_B_REJECTION_NOT_STABILITY')
    if source:
        registry.append(dict(id='tip-B-source-v198-v200',version='V198–V200 · TIP B源资格',name='TIP · 2020—2024原价与发行人现金独立核对',
            category='recent',record_type='conditional_source_qualification',source_date=source['actual_acceptance_utc'][:10],
            conclusion='B后段1258个实际日期及46正额／14明确零额发行人日期已独立核对并接受。仍是条件历史来源，保留当前归档、单源价格、日历代理和个人到账限制；源资格不证明收益。',
            source='root B源接受及原件pins；相关账户情景，不是新增IC因子或期限'))
    if not account:
        return dict(status='awaiting_root_account_acceptance',chart=None,cases=[],primary_net_W_hkd=None,
            new_factor_trials=0,new_horizon_trials=0,new_paper_T0=False),source,None
    assert source is not None and account['primary_original_screen_met'] is False
    for key in ['result','primary_daily']:
        ref=account[key];assert account['pins'].get(ref['path'])==ref['sha256'],key
    result=read(tip_accepted_file(account,'result'));tip_accepted_file(account,'primary_daily')
    assert result['symbol']=='US.TIP' and result['strategy_count']==1 and result['related_scenarios']==12
    assert result['stable_profitability_proven'] is False and result['new_T0'] is False and result['goal_status']=='ACTIVE'
    assert result['new_factor_trials']==0 and result['primary']['original_screen_met'] is False
    expected={(s,c,k) for s in ['issuer','quote_diagnostic'] for c in [10000,20000,30000] for k in ['base','pressure']}
    assert len(result['cases'])==12 and {(c['amount_source'],c['capital_hkd'],c['cost']) for c in result['cases']}==expected
    from decimal import Decimal as D
    def literal(value):
        assert isinstance(value,str) and re.fullmatch(r'-?(?:0|[1-9]\d*)\.\d{2}',value)
        return value
    cases=[]
    for c in result['cases']:
        t=c['terminal'];capital=c['capital_hkd']
        assert D(t['B_hkd'])-D(t['W_hkd'])==D(t['K_hkd'])
        assert D(t['W_hkd'])-capital==D(c['net_W_hkd']) and D(t['B_hkd'])-capital==D(c['net_B_hkd'])
        assert t['is_actual_exit'] is t['is_withdrawable_income'] is False
        assert c['months']==60 and c['years']==5 and c['positive_entitled_gross_events']==c['positive_service_reserve_events']==46
        if c['amount_source']=='issuer':
            cases.append(dict(capital_hkd=capital,cost=c['cost'],net_W_hkd=literal(c['net_W_hkd']),net_B_hkd=literal(c['net_B_hkd']),
                B_hkd=literal(t['B_hkd']),W_hkd=literal(t['W_hkd']),K_hkd=literal(t['K_hkd']),
                risk_pct=float(c['risk']['conservative_quote_high_low_DD_pct']),negative_months=c['negative_months'],months=60,
                negative_years=c['negative_years'],years=5,quantity=c['entry']['quantity'],
                net_distributions_usd=literal(c['attribution']['cumulative_rights']['net_usd'])))
    cases.sort(key=lambda c:(c['capital_hkd'],c['cost']))
    main=next(c for c in result['cases'] if c['amount_source']=='issuer' and c['capital_hkd']==30000 and c['cost']=='pressure')
    yearly=main['periods']['yearly'];assert [y['period'] for y in yearly]==['2020','2021','2022','2023','2024']
    for y in yearly:literal(y['B_change_hkd'])
    selected=lambda k:next(c for c in cases if c['capital_hkd']==30000 and c['cost']==k)
    primary=selected('pressure')
    conclusion=(f"B固定后段未通过原筛选：主3万压力累计五年模型净W{D(primary['net_W_hkd']):+,.2f}港币，"
        f"报价回撤约{primary['risk_pct']:.2f}%，{primary['negative_years']}／5亏损年、{primary['negative_months']}／60负月。"
        '本结论只针对2020—2024固定日期、一次持有规则及原成本版本，不代表TIP基金在所有情景下无效。')
    history=dict(status='accepted_rejected_B',claim_level='CONDITIONAL_HISTORICAL_MODEL',period='2020—2024 · 累计五年',
        accepted_at_utc=account['actual_acceptance_utc'],receipt_sha256=digest(MINING/'acceptance/TIP-B-ACCOUNT-v201-v202-ROOT-REVIEW-v1.json'),
        primary_capital_hkd=30000,primary_cost='pressure',primary_net_W_hkd=primary['net_W_hkd'],
        primary_B_hkd=primary['B_hkd'],primary_W_hkd=primary['W_hkd'],primary_K_hkd=primary['K_hkd'],
        primary_original_screen_met=False,cases=cases,yearly_B_changes=yearly,chart='assets/tip-history-B-v1.png',nav_points=1258,
        source_amount_scenarios=2,related_scenarios=12,actual_income_certified=False,stable_profitability_proven=False,
        new_paper_T0=False,new_factor_trials=0,new_horizon_trials=0,independent_initial_capital=True,combined_with_A=False,
        conclusion=conclusion,
        note='B为独立原本金的2020—2024累计五年相关账户情景；与A各自起账，不能相加或拼成连续账户。净W含假设退出储备，非已实现卖出、实际提现或年度收入。',
        limitations='税、费用、FX及90%事前预算均沿用原研究情景，不是个人实际已认证条件。日历与报价回撤仍是代理，发行人当前归档不证明当时可得；真实成交、个人税费及到账未知。B为按时间后续检验，不声称全新盲样本；稳定盈利仍未证实。',
        source_note='仅投影root接受绑定的原RESULT与1258行主账；曲线为原逐日B账面财富，年度柱为原B增量。12相关情景不当作12个独立策略，不增加IC因子、期限或纸面T0。')
    cards.insert(0,dict(id='us-tip-history-B',name='TIP · 2020—2024固定后段',status='closed',status_label='B段原筛选未通过',
        capital_hkd=30000,period='2020-01-02 — 2024-12-31 · 累计五年',basis='独立原本金；原90%预算、整股、税费与FX情景；净W含假设退出储备。',
        results=[dict(cost=k,net_hkd=float(selected(k)['net_W_hkd']),risk_pct=selected(k)['risk_pct'],cagr_pct=None) for k in ['base','pressure']],
        conclusion=conclusion,next='保留固定后段失败与A原结果；不拼接A/B、不调日期或成本救结果。总目标继续，三套纸面原T0与本金不变；最新观察与账面金额见纸面区。'))
    registry.append(dict(id='tip-B-history-v201-v202',version='V201–V202 · TIP B段固定检验',name='TIP · 固定2020—2024一次持有净账户',
        category='recent',record_type='conditional_economic_account',source_date=account['actual_acceptance_utc'][:10],
        conclusion=conclusion+history['note'],source='root接受绑定原结果、1258行主账和独立审计；12相关情景不作独立策略样本'))
    for owner in current_work['owners']:
        if owner['name']=='下一机制：TIP':owner.update(status='snapshot',task=conclusion+' A原结果保留；稳定盈利未证，0新T0。')
    return history,source,account


def render_tip_continuation_chart(review):
    """Use only accepted original B_close_hkd and yearly B_change_hkd, never splice A."""
    import csv
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    result=read(tip_accepted_file(review,'result'))
    main=next(c for c in result['cases'] if c['amount_source']=='issuer' and c['capital_hkd']==30000 and c['cost']=='pressure')
    daily_path=tip_accepted_file(review,'primary_daily')
    with daily_path.open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
    assert len(rows)==1258 and rows[0]['session']=='2020-01-02' and rows[-1]['session']=='2024-12-31'
    dates=[datetime.strptime(r['session'],'%Y-%m-%d') for r in rows];values=[float(r['B_close_hkd']) for r in rows]
    assert all(math.isfinite(v) for v in values)
    yearly=main['periods']['yearly'];changes=[float(y['B_change_hkd']) for y in yearly]
    with plt.rc_context({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False}):
        fig,(ax,annual)=plt.subplots(2,1,figsize=(12.5,7.6),gridspec_kw={'height_ratios':[2,1]},layout='constrained')
        fig.suptitle('TIP | 2020-2024 fixed B period: original screen failed | HKD 30,000 pressure',fontsize=13)
        ax.plot(dates,values,color='#176d75',linewidth=1.8,label='Stored close marked wealth B')
        ax.axhline(30000,color='#9e6d28',linestyle='--',linewidth=1,label='Independent original HKD principal')
        ax.set_ylabel('B wealth (HKD)');ax.legend(loc='upper right',frameon=False)
        ax.xaxis.set_major_locator(mdates.YearLocator());ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'));ax.grid(alpha=.2)
        annual.bar([y['period'] for y in yearly],changes,color=['#aa4e4b' if x<0 else '#176d75' for x in changes],width=.58)
        annual.axhline(0,color='#647480',linewidth=.8);annual.set_ylabel('Annual change in B (HKD)')
        for i,value in enumerate(changes):annual.annotate(f'{value:+,.2f}',(i,value),xytext=(0,-14 if value<0 else 5),textcoords='offset points',ha='center',fontsize=9)
        annual.margins(y=.25);annual.grid(axis='y',alpha=.15)
        fig.supxlabel('Separate B-period capital; never joined to A. W reserves exit cost. Model evidence, not actual withdrawal.',fontsize=10)
        path=OUT/'assets/tip-history-B-v1.png';path.parent.mkdir(parents=True,exist_ok=True)
        fig.savefig(path,dpi=150,metadata={'Software':'Accepted original TIP B-period wealth and annual change; no account recalculation'});plt.close(fig)
    assert digest(daily_path)==review['primary_daily']['sha256']
    return path


def project_actual_diversified_continuation(paper,evidence,current_work,registry):
    if not paper['activated']:return None
    latest='60／20／20组合已按root接受的实际接续建立原起点；年度再平衡／一次持有与2万／3万、基础／压力共8个相关情景，系统实际订单0。'
    latest+=' 当前原T0、意向与观察以组合纸面区及该次回执为准；账面增减不是已提现收益，稳定盈利尚未证实。'
    for owner in current_work['owners']:
        if owner['name'] in ['组合前向程序','组合账户研究','两套固定纸面']:
            owner.update(task=('03086与原SGOV保留各自原T0；'+latest if owner['name']=='两套固定纸面' else latest),status='snapshot')
        elif owner['name']=='分层评价验收':
            owner['task']=owner['task'].replace('尚未激活的组合8臂','已激活的组合8臂')
        elif owner['name']=='退出成本核算':
            owner['task']='只读退出成本适配已接受，原账面主列保留。组合实际接续单列原T0与账面值；尚无已验收的组合持仓退出估值／新月报，不据此宣称可兑现净利。'
    f=evidence['forward_evaluation']
    f['note']=f['note'].replace('尚未激活的组合8臂','已激活的组合8臂')
    f['note']=f['note'].replace('当前验收的真实边界仍为原8臂零仓、组合8槽未启动',
        '退出估值模块在其验收时的边界为原8臂零仓、组合8槽当时未启动')
    f['note']+=' 退出适配实施验收所述“当时未激活”属于历史时点；最新组合状态见实际接续记录。'
    f['layered_measurement'].update(planned_unactivated_arms=0,active_diversified_related_arms=8)
    registry.append(dict(id='diversified-actual-paper-v179',version='V179 · 实际日期接续',
        name='60／20／20组合 · 实际纸面已激活',category='recent',record_type='actual_paper_continuation',
        conclusion=latest,source_date=read(DIVERSIFIED_RECEIPT)['actual_acceptance_utc'][:10],
        source='root独占接受的实际journal与意向原件pins；历史程序验收的当时0T0记录保留'))
    return '总目标运行中，稳定盈利尚未证实。'+latest+' 03152的2024零普通分派仅局部补强来源，正式统计推断未启用；不增加因子或独立策略计数。'


def next_factor_progress(activity):
    """Describe actual preparation/run artifacts; an author RESULT is not root acceptance."""
    folder=ROOT/'reports/next-factor-candidate-owner-20261118-v204'
    accepted=accepted_peer_delay_review()
    if accepted:
        return dict(id='v204',state='root_accepted',active_at_snapshot=False,author_result_complete=True,
            independent_review_accepted=True,root_accepted=True,accepted_signal_increment=1,accepted_horizon_increment=2,
            task='价格延迟因子固定训练已完成独立复算并由root接受；两期限固定筛选未通过，详见因子区。只新增1个已验收信号与2个预定期限，不代表所有价格延迟机制无效。',new_account_runs=0,new_paper_T0=False)
    owners=[o for o in read(MINING/'TEAM.json')['owners'] if any('next-factor-candidate-owner-20261118-v204/' in p for p in o['write_paths'])]
    active=activity in ['preparing','checking'] and any(o['status']=='ACTIVE' for o in owners)
    started=(folder/'RUN-START-v1.json').exists()
    complete=(folder/'RESULT-v1.json').exists() and (folder/'OUTPUT-MANIFEST-v1.json').exists()
    if complete:
        state='author_complete_pending_review'
        text='下一因子固定训练已产生作者结果；独立复核与root接受状态待确认，不展示未接受指标，不增加已验收信号或期限。'
    elif started:
        state='running_unaccepted' if active else 'incomplete_unaccepted'
        text=('下一因子已固定假设，正在完成训练与检查；尚无已验收结果。' if active else '下一因子固定训练尚未交付完整结果；不预填表现或增加已验收计数。')
    else:
        state='preparing' if active else 'preparation_snapshot'
        text='下一因子'+('正在去重与固定假设' if active else '保留去重与假设准备记录')+'，尚无已验收结果。'
    return dict(id='v204',state=state,active_at_snapshot=active,author_result_complete=complete,
        independent_review_accepted=False,root_accepted=False,accepted_signal_increment=0,accepted_horizon_increment=0,
        task=text,new_account_runs=0,new_paper_T0=False)


def paper_progress_text(hk,sgov,diversified):
    """Summarize only actual observations, not source availability or future intent as a fill."""
    hk_dates=sorted({v.get('last_session') for v in hk['summaries'].values() if v.get('last_session')})
    hk_date=hk_dates[-1] if hk_dates else None
    sg_dates=sorted({v['last_observation'] for v in sgov.get('accounts',[]) if v.get('last_observation')})
    sg_date=sg_dates[-1] if sg_dates else None
    text=f"03086最近实际观察{hk_date or '尚无'}；SGOV最近实际观察{sg_date or '尚无'}；组合已观察{diversified['observations'] if diversified['activated'] else 0}会话，最近{diversified['last_observation'] or '尚无'}。"
    if sgov.get('valuation_current') is False:text+=f"SGOV本次{sgov['latest_attempt']['attempt_date']}因来源修订冻结，当前估值未知，旧值仅作最近成功记录。"
    return text+'三套纸面各自原T0与原本金保持，观察和账面金额随已接受记录接续；系统实际订单0，账面增减不是实际提现，正式统计推断未启用。'


def project_layered_evaluation_and_flot(evidence,current_work,cards,registry,activity):
    """Add qualified research milestones without changing old results or trial counts."""
    method=accepted_continuation_review('FORWARD-METHOD-v167-v170-ROOT-ACCEPTANCE-v1.json',
        'ACCEPT_LAYERED_MEASUREMENT_CONTRACT_ONLY_NOT_FORMAL_INFERENCE')
    flot=accepted_continuation_review('FLOT-v169-ROOT-REVIEW-v1.json',
        'ACCEPT_ECONOMIC_PREFLIGHT_GO_BOUNDED_SOURCE_QUALIFICATION_ONLY')
    flot_source=accepted_continuation_review('FLOT-SOURCE-v172-ROOT-REVIEW-v1.json',
        'ACCEPT_ISSUER_PRIMARY_CONDITIONAL_HISTORY_INPUTS_NOT_STRICT_BUNDLE_UPGRADE')
    exit_review=accepted_continuation_review('FORWARD-EXIT-v171-v173-ROOT-REVIEW-v1.json',
        'ACCEPT_PURE_EXIT_MEASUREMENT_ADAPTER_NOT_AUTOMATIC_REPORTING')
    flot_history=accepted_continuation_review('FLOT-ACCOUNT-v174-v175-ROOT-REVIEW-v1.json',
        'ACCEPT_CONDITIONAL_HISTORICAL_ACCOUNT_NOT_STABILITY')
    if not method or not flot:return None
    assert method['root_qualifications']['formal_inference_enabled'] is False
    assert not method['new_paper_T0_created'] and method['new_financial_observations']==0
    assert flot['new_factor_trials']==flot['historical_account_runs']==0
    cost=read(ROOT/'reports/us-floating-credit-preflight-owner-20261118-v169/COST-ARITHMETIC-v1.json')
    pressure={str(c['capital_hkd']):c['main_12_events_flat']['flat_arithmetic_surplus_hkd'] for c in cost['cases'] if c['cost']=='pressure'}
    assert pressure==flot['current_cost_interpretation']['pressure_flat_one_year_example_hkd']
    team=read(MINING/'TEAM.json')
    def running(fragment):
        return activity in ['preparing','checking'] and any(o['status']=='ACTIVE' and any(fragment in p for p in o['write_paths']) for o in team['owners'])
    economic='分层经济评价合同已接受：保留原本金、原T0及换汇费用，原账面收益与扣必要退出成本后的估值分别列示；原8臂与尚未激活的组合8臂不当作16份独立样本。'
    inference='正式统计推断仍未启用，所需假设尚无充分依据。没有规定等满几个月、凑够交易笔数或某次盈利即可成功；单个统计方案也不是永久验收门槛。'
    exit_text='只读退出成本适配与独立核账正在进行；原账户和订单不改，尚未形成已验收的新月报或收益。'
    flot_text='FLOT公开价格、公司行动与发行人分派正在做有限范围核对；目前尚无历史账户结果，不计为新因子试验或有效策略。'
    if flot_source:
        assert flot_source['original_v172_status']=='UNKNOWN' and not flot_source['old_bundle_code_tolerance_and_sources_modified']
        flot_text=flot_source['site_summary']
    if exit_review:exit_text=exit_review['site_summary']
    if flot_history:flot_text=flot_history['site_summary']
    f=evidence['forward_evaluation']
    f['layered_measurement']=dict(status='accepted_readonly_adapter_monthly_integration_pending' if exit_review else 'accepted_contract_adapter_pending',accepted_at_utc=method['actual_acceptance_utc'],
        active_original_arms=8,planned_unactivated_arms=8,formal_inference_enabled=False,
        original_marked_primary_preserved=True,automatic_goal_completion=False,
        exit_adapter_accepted_at_utc=exit_review['actual_acceptance_utc'] if exit_review else None,
        real_held_exit_end_to_end_verified=False)
    f['note']+=' '+economic+' '+exit_text
    f['limitation']+=' '+inference
    cards.insert(0,dict(id='us-flot-preflight',name='FLOT · 浮息信用与小资金成本预检',status='review',
        status_label='仅继续来源核对',capital_hkd=30000,period='当前指标的费用示例；不是历史账户',
        basis='90%整股预算、原30%税情景和每次USD1/2储备；保留交易、滑点与双向换汇成本。',
        results=[dict(cost=c,net_hkd=None,cagr_pct=None,risk_pct=None) for c in ['base','pressure']],
        conclusion='假设一年原价不变的压力费用示例：1万／2万／3万港币分别−110.40／+28.57／+178.49；价格下跌1%的同一示例三档均负。静态算术，不是回测、预测或实际到账。',
        next='浮息信用增加信用和流动性风险，固定费用并未降低。仅批准2015—2019拟议开发窗的价格／行动来源核对，尚不授权收益试跑。'))
    if flot_source:
        cards[0]['status_label']='固定条件账户核算中'
        cards[0]['next']=flot_text+' 原先30%税及USD1/2储备不变；源金额差异不以扩大容差消除。'
    if flot_history:
        assert flot_history['new_factor_trials']==flot_history['new_horizon_trials']==0
        assert flot_history['old_strict_source_status']=='UNKNOWN' and not flot_history['strict_bundle_promoted']
        assert not flot_history['new_paper_T0_created'] and not flot_history['later_period_authorized_here']
        cards[0]=flot_history['site_card']
        evidence['flot_history']=dict(status='conditional_history_only',accepted_at_utc=flot_history['actual_acceptance_utc'],
            economic_cases=flot_history['economic_cases'],source_sensitivity=flot_history['source_sensitivity'],
            single_strategy_related_scenarios=12,new_factor_trials=0,strict_source_status='UNKNOWN',
            stable_profitability_proven=False,new_paper_T0_created=False)
    cash_source_active=running('hk-money-market-source-gap-owner-20261118-v176/')
    cash_source_text='正在核查已有03152港币现金基准的逐类分派与历史单位资料；先判断能否补齐来源条件，不重复回测或把现金利息叫新因子。' if cash_source_active else '03152港币现金基准的来源缺口专项已交回，结果待主会话审查；原条件历史结论不自动升级。'
    added=[dict(name='分层评价验收',task=economic+' '+inference,status='snapshot'),
           dict(name='退出成本核算',task=exit_text,status='active' if not exit_review and running('forward-liquidation-measurement-') else 'snapshot'),
           dict(name='FLOT五年复核' if flot_history else 'FLOT条件账户' if flot_source else 'FLOT来源核对',task=flot_text,status='active' if not flot_history and (running('us-floating-credit-account-owner-20261118-v174/') or running('us-floating-credit-source-owner-20261118-v172/')) else 'snapshot'),
           dict(name='港币现金资料核查',task=cash_source_text,status='active' if cash_source_active else 'snapshot')]
    current_work['owners']=added+[o for o in current_work['owners'] if o['name']!='主会话核验与发布']
    registry.extend([
        dict(id='forward-method-v167-v170',version='V167–V173 · 评价与退出估值',name='持续经济证据分层 · 统计推断未启用',category='recent',record_type='evaluation_protocol',
             conclusion=economic+' '+inference+' '+exit_text,source_date='2026-11-18',source='root实际接受与独立方法审查；不是新增盈利或新T0'),
        dict(id='flot-history-v174-v175' if flot_history else 'flot-preflight-v169',version='V169–V175 · FLOT条件历史' if flot_history else 'V169 · 机制预检',name='FLOT浮息信用 · 固定费用空间有限',category='recent',record_type='conditional_economic_account' if flot_history else 'economic_preflight',
             conclusion=cards[0]['conclusion']+' '+cards[0]['next'],source_date='2026-11-18',source='独立Fraction账户先于作者结果；15096日行金额一致，12情景属于1条规则，不是12个独立策略' if flot_history else '发行人原文及312项独立精确货币核对；不是历史账户或收益预测')])
    return '总目标运行中，稳定盈利尚未证实。FLOT五年条件核算与退出估值独立审查已交付，FLOT暂不升级纸面；港币现金基准资料核查继续。正式统计推断未启用，原纸面起点不变，本轮不增加因子或盈利策略计数。' if flot_history and exit_review else '总目标运行中，稳定盈利尚未证实。分层评价与FLOT条件研究继续；原纸面起点不变，本轮不增加因子或盈利策略计数。'


def current_mining_work(new_paper,activity,milestone_delivered,accepted_a=False,accepted_b=False,accepted_c=False):
    team=read(MINING/'TEAM.json')
    source_folder=ROOT/'reports/us-action-panel-owner-20261117-v137'
    # The v1 compatibility failure stays archived; prefer a later bounded receipt.
    receipts=sorted(source_folder.glob('CAPTURE-RECEIPT-v*.json'),key=lambda p:int(re.search(r'-v(\d+)',p.name).group(1)))
    source='预定40股的显式拆股／毛现金诊断源正在核验，尚未认证为合格因子面板。'
    raw_status=None
    if receipts:
        capture=read(receipts[-1]);raw_status=capture.get('status')
        if str(raw_status).startswith('STOP'):
            source='请求兼容性修复／源资格待核；最近采集未扩展40股，未计算新因子表现。'
    qualification=source_folder/'QUALIFICATION-v1.json'
    if qualification.exists():
        qualified=read(qualification);raw_status=qualified['status']
        if raw_status=='LIMITED_GROSS_RIGHTS_DIAGNOSTIC_DATA_ONLY':
            assert qualified['historical_alpha_IC_or_return_labels_calculated'] is False
            assert qualified['old_700_files_qualified'] is False and qualified['old_v132_gate_unlocked'] is False
            source=f"固定{qualified['nominal_names']}股、{qualified['calendar_sessions']:,}会话的显式拆股／毛现金权利诊断源已构造，日截面{qualified['source_qualified_count_min']}—{qualified['source_qualified_count_max']}只。该源本身不认证因子有效性或净账户；旧700股未因此获认证。"
    def owner_active(path_fragment):
        return any(o['owner']!='/root' and o['status']=='ACTIVE' and any(path_fragment in p for p in o['write_paths']) for o in team['owners'])
    account_active=owner_active('us-diversified-carry-owner-20261117-v144/')
    registration_active=(owner_active('us-diversified-forward-source-owner-20261118-v157/') or
                         owner_active('us-diversified-forward-engine-owner-20261118-v158/') or
                         owner_active('us-diversified-forward-integration-audit-owner-20261118-v162/'))
    root_active=any(o['owner']=='/root' and o['status']=='ACTIVE' for o in team['owners'])
    observed_activity=activity in ['preparing','checking']
    forward=accepted_diversified_forward()
    factor_active=owner_active('us-downside-risk-validation-owner-20261118-v164/')
    downside=accepted_downside_review()
    return dict(goal_status='ACTIVE',research_batch_status='active',stable_profitability_proven=False,
        candidate_milestone_status='delivered' if milestone_delivered else 'pending',
        goal_label='总目标运行中',milestone_label='历史候选交付完成（里程碑）' if milestone_delivered else '历史候选交付待验收',
        evidence_label='稳定盈利与持续性尚未证实',
        task='T-012',team_updated_at=team['updated_hkt'],
        active_work=dict(account=account_active and observed_activity and not accepted_c,
                         registration=registration_active and observed_activity,review=root_active and observed_activity),
        source_status=raw_status,scope='港美个股及普通非杠杆ETF；持续研究与原03086／SGOV纸面并行。',
        owners=[dict(name='主会话核验与发布',task='组合公开源、八情景资金核算与日志程序已完成联合验收，正在同步证据；程序通过不等于盈利成立。' if forward else '组合真实公开源与资金核算程序正在独立联合验收；已有条件历史候选保留，稳定盈利未证。' if accepted_c else '组合历史账户及资料限制核验；候选交付不关闭总目标。',status='active' if root_active and observed_activity else 'snapshot'),
                dict(name='组合前向程序',task=forward['site_summary'] if forward else '60／20／20组合源适配、增量资金核算和协调器已实现，正在独立联合核验；未激活新钱包、意向或T0。',status='active' if registration_active and observed_activity else 'snapshot'),
                dict(name='下行波动筛选' if downside else '下一机制研究',task=downside['site_factor']['conclusion'] if downside else '低下行波动：旧库已有输入但未单独验证；正对原定126会话版本做首次固定训练评价，不声称新机制。尚无已验收新结果，不增加信号或盈利计数。',status='active' if factor_active and observed_activity and not downside else 'snapshot'),
                dict(name='组合账户研究',task='A/B/C条件历史核算已交付。没有新增组合纸面T0；后续机制研究与原纸面继续，不能把C当独立盲测或稳定证明。' if accepted_c else 'A/B条件结果已验收；同规则C 2021—2025连续账户研究中，结果待根验收，不预填。' if accepted_b else 'v144的A 2021—2023条件结果已验收；下一步准备冻结B 2024—2025，B/C尚未计算。' if accepted_a else 'v144固定60% SGOV／20% VTI／20% GLD，条件源核对后实现A 2021—2023模型。',status='active' if account_active and observed_activity and not accepted_c else 'snapshot'),
                dict(name='已验收因子',task='v141日内强度、v145低MAX、v147毛现金股息率及v151单代理残差趋势均未通过固定训练筛选；不是全球机制失败。',status='snapshot'),
                dict(name='两套固定纸面',task='03086与SGOV保留原T0。当前没有新增到期观察，按真实新时点接续。',status='snapshot')],
        note='历史候选交付是一项已完成里程碑，不代表总目标完成。工作分工只反映同步时观察，超过15分钟停动画；没有后台持续计算承诺。')


def conditional_diagnostic_card(review_path,identifier,name,basis):
    card=dict(id=identifier,name=name,status='pending',status_label='固定诊断待独立验收',capital_hkd=30000,
              period='固定历史窗口',basis=basis,
              results=[dict(cost=k,net_hkd=None,cagr_pct=None,risk_pct=None) for k in ['base','pressure']],
              conclusion='规则及来源已固定；验收前不展示模型收益。',next='核完整现金账和源限制，保持既有参数。')
    if not review_path.exists():return card
    result=read(review_path)
    assert result['decision'] in ['ACCEPT_CONDITIONAL_CASH_BENCHMARK_ONLY','ACCEPT_PRICE_ONLY_DIAGNOSTIC_ONLY','ACCEPT_HYBRID_2025_CASH_DIAGNOSTIC_ONLY']
    assert result['independent_cash_review_passed'] is True
    assert result['actual_personal_income_certified'] is False
    supplied=result['site_card']
    assert supplied['id']==identifier and supplied['name']==name and supplied['status'] in ['review','closed','unknown']
    assert len(supplied['results'])==2 and {r['cost'] for r in supplied['results']}=={'base','pressure'}
    assert all(r['net_hkd'] is None or type(r['net_hkd']) in (int,float) and math.isfinite(r['net_hkd']) for r in supplied['results'])
    return supplied

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
    parser.add_argument('--focus',choices=['sp500','small-nasdaq','hsi-hold','gold','ipo','validation','cash','us-vti','paper','mining'],default='sp500')
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
    factor_research=new_factor_research();sgov=sgov_history();new_paper=sgov_paper_status();portfolio=current_portfolio_research()
    diversified=validate_diversified_projection(diversified_paper_status())
    evidence_updates=accepted_evidence_updates()
    accepted_a=portfolio['status'].startswith('accepted_conditional_')
    accepted_b=portfolio.get('B_accepted',False);accepted_c=portfolio.get('C_accepted',False)
    current_work=current_mining_work(new_paper,args.activity,bool(sgov and new_paper['activated']),accepted_a,accepted_b,accepted_c)
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
    income_review=TEAM/'v115-review/FINAL-REVIEW-v1.json'
    dependence_review=TEAM/'v114-review/FINAL-REVIEW-v1.json'
    if income_review.exists():
        income=read(income_review)
        assert income['decision']=='ACCEPT_EXISTING_ACCOUNT_DISTRIBUTION_NO_STABLE_CASH_INCOME_ESTABLISHED'
        cards[0]['conclusion']='历史正额保留纸面；82完整月中两档均24负月，月净值变化中位122.65／90.67港币。最长水下515／531实际会话；2025及2026YTD均负，未建立稳定月收入或独立alpha。原5闭合+1开放。'
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
    ipo_observation_path=TEAM/'ipo-current-observation-20261117/CURRENT-PROXY-OBSERVATION-v1.json'
    ipo_observation=None
    if ipo_observation_path.exists():
        observed=read(ipo_observation_path)
        assert observed['observation_type']=='BOUNDED_CURRENT_PROXY_DESCRIPTION_NOT_FORWARD_DECISION' and not observed['future_decision_registered']
        ipo_observation=dict(observed_at_hkt=observed['observed_at_hkt'],count=observed['count'],median_pct=observed['median_pct'],
            up_count=observed['up_count'],broken_count=observed['broken_count'],flat_count=observed['flat_count'],
            one_member_max_up_count=observed['one_member_sensitivity']['maximum_up_count'],
            observed_proxy_only=True,not_an_account_win_rate=True,paper_decision_registered=False)
    ipo=dict(status='pending')
    cash_review=TEAM/'v120-review/FINAL-REVIEW-v1.json'
    us_vti_review=TEAM/'v123-review/FINAL-REVIEW-v1.json'
    cash=conditional_diagnostic_card(cash_review,'cash-03152','03152 · 低换手现金基准','场内原价、固定成本及零分派条件；不是新增alpha')
    us_vti=conditional_diagnostic_card(us_vti_review,'us-vti','VTI · 美股月度趋势诊断','不计入分派现金、固定汇兑情景；不是完整总回报')
    if (TEAM/'V120-CASH-HISTORICAL-BENCHMARK-20261117.md').exists():cards=[cash,*cards]
    if (TEAM/'V123-US-VTI-PRICE-DIAGNOSTIC-20261117.md').exists():cards=[us_vti,*cards]
    cash_bridge_review=TEAM/'v126-review/FINAL-REVIEW-v1.json'
    if cash_bridge_review.exists():
        cards=[conditional_diagnostic_card(cash_bridge_review,'us-vti-cash-2025','VTI · 2025现金路径桥接','混合来源与假设税费'),*cards]
    gld_path=ROOT/'reports/us-gold-candidate-owner-20261117-v131/RESULTS-v1.json'
    if gld_path.exists():
        gld=read(gld_path)
        assert gld['status']=='REJECT_FIXED_V131_A_COST_PRESSURE_PRICE_DIAGNOSTIC'
        assert gld['B_status']==gld['C_status']=='NOT_OPENED_A_FAILED'
        pairs=[r for r in gld['pairs'] if r['capital_hkd']==30000]
        cards=[dict(id='us-gld-monthly',name='GLD · 固定月末趋势',status='closed',status_label='A段压力淘汰',capital_hkd=30000,
                    period='2015-01-01 — 2019-12-31',basis='条件价格诊断；固定7.8、整股、双向换汇及逐项费用；分派源未完整认证',
                    results=[dict(cost=r['cost'],net_hkd=float(r['trend_net_hkd']),cagr_pct=None,risk_pct=float(r['trend_high_low_DD_pct'])) for r in pairs],
                    conclusion='主3万压力净亏224.15港币；1万／2万压力也亏。B/C未打开。简单持有对照盈利不代表本策略通过。',
                    next='保留固定负结果，不调窗口、不以被动持有替换主策略或新增纸面候选。'),*cards]
    if sgov:
        sgov_card=dict(sgov['card'])
        if new_paper['activated']:
            sgov_card.update(status_label='条件历史通过，纸面已启',next='独立真实日期纸面已建立；新结果见纸面视图，历史净额不导入前向账本。')
        cards=[sgov_card,*cards]
    if args.focus=='paper':cards=sorted(cards,key=lambda c:c['id']!='nasdaq-monthly')
    if args.focus=='ipo':
        assert ipo_review.exists() and read(ipo_review)['decision']=='ACCEPT_NEW_OFFER_CONFIRMED_ADMISSION_PENDING'
    if args.focus=='validation':
        assert income_review.exists() and dependence_review.exists()
        assert read(dependence_review)['independent_controls_exact']==4
    current,current_later={'sp500':(latest,later_review),'small-nasdaq':(small,small_later),'hsi-hold':(hsi,None),'gold':(gold,None),'ipo':(ipo,None),'validation':(dict(status='pending'),None),'cash':(cash,None),'us-vti':(us_vti,None),'paper':(dict(status='paper'),None),'mining':(dict(status='pending'),None)}[args.focus]
    registry=[]
    for i,line in enumerate((TEAM/'README.md').read_text(encoding='utf-8').splitlines()):
        if not line.startswith('| `/root'):continue
        cells=[clean(v) for v in line.split('|')[1:-1]]
        if len(cells)!=4:continue
        version=re.search(r'V\d+[A-Z]?',cells[1])
        registry.append(dict(id=f'team-{i}',version=version.group() if version else '研究汇总',name=cells[1],
              category='recent',conclusion=cells[2],source_date=now[:10],source='工作台记录同步'))
    factor_notes=next((TEAM/f'factor-validity/FACTOR-AND-RULE-CONCLUSIONS-v{version}.json' for version in [5,4,3] if (TEAM/f'factor-validity/FACTOR-AND-RULE-CONCLUSIONS-v{version}.json').exists()),TEAM/'factor-validity/FACTOR-AND-RULE-CONCLUSIONS-v3.json')
    if factor_notes.exists():
        notes=read(factor_notes)
        assert notes['new_factor_IC_computations']==0
        for note in notes['items']:
            registry.append(dict(id='signal-note-'+note['id'],version='信号与规则综述',name=note['name'],category='recent',
                conclusion=note['conclusion'],source_date=now[:10],source='此前已验账户证据综述；与本批新因子分列'))
    for factor in factor_research['items']:
        registry.append(dict(id='new-factor-'+factor['id'],version='本批新因子',name=factor['name'],category='recent',
            conclusion=factor['conclusion']+' '+factor['limitation']+' '+factor['next'],source_date=factor.get('source_date','2026-11-17'),source='固定信号诊断；不是可执行净账户'))
    qii=evidence_updates['sgov_qii'];evaluation=evidence_updates['forward_evaluation']
    registry.append(dict(id='sgov-qii-source-v148',version='V148 · 来源核验',name='SGOV官方QII分类 · 非个人税率',category='recent',record_type='source_review',
        conclusion=f"{qii['source_events']}笔官方分类；"+'；'.join(f"{r['year']} {float(r['weighted_qii_percent']):.4f}%" for r in qii['annual'])+'。'+qii['note']+' '+qii['limitation'],
        source_date=evaluation['accepted_at_hkt'][:10],source='发行人分类及root独立来源核验；不是新因子或经济试验'))
    registry.append(dict(id='forward-evaluation-v149',version='V149 · 评价协议',name='原T0八臂 · 描述性月报协议已接受',category='recent',record_type='evaluation_protocol',
        conclusion=f"{evaluation['accepted_at_hkt']} HKT接受。"+evaluation['note']+' '+evaluation['limitation'],source_date=evaluation['accepted_at_hkt'][:10],
        source='root真实UTC接受回执；不是新纸面T0或新策略试验'))
    vti_source_review=MINING/'acceptance/VTI-SOURCE-v153-ROOT-REVIEW-v1.json'
    if vti_source_review.exists():
        vti_source=read(vti_source_review)
        assert vti_source['decision']=='ACCEPT_SOURCE_AUDIT_ONLY_NO_QUALIFICATION_UPGRADE'
        assert vti_source['newly_jointly_qualified_events']==0 and not vti_source['old_source_ledger_cost_tax_FX_weights_T0_changed']
        registry.append(dict(id='vti-source-v153',version='V153 · 来源核验',name='VTI历史付款日核验 · 来源条件保留',category='recent',record_type='source_review',
            conclusion='12笔目标未获新增的完整官方身份／日期／金额证明：2021年4笔付款日来源待核，2022—2023年8笔日历打印CUSIP与VTI身份冲突。计划付款日不是实际付款或券商到账，旧账户金额及条件结论不变；新日期官方事件可独立留证。',
            source_date='2026-11-18',source='官方原页与root源审计；不是新增因子、交易或收益'))
    forward_review=accepted_diversified_forward()
    if forward_review:
        registry.append(dict(id='diversified-forward-v160',version='V157–V162 · 程序验收',name='60／20／20组合前向程序 · 尚未激活',category='recent',record_type='implementation_milestone',
            conclusion=forward_review['site_summary']+'旧VTI历史来源条件、个人税费未知与正式统计方法待冻结均保留。',source_date=forward_review['accepted_at_hkt'][:10],
            source='公开源、资金接口和日志联合审查；不是新因子、交易或净收益'))
    if gld_path.exists():registry.append(dict(id='v131-gld-fixed',version='V131',name='GLD固定月末趋势 · A段淘汰',category='recent',
        conclusion='3万主压力−224.15港币，条件价格诊断。1万／2万压力也负，B/C未打开；passive40盈利不能替代主策略门槛。',source_date='2026-11-17',source='固定原规则及12账户封存结果'))
    if sgov:registry.append(dict(id='sgov-carry-acceptance',version='V133 / V135',name='SGOV条件历史与独立核账',category='recent',
        conclusion=sgov['card']['conclusion']+' '+sgov['limitations']+' '+sgov['comparison'],source_date='2026-11-17',source='主会话正式条件历史验收；纸面另立起点'))
    archived=ROOT/'sites/hk-quant-research-hub/dist/data/catalog.json'
    archive=read(archived) if archived.exists() else None
    if archive:
        for r in archive['strategies']:
            registry.append(dict(id='archive-'+r['id'],version='早期归档',name=r['name'],category='archive',
                 conclusion=clean(str(r.get('short_conclusion') or r.get('conclusion') or r['summary']))[:800],
                 source_date='2026-11-03',source='旧快照，结论日期保留'))
        for r in archive['factors']:
            registry.append(dict(id='old-factor-'+r['id'],version='旧因子 · '+r['status_label'],name=r['name'],category='factor-archive',
                conclusion=clean(str(r.get('conclusion') or r.get('short_conclusion') or r['summary'])),
                definition=r.get('definition'),diagnostic=' · '.join(filter(None,[r.get('stat_display'),r.get('stat_note')])),
                period=r.get('period'),source_date='2026-11-03',source='旧因子目录快照；没有用本轮结果改写原结论',
                qualification='旧US缓存已发现拆股阶跃；本条未获本轮源资格认证。旧指标仅保留为存储价格诊断。' if r.get('market')=='US' else '旧快照，本轮未重新核验本条的源、统计或可执行账户。'))
    stage_status=['done','done','done','active','pending','pending']
    if current['status']!='pending':stage_status=['done','done','done','done','pending' if current['status']=='candidate' else 'not_opened','pending' if current['status']=='candidate' else 'not_opened']
    if args.phase=='source':stage_status=['done','active','pending','pending','pending','pending']
    if args.phase=='implementation' and current['status']=='pending':stage_status=['done','done','active','pending','pending','pending']
    if args.phase=='later' and current['status']=='candidate':stage_status=['done','done','done','done','active','pending']
    if current_later is not None and current_later.exists():stage_status=['done','done','done','done','done','pending' if current['status']=='candidate' else 'not_opened']
    if current['status']=='unknown':stage_status=['done','done','done','unknown','not_opened','not_opened']
    if args.focus=='ipo':stage_status=['done','active','active','pending','not_opened','not_opened']
    if args.focus=='ipo' and ipo_observation:stage_status=['done','unknown','done','pending','not_opened','not_opened']
    if args.focus=='validation':stage_status=['done','done','done','done','done','pending']
    if args.focus=='cash' and cash_review.exists():stage_status=['done','done','done','done','done','pending']
    if args.focus=='us-vti' and us_vti_review.exists():stage_status=['done','done','done','done','done','unknown']
    if args.focus=='paper':
        observed=paper['verified_data_through']>=paper['first_forward_session']
        next_intent=observed and any(v['eligible'] and v['date']>paper['verified_data_through'] for v in paper['recorded_intents'])
        monthly_review_observed=paper['verified_data_through'][:7]>paper['first_forward_session'][:7]
        stage_status=['done','done','done','done' if observed else 'pending','done' if next_intent else 'pending','done' if monthly_review_observed else 'pending']
    if args.focus=='mining':stage_status=['done' if current_work['candidate_milestone_status']=='delivered' else 'pending','done',
        'active' if current_work['active_work']['account'] or current_work['active_work']['registration'] else 'pending','active' if current_work['active_work']['review'] else 'pending','pending','pending']
    if args.activity not in ['preparing','checking']:stage_status=['pending' if s=='active' else s for s in stage_status]
    activity_active=args.activity in ['preparing','checking'] and current['status'] in ['pending','candidate']
    if args.focus=='mining':activity_active=args.activity in ['preparing','checking'] and any(s=='active' for s in stage_status)
    activity_text={'preparing':'准备固定开发检验','checking':'固定检验执行与独立核算','waiting':'等待下一项真实证据','done':'本轮检验已验收'}[args.activity]
    if args.focus=='hsi-hold' and args.activity in ['preparing','checking']:activity_text='已见历史的固定四案单变体诊断'
    if args.phase=='later' and args.activity in ['preparing','checking']:activity_text='固定后续段与连续账户检验'
    if args.phase=='source' and args.activity in ['preparing','checking']:activity_text='发行人现金事件复核与开发源准备'
    if args.focus=='gold' and args.activity in ['preparing','checking']:activity_text='黄金ETF来源、整手与小资金费用预检'
    if args.phase=='implementation' and args.activity in ['preparing','checking']:activity_text='高价ETF执行、现金与独立核算代码准备'
    if args.focus=='ipo' and args.activity in ['preparing','checking']:activity_text='09941现金路径核对，与新时点完整首日源补证并行；准入及温度仍待核'
    if args.focus=='ipo' and ipo_observation:activity_text='当前已核样本未达原热市条件；现金路径与11月19日08:30资料固化待核'
    if args.focus=='validation':activity_text='两项稳定性检验已验收；历史正额尚未成为稳定副业收入。下一轮核现金ETF历史扣费，原纸面待真实新日线。'
    if args.focus=='cash':activity_text='固定2024/2025现金基准与低换手对照；原价扣费模型仍有分派和执行条件，不是新alpha或实际入账。'
    if args.focus=='us-vti':activity_text='本轮36个价格诊断账户已验收。分派未计入现金、汇兑是固定情景；下一步补完整现金与独立原价，不改已有参数。' if us_vti_review.exists() else '普通美股ETF月度趋势的固定价格诊断正在准备，真实现金路径仍待核。'
    ipo_terms=TEAM/'ipo-public-cash-terms-20261117/PUBLIC-TERMS-v1.json'
    if args.focus=='ipo' and ipo_terms.exists():activity_text='普通现金申购手续费公开核为0；专用截止仍有时间口径差异。保留11月19日08:30研究时点，当日决定尚未登记。'
    if args.focus=='paper':
        primary=paper['summaries']['monthly-only-base']
        activity_text=f"用户已选择历史检验通过后转固定候选纸面跟踪。03086四臂规则及真实T0保持；主臂持仓{primary['open_quantity']}份、已闭合{primary['closed_rounds']}轮。接续依赖电脑和OpenD在线，尚未安装后台定时服务。"
    if args.focus=='mining':
        activity_text=f"总目标运行中，稳定盈利尚未证实；历史候选交付只是里程碑。v151单代理残差趋势双期限训练筛退，独立复算及root验收已完成。已验收记录累计{factor_research['unique_new_signals']}个信号、{factor_research['planned_horizon_trials']}个预定期限。正式稳定性统计方法尚未冻结。"+('60／20／20组合A/B/C条件历史保留；C与A/B重叠，不能相加。v153未解除VTI历史来源条件。当前推进组合前向实施准备：年度再平衡与一次持有并列，尚未新增组合钱包或T0。' if accepted_c else '既有组合研究及原纸面按各自真实证据接续，不以新来源说明改变旧金额。')
        forward=accepted_diversified_forward()
        if forward:activity_text=f"总目标运行中，稳定盈利尚未证实。已验收{factor_research['unique_new_signals']}个信号、{factor_research['planned_horizon_trials']}个期限；当前并行研究低下行波动候选，尚不计入已验收数。"+forward['site_summary']+'正式稳定性统计方法尚未冻结；旧历史金额与原03086／SGOV起点保持。'
        if forward and accepted_downside_review():activity_text=f"总目标运行中，稳定盈利尚未证实。已验收{factor_research['unique_new_signals']}个信号、{factor_research['planned_horizon_trials']}个期限；低下行波动首次固定训练已独立复算，两期限均未通过收益排序筛选，不代表低风险配置没有价值。"+forward['site_summary']+'正式稳定性统计方法尚未冻结；原纸面及历史金额保持。'
        continuation=project_layered_evaluation_and_flot(evidence_updates,current_work,cards,registry,args.activity)
        if continuation:activity_text=continuation
    project_hk_cash_addendum(evidence_updates,current_work,registry)
    if 'hk_cash_2024' in evidence_updates:
        activity_text=activity_text.replace('港币现金基准资料核查继续。','港币现金基准2024零普通分派来源局部补强已接受；2025及全期单位条件保留。')
    actual_continuation=project_actual_diversified_continuation(diversified,evidence_updates,current_work,registry)
    if actual_continuation and args.focus=='mining':activity_text=actual_continuation
    intermediate=accepted_intermediate_review()
    if intermediate and args.focus=='mining':
        current_work['owners'].append(dict(name='最新因子筛选',task=intermediate['site_factor']['conclusion'],status='snapshot'))
        activity_text+=f" 最新中间期动量的20／60日固定筛选均未通过；累计{factor_research['unique_new_signals']}个已验收信号、{factor_research['planned_horizon_trials']}个期限，仍无稳定盈利证明。"
    if args.focus=='mining':
        wrapper_owners=[o for o in read(MINING/'TEAM.json')['owners'] if any('hk-usd-cash-wrapper-preflight-owner-20261118-v181/' in p for p in o['write_paths'])]
        if wrapper_owners:
            wrapper_active=any(o['status']=='ACTIVE' for o in wrapper_owners)
            current_work['owners'].append(dict(name='下一机制预检',status='active' if wrapper_active else 'snapshot',
                task=('正在核查' if wrapper_active else '已交回')+'03196美元货币ETF港币柜台的官方身份、整手与费用可行性；这一步尚未计算历史收益，不增加有效因子或盈利策略数。'))
    wrapper_source=project_hk_usd_cash_source(evidence_updates,current_work,registry)
    wrapper_activity=project_hk_usd_activity(evidence_updates,current_work,registry)
    tip_source_work=project_tip_source_work(current_work) if args.focus=='mining' else None
    tip_history,tip_source_review,tip_account_review=project_tip_history(current_work,cards,registry,evidence_updates)
    tip_continuation,tip_B_source_review,tip_B_account_review=project_tip_continuation(current_work,cards,registry)
    next_factor=next_factor_progress(args.activity) if args.focus=='mining' else None
    paper_progress=paper_progress_text(paper,new_paper,diversified)
    if tip_B_account_review and args.focus=='mining':
        current_work['owners'].append(dict(name='价格延迟因子验收' if next_factor['root_accepted'] else '下一因子训练与复核',status='active' if next_factor['active_at_snapshot'] else 'snapshot',task=next_factor['task']))
    for owner in current_work['owners']:
        if owner['name']=='两套固定纸面':owner.update(name='三套固定纸面',status='snapshot',task=paper_progress)
    amihud=accepted_amihud_review()
    filing_event=filing_event_projection() if args.focus=='mining' else None
    form4=form4_projection() if args.focus=='mining' else None
    merger=merger_projection() if args.focus=='mining' else None
    merger_execution_control=civitas_projection() if merger else None
    merger_cost_control=merger_cost_projection() if merger else None
    merger_review=merger_review_projection() if merger else None
    merger_stress=merger_stress_projection() if merger else None
    ief_result=ief_result_projection() if args.focus=='mining' else None
    southbound=southbound_projection() if args.focus=='mining' else None
    pdbc_preflight=pdbc_preflight_projection() if args.focus=='mining' else None
    if args.focus=='mining':
        team=read(MINING/'TEAM.json')
        checking=args.activity in ['preparing','checking']
        filing_active=checking and any(o['status']=='ACTIVE' and any('us-filing-source-pilot-20261119-v208/' in p for p in o['write_paths']) for o in team['owners'])
        if filing_event:
            filing_task=('四家公司八份原始公告已核实。20日事件诊断已完成，下方可查看每一例及费用敏感性。'
                         if filing_event['result'] else '四家公司八份原始公告已核实。20日事件诊断等待验收。')
            if filing_event.get('expansion'):
                filing_task='四家公司48份新增财报已核实并独立复算。下方对比只买盈利增长和每次公告都买，保留首批八次结果。'
        else:
            filing_task='正在核对美股财报披露时点与当期公告中的盈利数据。' if filing_active else None
        if filing_task:current_work['owners'].append(dict(name='美股财报事件',status='snapshot' if filing_event else 'active',task=filing_task))
        root_running=checking and any(o['owner']=='/root' and o['status']=='ACTIVE' for o in team['owners'])
        audit_running=checking and any(o['status']=='ACTIVE' and any('v187/' in p for p in o['write_paths']) for o in team['owners'])
        current_work['owners']=[o for o in current_work['owners'] if o['name']!='主会话核验与发布']
        current_work['owners'].append(dict(name='主会话核验与发布',status='active' if root_running else 'snapshot',
            task='同步48份财报的同机会比较；跟踪原有纸面账户。' if filing_event and filing_event.get('expansion') else '同步财报事件检验与三ETF组合的首日成本拆解。' if filing_event else '同步TIP固定后段结论、实际日期纸面接续与下一因子审核状态。'))
        current_work['owners'].append(dict(name='Amihud固定筛选',status='snapshot' if amihud or not audit_running else 'active',
            task=amihud['site_factor']['conclusion'] if amihud else 'Amihud固定训练已首跑，独立审计与root验收尚未完成；不展示作者指标，也不增加已验收信号或期限。'))
        activity_text=f"总目标运行中，稳定盈利尚未证实；历史候选交付仍只是里程碑。当前已验收{factor_research['unique_new_signals']}个信号、{factor_research['planned_horizon_trials']}个预定期限。"
        activity_text+=('Amihud双期限固定排序筛选已独立复核并由root接受，结果与限制见因子区。' if amihud else 'Amihud固定筛选正在独立核验，验收前不展示结果或增加计数。')
        if wrapper_source:activity_text+=wrapper_source['site_summary']
        if wrapper_activity:activity_text+=wrapper_activity['site_summary']
        if tip_B_account_review:activity_text+=tip_continuation['conclusion']+' A段原结果保留；A/B各自起账，不合成为连续账户，不是新增IC因子。TIP固定后段筛退。'+next_factor['task']
        elif tip_account_review:activity_text+='TIP固定2015—2019一次持有的A段条件历史已独立核对并由root接受；这是五年累计模型结果，B段仅准备、尚未经济检验，不是稳定盈利或新增IC因子。'
        elif tip_source_work:activity_text+='TIP通胀挂钩国债固定A段源已接受，账户结果等待root接受，不展示作者收益；B段仅准备、尚未经济检验。'
        activity_text+=paper_progress
        if filing_task:activity_text=filing_task+' '+activity_text
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
    if ipo_observation_path.exists():source_paths['ipo_current_observation']=str(ipo_observation_path.relative_to(TEAM))
    if factor_notes.exists():source_paths['signal_and_rule_notes']=str(factor_notes.relative_to(TEAM))
    if income_review.exists():source_paths['nasdaq_income_distribution']=str(income_review.relative_to(TEAM))
    if dependence_review.exists():source_paths['ipo_allotment_dependence']=str(dependence_review.relative_to(TEAM))
    if (TEAM/'v116-cash-quote-preflight/V116B-ISSUER-NAV-QUALIFICATION-v1.json').exists():source_paths['cash_issuer_nav']='v116-cash-quote-preflight/V116B-ISSUER-NAV-QUALIFICATION-v1.json'
    if cash_review.exists():source_paths['cash_historical_benchmark']=str(cash_review.relative_to(TEAM))
    if us_vti_review.exists():source_paths['US_VTI_price_diagnostic']=str(us_vti_review.relative_to(TEAM))
    if ipo_terms.exists():source_paths['IPO_public_cash_terms']=str(ipo_terms.relative_to(TEAM))
    if cash_bridge_review.exists():source_paths['US_VTI_2025_cash_bridge']=str(cash_bridge_review.relative_to(TEAM))
    if (TEAM/'paper-transition-20261117/USER-CRITERION-v1.json').exists():source_paths['user_paper_transition']='paper-transition-20261117/USER-CRITERION-v1.json'
    stage_names=(['已有规则','收益分布','配售依赖','现金对照','独立核账','新前向观察'] if args.focus=='validation' else ['原前向协议','发售资格与截止','首日源补证','08:30资料固化','分配与资金回流','首日退出证据'] if args.focus=='ipo' else ['规则固定','原价与事件','现金与成本','开发检验','后续历史段','真实日期纸面'])
    if args.focus=='cash':stage_names=['规则固定','历史来源','现金与费用','2024检验','2025与独立核账','实际成交观察']
    if args.focus=='us-vti':stage_names=['规则固定','长历史来源','价格诊断','后续历史段','独立核账','完整现金补证']
    if args.focus=='paper':stage_names=['历史检验','规则冻结','纸面起点','新会话观察','意向接续','月初复核']
    if args.focus=='mining':stage_names=['历史候选里程碑','A/B/C条件历史' if accepted_c else 'A/B条件验收' if accepted_b else 'A段条件验收' if accepted_a else '组合条件资料','组合前向实现准备' if accepted_c else 'C连续账户研究' if accepted_b else 'B段冻结准备' if accepted_a else 'A段账户实现','研究交付核验' if accepted_c else 'C独立核验' if accepted_b else '后续独立核验' if accepted_a else '独立账户核验','持续前向样本','稳定盈利证据']
    if args.focus=='mining' and current_work['active_work']['registration']:stage_names[2]='组合前向程序核验'
    if args.focus=='mining' and accepted_diversified_forward():
        stage_names[2]='组合前向程序已验收';stage_status[2]='done'
    stage_details=[None]*6
    if args.focus=='mining':stage_details=['历史阶段已交付','条件历史已复核' if accepted_c else '各自起账条件通过' if accepted_b else 'A段条件通过' if accepted_a else '有条件采用',
        '尚未激活新组合纸面' if current_work['active_work']['registration'] else '同步时进行中' if stage_status[2]=='active' else '等待实际新进展','同步时进行中' if stage_status[3]=='active' else '等待实际新进展','描述性月报已接受；待新样本','统计方法尚未冻结']
    if args.focus=='mining' and diversified['activated']:
        stage_names[2]='组合实际纸面已激活';stage_details[2]='保留本次实际原T0'
        stage_details[4]=f"组合已观察{diversified['observations']}会话；原两套起点不变"
        stage_details[5]='正式推断未启用；盈利未证'
    if args.focus=='mining' and tip_account_review:
        stage_names[3]='TIP历史验收与后段准备';stage_details[3]='A条件历史已接受；B尚未经济检验'
    if args.focus=='mining' and tip_B_account_review:
        stage_names[3]='本轮核验与公开同步' if next_factor['root_accepted'] else '下一因子训练与复核';stage_details[3]=next_factor['task']
        stage_status[3]='active' if next_factor['active_at_snapshot'] or current_work['active_work']['review'] else 'pending'
        stage_details[1]+='；TIP B固定后段筛退'
    if args.focus=='mining':
        activity_active=args.activity in ['preparing','checking'] and any(s=='active' for s in stage_status)
    if filing_event:
        stage_names[3]='财报事件核验与同步'
        stage_details[3]=filing_task
    extra_sources={
        'mining_goal':MINING/'GOAL.md','mining_scope':MINING/'GOAL-SCOPE-ADDENDUM-v1.json','mining_team':MINING/'TEAM.json',
        'fip_protocol':MINING/'PROTOCOL-v1.json','fip_original':MINING/'RESULT-v1.json','fip_calendar_correction':MINING/'calendar-correction-v2/RESULT.json',
        'fip_corrected_findings':MINING/'calendar-correction-v2/FINDINGS.md',
        'liquidity_factor':ROOT/'reports/hk-liquidity-factor-owner-20261117-v130/RESULT-v1.json',
        'us_anchor_factor':ROOT/'reports/us-anchor-factor-owner-20261117-v132/RESULT-v1.json',
        'old_factor_catalog_review':ROOT/'reports/us-anchor-factor-owner-20261117-v132/OLD-CATALOG-REVIEW-v1.json'}
    if form4:
        extra_sources['form4_root_acceptance']=FORM4_RECEIPT
        if 'annual' in form4:
            extra_sources['form4_annual_root_acceptance']=FORM4_ANNUAL_RECEIPT
            if 'attachment_audit' in form4['annual']:
                extra_sources['form4_attachment_audit_root_acceptance']=FORM4_AUDIT_RECEIPT
        form4_task=('固定40股的2018年全年申报结构已核对，正在逐份核查候选原件的交易场所。'
                    if 'annual' in form4 else '四家公司单季来源试点已复核，下一步核对固定40股的全年申报覆盖。')
        if 'final_review' in form4.get('annual',{}):
            extra_sources['form4_final_root_acceptance']=FORM4_FINAL_RECEIPT
            form4_task='固定样本的 Form 4 原件来源核查已收尾。严格公开市场买入证据不足，本轮未做收益检验。'
        current_work['owners'].append(dict(name='美股 Form 4 披露',status='snapshot',task=form4_task))
    if merger:
        extra_sources['merger_root_acceptance']=MERGER_RECEIPT
        if merger_execution_control:
            extra_sources['merger_civitas_root_acceptance']=CIVITAS_RECEIPT
        if merger_cost_control:
            extra_sources['merger_cost_control']=MERGER_EXECUTION_CHECKS
        if merger_review:
            extra_sources['merger_review_progress']=MERGER_REVIEW_RECEIPT
        if merger_review and 'closeout' in merger_review:
            extra_sources['merger_vote_closeout']=MERGER_CLOSEOUT_RECEIPT
            merger_task='试点补查的 122 份投票申报已全部核过，新增合格事件为 0。PacBio 两个退出日期已对照两家行情发布方，仍需核对可执行性与现金到帐。'
        elif merger_review:
            merger_task='已完成 125 份代理书分类，并从 122 份补取的投票申报提取正文。继续核对 106 份仅分诊的投票材料及可执行价格。'
        else:
            merger_task='正在核对 2019 年第一季度股东批准样例、并购终局和可执行行情。'
        if merger_stress:
            extra_sources['merger_failure_and_timing']=MERGER_STRESS_RECEIPT
            merger_task='固定候选中，PACB 全仓未通过失败压力筛选。已复核 36 个损失情景和 12 个资金排程，组合收益待验证。'
        current_work['owners'].append(dict(name='美股现金并购',status='snapshot',
            task=merger_task))
    if pdbc_preflight:
        extra_sources['pdbc_risk_preflight']=PDBC_PREFLIGHT_RECEIPT
        losses='、'.join(f"{float(row['mark_change_hkd']):,.0f}" for row in pdbc_preflight['tiers'])
        current_work['owners'].append(dict(name='PDBC 商品 ETF',status='snapshot',
            task=f'2015 年两个价格端点由富途 OpenD 与 Yahoo 对照。在固定汇率下，1 万、2 万、3 万港币三档的整股市值变化分别约为 {losses} 港币，均低于 −20%。全仓持有未通过风险初筛。'))
    if ief_result:
        extra_sources['fomc_ief_account']=IEF_RESULT_RECEIPT
        current_work['owners'].append(dict(name='联储降息后的 IEF 持有检验',status='snapshot',
            task='双源、三档本金和两种分派预扣情景已核。9 个降息窗口对照 9 个维持利率窗口，24 个情景的平均匹配差额均为负，固定降息择时规则筛退。'))
    elif args.focus=='mining' and IEF_PREFLIGHT_RECEIPT.exists():
        ief=read(IEF_PREFLIGHT_RECEIPT)
        assert ief['decision']=='SOURCE_PILOT_ONLY_CASH_EVENTS_PENDING' and ief['return_tests']==0
        assert ief['pins']
        for path,expected in ief['pins'].items():
            source=(ROOT/path).resolve()
            assert source.is_relative_to(ROOT) and digest(source)==expected,path
        extra_sources['fomc_ief_preflight']=IEF_PREFLIGHT_RECEIPT
        current_work['owners'].append(dict(name='联储降息后的 IEF 持有检验',status='snapshot',
            task='已核三个预定降息日和一个维持决议。四个窗口的 8 个开盘端点均有两源报价，其中 1 个相差半美分。待补发行人现金事件，暂无收益结果。'))
    if merger and HK_NOV19_RECEIPT.exists():
        hkn=read(HK_NOV19_RECEIPT)
        assert hkn['observed'] is False and hkn['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in hkn['pins'].items())
        extra_sources['hk_03086_nov19_collection']=HK_NOV19_RECEIPT
        current_work['owners'].append(dict(name='03086 · 11月19日纸面',status='snapshot',
            task='收盘后连接本机富途 OpenD 超时，11 月 19 日未取得完整日线。纸面最后确认到 11 月 18 日，盘前登记缺口保留。'))
    elif merger:
        current_work['owners'].append(dict(name='03086 · 11月19日纸面',status='snapshot',
            task='香港时间09:00前的登记缺失。按11月18日可用资料只读核算，11月19日为非月度复核日，四组均持现金，规则未安排买卖。16:30才取完整日线。'))
    for name,file in [('continuous_goal','GOAL-CONTINUOUS-v2.md'),('restored_goal_receipt','GOAL-RESTORED-RECEIPT-v2.json')]:
        if (MINING/file).exists():extra_sources[name]=MINING/file
    for version,folder,review_file in [('v141','us-intraday-persistence-owner-20261117-v141','US-INTRADAY-v141-ROOT-REVIEW-v1.json'),
                                      ('v145','us-max-lottery-owner-20261117-v145','MAX-v145-ROOT-REVIEW-v1.json'),
                                      ('v147','us-dividend-yield-owner-20261118-v147','DIVIDEND-YIELD-v147-ROOT-REVIEW-v1.json')]:
        for file in ['RESULT-v1.json','PROTOCOL-v1.json','FINDINGS.md']:
            extra_sources[version+'_'+file]=ROOT/'reports'/folder/file
        extra_sources[version+'_root_review']=MINING/'acceptance'/review_file
    extra_sources['v145_root_verify']=MINING/'acceptance/MAX-v145-ROOT-VERIFY-v1.json'
    extra_sources['v147_root_verify']=MINING/'acceptance/DIVIDEND-YIELD-v147-ROOT-VERIFY-v1.json'
    residual_review=MINING/'acceptance/RESIDUAL-v151-ROOT-REVIEW-v1.json'
    if residual_review.exists():
        extra_sources['v151_root_review']=residual_review
        extra_sources['v151_result']=ROOT/'reports/us-next-factor-preparation-owner-20261118-v151/RESULT-v1.json'
        extra_sources['v151_protocol']=ROOT/'reports/us-next-factor-preparation-owner-20261118-v151/NEXT-PROTOCOL-v1.json'
        extra_sources['v151_root_verify']=MINING/'acceptance/RESIDUAL-v151-ROOT-VERIFY-v1.json'
    if vti_source_review.exists():extra_sources['v153_root_source_review']=vti_source_review
    if accepted_diversified_forward():
        extra_sources['v160_forward_root_review']=MINING/'acceptance/DIVERSIFIED-FORWARD-v157-v160-ROOT-REVIEW-v1.json'
        extra_sources['v160_package_freeze']=ROOT/'reports/us-diversified-forward-coordinator-20261118-v160/PACKAGE-FREEZE-v1.json'
        extra_sources['v160_root_acceptance']=ROOT/'reports/us-diversified-forward-coordinator-20261118-v160/ROOT-ACCEPTANCE-v1.json'
    if accepted_downside_review():
        extra_sources['v164_root_review']=MINING/'acceptance/DOWNSIDE-v164-ROOT-REVIEW-v1.json'
        extra_sources['v164_result']=ROOT/'reports/us-downside-risk-validation-owner-20261118-v164/RESULT-v1.json'
        extra_sources['v164_protocol']=ROOT/'reports/us-downside-risk-validation-owner-20261118-v164/PROTOCOL-v1.json'
    if accepted_intermediate_review():extra_sources['v177_root_review']=MINING/'acceptance/INTERMEDIATE-v177-ROOT-REVIEW-v1.json'
    if amihud:extra_sources['v186_root_review']=MINING/'acceptance/AMIHUD-v186-ROOT-REVIEW-v1.json'
    if accepted_peer_delay_review():extra_sources['v204_v207_root_review']=MINING/'acceptance/PEER-DELAY-v204-v207-ROOT-REVIEW-v1.json'
    if wrapper_source:extra_sources['v183_v184_root_review']=MINING/'acceptance/HK-USD-CASH-v183-v184-ROOT-REVIEW-v1.json'
    if wrapper_activity:extra_sources['v190_v191_root_review']=MINING/'acceptance/HK-USD-ACTIVITY-v190-v191-ROOT-REVIEW-v1.json'
    if tip_source_work:extra_sources['v192_tip_preparation']=MINING/'acceptance/TIP-PREP-v192-ROOT-REVIEW-v1.json'
    if tip_source_review:extra_sources['v193_v195_tip_source']=MINING/'acceptance/TIP-SOURCE-v193-v195-ROOT-REVIEW-v1.json'
    if tip_account_review:
        extra_sources['v196_v197_tip_account']=MINING/'acceptance/TIP-ACCOUNT-v196-v197-ROOT-REVIEW-v1.json'
        for key in ['result','primary_daily']:extra_sources['tip_accepted_'+key]=tip_accepted_file(tip_account_review,key)
        extra_sources['tip_B_preparation_protocol']=MINING/'tip-continuation-protocol-v198/PROTOCOL-v1.json'
    if tip_B_source_review:extra_sources['v198_v200_tip_B_source']=MINING/'acceptance/TIP-B-SOURCE-v198-v200-ROOT-REVIEW-v1.json'
    if tip_B_account_review:
        extra_sources['v201_v202_tip_B_account']=MINING/'acceptance/TIP-B-ACCOUNT-v201-v202-ROOT-REVIEW-v1.json'
        for key in ['result','primary_daily']:extra_sources['tip_B_accepted_'+key]=tip_accepted_file(tip_B_account_review,key)
    extra_sources['v148_root_review']=MINING/'acceptance/SGOV-QII-v148-ROOT-REVIEW-v1.json'
    extra_sources['v148_classification']=ROOT/'reports/us-cash-tax-fee-source-owner-20261118-v148/SGOV-QII-QUALIFICATION-v2.json'
    extra_sources['v148_source_findings']=ROOT/'reports/us-cash-tax-fee-source-owner-20261118-v148/SOURCE-FINDINGS-v1.md'
    if filing_event:
        for filename in ['FILING-SOURCE-v208-v210-ROOT-v1.json','FILING-EVENT-v211-ROOT-v1.json','FILING-EVENT-v211-EQUAL-OPPORTUNITY.json','FILING-SOURCE-v212-ROOT-v1.json','FILING-EVENT-v214-ROOT-v1.json']:
            path=MINING/'acceptance'/filename
            if path.exists():extra_sources[path.stem]=path
    extra_sources['v149_root_acceptance']=MINING/'acceptance/FORWARD-EVALUATION-v149-ROOT-ACCEPTANCE-v1.json'
    extra_sources['v149_root_completion']=MINING/'acceptance/FORWARD-EVALUATION-v149-ROOT-COMPLETION-v1.json'
    for key,filename in [('v170_layered_measurement','FORWARD-METHOD-v167-v170-ROOT-ACCEPTANCE-v1.json'),('v169_flot_preflight','FLOT-v169-ROOT-REVIEW-v1.json'),('v172_flot_source','FLOT-SOURCE-v172-ROOT-REVIEW-v1.json'),('v173_exit_measurement','FORWARD-EXIT-v171-v173-ROOT-REVIEW-v1.json'),('v175_flot_history','FLOT-ACCOUNT-v174-v175-ROOT-REVIEW-v1.json')]:
        path=MINING/'acceptance'/filename
        if path.exists():extra_sources[key]=path
    cash_addendum=MINING/'acceptance/HK-CASH-v176-ROOT-REVIEW-v1.json'
    if cash_addendum.exists():extra_sources['v176_hk_cash_source_addendum']=cash_addendum
    if diversified['activated']:extra_sources['v179_actual_paper_continuation']=DIVERSIFIED_RECEIPT
    if diversified['activated']:extra_sources['latest_actual_paper_continuation']=ROOT/diversified['root_receipt']
    if next_factor:
        for name in ['PROTOCOL-v1.json','RUN-START-v1.json','OUTPUT-MANIFEST-v1.json']:
            candidate_path=ROOT/'reports/next-factor-candidate-owner-20261118-v204'/name
            if candidate_path.exists():extra_sources['v204_progress_'+name]=candidate_path
    extra_sources['v144_protocol']=ROOT/'reports/us-diversified-carry-owner-20261117-v144/PROTOCOL-v1.json'
    extra_sources['v144_conditional_use']=MINING/'portfolio-source-v144/CONDITIONAL-USE-v1.md'
    portfolio_review=MINING/'acceptance/DIVERSIFIED-v144-A-ROOT-REVIEW-v2.json'
    if portfolio_review.exists():
        extra_sources['v144_A_root_review_v2']=portfolio_review
        extra_sources['v144_A_summaries_v2']=ROOT/'reports/us-diversified-carry-owner-20261117-v144/A-v2/ALL-A-SUMMARIES-v2.json'
        extra_sources['v144_A_primary_result_v2']=ROOT/'reports/us-diversified-carry-owner-20261117-v144/A-v2/accounts/A_main_HKD30000_pressure/result.json'
        extra_sources['v144_fee_scenario_clarification']=MINING/'acceptance/FEE-SCENARIO-CLARIFICATION-v1.md'
        extra_sources['v144_A_concentration']=MINING/'acceptance/DIVERSIFIED-v144-A-CONCENTRATION-v1.json'
    b_review_path=MINING/'acceptance/DIVERSIFIED-v144-B-ROOT-REVIEW-v1.json'
    if b_review_path.exists():
        extra_sources['v144_B_root_review']=b_review_path
        extra_sources['v144_B_summaries']=ROOT/'reports/us-diversified-carry-owner-20261117-v144/B-v1/ALL-B-SUMMARIES-v1.json'
    c_review_path=MINING/'acceptance/DIVERSIFIED-v144-C-ROOT-REVIEW-v1.json'
    if c_review_path.exists():
        extra_sources['v144_C_root_review']=c_review_path
        extra_sources['v144_ABC_total']=ROOT/'reports/us-diversified-carry-owner-20261117-v144/C-v1/ABC-TOTAL-v1.json'
    if archive:extra_sources['old_catalog']=archived
    if gld_path.exists():extra_sources['us_gld_fixed']=gld_path
    if sgov:
        extra_sources.update(sgov_history_review=MINING/'sgov-review/FINAL-REVIEW-v1.json',
                             sgov_missed_entry=MINING/'sgov-sensitivity-v1/RESULT.json',
                             sgov_history_chart=MINING/'sgov-review/SGOV-history-v1.png')
    source_folder=ROOT/'reports/us-action-panel-owner-20261117-v137'
    for p in source_folder.glob('CAPTURE-RECEIPT-v*.json'):extra_sources['source_'+p.stem]=p
    if (source_folder/'QUALIFICATION-v1.json').exists():extra_sources['us_action_panel_qualification']=source_folder/'QUALIFICATION-v1.json'
    if (SGOV_PACKET/'ROOT-ACCEPTANCE-v1.json').exists():
        extra_sources['sgov_paper_root_acceptance']=SGOV_PACKET/'ROOT-ACCEPTANCE-v1.json'
        extra_sources['sgov_paper_policy']=SGOV_PACKET/'POLICY-v1.json'
    if (MINING/'sgov-review/PAPER-ACTIVATION-ACCEPTANCE-v1.json').exists():
        extra_sources['sgov_real_paper_activation']=MINING/'sgov-review/PAPER-ACTIVATION-ACCEPTANCE-v1.json'
    # These legacy rows used the export day as source_date. Keep the published date
    # when their actual content is unchanged, so a refresh is not new evidence.
    legacy_dates=ROOT/'reports/research-tip-continuation-dashboard-owner-20261118-v203/BASELINE-SNAPSHOT-V22.json'
    if legacy_dates.exists():
        original={r['id']:r for r in read(legacy_dates)['registry']}
        for row in registry:
            before=original.get(row['id'])
            if row['id'].startswith(('team-','signal-note-')) and before and \
               {k:v for k,v in row.items() if k!='source_date'}=={k:v for k,v in before.items() if k!='source_date'}:
                row['source_date']=before['source_date']
        extra_sources['published_V22_legacy_record_dates']=legacy_dates
    if southbound:
        extra_sources['hk_southbound_first_eligibility']=SOUTHBOUND_RECEIPT
        march_checked='march_controls' in southbound
        if march_checked:
            extra_sources['hk_southbound_march_matching']=SOUTHBOUND_MARCH_RECEIPT
        if 'control_closeout' in southbound:
            extra_sources['hk_southbound_control_closeout']=HK_CONTROL_CLOSEOUT
        current_work['owners'].insert(0,dict(name='港股通首次开放买入',status='snapshot',
            task=('3 月同批 14 只均已复原沪深资格。上市龄筛后 8 只，再按成交额筛至 4 只。待核当时的行业、指数市值分组和自由流通市值。'
                  if march_checked else '沪深两案各核到一次调入。已算开盘整手与回本门槛。同批指数对照的行业、规模、成交额及事前资格待核。')))
        if 'control_closeout' in southbound:
            current_work['owners'][0]['task']='3 月 4 只通过成交额筛选的对照均不符行业或市值分组。9 月唯一同组对照的富途成交额为目标的 2.0050 倍，超过 2 倍上限。两批均无合格配对，未检验收益。'
    if args.focus=='mining' and ISSUER_TENDER_RECEIPT.exists():
        tender=read(ISSUER_TENDER_RECEIPT)
        assert tender['qualified_candidates']==tender['return_tests']==0 and tender['pins']
        for name,expected in tender['pins'].items():
            path=(ROOT/name).resolve()
            assert path.is_relative_to(ROOT) and digest(path)==expected,name
        extra_sources['us_issuer_tender_preflight']=ISSUER_TENDER_RECEIPT
        current_work['owners'].insert(1,dict(name='美股发行人现金要约',status='snapshot',task=(
            f"SEC 一季度 {tender['q1_initial']} 份初始要约已登记。1 月 {tender['january_initial']} 份中 "
            f"{tender['january_source_excluded']} 份已由原件排除，{tender['january_unknown']} 份仍待核固定价格及不足百股优先条款。")))
    if args.focus=='mining' and TENDER_CLOSEOUT.exists():
        t=read(TENDER_CLOSEOUT)
        assert t['january_initial']==t['january_source_excluded']==38 and t['january_unknown']==t['return_tests']==t['qualified_candidates']==0
        assert all(digest(ROOT/path)==expected for path,expected in t['pins'].items())
        extra_sources['us_issuer_tender_closeout']=TENDER_CLOSEOUT
        current_work['owners'][1]['task']='第一季度登记 151 宗。1 月 38 宗全部排除。3 月 RBNE 原件确认每股 3 美元现金及最多 99 股的优先条款，富途办理和买入后资格待证。尚无通过资格的候选或收益检验。'
    if args.focus=='mining' and TENDER_COVERAGE.exists():
        tc=read(TENDER_COVERAGE)
        te=read(TENDER_EXECUTION)
        for receipt in (tc,te):
            assert receipt['qualified_candidates']==receipt['return_tests']==receipt['actual_orders']==0
            assert all(digest(ROOT/path)==expected for path,expected in receipt['pins'].items())
        extra_sources['us_issuer_tender_coverage']=TENDER_COVERAGE
        extra_sources['us_issuer_tender_execution']=TENDER_EXECUTION
        tf=tc['february']
        feb=(f"2 月 {tf['total']} 宗排除 {tf['excluded']} 宗，{tf['unknown']} 宗未知。"
             if tf['delivered'] else '2 月 63 宗仍在核原件。')
        current_work['owners'][1]['task']=(
            '第一季度登记 151 宗。1 月 38 宗全部排除。'+feb+
            '3 月 50 宗排除 49 宗，只留 RBNE 条款候选，富途办理待证。')
        current_work['owners'].insert(2,dict(name='不足百股要约 · 富途与税费',status='snapshot',
            task='富途曾受理 2023 年 Docebo 的 99 股优先申报，该次券商截止比发行人早 8 天 14 小时。另核 2026 年 Docebo 的跨境申报：20.40 美元定价在 15% 预扣税情景下折至约 18.56 美元，低于正式要约后的参考开盘 19.26 美元。尚无通过账户资格的案例或收益检验。'))
    if args.focus=='mining' and TENDER_BROKER.exists():
        tb=read(TENDER_BROKER)
        assert tb['return_tests']==tb['qualified_candidates']==tb['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in tb['pins'].items())
        extra_sources['us_issuer_tender_broker_first']=TENDER_BROKER
        current_work['owners'].insert(3,dict(name='富途专属公告抽查',status='snapshot',
            task='5 宗历史通知中，4 宗初始价格不固定。2023 年 Docebo 每股 55 美元回购，假设对视同股息部分预扣 15%，估算每股到手 47.95 美元，低于 49.18 和 48.37 美元两个开盘参考。三档本金均未过门槛，未计券商费。RBNE 仍待事件专属证据。'))
    next_exec=MINING/'acceptance/EXECUTION-NEW-MECHANISMS-v281-v282-ROOT-v1.json'
    if args.focus=='mining' and next_exec.exists():
        e=read(next_exec)
        assert e['return_tests']==e['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in e['pins'].items())
        extra_sources['new_execution_mechanisms']=next_exec
        current_work['owners'][4:4]=[
            dict(name='港股 03115 · 月度波动筛选',status='snapshot',
                 task='60 个月仅 44 个月具合格信号，16 个月因收盘时段成交数据缺口未知。按原开盘价、未扣费且有正成交字段，1 万／2 万／3 万档名义可负担 47／59／59 个月。未做收益检验。下一步查官方恒指总收益数据。'),
            dict(name='美股 SPY · 失业率信号筛选',status='snapshot',
                 task='2020–2025 年可见 15 个信号达标月，却只集中于 2 次独立触发，低于事先设定的 3 次。没有运行 SPY 收益回测。')]
    benchmark_breadth=MINING/'acceptance/VOLATILITY-BENCHMARK-AND-US-BREADTH-v287-v290-ROOT-v1.json'
    if args.focus=='mining' and benchmark_breadth.exists():
        b=read(benchmark_breadth)
        assert b['new_paper_accounts']==b['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in b['pins'].items())
        extra_sources['benchmark_and_us_breadth']=benchmark_breadth
        current_work['owners'][6:6]=[
            dict(name='港股 03115 · 独立基准信号',status='snapshot',
                 task='BlackRock 的历史基准覆盖 60 个窗口。2017–2021 年图表指示 55 月持有、5 月持现金，次月第二交易日执行字段有 2 月异常。净总收益基准的身份和发布制度已核，逐日网页历史取值时点仍待证。未做 03115 账户收益回测。'),
            dict(name='美股 VTI＋GLD · 双确认',status='snapshot',
                 task='2021–2023 年开发段压力成本后，1 万／2 万／3 万档净变动分别 −450.72／−85.28／+271.31 港币，三档均落后同参数 VTI 单确认。分派到账为情景，留存期未读，筛退。')]
    odd_lot_gate=MINING/'acceptance/HK-BENCHMARK-ODD-LOT-v289-v290-ROOT-v1.json'
    if args.focus=='mining' and odd_lot_gate.exists():
        o=read(odd_lot_gate)
        assert o['return_tests']==o['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in o['pins'].items())
        extra_sources['hk_benchmark_odd_lot_gate']=odd_lot_gate
        current_work['owners'].insert(8,dict(name='港股 03115 · 历史碎股退出',status='snapshot',
            task='2019 年每手 10 份改为 100 份。按预先固定的规则和两套成本，2020 年 4 月 2 日必要退出时，1 万／2 万／3 万档各余 20／50／80 份碎股。缺历史碎股可执行报价，6 个情景均无法完成账户回放。'))
    tracker_vol=MINING/'acceptance/HK-TRACKER-VOLATILITY-v293-v296-ROOT-v1.json'
    if args.focus=='mining' and tracker_vol.exists():
        tr=read(tracker_vol)
        assert tr['new_paper_accounts']==tr['orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in tr['pins'].items())
        extra_sources['hk_tracker_volatility']=tracker_vol
        current_work['owners'][9:9]=[
            dict(name='港股 02800 · 恒指波动策略',status='snapshot',
                 task='2017–2021 年，1 万港币在 60 个预定开盘都不足一手。2 万／3 万档压力成本后分别 −340.11／−80.22 港币，收盘回撤 22.91%／27.34%，均劣于同档持续持有。固定规则筛退，留存期未运行。'),
            dict(name='美股 VTI · 单确认对照复核',status='snapshot',
                 task='六个月规则与旧 SMA200 在 36 月中有 30 月同方向；三年派息总额获发行人年报佐证，逐次派息到账证据未补齐。保持开发期对照，不开新纸面。')]
    quarter_pilots=MINING/'acceptance/QUARTER-END-PILOTS-v301-v302-ROOT-v1.json'
    if args.focus=='mining' and quarter_pilots.exists():
        q=read(quarter_pilots)
        assert q['new_paper_accounts']==q['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in q['pins'].items())
        extra_sources['hk_us_quarter_end_pilots']=quarter_pilots
        current_work['owners'][11:11]=[
            dict(name='港股 03033 · 季末三日窗口',status='snapshot',
                 task='2021–2023 年季末相对同季普通月毛差 +68.16 基点；12 次机会、8 次模型成交。1 万／2 万／3 万档压力净变动 −397.94／−268.61／−84.40 港币，固定规则筛退。'),
            dict(name='美股 VTI／IEF · 季末再平衡',status='snapshot',
                 task='开发段 11 个窗口仅触发 1 次，原开盘至开盘 −136.28 基点。三档压力净变动 −301.94／−565.22／−828.58 港币，均低于美元现金对照。两条规则的留存期均未运行。')]
    longer_hold=MINING/'acceptance/LONGER-HOLD-PILOTS-v304-v307-ROOT-v1.json'
    if args.focus=='mining' and longer_hold.exists():
        q=read(longer_hold)
        assert q['new_paper_accounts']==q['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in q['pins'].items())
        extra_sources['hk_us_longer_hold_pilots']=longer_hold
        current_work['owners'][13:13]=[
            dict(name='港股 03033／03081 · 固定配置',status='snapshot',
                 task='2021–2023 年，各投入一半且不调仓。1 万／2 万／3 万档压力净变动 −1666.22／−4128.91／−6595.17 港币；最大收盘回撤 33.55%／40.07%／42.17%。两腿都买得起，但净收益和风险均未过门槛。'),
            dict(name='美股 SGOV／VTI／GLD · 调仓门槛',status='snapshot',
                 task='月度偏离 5 个百分点才调仓。1 万档 32 次触发却没有调仓；2 万／3 万档压力净额虽为正，均低于买入后持有的同成本对照。固定规则筛退，留存期未跑。')]
    recovery_pilots=MINING/'acceptance/RECOVERY-PILOTS-v309-v312-ROOT-v1.json'
    if args.focus=='mining' and recovery_pilots.exists():
        q=read(recovery_pilots)
        assert q['new_paper_accounts']==q['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in q['pins'].items())
        extra_sources['hk_us_recovery_pilots']=recovery_pilots
        current_work['owners'][15:15]=[
            dict(name='港股 03033 · 月度修复',status='snapshot',
                 task='2021–2023 年 3 次信号，压力情景仅 1 次完整持有，另有一次入场参考价超过限价。1 万／2 万／3 万档压力净变动 −332.42／−592.80／−855.83 港币，均低于现金。'),
            dict(name='美股 VTI · 急跌后三日反弹',status='snapshot',
                 task='2021–2023 年 6 次触发，剩 3 次非重叠机会，三次原始收益均为负，平均 −215.58 基点。三档压力净变动 −503.33／−898.71／−1246.04 港币。两条规则均筛退，留存期未运行。'),
            dict(name='港股 02823 · 月末汇率来源',status='snapshot',
                 task='原定 TMA 同时点定盘仍为 0／85 个合格月末。港交所免费结算文件仅 23／85 个月末取得 ZIP 文件头，且期货交收口径不同。8 个分派实付日均匹配金管局收盘换汇参考，可用于现金敏感度。')]
    frequent_mechanisms=MINING/'acceptance/FREQUENT-MECHANISMS-v315-v318-ROOT-v1.json'
    if args.focus=='mining' and frequent_mechanisms.exists():
        q=read(frequent_mechanisms)
        assert q['new_paper_accounts']==q['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in q['pins'].items())
        extra_sources['hk_us_frequent_mechanisms']=frequent_mechanisms
        current_work['owners'][15:15]=[
            dict(name='港股 03033 · 低开修复',status='snapshot',
                 task='493 日有 10 次低开后收复昨收，压力成本下只完成 7 笔。1 万／2 万／3 万档净变动 +1.47／+515.33／+1111.54 港币，各档减去最大盈利一笔后均转负，样本未达门槛。'),
            dict(name='港股 03067 · 净值折价',status='snapshot',
                 task='36 个互不重叠窗口，对同资产同季配对毛差 +266.02 基点。三档压力每笔平均 −59.18／−49.47／−40.46 港币，均为负。净值网页首次发布时间仍未核实。'),
            dict(name='美股 VTI · 跌破前低后收复',status='snapshot',
                 task='37 次非重叠，原价毛均 −25.30 基点，低于同期 VTI 全部日内均值 −2.49 基点。三档压力净变动 −2840.17／−3600.24／−4347.88 港币。三条规则均筛退，留存期未运行。')]
    cost_first=MINING/'acceptance/COST-FIRST-v320-v323-ROOT-v1.json'
    if args.focus=='mining' and cost_first.exists():
        q=read(cost_first)
        assert q['new_paper_accounts']==q['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in q['pins'].items())
        extra_sources['small_capital_cost_first']=cost_first
        current_work['owners'][15:15]=[
            dict(name='港美 ETF · 小账户保本门槛',status='snapshot',
                 task='同一历史日开盘示例，1 万档压力保本涨幅：03033／03067 约 2.22%，VTI／GLD 约 1.90%／2.32%（复用美元）。价格档、整手与平台费均计入。'),
            dict(name='港股 03033 · 相对宽基放量',status='snapshot',
                 task='37 次放量越阈，15 个非重叠的 20 日窗口，毛均 −36.82 基点，一万初始压力摩擦中位 141.24 基点。三档压力净变动 −3446.40／−6864.97／−10301.61 港币，回撤约 50%，固定规则筛退。'),
            dict(name='美股 GLD · 避险状态切换',status='snapshot',
                 task='持有 20 个交易日，共 11 笔，毛均 −93.04 基点，低于 GLD 同长滚动基准 +26.97 基点。三档压力净变动 −1138.96／−1725.64／−2355.40 港币。两条候选均未运行留存。')]
    flows_rates=MINING/'acceptance/FUND-FLOWS-RATES-v325-v328-ROOT-v1.json'
    if args.focus=='mining' and flows_rates.exists():
        q=read(flows_rates)
        assert q['new_paper_accounts']==q['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in q['pins'].items())
        extra_sources['fund_flows_and_rates']=flows_rates
        current_work['owners'][15:15]=[
            dict(name='港股 02823 · 净创设公告',status='snapshot',
                 task='84 个月实际公告时点已核。发行人历史工作簿与原公告有 34 月余额差异。18 个完整窗口只剩 17 个非重叠，低于预设 18 个，停在来源和次数筛。'),
            dict(name='美股 IEF · 国债曲线走陡',status='snapshot',
                 task='8 个非重叠窗口，配对毛差 +61.42 基点，低于一万压力摩擦 88.42 基点。三档压力净变动 −127.55／+281.43／+665.26 港币，漏掉最高毛收益一笔后三档都亏。'),
            dict(name='美股 FLOT · 半年净息开关',status='snapshot',
                 task='一万和两万档压力均零持仓。三万档仅一段，净 +248.73 港币，低于静持 +345.19 港币。两条美股候选均筛退，留存未运行。')]
    weekly_creations=MINING/'acceptance/WEEKLY-FUND-CREATIONS-v331-v335-ROOT-v1.json'
    if args.focus=='mining' and weekly_creations.exists():
        q=read(weekly_creations)
        assert q['new_paper_accounts']==q['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in q['pins'].items())
        extra_sources['weekly_fund_creations']=weekly_creations
        current_work['owners'][15:15]=[
            dict(name='港股 02823 · 周净创设',status='snapshot',
                 task='周末份额取到 361／365。23 个非重叠窗口相对同资产配对毛差 −15.11 基点。三档各成交 15 笔，压力净变动 −1817.92／−2582.71／−3253.94 港币。纳入停市日已发布原件后覆盖 365／365，账面结果相同。'),
            dict(name='美股 GLD · 东京份额公告',status='snapshot',
                 task='东京 1326 与纽约 GLD 对应同一信托。交易所验证三个连续周末份额与实际刊登时点，周差 −10 万／+120 万股。本轮未核长历史覆盖，尚未计算策略收益。')]
    gold_filings=MINING/'acceptance/GOLD-FLOW-COVERAGE-v337-v340-ROOT-v1.json'
    if args.focus=='mining' and gold_filings.exists():
        q=read(gold_filings)
        assert q['new_paper_accounts']==q['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in q['pins'].items())
        extra_sources['gold_flow_historical_coverage']=gold_filings
        current_work['owners'][15:15]=[
            dict(name='美股 GLD · 东京历史公告',status='snapshot',
                 task='两条免费官方查询路线核到 2021 首季 0／12 合格周末。近期原件和 2021 半年报仍可读取，历史逐周原件及刊登时分尚未取得。'),
            dict(name='美股 GLD · SEC 季度净份额',status='snapshot',
                 task='37 个报告期末份额独立通过原 accession，公告滞后中位 38 天。10 次信号原价毛均 −43.99 基点，只有 2 对中性配对；三档压力净额 −992.20／−1417.30／−1785.20 港币，开发筛退。'),
            dict(name='港股 03081 · 黄金份额原表',status='snapshot',
                 task='2021 首季 12／12 周末及期初基线取得原表，2021–2023 年索引有 724 条日公告。三柜台合计份额只计一次、一万满预算压力保本中位约 1.34%。尚未计算该规则的收益。')]
    listed_gold=MINING/'acceptance/LISTED-GOLD-CREATION-AND-CFTC-v343-v346-ROOT-v1.json'
    if args.focus=='mining' and listed_gold.exists():
        q=read(listed_gold)
        assert q['new_paper_accounts']==q['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in q['pins'].items())
        extra_sources['listed_gold_and_cftc_clock']=listed_gold
        current_work['owners'][15:15]=[
            dict(name='港股 03081 · 上市份额四周净创设',status='snapshot',
                 task='155／156 个周末可追原件，148 个四周变化中只确认 1 次穿越。三档压力净变动 −78.42／−90.26／−102.37 港币。把所有未知日期都算作信号也最多 11 次，低于预设 12 次。'),
            dict(name='美股研究 · 黄金 CFTC 首发版本',status='snapshot',
                 task='2018–2023 年 313／313 观察周齐全，两条官方数据渠道一致。仅核到 10 个实际发布日期，已见黄金历史值在首发后更正。全期首发时间及版本待证，未计算收益。'),
            dict(name='美股研究 · Cboe 波动率期限',status='snapshot',
                 task='2015–2023 年 2264 个美股交易日均取得 VIX 与 VIX3M。VIX 另有 12 个股票停市日数据，后续不能据此模拟当日股票成交。当前只验证来源覆盖。')]
    vix_rule=MINING/'acceptance/VIX-CURVE-VTI-v349-v352-ROOT-v1.json'
    if args.focus=='mining' and vix_rule.exists():
        q=read(vix_rule)
        assert q['new_paper_accounts']==q['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in q['pins'].items())
        extra_sources['vix_curve_vti_historical']=vix_rule
        current_work['owners'][15:15]=[
            dict(name='美股 VTI · VIX 期限倒挂月度规则',status='snapshot',
                 task='108 次决策、7 段目标现金。1 万／2 万／3 万压力净额 +3098.00／+6935.01／+10930.81 港币，回撤约 11.5%，但只保留静持净收益的 58.54%–61.33%，规则筛退。'),
            dict(name='美股 VIX 期限 · 历史版本与归因',status='snapshot',
                 task='92／108 次决策的指数值有开盘前日期级记录。9 个目标现金月 VTI 有 6 个上涨，平均原价涨约 2.00%。1 万档日均实际股票比重 35.26%，静持 50.88%。留存未运行。'),
            dict(name='美股 USMV · 低波宽基分派资料',status='snapshot',
                 task='从发行人同一基金原表核对 2015–2023 年 37 条分派的除息、登记、支付日期及金额。')]
        if q.get('hk_source_review_complete'):
            current_work['owners'].insert(17,dict(name='港股 VHSI · 香港波动率资料',status='snapshot',task=q['hk_site_summary']))
    usmv_receipt=MINING/'acceptance/USMV-RISK-v355-v358-ROOT-v1.json'
    if args.focus=='mining' and usmv_receipt.exists():
        q=read(usmv_receipt)
        assert q['new_paper_accounts']==q['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in q['pins'].items())
        extra_sources['usmv_risk_historical']=usmv_receipt
        current_work['owners'][15:15]=[
            dict(name='美股 USMV · 低波 ETF 同预算静持',status='snapshot',task=q['account_site_summary']),
            dict(name='美股 USMV · 价格与账户复核',status='snapshot',task=q['audit_site_summary']),
            dict(name='美股 QUAL · 质量因子来源',status='snapshot',task=q['qual_site_summary'].split('下一步',1)[0])]
        if q.get('hk_site_summary'):
            current_work['owners'].insert(17,dict(name='港股低波 · 上市产品核查',status='snapshot',task=q['hk_site_summary']))
        activity_text='USMV 静持已复算并筛退。接下来核对 QUAL 历史价格的股份单位。 '+activity_text
    qual_receipt=MINING/'acceptance/QUAL-AND-HK-PIT-v361-v366-ROOT-v1.json'
    if args.focus=='mining' and qual_receipt.exists():
        q=read(qual_receipt)
        assert q['new_paper_accounts']==q['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in q['pins'].items())
        extra_sources['qual_historical_and_hk_point_in_time']=qual_receipt
        current_work['owners'][15:15]=[
            dict(name='美股 QUAL · 冻结限价与换汇',status='snapshot',task=q['frozen_site_summary']),
            dict(name='美股 QUAL · 假定开盘成交',status='snapshot',task=q['control_site_summary']),
            dict(name='美股 QUAL · 旧单位和独立核算',status='snapshot',task=q['audit_site_summary']),
            dict(name='港股质量 · 挂牌状态与历史股票池',status='snapshot',task=q['hk_site_summary'])]
        activity_text='QUAL 历史测试已结案，开始扩充港股质量因子的时点财报与历史股票池。 '+activity_text.replace(
            'USMV 静持已复算并筛退。接下来核对 QUAL 历史价格的股份单位。 ', '')
    hk_quality_annual=MINING/'acceptance/HK-QUALITY-ANNUAL-v367-v370-ROOT-v1.json'
    if args.focus=='mining' and hk_quality_annual.exists():
        q=read(hk_quality_annual)
        assert q['new_paper_accounts']==q['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in q['pins'].items())
        extra_sources['hk_quality_annual_public_source']=hk_quality_annual
        current_work['owners'][15:15]=[
            dict(name='港股质量 · 年度原件和披露分钟',status='snapshot',task=q['annual_site_summary']),
            dict(name='港股质量 · 五年基本 EPS',status='snapshot',task=q['eps_site_summary']),
            dict(name='港股质量 · 旧财报档复用',status='snapshot',task=q['archive_site_summary'])]
        activity_text='港股质量因子已核一批时点财报，正在排查多期数据及报表口径。 '+activity_text.replace(
            'QUAL 历史测试已结案，开始扩充港股质量因子的时点财报与历史股票池。 ', '')
    hk_quality_sector=MINING/'acceptance/HK-QUALITY-SECTORS-v373-v376-ROOT-v1.json'
    if args.focus=='mining' and hk_quality_sector.exists():
        q=read(hk_quality_sector)
        assert q['new_paper_accounts']==q['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in q['pins'].items())
        extra_sources['hk_quality_sector_and_board_lot']=hk_quality_sector
        current_work['owners'][15:15]=[
            dict(name='港股质量 · 两个时点跨行业财报',status='snapshot',task=q['financial_site_summary']),
            dict(name='港股质量 · 六只股票整手容量',status='snapshot',task=q['capacity_site_summary']),
            dict(name='美股 COWZ · 自由现金流来源',status='snapshot',task=q['cowz_site_summary'])]
        activity_text='港股跨行业财报与整手容量已核。下一项准备核 COWZ 原价和现金分派。 '+activity_text.replace(
            '港股质量因子已核一批时点财报，正在排查多期数据及报表口径。 ', '')
    cowz_result=MINING/'acceptance/COWZ-AND-HK-LOTS-v379-v382-ROOT-v1.json'
    if args.focus=='mining' and cowz_result.exists():
        q=read(cowz_result)
        assert q['new_paper_accounts']==q['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in q['pins'].items())
        extra_sources['cowz_and_hk_lots']=cowz_result
        current_work['owners'][15:15]=[
            dict(name='美股 COWZ · 半仓开发账户',status='snapshot',task=q['half_site_summary']),
            dict(name='美股 COWZ · 四成预算留存准备',status='snapshot',task=q['reduced_site_summary']),
            dict(name='美股 COWZ · 报价与分派复核',status='snapshot',task=q['audit_site_summary']),
            dict(name='港股质量 · 扩大整手筛选',status='snapshot',task=q['hk_site_summary'])]
        activity_text='COWZ 半仓筛退，四成预算已在已见历史完成诊断，正在核验 2024 留存来源。 '+activity_text.replace(
            '港股跨行业财报与整手容量已核。下一项准备核 COWZ 原价和现金分派。 ', '')
    cowz_holdout=MINING/'acceptance/COWZ-2024-v385-v388-ROOT-v1.json'
    cowz_holdout_activity=''
    if args.focus=='mining' and cowz_holdout.exists():
        q=read(cowz_holdout)
        assert q['new_paper_accounts']==q['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in q['pins'].items())
        extra_sources['cowz_2024_holdout']=cowz_holdout
        current_work['owners'][15:15]=[
            dict(name='美股 COWZ · 2024 年冻结留存',status='snapshot',task=q['holdout_site_summary']),
            dict(name='美股 COWZ · 基准和漏单复核',status='snapshot',task=q['comparison_site_summary'])]
        cowz_holdout_activity=q['activity_site_summary']+' '
        activity_text=cowz_holdout_activity+activity_text.replace(
            'COWZ 半仓筛退，四成预算已在已见历史完成诊断，正在核验 2024 留存来源。 ', '')
    bank_reit=MINING/'acceptance/HK-BANK-REIT-v390-v393-ROOT-v1.json'
    bank_reit_activity=''
    if args.focus=='mining' and bank_reit.exists():
        h=read(bank_reit)
        assert h['new_paper_accounts']==h['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in h['pins'].items())
        extra_sources['hk_bank_reit_calibration']=bank_reit
        current_work['owners'][15:15]=[
            dict(name='港股中行＋领展 · 合费整手',status='snapshot',task=h['budget_site_summary']),
            dict(name='港股中行＋领展 · 两段静持诊断',status='snapshot',task=h['account_site_summary']),
            dict(name='港股领展 · 供股与除净',status='snapshot',task=h['action_site_summary'])]
        if cowz_holdout_activity:
            activity_text=activity_text.removeprefix(cowz_holdout_activity)
        bank_reit_activity=h['activity_site_summary']+' '
        activity_text=bank_reit_activity+activity_text
    hk_preopen=MINING/'acceptance/HK-PREOPEN-LOT-v396-v401-ROOT-v1.json'
    hk_preopen_activity=''
    if args.focus=='mining' and hk_preopen.exists():
        h=read(hk_preopen)
        assert h['new_paper_accounts']==h['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in h['pins'].items())
        extra_sources['hk_preopen_lot_screen']=hk_preopen
        current_work['owners'][15:15]=[
            dict(name='港股 · 开盘限价与整手预筛',status='snapshot',task=h['gate_site_summary']),
            dict(name='港股 · 历史股票池扩样',status='snapshot',task=h['universe_site_summary']),
            dict(name='港股金融 · 126 日下行风险',status='snapshot',task=h['factor_site_summary'])]
        if bank_reit_activity:
            activity_text=activity_text.removeprefix(bank_reit_activity)
        hk_preopen_activity=h['activity_site_summary']+' '
        activity_text=hk_preopen_activity+activity_text
    hk_industry_signal=MINING/'acceptance/HK-INDUSTRY-SIGNAL-v402-v405-ROOT-v1.json'
    hk_industry_signal_activity=''
    if args.focus=='mining' and hk_industry_signal.exists():
        h=read(hk_industry_signal)
        assert h['new_paper_accounts']==h['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in h['pins'].items())
        extra_sources['hk_industry_downside_signal']=hk_industry_signal
        current_work['owners'][15:15]=[
            dict(name='港股工商 · 127 日双源原收',status='snapshot',task=h['price_site_summary']),
            dict(name='港股工商 · 发行人公司行动',status='snapshot',task=h['action_site_summary']),
            dict(name='港股工商 · 冻结下行信号',status='snapshot',task=h['signal_site_summary'])]
        if hk_preopen_activity:
            activity_text=activity_text.removeprefix(hk_preopen_activity)
        hk_industry_signal_activity=h['activity_site_summary']+' '
        activity_text=hk_industry_signal_activity+activity_text
    hk_industry_peers=MINING/'acceptance/HK-INDUSTRY-PEERS-v409-v415-ROOT-v1.json'
    hk_industry_peer_activity=''
    if args.focus=='mining' and hk_industry_peers.exists():
        h=read(hk_industry_peers)
        assert h['new_paper_accounts']==h['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in h['pins'].items())
        extra_sources['hk_industry_peer_accounts']=hk_industry_peers
        current_work['owners'][15:15]=[
            dict(name='港股工商 · 13 账户同期基准',status='snapshot',task=h['benchmark_site_summary']),
            dict(name='港股工商 · 同期账本独立复核',status='snapshot',task=h['ledger_site_summary']),
            dict(name='港股工商 · 2022 历史留出准备',status='snapshot',task=h['holdout_site_summary'])]
        if hk_industry_signal_activity:
            activity_text=activity_text.removeprefix(hk_industry_signal_activity)
        hk_industry_peer_activity=h['activity_site_summary']+' '
        activity_text=hk_industry_peer_activity+activity_text
    hk_industry_holdout=MINING/'acceptance/HK-INDUSTRY-HOLDOUT-v416-v420-ROOT-v1.json'
    hk_industry_holdout_activity=''
    if args.focus=='mining' and hk_industry_holdout.exists():
        h=read(hk_industry_holdout)
        assert h['new_paper_accounts']==h['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in h['pins'].items())
        extra_sources['hk_industry_first_holdout']=hk_industry_holdout
        current_work['owners']=[owner for owner in current_work['owners']
                                if owner['name']!='港股工商 · 2022 历史留出准备']
        current_work['owners'][15:15]=[
            dict(name='港股工商 · 2022 首个留出结果',status='snapshot',task=h['holdout_site_summary']),
            dict(name='港股工商 · 留出与开发窗口对照',status='snapshot',task=h['comparison_site_summary']),
            dict(name='港股工商 · 两万及三万档准备',status='snapshot',task=h['coverage_site_summary'])]
        if hk_industry_peer_activity:
            activity_text=activity_text.removeprefix(hk_industry_peer_activity)
        hk_industry_holdout_activity=h['activity_site_summary']+' '
        activity_text=hk_industry_holdout_activity+activity_text
    hk_industry_capitals=MINING/'acceptance/HK-INDUSTRY-LARGER-HOLDOUT-v422-v427-ROOT-v1.json'
    hk_industry_capital_activity=''
    if args.focus=='mining' and hk_industry_capitals.exists():
        h=read(hk_industry_capitals)
        assert h['new_paper_accounts']==h['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in h['pins'].items())
        extra_sources['hk_industry_larger_holdout']=hk_industry_capitals
        current_work['owners']=[owner for owner in current_work['owners']
                                if owner['name']!='港股工商 · 两万及三万档准备']
        current_work['owners'][15:15]=[
            dict(name='港股工商 · 两万港币留出结果',status='snapshot',task=h['capital20_site_summary']),
            dict(name='港股工商 · 三万港币留出结果',status='snapshot',task=h['capital30_site_summary']),
            dict(name='港股工商 · 外币分派及应收复核',status='snapshot',task=h['fx_site_summary']),
            dict(name='港股ETF · 固定月份假设',status='snapshot',task=h['next_candidate_site_summary'])]
        if hk_industry_holdout_activity:
            activity_text=activity_text.removeprefix(hk_industry_holdout_activity)
        hk_industry_capital_activity=h['activity_site_summary']+' '
        activity_text=hk_industry_capital_activity+activity_text
    hk_seasonal=MINING/'acceptance/HK-ETF-SEASONAL-v431-v438-ROOT-v1.json'
    hk_seasonal_activity=''
    if args.focus=='mining' and hk_seasonal.exists():
        h=read(hk_seasonal)
        assert h['new_paper_accounts']==h['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in h['pins'].items())
        extra_sources['hk_etf_seasonal']=hk_seasonal
        current_work['owners']=[owner for owner in current_work['owners']
                                if owner['name']!='港股ETF · 固定月份假设']
        current_work['owners'][15:15]=[
            dict(name='盈富基金 · 固定月份开发',status='snapshot',task=h['tracker_development_site_summary']),
            dict(name='盈富基金 · 固定月份留出',status='snapshot',task=h['tracker_holdout_site_summary']),
            dict(name='安硕恒指 · 低整手固定月份',status='snapshot',task=h['low_lot_site_summary']),
            dict(name='美股 · 等权与市值加权',status='snapshot',task=h['us_equal_weight_site_summary'])]
        if hk_industry_capital_activity:
            activity_text=activity_text.removeprefix(hk_industry_capital_activity)
        hk_seasonal_activity=h['activity_site_summary']+' '
        activity_text=hk_seasonal_activity+activity_text
    us_weights=MINING/'acceptance/US-RSP-XLP-v441-v448-ROOT-v1.json'
    if args.focus=='mining' and us_weights.exists():
        h=read(us_weights)
        assert h['new_paper_accounts']==h['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in h['pins'].items())
        extra_sources['us_equal_weight_and_staples']=us_weights
        current_work['owners']=[owner for owner in current_work['owners']
                                if owner['name']!='美股 · 等权与市值加权']
        current_work['owners'][15:15]=[
            dict(name='美股 RSP · 固定等权对照',status='snapshot',task=h['rsp_site_summary']),
            dict(name='美股 RSP · 整股投入差异',status='snapshot',task=h['exposure_site_summary']),
            dict(name='美股 XLP · 日常消费防御留出',status='snapshot',task=h['xlp_site_summary'])]
        if hk_seasonal_activity:
            activity_text=activity_text.removeprefix(hk_seasonal_activity)
        activity_text=h['activity_site_summary']+' '+activity_text
    short_credit=MINING/'acceptance/US-SHORT-CREDIT-v450-v453-ROOT-v1.json'
    if args.focus=='mining' and short_credit.exists():
        bond=read(short_credit)
        assert bond['new_paper_accounts']==bond['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in bond['pins'].items())
        extra_sources['us_short_credit_vs_treasury']=short_credit
        current_work['owners'][15:15]=[
            dict(name='美股 VCSH／VGSH · 短期公司债与国债',status='snapshot',task=bond['account_site_summary']),
            dict(name='短期债券 · 分派税与成本',status='snapshot',task=bond['tax_site_summary'])]
        if us_weights.exists():
            activity_text=activity_text.removeprefix(read(us_weights)['activity_site_summary']+' ')
        activity_text=bond['activity_site_summary']+' '+activity_text
    credit_forward=MINING/'acceptance/US-SHORT-CREDIT-SGOV-v455-v461-ROOT-v1.json'
    if args.focus=='mining' and credit_forward.exists():
        credit=read(credit_forward)
        assert credit['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in credit['pins'].items())
        extra_sources['us_short_credit_sgov_forward']=credit_forward
        current_work['owners'][15:15]=[
            dict(name='美股 SGOV · 短债同期参照',status='snapshot',task=credit['sgov_site_summary']),
            dict(name='VCSH／VGSH · 纸面开盘准备',status='snapshot',task=credit['forward_site_summary'])]
        if short_credit.exists():
            activity_text=activity_text.removeprefix(read(short_credit)['activity_site_summary']+' ')
        activity_text=credit['activity_site_summary']+' '+activity_text
    credit_and_holiday=MINING/'acceptance/US-CREDIT-T0-HK-HOLIDAY-v459-v466-ROOT-v1.json'
    if args.focus=='mining' and credit_and_holiday.exists():
        h=read(credit_and_holiday)
        assert h['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in h['pins'].items())
        extra_sources['us_credit_t0_hk_holiday']=credit_and_holiday
        current_work['owners']=[owner for owner in current_work['owners']
                                if owner['name']!='VCSH／VGSH · 纸面开盘准备']
        current_work['owners'][15:15]=[
            dict(name='VCSH／VGSH · 真实日期纸面',status='snapshot',task=h['paper_site_summary']),
            dict(name='SGOV · 既有纸面行情修订',status='snapshot',task=h['sgov_review_site_summary']),
            dict(name='02823 · 港股复市折价筛查',status='snapshot',task=h['holiday_site_summary']),
            dict(name='02822／02823 · 同指数价差',status='snapshot',task=h['a50_peer_site_summary']),
            dict(name='美股 · 信贷环境来源覆盖',status='snapshot',task=h['credit_regime_site_summary'])]
        if credit_forward.exists():
            activity_text=activity_text.removeprefix(read(credit_forward)['activity_site_summary']+' ')
        activity_text=h['activity_site_summary']+' '+activity_text
    credit_t0=MINING/'acceptance/US-CREDIT-LOCAL-T0-v472-v473-ROOT-v1.json'
    if args.focus=='mining' and credit_t0.exists():
        registered=read(credit_t0)
        assert registered['new_paper_accounts']==12 and registered['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in registered['pins'].items())
        extra_sources['us_credit_local_t0']=credit_t0
        for owner in current_work['owners']:
            if owner['name']=='VCSH／VGSH · 真实日期纸面':
                owner['task']=registered['paper_site_summary']
        if credit_and_holiday.exists():
            activity_text=activity_text.removeprefix(read(credit_and_holiday)['activity_site_summary']+' ')
        activity_text=registered['activity_site_summary']+' '+activity_text
    credit_rotation=MINING/'acceptance/US-NFCI-ROTATION-v475-v477-ROOT-v1.json'
    if args.focus=='mining' and credit_rotation.exists():
        rotation=read(credit_rotation)
        assert rotation['new_paper_accounts']==rotation['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in rotation['pins'].items())
        extra_sources['us_nfci_credit_rotation']=credit_rotation
        current_work['owners'][15:15]=[
            dict(name='美股 NFCICREDIT · 短债轮动',status='snapshot',task=rotation['rotation_site_summary']),
            dict(name='短债轮动 · 交易成本拆分',status='snapshot',task=rotation['friction_site_summary'])]
        if credit_t0.exists():
            activity_text=activity_text.removeprefix(read(credit_t0)['activity_site_summary']+' ')
        activity_text=rotation['activity_site_summary']+' '+activity_text
    placement_lapse=MINING/'acceptance/HK-PLACING-CANCELLATION-v478-v486-ROOT-v1.json'
    if args.focus=='mining' and placement_lapse.exists():
        placement=read(placement_lapse)
        assert placement['new_paper_accounts']==placement['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in placement['pins'].items())
        extra_sources['hk_placement_lapse']=placement_lapse
        current_work['owners'][15:15]=[
            dict(name='港股 · 配售失效公告',status='snapshot',task=placement['source_site_summary']),
            dict(name='港股配售 · 整手往返成本',status='snapshot',task=placement['cost_site_summary'])]
        if credit_rotation.exists():
            activity_text=activity_text.removeprefix(read(credit_rotation)['activity_site_summary']+' ')
        activity_text=placement['activity_site_summary']+' '+activity_text
    sgov_nov19=ROOT/'reports/us-sgov-nov19-public-source-recheck-20261120-v488/RESULT-v1.json'
    if args.focus=='mining' and sgov_nov19.exists():
        recheck=read(sgov_nov19)
        assert recheck['verdict']=='UNKNOWN_UNCHANGED' and recheck['original_ledger_writes']==0
        extra_sources['sgov_nov19_source_recheck']=sgov_nov19
        current_work['owners'][17:17]=[dict(name='美股 SGOV · 11月19日来源复核',status='snapshot',
            task='发行人分派记录未变，Nasdaq 尚无19日日线；原T0的UNKNOWN继续保留。')]
    treasury_frn=MINING/'acceptance/US-TFLO-SGOV-v489-v496-ROOT-v1.json'
    if args.focus=='mining' and treasury_frn.exists():
        frn=read(treasury_frn)
        assert frn['new_paper_accounts']==frn['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in frn['pins'].items())
        extra_sources['us_treasury_frn']=treasury_frn
        current_work['owners'][15:15]=[
            dict(name='美股 TFLO／SGOV · 三档持有比较',status='snapshot',task=frn['later_site_summary']),
            dict(name='美股 TFLO · 较低利率诊断',status='snapshot',task=frn['early_site_summary']),
            dict(name='港股 ETF · 双柜台成本',status='snapshot',task=frn['hk_site_summary'])]
        if placement_lapse.exists():
            activity_text=activity_text.removeprefix(read(placement_lapse)['activity_site_summary']+' ')
        activity_text=frn['activity_site_summary']+' '+activity_text
    iyr_real_rate=MINING/'acceptance/US-IYR-DFII10-v499-v503-ROOT-v1.json'
    if args.focus=='mining' and iyr_real_rate.exists():
        reit=read(iyr_real_rate)
        assert reit['new_paper_accounts']==reit['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in reit['pins'].items())
        extra_sources['us_iyr_dfii10']=iyr_real_rate
        current_work['owners'][15:15]=[
            dict(name='美股 IYR · 实际利率月度择时',status='snapshot',task=reit['iyr_site_summary']),
            dict(name='美股 IYR · 信号与交易成本',status='snapshot',task=reit['diagnostic_site_summary']),
            dict(name='港股 01200 · 住宅买卖登记',status='active',task=reit['hk_site_summary'])]
        if treasury_frn.exists():
            activity_text=activity_text.removeprefix(read(treasury_frn)['activity_site_summary']+' ')
        activity_text=reit['activity_site_summary']+' '+activity_text
    midland_registration=MINING/'acceptance/HK-MIDLAND-REGISTRATION-v503-v510-ROOT-v1.json'
    if args.focus=='mining' and midland_registration.exists():
        midland=read(midland_registration)
        assert midland['new_paper_accounts']==midland['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in midland['pins'].items())
        extra_sources['hk_midland_registration']=midland_registration
        current_work['owners']=[owner for owner in current_work['owners'] if owner['name']!='港股 01200 · 住宅买卖登记']
        current_work['owners'][15:15]=[
            dict(name='港股 01200 · 住宅登记择时',status='snapshot',task=midland['history_site_summary']),
            dict(name='港股 01200 · 2026失效复验',status='snapshot',task=midland['latest_site_summary']),
            dict(name='港股 01200 · 实物分派和账本',status='snapshot',task=midland['corporate_site_summary'])]
        if iyr_real_rate.exists():
            activity_text=activity_text.removeprefix(read(iyr_real_rate)['activity_site_summary']+' ')
        activity_text=midland['activity_site_summary']+' '+activity_text
    us_em_dollar=MINING/'acceptance/US-EM-DOLLAR-v512-v517-ROOT-v1.json'
    if args.focus=='mining' and us_em_dollar.exists():
        usd=read(us_em_dollar)
        assert usd['new_paper_accounts']==usd['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in usd['pins'].items())
        extra_sources['us_em_dollar']=us_em_dollar
        current_work['owners'][15:15]=[
            dict(name='美股 EEM／EWZ／INDA · 美元月度信号',status='snapshot',task=usd['account_site_summary']),
            dict(name='美元月度信号 · 2026追加历史检验',status='snapshot',task=usd['latest_site_summary']),
            dict(name='美股新兴市场ETF · 版本与小账户成本',status='snapshot',task=usd['source_site_summary']),
            dict(name='港股 · 证监会淡仓周报预检',status='active',task=usd['hk_site_summary'])]
        if midland_registration.exists():
            activity_text=activity_text.removeprefix(read(midland_registration)['activity_site_summary']+' ')
        activity_text=usd['activity_site_summary']+' '+activity_text
    sfc_shorts=MINING/'acceptance/HK-SFC-BREADTH-v521-v526-ROOT-v1.json'
    if args.focus=='mining' and sfc_shorts.exists():
        shorts=read(sfc_shorts)
        assert shorts['new_paper_accounts']==shorts['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in shorts['pins'].items())
        extra_sources['sfc_short_readiness']=sfc_shorts
        current_work['owners']=[owner for owner in current_work['owners'] if owner['name']!='港股 · 证监会淡仓周报预检']
        current_work['owners'][15:15]=[
            dict(name='港股 · 淡仓因子扣费结果',status='snapshot',task=shorts['economic_site_summary']),
            dict(name='港股 · 淡仓历史整手',status='snapshot',task=shorts['lot_site_summary']),
            dict(name='港股 · 周报时点及并股',status='snapshot',task=shorts['version_site_summary'])]
        if us_em_dollar.exists():
            activity_text=activity_text.removeprefix(read(us_em_dollar)['activity_site_summary']+' ')
        activity_text=shorts['activity_site_summary']+' '+activity_text
    repurchase_accounts=MINING/'acceptance/US-REPURCHASE-v528-v534-ROOT-v1.json'
    if args.focus=='mining' and repurchase_accounts.exists():
        repurchase=read(repurchase_accounts)
        assert repurchase['new_paper_accounts']==repurchase['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in repurchase['pins'].items())
        extra_sources['us_repurchase_accounts']=repurchase_accounts
        current_work['owners'][15:15]=[
            dict(name='美股 · 实际回购扣费结果',status='snapshot',task=repurchase['economic_site_summary']),
            dict(name='美股 · 回购信号追加历史检验',status='snapshot',task=repurchase['history_site_summary']),
            dict(name='美股 · 股数、拆股与披露时钟',status='snapshot',task=repurchase['report_site_summary'])]
        if sfc_shorts.exists():
            activity_text=activity_text.removeprefix(read(sfc_shorts)['activity_site_summary']+' ')
        activity_text=repurchase['activity_site_summary']+' '+activity_text
    gaap_earnings=MINING/'acceptance/EARNINGS-HIBOR-v535-v539-ROOT-v1.json'
    if args.focus=='mining' and gaap_earnings.exists():
        earnings=read(gaap_earnings)
        assert earnings['new_paper_accounts']==earnings['actual_orders']==0
        assert all(digest(ROOT/path)==expected for path,expected in earnings['pins'].items())
        extra_sources['us_earnings_gaap']=gaap_earnings
        current_work['owners'][15:15]=[
            dict(name='美股 · GAAP业绩公告与扣费',status='snapshot',task=earnings['economic_site_summary']),
            dict(name='美股 · 首报EPS与收盘时钟',status='snapshot',task=earnings['clock_site_summary']),
            dict(name='港股 00823 · HIBOR预筛',status='snapshot',task=earnings['hk_site_summary'])]
        if repurchase_accounts.exists():
            activity_text=activity_text.removeprefix(read(repurchase_accounts)['activity_site_summary']+' ')
        activity_text=earnings['activity_site_summary']+' '+activity_text
    payload=dict(schema_version=1,updated_at=now,market_data_through=paper['verified_data_through'],
      activity=dict(status=args.activity,active_at_snapshot=activity_active,focus={'small-nasdaq':'03034 · 1万港币账户','sp500':'03195 · 1万港币账户','hsi-hold':'02800 · 3万港币账户','gold':'黄金 ETF · 来源与小资金预检','ipo':'IPO · 09941前向资料核对','validation':'已有正额候选 · 收益稳定性','cash':'03152 · 现金管理的扣费底线','us-vti':'VTI · 美股普通ETF价格诊断','paper':'03086 · 固定候选纸面跟踪','mining':'港美持续研究 · 总目标运行中'}[args.focus],
                    text=activity_text,
                    snapshot_only=True,fresh_for_minutes=15),
      stages=[dict(name=n,status=s,detail=d) for n,s,d in zip(stage_names,stage_status,stage_details)],
      cards=cards,registry=registry,ipo_observation=ipo_observation,default_evidence_view='paper' if args.focus in ['paper','mining'] else 'history',
      factor_research=factor_research,next_factor_progress=next_factor,current_work=current_work,evidence_updates=evidence_updates,portfolio_research=portfolio,tip_history=tip_history,tip_continuation=tip_continuation,sgov_history={k:v for k,v in sgov.items() if k!='card'} if sgov else None,sgov_paper=new_paper,diversified_paper=diversified,
      paper=dict(checked_at=paper['checked_at_hkt'],activation_utc=paper['activation_utc'],first_forward_session=paper['first_forward_session'],
                 account_count=len(paper['summaries']),closed_rounds=paper['summaries']['monthly-only-base']['closed_rounds'],
                 open_quantity=paper['summaries']['monthly-only-base']['open_quantity'],
                 last_observation=paper['summaries']['monthly-only-base'].get('last_session'),source_quote_through=paper['verified_data_through'],
                 journal_events=paper['journal_events'],recorded_intents=paper['recorded_intents'],
                 modeled_change_hkd=paper['summaries']['monthly-only-base']['total_marked_change_hkd'],orders_sent=0,
                 primary_account='monthly-only-base',accounts=[dict(id=k,nav_hkd=v['marked_nav_hkd'],change_hkd=v['total_marked_change_hkd'],closed_rounds=v['closed_rounds'],quantity=v['open_quantity']) for k,v in paper['summaries'].items()],
                 note='四组独立纸面假设，每组初始3万港币。历史收益不计入前向账本。'),
      research_note='不同资金、期间与规则的结果不能相加。新因子IC、历史净账户与真实日期纸面分别列示。模型回撤不是未来亏损上限；历史正额不证明稳定副业收入。',
      baseline=dict(monthly_base_net_hkd=11644.34,passive_base_net_hkd=24201.91,monthly_base_risk_pct=12.49025137086156,
                    passive_base_risk_pct=19.548568745437528,independent_alpha_confirmed=False,
                    pressure_passive_note='压力参考首次未买到后保持现金，主市场暴露无法估计。'),
      factor_archive=dict(count=len(archive['factors']) if archive else 0,source_date='2026-11-03',
                          note=f"其中500条为30种基础表达式的模板组合，不是538个有效因子。旧US缓存发现拆股阶跃，相关旧条目未获本轮资格认证；原IC和原结论保留。与已验收的{factor_research['unique_new_signals']}个信号分开计数。"),
      source_hashes={**{k:digest(TEAM/v) for k,v in source_paths.items()},**{k:digest(v) for k,v in extra_sources.items()}})
    payload['filing_event']=filing_event
    payload['form4']=form4
    payload['merger']=merger
    payload['merger_execution_control']=merger_execution_control
    payload['merger_cost_control']=merger_cost_control
    payload['merger_review']=merger_review
    payload['merger_stress']=merger_stress
    payload['ief_account']=ief_result
    payload['southbound']=southbound
    payload['nov18_cost_attribution']=november18_attribution() if diversified['activated'] else []
    OUT.mkdir(exist_ok=True,parents=True);(OUT/'assets').mkdir(exist_ok=True)
    if tip_account_review:render_tip_history_chart(tip_account_review)
    if tip_B_account_review:render_tip_continuation_chart(tip_B_account_review)
    with (OUT/'progress.json').open('w',encoding='utf-8',newline='\n') as f:json.dump(payload,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
    shutil.copyfile(ROOT/'reports/hk-nasdaq-baseline-attribution-owner-20261116-v103/baseline-nav-close-drawdown-v1.png',OUT/'assets/nav-risk.png')
    if later_review.exists():shutil.copyfile(ROOT/'reports/hk-sp500-later-validation-owner-20261117-v106c/C-ONLY-NAV-DRAWDOWN-v2.png',OUT/'assets/sp500-later-risk.png')
    if gold_review.exists():shutil.copyfile(TEAM/'v111-review/C-ONLY-NAV-RISK-v1.png',OUT/'assets/gold-later-risk.png')
    if income_review.exists():shutil.copyfile(ROOT/'reports/hk-nasdaq-income-distribution-owner-20261117-v115/income-distribution-underwater-v1.png',OUT/'assets/nasdaq-income-water.png')
    if dependence_review.exists():shutil.copyfile(ROOT/'reports/hk-ipo-allotment-dependence-owner-20261117-v114/ALLOTMENT-DEPENDENCE-v1.png',OUT/'assets/ipo-dependence.png')
    if cash_review.exists():shutil.copyfile(TEAM/'v120-review/CASH-COST-AND-CAPITAL-v1.png',OUT/'assets/cash-cost-capital.png')
    if us_vti_review.exists():shutil.copyfile(TEAM/'v123-review/VTI-PRICE-NAV-RISK-v1.png',OUT/'assets/vti-price-risk.png')
    if sgov:shutil.copyfile(MINING/'sgov-review/SGOV-history-v1.png',OUT/'assets/sgov-history.png')
    print(json.dumps(dict(updated_at=now,records=len(registry),focus=args.focus,latest_status=current_work['research_batch_status'] if args.focus=='mining' else current['status'],new_signals=factor_research['unique_new_signals'],
                         sgov_paper_activated=new_paper['activated'],diversified_paper_activated=diversified['activated'],paper_closed_rounds=payload['paper']['closed_rounds'],orders_sent=0),ensure_ascii=False))

if __name__=='__main__':main()
