from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from screener import factor_research as research
from screener import research_review as review
from screener import research_signals as signals


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.rules = research.policy()
        self.program = {**deepcopy(signals.SEEDS[0]), 'id': 'test', 'definition_hash': 'original',
                        'discovery': {'kind': 'predeclared'}, 'assessments': []}
        self.card = {'version': 1, 'evidence': 'Completed outcomes only',
                     'failure_condition': 'Fail the original fixed gates', 'data_risks': 'OHLCV only, no news'}

    def row(self, **updates):
        holding = {'code': 'US.TEST', 'status': 'matured', 'entry_price': 100, 'exit_price': 101, 'return_pct': .697}
        return {'trial_id': 'test', 'entry_date': 20261001, 'exit_date': 20261008, 'due': True, 'benchmark_pct': 2,
                'branch': {'count': 1, 'complete': True, 'return_pct': .697, 'holdings': [holding]},
                'parent': {'complete': True, 'return_pct': .5}, 'pool': {'complete': True, 'return_pct': .5}, **updates}

    def test_missing_and_pending_never_become_flat_or_losses(self):
        missing = self.row(branch={'count': 1, 'complete': False, 'return_pct': None, 'holdings': []})
        pending = self.row(entry_date=20261002, due=False)
        result = review.program_review(self.program, [missing, pending], self.rules)
        s = result['summary']
        self.assertEqual((s['paired'], s['missing'], s['pending'], s['flat']), (0, 1, 1, 0))
        self.assertIsNone(s['mean_return_pct'])
        self.assertIn('不能判断', result['headline'])

    def test_gains_and_beating_index_are_different(self):
        result = review.program_review(self.program, [self.row()], self.rules)
        self.assertEqual(result['summary']['wins'], 1)
        self.assertEqual(result['summary']['beat_benchmark'], 0)
        self.assertIn('落后指数', result['headline'])
        self.assertAlmostEqual(result['summary']['stress_excess_pp'], (101 / 100 * .997 / 1.003 - 1) * 100 - 2)

    def test_missing_pool_or_index_excludes_entire_pair(self):
        for row in [self.row(pool={'complete': False, 'return_pct': None}), self.row(benchmark_pct=None)]:
            self.assertEqual(review.program_review(self.program, [row], self.rules)['summary']['paired'], 0)
        for row in [self.row(benchmark_pct=float('nan')),
                    self.row(branch={'complete': True, 'return_pct': float('inf'), 'count': 1, 'holdings': []})]:
            with self.assertRaises(ValueError):
                review.program_review(self.program, [row], self.rules)

    def test_overlapping_periods_do_not_inflate_independent_count(self):
        rows = [self.row(), self.row(entry_date=20261002, exit_date=20261009), self.row(entry_date=20261009, exit_date=20261016)]
        s = review.program_review(self.program, rows, self.rules)['summary']
        self.assertEqual((s['paired'], s['independent']), (3, 2))

    def test_duplicate_cohorts_block_explanatory_statistics(self):
        result = review.program_review(self.program, [self.row(), self.row()], self.rules)
        self.assertTrue(result['summary']['duplicate'])
        self.assertEqual(result['summary']['paired'], 0)
        self.assertEqual(result['checks'][0]['status'], 'fail')
        self.assertIsNone(result['summary']['mean_return_pct'])

    def test_rows_cannot_take_credit_for_another_definition(self):
        with self.assertRaisesRegex(ValueError, 'different frozen definition'):
            review.program_review(self.program, [self.row(definition_hash='another')], self.rules)

    def test_cash_is_zero_but_unavailable_stress_prices_stay_unknown(self):
        cash = self.row(branch={'count': 0, 'complete': True, 'return_pct': 0, 'holdings': []})
        s = review.program_review(self.program, [cash], self.rules)['summary']
        self.assertEqual((s['cash'], s['flat'], s['wins']), (1, 1, 0))
        bad = self.row(branch={'count': 1, 'complete': True, 'return_pct': 1, 'holdings': []})
        self.assertIsNone(review.program_review(self.program, [bad], self.rules)['summary']['stress_excess_pp'])

    def test_old_studies_are_not_retroactively_predeclared(self):
        result = review.program_review(self.program, [], self.rules)
        self.assertEqual(result['card']['origin'], 'legacy')
        self.assertIn('不事后补写', result['card']['evidence'])
        self.assertTrue(any(c['status'] == 'pending' for c in result['checks']))

    def test_frozen_card_and_original_gate_are_used(self):
        self.program['discovery']['research_card'] = self.card
        self.program['assessments'] = [{'hash': 'gate', 'gates': {'uncertainty': False}}]
        result = review.program_review(self.program, [self.row()], self.rules)
        self.assertEqual(result['card']['origin'], 'frozen')
        self.assertEqual(result['assessment_hash'], 'gate')
        self.assertEqual(result['checks'][-1]['status'], 'fail')

    def test_enrichment_is_idempotent_read_only_and_source_bound(self):
        report = {'generated_at': '2026-10-22', 'engine_version': research.engine_version(), 'policy_hash': 'p',
                  'programs': [self.program], 'observations': [self.row()], 'policy': self.rules}
        before = deepcopy(report)
        version = research.engine_version()
        result = review.enrich(report)
        self.assertEqual(report, before)
        self.assertEqual(review.enrich(result), result)
        self.assertEqual(research.engine_version(), version)
        self.assertEqual(result['research_review']['source_engine_version'], version)
        old_hash = result['research_review']['programs'][0]['evidence_hash']
        report['observations'][0]['benchmark_pct'] = 50
        self.assertNotEqual(review.enrich(report)['research_review']['programs'][0]['evidence_hash'], old_hash)

    def test_cards_reject_missing_unknown_wrong_version_and_blank_fields(self):
        for card in [None, {}, {**self.card, 'code': 'shell'}, {**self.card, 'version': True},
                     {**self.card, 'failure_condition': ' '}, {**self.card, 'evidence': 'x' * 401}]:
            with self.assertRaises(ValueError):
                review.validate_card(card)

    def test_new_start_freezes_card_in_definition_without_changing_other_studies(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = research.load_state(tmp)
            universe = {'market': 'US', 'members': [], 'created_at': '2026-10-22'}
            state['universes']['US'] = {**universe, 'hash': research.digest(universe)}
            research.save_state(tmp, state)
            proposal = {k: deepcopy(self.program[k]) for k in review.PROPOSAL_FIELDS if k in self.program}
            proposal.update(market='US', parent_id=None, research_card=self.card)
            now = datetime(2026, 10, 22, tzinfo=timezone.utc)
            started = review.start_with_card(tmp, proposal, 'owner', now)
            saved = research.load_state(tmp)
            self.assertEqual(saved['programs'][0]['discovery']['research_card'], self.card)
            self.assertEqual(started['engine_version'], research.engine_version())
            before = deepcopy(saved)
            with self.assertRaises(ValueError):
                review.start_with_card(tmp, {**proposal, 'research_card': {}}, 'owner', now)
            self.assertEqual(research.load_state(tmp), before)
            saved['programs'][0]['discovery']['research_card']['evidence'] = 'changed after start'
            research.save_state(tmp, saved)
            with self.assertRaisesRegex(ValueError, 'definition'):
                research.load_state(tmp)


if __name__ == '__main__':
    unittest.main()
