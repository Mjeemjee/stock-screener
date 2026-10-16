import unittest
from datetime import date, timedelta

import numpy as np

from screener.factor_rank import calculate_factors, rerank, score_candidates


def bars(seed=1, last=date(2026, 10, 13)):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.001, 0.01, 60)))
    return [[int((last - timedelta(days=59 - i)).strftime('%Y%m%d')),
             float(c), float(c * 1.01), float(c * .99), float(c), 10000]
            for i, c in enumerate(close)]


def result(strategy='momentum_breakout', count=25):
    return {'meta': {'id': strategy, 'status': 'active'},
            'hits': [{'code': f'US.S{i:02d}'} for i in range(count)]}


class FactorScopeTests(unittest.TestCase):
    def run_rank(self, results, **kwargs):
        return rerank(results, sleep=0, log=lambda _: None, as_of='2026-10-14',
                      fetch_bars=lambda code, market: bars(int(code.split('S')[-1])), **kwargs)

    def test_only_us_momentum_is_ranked_and_hk_slots_stay(self):
        momentum = result()
        momentum['hits'].insert(3, {'code': 'HK.00700'})
        oversold = result('oversold_watch')
        before = [h['code'] for h in oversold['hits']]
        summary = self.run_rank([momentum, oversold])
        self.assertEqual(summary['ranked'], 25)
        self.assertEqual(momentum['hits'][3]['code'], 'HK.00700')
        self.assertEqual([h['code'] for h in oversold['hits']], before)
        self.assertTrue(all('factor_score' not in h for h in oversold['hits']))
        self.assertEqual(summary['scope'], 'US momentum_breakout')

    def test_failed_rerun_clears_old_scores(self):
        r = result()
        self.run_rank([r])
        summary = rerank([r], sleep=0, log=lambda _: None, as_of='2026-10-14',
                         fetch_bars=lambda *_: None)
        self.assertFalse(summary['applied'])
        self.assertTrue(all('factor_score' not in h for h in r['hits']))

    def test_budget_and_insufficient_samples_are_explicit(self):
        r = result()
        summary = self.run_rank([r], max_codes=10)
        self.assertFalse(summary['applied'])
        self.assertEqual(summary['coverage'], 0)
        self.assertEqual(sum(h['factor_status'] == 'budget_excluded' for h in r['hits']), 15)

    def test_stale_and_different_session_bars_excluded(self):
        r = result()
        summary = rerank([r], sleep=0, log=lambda _: None, as_of='2026-10-14',
                         fetch_bars=lambda code, _: bars(1, date(2026, 10, 12)
                                                        if code == 'US.S00' else date(2026, 10, 13)))
        self.assertEqual(summary['ranked'], 24)
        self.assertEqual(next(h for h in r['hits'] if h['code'] == 'US.S00')['factor_status'], 'stale_history')
        summary = rerank([r], sleep=0, log=lambda _: None, as_of='2026-10-25',
                         fetch_bars=lambda *_: bars())
        self.assertFalse(summary['applied'])

    def test_intraday_bar_not_used(self):
        r = result()
        def get(code, _):
            b = bars(int(code.split('S')[-1]))
            b.append([20261014, 999, 1000, 1, 2, 10000])
            return b
        summary = rerank([r], sleep=0, log=lambda _: None, as_of='2026-10-14', fetch_bars=get)
        self.assertTrue(summary['applied'])
        self.assertTrue(all(h['factor_as_of'] == '2026-10-13' for h in r['hits']))

    def test_malformed_history_is_rejected(self):
        b = bars()
        b[-1][2] = 1
        self.assertIsNone(calculate_factors(b))
        b = bars()
        b[-1][0] = b[-2][0]
        self.assertIsNone(calculate_factors(b))
        self.assertIsNone(calculate_factors([['bad']] * 60))

    def test_bad_factor_does_not_poison_other_scores(self):
        raw = {f'US.S{i}': {'bias': i, 'slope': i * 2, 'efficiency': i * .1} for i in range(25)}
        raw['bad'] = {'bias': np.inf, 'slope': 1, 'efficiency': 1}
        scores = score_candidates(raw)
        self.assertEqual(len(scores), 25)
        self.assertTrue(all(np.isfinite(v) for v in scores.values()))
        robust = score_candidates(raw, method='winsorized_zscore')
        self.assertAlmostEqual(np.mean(list(robust.values())), 0)
        self.assertAlmostEqual(np.std(list(robust.values())), 1)


if __name__ == '__main__':
    unittest.main()
