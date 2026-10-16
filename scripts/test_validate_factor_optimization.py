"""Execution timing and incomplete-data regressions for factor diagnostics."""
import unittest

import numpy as np

from validate_factor_optimization import (
    bootstrap_mean, evaluate_market, holding_result, net_return, performance, split_periods,
)


class FactorValidationTests(unittest.TestCase):
    def test_next_open_to_open_ignores_signal_and_exit_close(self):
        bars = {20240102: [20240102, 90, 999, 80, 999, 100],
                20240103: [20240103, 100, 999, 90, 999, 100],
                20240131: [20240131, 110, 999, 90, 999, 100]}
        result = holding_result(bars, 20240103, 20240131)
        self.assertAlmostEqual(result["gross"], 0.10)
        self.assertTrue(result["filled"])

    def test_missing_entry_stays_cash_and_missing_exit_is_unknown(self):
        bars = {20240103: [20240103, 100, 110, 90, 100, 100]}
        self.assertEqual(holding_result(bars, 20240102, 20240103),
                         {"gross": 0.0, "filled": False, "missing_exit": False})
        result = holding_result(bars, 20240103, 20240131)
        self.assertIsNone(result["gross"])
        self.assertTrue(result["missing_exit"])

    def test_zero_volume_is_not_assumed_executable(self):
        bars = {20240103: [20240103, 100, 110, 90, 100, 0]}
        self.assertFalse(holding_result(bars, 20240103, 20240131)["filled"])

    def test_fees_charge_entry_and_exit_and_do_not_charge_cash(self):
        self.assertAlmostEqual(net_return(0.10, True, 15), 1.1 * 0.9985 / 1.0015 - 1)
        self.assertEqual(net_return(0.10, False, 15), 0)
        self.assertLess(net_return(0, True, 30), net_return(0, True, 15))

    def test_time_split_not_changed_by_missing_outcomes(self):
        rows = [{"valid": i % 2 == 0, "signal_date": i * 20, "entry_date": i * 20 + 1,
                 "exit_date": (i + 1) * 20 + 1} for i in range(30)]
        split_periods(rows)
        self.assertEqual(sum(r["split"] == "development" for r in rows), 18)
        self.assertEqual(rows[18]["split"], "embargo")
        self.assertEqual(rows[19]["split"], "holdout")
        self.assertLess(rows[17]["exit_date"], rows[19]["signal_date"])
        self.assertEqual({r["fold"] for r in rows[19:]}, {1, 2, 3})

    def test_initial_loss_is_in_drawdown(self):
        self.assertAlmostEqual(performance([-0.10, 0.02])["max_drawdown_at_period_end"], -0.10)

    def test_bootstrap_is_reproducible_and_does_not_invent_small_sample_ci(self):
        self.assertEqual(bootstrap_mean(np.arange(20)), bootstrap_mean(np.arange(20)))
        self.assertIsNone(bootstrap_mean([1, 2, 3])["ci95"])
        self.assertEqual(bootstrap_mean([0.5] * 20)["ci95"], [0.5, 0.5])

    def test_bootstrap_keeps_missing_periods_in_calendar(self):
        result = bootstrap_mean([0.1, np.nan, 0.2, 0.3, np.nan, 0.4])
        self.assertEqual(result["scheduled_periods"], 6)
        self.assertEqual(result["n"], 4)
        self.assertAlmostEqual(result["mean"], 0.25)

    def test_future_price_mutation_cannot_change_first_candidate_selection(self):
        stocks = {}
        for i in range(50):
            dates = np.arange(100, dtype=float) + 20240101
            close = 100 + np.arange(100) * (i + 1) / 100
            bars = np.column_stack([dates, close, close + 1, close - 1, close, np.ones(100) * 1000])
            stocks[f"US.TEST{i:02d}"] = {"bars": bars,
                "index": {int(d): j for j, d in enumerate(dates)},
                "by_date": {int(row[0]): row for row in bars}}
        before = evaluate_market(stocks, {})[0]
        code = "US.TEST00"
        stocks[code]["by_date"].pop(before["exit_date"])
        for stock in stocks.values():
            stock["bars"][49:, 1:5] *= 2
        after = evaluate_market(stocks, {})[0]
        self.assertEqual(before["cross_section"], after["cross_section"])
        self.assertEqual(before["methods"]["zscore"]["top_codes"],
                         after["methods"]["zscore"]["top_codes"])
        self.assertTrue(before["valid"])
        self.assertFalse(after["valid"])
        self.assertEqual(after["missing_exits"], [code])


if __name__ == "__main__":
    unittest.main()
