from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from screener.common import clean, finalize_results, run_strategies
from screener.risk import risk_metrics, session_open
from screener.strategies import momentum_breakout
from screener.tests.test_strategy_pipeline import stock
from screener.tracking import evaluate_holding, evaluate_record, freeze_snapshot, read_archives, summarize, update_tracking, write_json


def fixture():
    return {"generated_at": "2026-10-01T12:00:00+00:00", "strategies": [{
        "meta": {"id": "momentum_breakout", "name": "Momentum", "hit_count": 2},
        "hits": [{"code": "US.B", "name": "B", "original_market_rank": 2},
                 {"code": "US.A", "name": "A", "original_market_rank": 1}],
    }]}


def history(n=75):
    dates = pd.bdate_range("2026-10-01", periods=n)
    return [[int(day.strftime("%Y%m%d")), 100 + i, 102 + i, 99 + i, 101 + i, 1000] for i, day in enumerate(dates)]


class TrackingTests(unittest.TestCase):
    def test_archive_is_immutable_complete_and_idempotent(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            payload = fixture()
            first = freeze_snapshot(payload, temp, frozen_at=datetime(2026, 10, 1, 12, 10, tzinfo=timezone.utc))
            again = freeze_snapshot(payload, temp, frozen_at=datetime(2026, 10, 2, tzinfo=timezone.utc))
            self.assertEqual(first, again)
            self.assertEqual(len(read_archives(temp)), 1)
            self.assertEqual(first["payload"]["strategies"][0]["hits"][1]["selection_market_rank"], 2)
            self.assertNotIn("selection_market_rank", payload["strategies"][0]["hits"][0])
            payload["strategies"][0]["meta"]["hit_count"] = 3
            with self.assertRaisesRegex(ValueError, "truncated"):
                freeze_snapshot(payload, temp)
            imported = freeze_snapshot(payload, temp, prospective=False)
            self.assertFalse(imported["complete_candidates"])
            self.assertEqual(imported["provenance"], "historical_import")

    def test_naive_and_future_timestamps_cannot_be_prospective(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            payload = fixture()
            payload["generated_at"] = "2026-10-01 12:00:00"
            with self.assertRaises(ValueError):
                freeze_snapshot(payload, temp)
            payload["generated_at"] = "2099-01-01T00:00:00Z"
            with self.assertRaises(ValueError):
                freeze_snapshot(payload, temp)

    def test_tampering_with_frozen_payload_is_detected(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            record = freeze_snapshot(fixture(), temp, frozen_at=datetime(2026, 10, 1, 12, 10, tzinfo=timezone.utc))
            path = next((Path(temp) / 'snapshots').glob('*.json'))
            record['payload']['strategies'][0]['hits'][0]['code'] = 'US.TAMPERED'
            path.write_text(json.dumps(record), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'integrity'):
                read_archives(temp)

    def test_first_open_after_freeze_and_session_horizons(self):
        record = {"id": "id", "frozen_at": "2026-10-01T14:00:00Z", "strategy_version": "v1",
                  "provenance": "prospective", "payload": fixture()}
        bars = history()
        rows = evaluate_record(record, {"US.A": bars, "US.B": bars}, {"SPX": bars},
                               as_of=datetime(2027, 2, 1, tzinfo=timezone.utc))
        row = rows[0]
        self.assertEqual(row["entry_date"], bars[1][0])
        self.assertEqual(row["exit_date"], bars[6][0])
        self.assertTrue(row["baskets"]["selected"]["complete"])
        self.assertEqual([item["code"] for item in row["baskets"]["original"]["holdings"]], ["US.A", "US.B"])

    def test_timezone_dst_and_hk_open(self):
        self.assertEqual(session_open(20260701, "US").hour, 13)
        self.assertEqual(session_open(20261201, "US").hour, 14)
        self.assertEqual(session_open(20261201, "HK").hour, 1)
        self.assertEqual(session_open(20261201, "HK").minute, 30)

    def test_missing_index_row_is_not_treated_as_a_holiday(self):
        record = {"id": "id", "frozen_at": "2026-10-01T12:00:00Z", "strategy_version": "v1",
                  "provenance": "prospective", "payload": fixture()}
        bars = history()
        index_with_gap = bars[1:]
        row = evaluate_record(record, {"US.A": bars, "US.B": bars}, {"SPX": index_with_gap},
                              as_of=datetime(2027, 2, 1, tzinfo=timezone.utc))[0]
        self.assertEqual(row["entry_date"], 20261001)
        self.assertIsNone(row["benchmark_pct"])

    def test_nyse_holiday_is_skipped_and_half_day_close_is_respected(self):
        from screener.risk import completed_bars
        record = {"id": "id", "frozen_at": "2026-11-25T22:00:00Z", "strategy_version": "v1",
                  "provenance": "prospective", "payload": fixture()}
        row = evaluate_record(record, {}, {}, as_of=datetime(2026, 11, 27, 16, tzinfo=timezone.utc))[0]
        self.assertEqual(row["entry_date"], 20261127)
        bars = [[20261127, 100, 101, 99, 100, 1000]]
        self.assertEqual(len(completed_bars(bars, 'US', datetime(2026, 11, 27, 18, 1, tzinfo=timezone.utc))), 1)

    def test_fees_and_no_trade_cash(self):
        bars = [[20261001, 100, 110, 90, 105, 100], [20261008, 110, 120, 100, 115, 100]]
        result = evaluate_holding(bars, 20261001, 20261008)
        self.assertAlmostEqual(result["return_pct"], (1.1 * .9985 / 1.0015 - 1) * 100, places=5)
        bars[0][5] = 0
        result = evaluate_holding(bars, 20261001, 20261008)
        self.assertEqual(result, {"status": "no_trade", "return_pct": 0.0})

    def test_missing_exit_never_reweights_other_holdings(self):
        record = {"id": "id", "frozen_at": "2026-10-01T12:00:00Z", "strategy_version": "v1",
                  "provenance": "prospective", "payload": fixture()}
        bars = history()
        missing = [bar for i, bar in enumerate(bars) if i != 5]
        row = evaluate_record(record, {"US.A": bars, "US.B": missing}, {"SPX": bars},
                              as_of=datetime(2027, 2, 1, tzinfo=timezone.utc))[0]
        self.assertFalse(row["baskets"]["selected"]["complete"])
        self.assertIsNone(row["baskets"]["selected"]["return_pct"])
        self.assertEqual(row["baskets"]["selected"]["known_count"], 1)

    def test_pending_not_prematurely_matured(self):
        record = {"id": "id", "frozen_at": "2026-10-01T12:00:00Z", "strategy_version": "v1",
                  "provenance": "prospective", "payload": fixture()}
        bars = history()
        rows = evaluate_record(record, {"US.A": bars, "US.B": bars}, {"SPX": bars},
                               as_of=datetime(2026, 10, 2, 12, tzinfo=timezone.utc))
        self.assertTrue(all(row["exit_date"] is None for row in rows))
        self.assertTrue(all(not row["baskets"]["selected"]["complete"] for row in rows))

    def test_imports_and_same_day_retries_excluded_from_summary(self):
        records = [{"id": "one", "frozen_at": "2026-10-01T12:00:00Z", "strategy_version": "v1", "provenance": "prospective"},
                   {"id": "two", "frozen_at": "2026-10-01T13:00:00Z", "strategy_version": "v1", "provenance": "prospective"},
                   {"id": "old", "frozen_at": "2026-10-02T12:00:00Z", "strategy_version": "v1", "provenance": "historical_import"}]
        row = {"strategy_id": "m", "market": "US", "horizon": 5, "strategy_version": "v1", "benchmark_pct": 1,
               "baskets": {"selected": {"complete": True, "return_pct": 5}, "original": {"complete": True, "return_pct": 3}}}
        result = summarize([{**row, "snapshot_id": r["id"]} for r in records], records)
        self.assertEqual(result[0]["cohorts"], 1)
        self.assertEqual(result[0]["matured_pairs"], 1)
        self.assertEqual(result[0]["mean_delta_pp"], 2)

    def test_empty_pipeline_exports_valid_json(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            output = Path(temp) / "tracking.json"
            result = update_tracking(temp, Path(temp) / "history", output)
            self.assertEqual(result["archives"], [])
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["summary"], [])

    def test_failed_history_requests_do_not_starve_the_rest_of_the_queue(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            freeze_snapshot(fixture(), temp, frozen_at=datetime(2026, 10, 1, 12, 10, tzinfo=timezone.utc))
            with patch('screener.history_fetch.us_bars', return_value=None) as fetch, patch('screener.tracking.time.sleep'):
                update_tracking(temp, Path(temp) / 'history', Path(temp) / 'one.json',
                                as_of=datetime(2026, 10, 15, tzinfo=timezone.utc), fetch_missing=True, max_fetch=1)
                update_tracking(temp, Path(temp) / 'history', Path(temp) / 'two.json',
                                as_of=datetime(2026, 10, 16, tzinfo=timezone.utc), fetch_missing=True, max_fetch=1)
                self.assertEqual([call.args[0] for call in fetch.call_args_list], ['US.A', 'US.B'])

    def test_windows_derived_file_refresh_survives_replace_lock(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            path = Path(temp) / 'derived.json'
            from types import SimpleNamespace
            with patch('screener.tracking.os', SimpleNamespace(name='nt')), patch.object(Path, 'replace', side_effect=PermissionError), \
                    patch('screener.tracking.time.sleep'):
                write_json(path, {'new': 1})
            self.assertEqual(json.loads(path.read_text()), {'new': 1})

    def test_archive_survives_restore_into_a_fresh_runner_directory(self):
        import shutil
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            one, two = Path(temp) / "run1", Path(temp) / "run2"
            first = freeze_snapshot(fixture(), one, frozen_at=datetime(2026, 10, 1, 12, 10, tzinfo=timezone.utc))
            shutil.copytree(one, two)
            second = fixture()
            second["generated_at"] = "2026-10-02T12:00:00Z"
            freeze_snapshot(second, two, frozen_at=datetime(2026, 10, 2, 12, 10, tzinfo=timezone.utc))
            restored = read_archives(two)
            self.assertEqual(len(restored), 2)
            self.assertEqual(restored[0], first)

    def test_future_prices_do_not_change_frozen_basket_selection(self):
        record = {"id": "id", "frozen_at": "2026-10-01T12:00:00Z", "strategy_version": "v1",
                  "provenance": "prospective", "payload": fixture()}
        bars = history()
        before = evaluate_record(record, {"US.A": bars, "US.B": bars}, {"SPX": bars},
                                 as_of=datetime(2027, 2, 1, tzinfo=timezone.utc))
        changed = deepcopy(bars)
        for bar in changed[1:]:
            bar[1] *= 10
        after = evaluate_record(record, {"US.A": changed, "US.B": bars}, {"SPX": bars},
                                as_of=datetime(2027, 2, 1, tzinfo=timezone.utc))
        for mode in ('original', 'selected'):
            self.assertEqual([h["code"] for h in before[0]["baskets"][mode]["holdings"]],
                             [h["code"] for h in after[0]["baskets"][mode]["holdings"]])


class MarketAndRiskTests(unittest.TestCase):
    def test_display_cap_keeps_both_markets_in_their_own_order(self):
        results = [{"meta": {"hit_count": 80}, "hits":
                    [{"code": f"US.A{i}"} for i in range(40)] + [{"code": f"HK.{i:05d}"} for i in range(40)]}]
        finalize_results(results)
        codes = [hit["code"] for hit in results[0]["hits"]]
        self.assertEqual(len(codes), 50)
        self.assertEqual(codes[0:4], ["US.A0", "HK.00000", "US.A1", "HK.00001"])
        self.assertEqual(sum(code.startswith("HK.") for code in codes), 25)

    def test_market_thresholds_differ_and_are_recorded(self):
        df = clean(pd.DataFrame([stock("US.SMALL", circular_market_val=2.5e9),
                                 stock("HK.00001", circular_market_val=2.5e9),
                                 stock("HK.00002", circular_market_val=16e9, turnover=2e8)]))
        result = run_strategies(df, [momentum_breakout])[0]
        self.assertEqual({h["code"] for h in result["hits"]}, {"US.SMALL", "HK.00002"})
        self.assertEqual(result["meta"]["market_params"]["HK"]["min_market_val"], 15.6e9)
        self.assertTrue(all("original_market_rank" in h for h in result["hits"]))

    def test_optional_median_filter_requires_history(self):
        from types import SimpleNamespace
        meta = deepcopy(momentum_breakout.META)
        meta["market_params"] = {"US": {"use_median_liquidity": True}}
        module = SimpleNamespace(META=meta, required_fields=momentum_breakout.required_fields, run=momentum_breakout.run)
        result = run_strategies(clean(pd.DataFrame([stock()])), [module])[0]
        self.assertEqual(result["meta"]["execution_status"], "unavailable")

    def test_risk_drops_incomplete_future_bars(self):
        bars = history(30)
        cutoff = datetime(2026, 10, 30, 12, tzinfo=timezone.utc)
        first = risk_metrics(bars, "US", cutoff)
        mutated = deepcopy(bars)
        for bar in mutated:
            if bar[0] >= 20261030:
                bar[1:5] = [100000, 100001, 99999, 100000]
        second = risk_metrics(mutated, "US", cutoff)
        self.assertEqual(first, second)
        self.assertEqual(first["risk_as_of"], "20261029")
        self.assertEqual(risk_metrics(bars[:10], "US", cutoff)["risk_status"], "insufficient_history")
        self.assertEqual(risk_metrics(bars[:21], "US", datetime(2027, 2, 1, tzinfo=timezone.utc))["risk_status"], "stale_history")


if __name__ == "__main__":
    unittest.main()
