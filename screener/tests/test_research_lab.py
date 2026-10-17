from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from screener import research_lab as lab
from screener.strategies import momentum_breakout
from screener.market_policy import market_parameters
from screener.tracking import freeze_snapshot, read_archives


class LabTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.now = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
        self.params = market_parameters(momentum_breakout.META)[1]['US']
        self.mother = dict(id='root_test', root_id='momentum_breakout', generation=0, market='US',
                           source_version=lab.strategy_version(), base_params=self.params, params=self.params)
        self.state = lab.load_state(self.path)

    def spawn(self):
        lab.spawn(self.state, self.mother, self.now, lab.policy())
        lab.save_state(self.path, self.state)
        return self.state['trials'][0]

    def source(self, now=None):
        now = now or self.now + timedelta(days=1)
        hits = [{'code': 'US.ONE', 'name': 'One', 'off_52w_high_pct': -1,
                 'turnover': 100e6, 'original_market_rank': 1},
                {'code': 'US.TWO', 'name': 'Two', 'off_52w_high_pct': -2.5,
                 'turnover': 25e6, 'original_market_rank': 2}]
        meta = {**deepcopy(momentum_breakout.META), 'market_params': {'US': self.params}, 'hit_count': 2}
        return freeze_snapshot({'generated_at': now.isoformat(), 'strategies': [{'meta': meta, 'hits': hits}]},
                               self.path, frozen_at=now)

    def observation(self, i, delta=2.0, complete=True):
        holding = {'code': 'US.ONE', 'status': 'matured', 'return_pct': 3 + delta,
                   'entry_price': 100.0, 'exit_price': 106.0}
        return {'trial_id': 'example', 'snapshot_id': str(i), 'entry_date': 20200101 + i * 10,
                'exit_date': 20200106 + i * 10, 'due': True, 'definition_hash': 'hash',
                'branch': {'complete': complete, 'count': 1, 'holdings': [holding], 'return_pct': 3 + delta if complete else None},
                'parent': {'complete': True, 'count': 1, 'holdings': [holding], 'return_pct': 3}, 'benchmark_pct': 1.0}

    def test_spawn_is_single_change_bounded_and_idempotent(self):
        self.spawn()
        self.assertEqual(len(self.state['trials']), 2)
        for trial in self.state['trials']:
            self.assertEqual(sum(trial['params'][k] != self.params[k] for k in self.params), 1)
            self.assertEqual(trial['generation'], 1)
        lab.spawn(self.state, self.mother, self.now, lab.policy())
        self.assertEqual(len(self.state['trials']), 2)
        for i in range(20):
            lab.spawn(self.state, {**self.mother, 'id': f'root_{i}', 'market': str(i)}, self.now, lab.policy())
        self.assertLessEqual(len(self.state['trials']), lab.policy()['max_active'])

    def test_definition_tampering_and_policy_reset_are_rejected(self):
        self.spawn()
        self.state['trials'][0]['params']['near_high_pct'] = 100
        lab.save_state(self.path, self.state)
        with self.assertRaises(ValueError):
            lab.load_state(self.path)
        self.state['trials'] = []
        self.state['policy_hash'] = 'changed'
        lab.save_state(self.path, self.state)
        with self.assertRaises(ValueError):
            lab.load_state(self.path)

    def test_second_generation_stops_at_depth_and_total_budget(self):
        mother = self.spawn()
        lab.spawn(self.state, mother, self.now + timedelta(days=10), lab.policy())
        grandchildren = [t for t in self.state['trials'] if t['generation'] == 2]
        self.assertTrue(grandchildren)
        count = len(self.state['trials'])
        lab.spawn(self.state, grandchildren[0], self.now, lab.policy())
        self.assertEqual(len(self.state['trials']), count)
        limited = {**lab.policy(), 'max_trials': count, 'max_active': 100}
        lab.spawn(self.state, {**self.mother, 'id': 'new_mother'}, self.now, limited)
        self.assertEqual(len(self.state['trials']), count)

    def test_empty_branch_stays_cash_but_cannot_pass_signal_gate(self):
        row = self.observation(0)
        row['branch'] = {'complete': True, 'count': 0, 'holdings': [], 'return_pct': 0.0}
        values = lab.metrics([row], lab.policy())
        self.assertEqual(values['mean_return_pct'], 0)
        self.assertFalse(lab.gates(values, lab.policy())['signal_rate'])
    def test_refinement_preserves_rank_and_rejects_relaxation(self):
        trial = self.spawn()
        source = self.source()
        hits = source['payload']['strategies'][0]['hits']
        before = deepcopy(hits)
        chosen = lab.selected(hits, 'US', self.params, trial['params'])
        self.assertEqual([h['code'] for h in chosen], ['US.ONE'])
        self.assertEqual(hits, before)
        with self.assertRaises(ValueError):
            lab.selected(hits, 'US', self.params, {**self.params, 'near_high_pct': 4})

    def test_no_backfill_and_repeat_source_is_idempotent(self):
        self.spawn()
        older = self.source(self.now - timedelta(seconds=1))
        lab.prepare([older], self.path, self.now)
        self.assertFalse(read_archives(self.path / 'lab'))
        current = self.source()
        later = self.now + timedelta(days=1, minutes=30)
        lab.prepare([current], self.path, later)
        records = read_archives(self.path / 'lab')
        self.assertEqual(len(records), 1)
        self.assertEqual(lab.instant(records[0]['frozen_at']), later)
        lab.prepare([current], self.path, later + timedelta(hours=1))
        self.assertEqual(len(read_archives(self.path / 'lab')), 1)

    def test_source_change_pauses_without_rewriting_past_runs(self):
        self.spawn()
        source = self.source()
        source['strategy_version'] = 'another'
        lab.prepare([source], self.path, self.now + timedelta(days=2))
        self.assertTrue(all(t['status'] == 'paused' for t in lab.load_state(self.path)['trials']))
        self.assertEqual(read_archives(self.path / 'lab'), [])

    def test_missing_prices_never_reweights_and_pending_not_counted(self):
        rows = [self.observation(i) for i in range(20)]
        rows[0]['branch']['complete'] = False
        rows[0]['branch']['return_pct'] = None
        rows.append({**self.observation(100), 'due': False})
        values = lab.metrics(rows, lab.policy())
        self.assertEqual(values['due'], 20)
        self.assertEqual(values['paired'], 19)
        self.assertEqual(values['coverage'], .95)
        self.assertEqual(values['mean_delta_pp'], 2)

    def test_positive_evidence_gate_and_cost_stress(self):
        values = lab.metrics([self.observation(i) for i in range(20)], lab.policy())
        self.assertTrue(all(lab.gates(values, lab.policy()).values()))
        self.assertAlmostEqual(lab.reprice({'holdings': [{'status': 'no_trade'}]}, 30), 0)
        self.assertIsNone(lab.reprice({'holdings': [{'status': 'missing_exit'}]}, 30))
        self.assertLess(lab.reprice(self.observation(0)['branch'], 30), lab.reprice(self.observation(0)['branch'], 15))

    def test_identical_branch_and_overlapping_samples_do_not_qualify(self):
        rows = [self.observation(i, 0) for i in range(20)]
        values = lab.metrics(rows, lab.policy())
        self.assertFalse(lab.gates(values, lab.policy())['uncertainty'])
        for i, row in enumerate(rows):
            row.update(entry_date=20200101 + i, exit_date=20200106 + i)
        self.assertFalse(lab.gates(lab.metrics(rows, lab.policy()), lab.policy())['independent'])

    def test_checkpoint_first_n_is_frozen_and_loser_eventually_stops(self):
        trial = self.spawn()
        rows = [{**self.observation(i, -1), 'trial_id': trial['id'], 'definition_hash': trial['definition_hash']} for i in range(60)]
        with patch.object(lab, 'observations', return_value=rows):
            report = lab.update_lab([], {'evaluations': []}, {}, {}, self.path, self.now, self.path / 'public.json')
        result = report['trials'][0]
        self.assertEqual(result['status'], 'rejected')
        self.assertEqual([e['checkpoint'] for e in result['assessments']], [20, 40, 60])
        self.assertEqual(len(result['assessments'][0]['snapshot_ids']), 20)
        self.assertEqual(len(report['trials']), 2)

    def test_review_requires_ready_status_current_evidence_and_explicit_actor(self):
        trial = self.spawn()
        with self.assertRaises(ValueError):
            lab.review(self.path, trial['id'], 'approve', 'unknown', 'owner')
        with self.assertRaises(ValueError):
            lab.review(self.path, trial['id'], 'reject', 'unknown', '')

    def test_owner_can_pause_without_a_completed_checkpoint(self):
        trial = self.spawn()
        lab.review(self.path, trial['id'], 'pause', trial['definition_hash'], 'owner')
        self.assertEqual(lab.load_state(self.path)['trials'][0]['status'], 'paused')

    def test_pairing_uses_lab_freeze_not_the_older_mother_opening(self):
        trial = self.spawn()
        source = self.source()
        lab.prepare([source], self.path, self.now + timedelta(days=2))
        bars = [[20261005, 100, 102, 99, 101, 100], [20261012, 110, 112, 109, 111, 100]]
        stocks = {'US.ONE': bars, 'US.TWO': [bars[0], [20261012, 101, 102, 100, 101, 100]]}
        now = self.now + timedelta(days=14)
        rows = lab.observations(self.path, stocks, {'SPX': bars}, now)
        row = next(r for r in rows if r['trial_id'] == trial['id'])
        self.assertEqual(row['entry_date'], 20261005)
        self.assertEqual(row['exit_date'], 20261012)
        self.assertTrue(row['branch']['complete'])
        self.assertGreater(row['branch']['return_pct'], row['parent']['return_pct'])
        self.assertEqual(lab.needed_prices(self.path, {}, {'SPX': bars}, now), {'US.ONE', 'US.TWO'})

    def test_mother_maturity_opens_exploration_only_after_threshold(self):
        source = self.source()
        row = {'prospective': True, 'horizon': 5, 'market': 'US', 'strategy_id': 'momentum_breakout',
               'strategy_version': source['strategy_version'], 'baskets': {'selected': {'complete': True}},
               'benchmark_pct': 1}
        rows = [{**row, 'scheduled_entry_date': 20260101 + i} for i in range(7)]
        report = lab.update_lab([source], {'evaluations': rows + rows}, {}, {}, self.path, self.now + timedelta(days=2), self.path / 'public.json')
        self.assertEqual(len(report['trials']), 0)
        self.assertEqual(report['parents'][0]['matured'], 7)
        rows.append({**row, 'scheduled_entry_date': 20260109})
        report = lab.update_lab([source], {'evaluations': rows}, {}, {}, self.path, self.now + timedelta(days=2), self.path / 'public.json')
        self.assertEqual(len(report['trials']), 2)
        self.assertTrue(all(t['status'] == 'testing' for t in report['trials']))

    def test_approved_review_changes_only_market_rule_and_keeps_audit(self):
        trial = self.spawn()
        rows = [{**self.observation(i), 'trial_id': trial['id'], 'definition_hash': trial['definition_hash']} for i in range(20)]
        with patch.object(lab, 'observations', return_value=rows):
            report = lab.update_lab([], {'evaluations': []}, {}, {}, self.path, self.now, self.path / 'public.json')
        trial = report['trials'][0]
        self.assertEqual(trial['status'], 'review')
        config = self.path / 'rules.json'
        config.write_bytes((lab.ROOT / 'screener/market_rules.json').read_bytes())
        before = json.loads(config.read_text())
        evidence = trial['assessments'][-1]['hash']
        lab.review(self.path, trial['id'], 'approve', evidence, 'repository-owner', config)
        after = json.loads(config.read_text())
        self.assertEqual(after['strategies']['momentum_breakout']['HK'], before['strategies']['momentum_breakout']['HK'])
        self.assertEqual(after['strategies']['momentum_breakout']['US']['near_high_pct'], 2.0)
        self.assertEqual(lab.load_state(self.path)['events'][-1]['actor'], 'repository-owner')

    def test_mutated_evidence_prices_cannot_be_approved(self):
        trial = self.spawn()
        rows = [{**self.observation(i), 'trial_id': trial['id'], 'definition_hash': trial['definition_hash']} for i in range(20)]
        with patch.object(lab, 'observations', return_value=rows):
            report = lab.update_lab([], {'evaluations': []}, {}, {}, self.path, self.now, self.path / 'public.json')
        evidence = report['trials'][0]['assessments'][-1]['hash']
        path = self.path / 'lab/evidence' / (evidence + '.json')
        data = json.loads(path.read_text())
        data['cohorts'][0]['branch']['holdings'][0]['exit_price'] = 1000
        path.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises(ValueError):
            lab.review(self.path, trial['id'], 'approve', evidence, 'owner')

    def test_archive_restore_retains_lab_state_and_runs(self):
        self.spawn()
        source = self.source()
        lab.prepare([source], self.path, self.now + timedelta(days=2))
        from scripts.restore_screening_archive import restore
        destination = self.path / 'restored'
        restore(self.path, destination)
        restore(self.path, destination)
        self.assertEqual(len(lab.load_state(destination)['trials']), 2)
        self.assertEqual(len(read_archives(destination / 'lab')), 1)

    def test_old_backup_cannot_roll_back_experiment_history(self):
        self.spawn()
        self.source()
        from scripts.restore_screening_archive import restore
        destination = self.path / 'restored'
        restore(self.path, destination)
        current = lab.load_state(destination)
        lab.event(current, current['trials'][0]['id'], 'paused', self.now, actor='owner')
        lab.save_state(destination, current)
        with self.assertRaisesRegex(ValueError, 'roll back'):
            restore(self.path, destination)
        self.assertEqual(lab.load_state(destination)['events'][-1]['actor'], 'owner')
