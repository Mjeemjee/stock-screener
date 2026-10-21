from datetime import timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from screener import long_horizon as study
from screener.tracking import read_archives, write_json


class LongStudyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.cal = study.calendar('US')
        self.days = self.cal.sessions_in_range('2024-01-02', '2026-10-20')
        self.today = self.days[350]
        self.now = self.cal.session_close(self.today).to_pydatetime() + timedelta(minutes=5)
        self.members = [{'code': f'US.T{i:02d}', 'name': f'T{i}'} for i in range(35)]
        self.prices = {}
        for i, m in enumerate(self.members):
            self.prices[m['code']] = [[study.day(d), float(100 + t * (.01 + i * .001)),
                float(102 + t * (.01 + i * .001)), float(98 + t * (.01 + i * .001)),
                float(100 + t * (.01 + i * .001)), 10000 + i * 100] for t, d in enumerate(self.days)]
        self.history = self.path / 'history'
        write_json(self.history / 'us.json', {'stocks': [{**m, 'bars': self.prices[m['code']]} for m in self.members]})
        write_json(self.history / 'index.json', {'indexes': {'SPX': {'bars': self.prices['US.T00']}}})

    def run_study(self, now=None):
        return study.run(self.path, self.history, self.path / 'report.json', now=now or self.now,
                         universe={'US': self.members})

    def test_real_freeze_cannot_buy_at_an_already_opened_session(self):
        midday = self.cal.session_open(self.today).to_pydatetime() + timedelta(hours=2)
        entry = study.next_entry('US', midday)
        self.assertEqual(entry, study.day(self.cal.next_session(self.today)))
        before = self.cal.session_open(self.today).to_pydatetime() - timedelta(seconds=1)
        self.assertEqual(study.next_entry('US', before), study.day(self.today))

    def test_completed_signal_ignores_future_bars_and_requires_long_history(self):
        a = study.signal(self.prices, self.members, 'US', study.day(self.today))
        limited = {c: [b for b in bars if b[0] <= study.day(self.today)] for c, bars in self.prices.items()}
        self.assertEqual(a, study.signal(limited, self.members, 'US', study.day(self.today)))
        short = {c: bars[:60] for c, bars in limited.items()}
        self.assertEqual(study.signal(short, self.members, 'US', study.day(self.today))[1]['status'], 'insufficient_data')

    def test_retry_keeps_one_frozen_period_and_twenty_one_session_spacing(self):
        first = self.run_study()
        self.assertEqual(len(first['cohorts']), 1)
        record = read_archives(self.path / 'long_study')[0]
        same = self.run_study(self.now + timedelta(minutes=10))
        self.assertEqual(same['cohorts'][0]['frozen_at'], first['cohorts'][0]['frozen_at'])
        entry = first['cohorts'][0]['entry_date']
        due_signal = self.cal.session_offset(str(entry), 20)
        later = self.run_study(self.cal.session_close(due_signal).to_pydatetime() + timedelta(minutes=1))
        self.assertEqual(len(later['cohorts']), 2)
        self.assertEqual(later['cohorts'][1]['entry_date'], first['cohorts'][0]['exit_date'])
        self.assertEqual(read_archives(self.path / 'long_study')[0], record)

    def test_exact_missing_entry_and_exit_remain_unknown_without_reweighting(self):
        entry, exit_day = study.day(self.days[351]), study.day(self.days[372])
        due = self.cal.session_open(self.days[372]).to_pydatetime() + timedelta(minutes=1)
        prices = dict(self.prices)
        prices['US.T00'] = [b for b in prices['US.T00'] if b[0] != entry]
        result = study.basket(['US.T00', 'US.T01'], prices, entry, exit_day, due, 'US')
        self.assertEqual(result['count'], 2)
        self.assertFalse(result['complete'])
        self.assertIsNone(result['return_pct'])
        self.assertEqual(result['holdings'][0]['status'], 'missing_entry')

    def test_zero_volume_entry_is_unexecuted_cash(self):
        entry, exit_day = study.day(self.days[351]), study.day(self.days[372])
        bars = [b[:] for b in self.prices['US.T00']]
        next(b for b in bars if b[0] == entry)[5] = 0
        result = study.basket(['US.T00'], {'US.T00': bars}, entry, exit_day,
                             self.cal.session_close(self.days[372]).to_pydatetime(), 'US')
        self.assertTrue(result['complete'])
        self.assertEqual(result['return_pct'], 0)

    def test_first_complete_paired_evidence_is_immutable(self):
        report = self.run_study()
        exit_day = report['cohorts'][0]['exit_date']
        later = self.cal.session_open(str(exit_day)).to_pydatetime() + timedelta(minutes=1)
        settled = self.run_study(later)['cohorts'][0]
        self.assertTrue(settled['due'])
        self.assertTrue(settled['baskets']['combined']['complete'])
        altered = {c: [b[:] for b in bars] for c, bars in self.prices.items()}
        for bars in altered.values():
            next(b for b in bars if b[0] == exit_day)[1] *= 1.1
        with patch.object(study, 'load_histories', return_value=(altered, {'SPX': altered['US.T00']})):
            self.assertEqual(self.run_study(later)['cohorts'][0], settled)

    def test_definition_changes_fail_closed(self):
        self.run_study()
        with patch.dict(study.POLICY, {'horizon': 5}):
            with self.assertRaisesRegex(ValueError, 'Immutable'):
                self.run_study()

    def test_missing_samples_cannot_count_towards_review(self):
        rows = [{'due': True, 'baskets': {k: {'complete': False} for k in study.VARIANTS}, 'benchmark_pct': None}] * 30
        values = study.metrics(rows)
        self.assertEqual(values['paired'], 0)
        self.assertEqual(values['stage'], '未达门槛')

    def test_failed_first_twenty_four_periods_cannot_be_rescued_by_later_winners(self):
        def row(value):
            return {'due': True, 'baskets': {k: {'complete': True, 'return_pct': value if k == 'combined' else 0}
                    for k in study.VARIANTS}, 'benchmark_pct': 0,
                    'stress': {'complete': True, 'return_pct': value - .3}}
        failed = [row(-1) for _ in range(24)]
        result = study.metrics(failed + [row(100) for _ in range(50)])
        self.assertEqual(result['stage'], '未达门槛')
        self.assertEqual(result['paired'], 24)
        self.assertEqual(result['mean_net_pct'], -1)
        self.assertEqual(result['total_due'], 74)

    def test_fixed_pool_refresh_is_bounded_and_rotates_failed_or_absent_members(self):
        from screener import long_history_refresh
        universe = self.path / 'universe.json'
        write_json(universe, {'US': self.members})
        fetched = []
        def fetch(code):
            fetched.append(code)
            return [b for b in self.prices[code] if b[0] <= study.day(self.today)]
        with patch.object(long_history_refresh, 'UNIVERSE', universe), patch.object(long_history_refresh, 'load_histories', return_value=({}, {})):
            long_history_refresh.refresh(self.path, self.history, now=self.now, budget=3, fetch=fetch)
            long_history_refresh.refresh(self.path, self.history, now=self.now, budget=3, fetch=fetch)
        self.assertEqual(len(fetched), 6)
        self.assertEqual(len(set(fetched)), 6)


if __name__ == '__main__':
    unittest.main()
