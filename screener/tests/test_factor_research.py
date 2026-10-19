from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from screener import factor_research as research
from screener import research_signals as signals
from screener import research_validation as validation
from screener.risk import exchange_calendar
from screener.tracking import freeze_snapshot, read_archives, write_json


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.calendar = exchange_calendar('US')
        self.sessions = self.calendar.sessions_in_range('2025-01-02', '2026-10-16')
        self.day = self.sessions[300]
        self.now = self.calendar.session_close(self.day).to_pydatetime() + timedelta(minutes=10)
        self.stocks = {}
        for j in range(24):
            prices = 100 * np.exp(np.arange(len(self.sessions)) * (.0002 + .0001 * j)
                                  + .035 * np.sin(np.arange(len(self.sessions)) * (.07 + j * .013)))
            self.stocks[f'US.T{j:02d}'] = [[int(day.strftime('%Y%m%d')), float(c * .999), float(c * 1.02),
                float(c * .98), float(c), int(10000 + 2000 * np.sin(i * .4 + j))] for i, (day, c) in enumerate(zip(self.sessions, prices))]
        self.indexes = {'SPX': self.stocks['US.T00']}
        self.history = self.path / 'history'
        write_json(self.history / 'us.json', {'generated_at': self.now.isoformat(),
            'stocks': [{'code': c, 'name': c, 'bars': b} for c, b in self.stocks.items()]})
        write_json(self.history / 'index.json', {'indexes': {'SPX': {'bars': self.indexes['SPX']}}})
        self.state = research.load_state(self.path)
        research.initialize(self.state, self.history, self.now)
        research.save_state(self.path, self.state)

    def test_fixed_universe_is_independent_and_does_not_rotate(self):
        before = deepcopy(self.state['universes'])
        self.assertEqual(len(self.state['programs']), 3)
        write_json(self.history / 'us.json', {'stocks': [{'code': 'US.NEW', 'bars': []}]})
        research.initialize(self.state, self.history, self.now + timedelta(days=1))
        self.assertEqual(self.state['universes'], before)
        self.assertEqual({p['family'] for p in self.state['programs']}, {'volume_breakout', 'compression_breakout', 'short_reversal'})

    def test_features_ignore_future_prices_and_require_exact_sessions(self):
        members = self.state['universes']['US']['members']
        day = int(self.day.strftime('%Y%m%d'))
        panel, missing, _ = validation.panel_at(members, self.stocks, 'US', day)
        self.assertEqual(len(panel), 24)
        self.assertFalse(missing)
        changed = deepcopy(self.stocks)
        changed['US.T00'][-1][4] *= 100
        self.assertEqual(validation.panel_at(members, changed, 'US', day)[0], panel)
        changed['US.T00'] = [b for b in changed['US.T00'] if b[0] != day]
        self.assertNotIn('US.T00', validation.panel_at(members, changed, 'US', day)[0])

    def test_intraday_and_stale_bars_cannot_generate_a_new_cohort(self):
        before_close = self.calendar.session_open(self.day).to_pydatetime() + timedelta(hours=1)
        self.assertLess(validation.last_completed('US', before_close), int(self.day.strftime('%Y%m%d')))
        stale = {c: bars[:250] for c, bars in self.stocks.items()}
        quality = research.freeze_inputs(self.state, self.path, stale, self.now)
        self.assertEqual(quality[0]['status'], 'insufficient_data')
        self.assertFalse(self.state['inputs'])

    def test_expression_contract_rejects_code_nonfinite_and_unbounded_trees(self):
        for expr in [{'op': 'eval', 'code': '__import__("os")'}, {'op': 'feature', 'name': 'news_url'},
                     {'op': 'feature', 'name': 'gap', 'code': 'ignored'}, {'op': 'mean', 'args': []}]:
            with self.assertRaises(ValueError):
                signals.validate_expression(expr)
        spec = deepcopy(signals.SEEDS[0])
        spec['filters'] = [{'feature': 'gap', 'gte': float('nan')}]
        with self.assertRaises(ValueError):
            signals.validate_spec(spec)
        expr = signals.feature('gap')
        for _ in range(6):
            expr = {'op': 'neg', 'arg': expr}
        with self.assertRaises(ValueError):
            signals.validate_expression(expr)

    def test_raw_factors_and_normalization_are_finite_and_deterministic(self):
        raw = signals.raw_features(self.stocks['US.T00'][:61])
        self.assertEqual(set(raw), set(signals.FEATURES))
        self.assertAlmostEqual(raw['relative_volume'], self.stocks['US.T00'][60][5] /
                               np.mean([b[5] for b in self.stocks['US.T00'][40:60]]))
        self.assertTrue(all(v == 0 for v in signals.standardize({'A': raw, 'B': raw})['A'].values()))
        panel = {c: signals.raw_features(b[:61]) for c, b in self.stocks.items()}
        before = deepcopy(panel)
        self.assertEqual(signals.select(signals.SEEDS[2], panel), signals.select(signals.SEEDS[2], dict(reversed(list(panel.items())))))
        self.assertEqual(panel, before)

    def test_duplicate_commutative_formula_and_frozen_definition(self):
        spec = deepcopy(signals.SEEDS[0])
        spec['expression']['args'].reverse()
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            research.register(self.state, spec, 'US', self.now, {'kind': 'test'})
        self.state['programs'][0]['expression'] = signals.feature('gap')
        research.save_state(self.path, self.state)
        with self.assertRaisesRegex(ValueError, 'definition'):
            research.load_state(self.path)

    def test_session_freeze_is_immutable_idempotent_and_all_pool_members_count(self):
        research.freeze_inputs(self.state, self.path, self.stocks, self.now)
        record = read_archives(self.path / 'research/runs')[0]
        self.assertEqual(len(record['payload']['strategies'][0]['hits']), 24)
        first = deepcopy(self.state['inputs'])
        changed = deepcopy(self.stocks)
        changed['US.T00'][300][5] *= 10
        research.freeze_inputs(self.state, self.path, changed, self.now + timedelta(hours=1))
        self.assertEqual(self.state['inputs'], first)
        self.assertEqual(len(read_archives(self.path / 'research/runs')), 1)
        due = self.calendar.session_open(self.sessions[306]).to_pydatetime() + timedelta(minutes=1)
        rows = research.observations(self.state, self.path, self.stocks, self.indexes, due)
        self.assertEqual(rows[0]['parent']['count'], 24)
        self.assertEqual(rows[0]['entry_date'], int(self.sessions[301].strftime('%Y%m%d')))
        self.assertEqual(rows[0]['exit_date'], int(self.sessions[306].strftime('%Y%m%d')))
        self.assertTrue(all(r['due'] for r in rows))
        changed['US.T00'][306][1] *= 2
        self.assertEqual(rows, research.observations(self.state, self.path, changed, self.indexes, due))

    def test_empty_signal_is_cash_but_missing_price_is_unknown(self):
        spec = deepcopy(signals.SEEDS[0])
        spec.update(name='empty test', filters=[{'feature': 'gap', 'gte': 100}])
        program = research.register(self.state, spec, 'US', self.now, {'kind': 'test'})
        research.freeze_inputs(self.state, self.path, self.stocks, self.now)
        due = self.calendar.session_open(self.sessions[306]).to_pydatetime() + timedelta(minutes=1)
        stocks = deepcopy(self.stocks)
        stocks['US.T00'] = [b for b in stocks['US.T00'] if b[0] != int(self.sessions[306].strftime('%Y%m%d'))]
        row = next(r for r in research.observations(self.state, self.path, stocks, self.indexes, due) if r['trial_id'] == program['id'])
        self.assertEqual(row['branch']['return_pct'], 0)
        self.assertFalse(row['parent']['complete'])
        values, checks = research.assess([row], research.policy())
        self.assertEqual(values['paired'], 0)
        self.assertFalse(checks['signal_rate'])

    def test_proposal_cannot_reuse_prior_inputs_and_owner_controls_work(self):
        research.freeze_inputs(self.state, self.path, self.stocks, self.now)
        research.save_state(self.path, self.state)
        proposal = {k: deepcopy(v) for k, v in signals.SEEDS[0].items() if k != 'family'}
        proposal.update(name='new formula', market='US', expression=signals.feature('gap'), filters=[])
        research.owner_action(self.path, 'start', 'owner', proposal=proposal, now=self.now + timedelta(hours=1))
        state = research.load_state(self.path)
        program = state['programs'][-1]
        research.freeze_inputs(state, self.path, self.stocks, self.now + timedelta(hours=2))
        self.assertFalse(any(r['trial_id'] == program['id'] for r in research.observations(state, self.path, self.stocks, self.indexes, self.now + timedelta(days=20))))
        with self.assertRaisesRegex(ValueError, 'stale'):
            research.owner_action(self.path, 'pause', 'owner', program['id'], 'wrong')
        research.owner_action(self.path, 'pause', 'owner', program['id'], program['definition_hash'])
        self.assertEqual(research.load_state(self.path)['programs'][-1]['status'], 'paused')

    def test_walk_forward_purges_labels_and_keeps_test_folds_disjoint(self):
        report = validation.historical_diagnostic(self.state['programs'][0], self.state['universes']['US']['members'],
                                                  self.stocks, 'US', self.now, research.policy())
        self.assertEqual(len(report['folds']), 3)
        for fold in report['folds']:
            label_end = self.calendar.session_offset(str(fold['train_end']), 6)
            self.assertLess(int(label_end.strftime('%Y%m%d')), fold['test_start'])
            self.assertEqual(fold['test_periods'], 20)
        self.assertLess(report['folds'][0]['test_end'], report['folds'][1]['test_start'])
        self.assertEqual(report['kind'], 'retrospective_diagnostic')

    def test_data_driven_discovery_adds_formula_and_never_backfills_it(self):
        spec = {**deepcopy(signals.SEEDS[0]), 'name': 'parent', 'expression': signals.feature('breakout'), 'filters': []}
        parent = research.register(self.state, spec, 'US', self.now - timedelta(days=100), {'kind': 'test'})
        rng, rows = np.random.default_rng(42), []
        target = {'op': 'product', 'args': [signals.feature('breakout'), signals.feature('relative_volume')]}
        for i in range(20):
            panel = {code: {k: float(rng.normal()) for k in signals.FEATURES} for code in self.stocks}
            score = signals.expression_values(target, signals.standardize(panel))
            returns = {code: 3 + value for code, value in score.items()}
            chosen = signals.select(parent, panel)
            value = sum(returns[h['code']] for h in chosen) / len(chosen)
            pool = {'count': 24, 'complete': True, 'return_pct': 3,
                    'holdings': [{'code': c, 'return_pct': r, 'status': 'matured', 'entry_price': 100, 'exit_price': 100 + r} for c, r in returns.items()]}
            input_id = f'US_fixture_{i}'
            research.sealed(self.path / 'research/inputs' / (input_id + '.json'), {'panel': panel})
            rows.append({'trial_id': parent['id'], 'due': True, 'input_id': input_id,
                         'exit_date': int(self.sessions[270 + i].strftime('%Y%m%d')),
                         'branch': {**pool, 'return_pct': value}, 'parent': pool, 'pool': pool, 'benchmark_pct': 0})
        research.discover(self.state, rows, self.path, self.now)
        self.assertEqual(len(self.state['searches']), 1)
        self.assertTrue(self.state['searches'][0]['candidates'])
        children = [p for p in self.state['programs'] if p['parent_id'] == parent['id']]
        self.assertEqual(len(children), 1)
        self.assertNotEqual(signals.fingerprint(children[0]), signals.fingerprint(parent))
        self.assertEqual(children[0]['created_at'], self.now.isoformat())
        self.assertEqual(children[0]['assessments'], [])
        research.discover(self.state, rows, self.path, self.now + timedelta(days=1))
        self.assertEqual(len(self.state['searches']), 1)

    def test_backup_restore_keeps_research_and_rejects_rollback_and_tampering(self):
        from scripts.restore_screening_archive import restore
        freeze_snapshot({'generated_at': self.now.isoformat(), 'strategies': []}, self.path, frozen_at=self.now)
        research.freeze_inputs(self.state, self.path, self.stocks, self.now)
        research.save_state(self.path, self.state)
        target = self.path / 'restored'
        restore(self.path, target)
        restore(self.path, target)
        self.assertEqual(len(research.load_state(target)['programs']), 3)
        current = research.load_state(target)
        research.log(current, 'pause', self.now, current['programs'][0]['id'], actor='owner')
        research.save_state(target, current)
        with self.assertRaisesRegex(ValueError, 'roll back'):
            restore(self.path, target)
        file = next((self.path / 'research/inputs').glob('*.json'))
        node = json.loads(file.read_text())
        node['payload']['session'] = 20000101
        write_json(file, node)
        with self.assertRaisesRegex(ValueError, 'integrity'):
            research.read_sealed(file)

    def test_source_change_pauses_and_policy_change_does_not_reset_budget(self):
        with patch.object(research, 'engine_version', return_value='new-engine'):
            research.freeze_inputs(self.state, self.path, self.stocks, self.now)
        self.assertTrue(all(p['status'] == 'paused' for p in self.state['programs']))
        with patch.object(research, 'policy', return_value={**research.policy(), 'max_programs': 100}):
            with self.assertRaisesRegex(ValueError, 'migrate'):
                research.load_state(self.path)

    def evidence_rows(self, delta=3, count=60):
        program = self.state['programs'][0]
        rows = []
        for i in range(count):
            hold = {'code': 'US.T00', 'status': 'matured', 'entry_price': 100, 'exit_price': 106, 'return_pct': 1 + delta}
            branch = {'count': 1, 'holdings': [hold], 'complete': True, 'return_pct': 1 + delta}
            parent = {**branch, 'return_pct': 1}
            rows.append({'trial_id': program['id'], 'definition_hash': program['definition_hash'],
                         'snapshot_id': str(i), 'input_id': str(i), 'due': True, 'rank_ic': .1, 'pearson_ic': .1,
                         'control_correlations': [.2, .3, .1], 'entry_date': 20200101 + i * 10,
                         'exit_date': 20200106 + i * 10, 'branch': branch, 'parent': parent,
                         'pool': parent, 'benchmark_pct': 0})
        return rows

    def test_checkpoint_is_fixed_and_owner_approval_revalidates_evidence(self):
        research.checkpoints(self.state, self.evidence_rows(count=20), self.path, self.now)
        program = self.state['programs'][0]
        self.assertEqual(program['status'], 'review')
        self.assertEqual(len(program['assessments']), 1)
        research.save_state(self.path, self.state)
        evidence = program['assessments'][0]['hash']
        research.owner_action(self.path, 'approve', 'owner', program['id'], evidence, now=self.now)
        approved = research.load_state(self.path)
        self.assertEqual(approved['programs'][0]['status'], 'approved')
        self.assertEqual(approved['events'][-1]['actor'], 'owner')
        with self.assertRaisesRegex(ValueError, 'eligible'):
            research.owner_action(self.path, 'approve', 'owner', program['id'], evidence, now=self.now)

    def test_loser_keeps_failed_evidence_and_is_stopped_at_final_checkpoint(self):
        research.checkpoints(self.state, self.evidence_rows(delta=-2), self.path, self.now)
        program = self.state['programs'][0]
        self.assertEqual(program['status'], 'rejected')
        self.assertEqual([a['checkpoint'] for a in program['assessments']], [20, 40, 60])
        self.assertEqual(len(list((self.path / 'research/evidence').glob('*.json'))), 3)

    def test_rehashed_definition_cannot_take_credit_for_old_evidence(self):
        research.checkpoints(self.state, self.evidence_rows(count=20), self.path, self.now)
        program = self.state['programs'][0]
        evidence = program['assessments'][0]['hash']
        program['expression'] = signals.feature('gap')
        program['definition_hash'] = research.digest({k: program[k] for k in research.CORE})
        research.save_state(self.path, self.state)
        with self.assertRaisesRegex(ValueError, 'evidence'):
            research.owner_action(self.path, 'approve', 'owner', program['id'], evidence, now=self.now)

    def test_interrupted_diagnostics_keeps_original_birth_and_input_on_retry(self):
        with patch.object(validation, 'historical_diagnostic', side_effect=RuntimeError('interrupted')):
            with self.assertRaisesRegex(RuntimeError, 'interrupted'):
                research.run(self.path, self.history, self.path / 'public.json', now=self.now)
        before = research.load_state(self.path)
        self.assertTrue(before['inputs'])
        with patch.object(validation, 'historical_diagnostic', return_value={'kind': 'fixture', 'folds': []}):
            research.run(self.path, self.history, self.path / 'public.json', now=self.now + timedelta(minutes=1))
        after = research.load_state(self.path)
        self.assertEqual([p['definition_hash'] for p in before['programs']], [p['definition_hash'] for p in after['programs']])
        self.assertEqual(before['inputs'], after['inputs'])


if __name__ == '__main__':
    unittest.main()
