"""Offline regression coverage for snapshot cleaning and strategy execution."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pandas as pd
import requests

from screener import cloud_engine
from screener.common import clean, finalize_results, run_strategies, to_records
from screener.strategies import momentum_breakout, oversold_watch, value_dividend


def stock(code="US.AAPL", **overrides):
    row = {
        "code": code, "name": code, "last_price": 100.0,
        "prev_close_price": 99.0, "change_rate": 1.0,
        "turnover": 3e7, "turnover_rate": None,
        "highest52weeks_price": 101.0, "lowest52weeks_price": 95.0,
        "circular_market_val": 2e10, "pe_ratio": 8.0,
        "pe_ttm_ratio": None, "pb_ratio": None, "dividend_ratio_ttm": None,
    }
    row.update(overrides)
    return row


def tx_line(code="usAAPL", **values):
    fields = [""] * 50
    fields[1] = "Apple"
    defaults = {3: "100", 4: "99", 32: "1", 36: "500", 37: "30000000",
                39: "8", 44: "200", 48: "101", 49: "95"}
    defaults.update({int(key): value for key, value in values.items()})
    for index, value in defaults.items():
        fields[index] = value
    return f'v_{code}="' + "~".join(fields) + '";'


class CleaningTests(unittest.TestCase):
    def test_partial_change_is_repaired_per_row_without_dividing_by_zero(self):
        df = clean(pd.DataFrame([
            stock(change_rate=None), stock("US.B", prev_close_price=0, change_rate=None),
            stock("US.C", change_rate=7),
        ])).set_index("code")
        self.assertAlmostEqual(df.loc["US.AAPL", "change_rate"], 100 / 99 * 100 - 100)
        self.assertTrue(pd.isna(df.loc["US.B", "change_rate"]))
        self.assertEqual(df.loc["US.C", "change_rate"], 7)

    def test_nonfinite_prices_turnover_duplicates_and_suspensions_are_excluded(self):
        df = clean(pd.DataFrame([
            stock(), stock(last_price=102), stock("US.INF", last_price=float("inf")),
            stock("US.BAD", turnover=float("inf")), stock("HK.00001", suspension=True),
            stock("HK.00002", suspension="false"), stock("invalid"),
        ]))
        self.assertEqual(df["code"].tolist(), ["US.AAPL", "HK.00002"])
        self.assertEqual(df.iloc[0]["last_price"], 102)
        self.assertEqual(df.attrs["data_quality"]["duplicate_count"], 1)
        self.assertEqual(df.attrs["data_quality"]["excluded_count"], 5)

    def test_zero_and_inverted_ranges_cannot_generate_hits(self):
        df = clean(pd.DataFrame([
            stock(highest52weeks_price=0, lowest52weeks_price=0),
            stock("US.BAD", highest52weeks_price=80, lowest52weeks_price=90),
        ]))
        self.assertTrue(df[["off_52w_high_pct", "off_52w_low_pct"]].isna().all().all())
        results = run_strategies(df, [momentum_breakout, oversold_watch])
        self.assertTrue(all(result["hits"] == [] for result in results))
        self.assertTrue(all(result["meta"]["execution_status"] == "unavailable" for result in results))

    def test_missing_optional_columns_and_empty_input_have_stable_schema(self):
        df = clean(pd.DataFrame([{"code": "US.A", "last_price": 10, "turnover": 100}]))
        self.assertTrue(pd.isna(df.iloc[0]["off_52w_high_pct"]))
        results = run_strategies(clean(pd.DataFrame()))
        self.assertEqual(len(results), 3)
        self.assertTrue(all(result["meta"]["execution_status"] == "ok" for result in results))

    def test_serialization_never_exports_infinity_or_nan(self):
        records = to_records(pd.DataFrame([{"code": "US.A", "last_price": float("inf"),
                                            "change_rate": float("nan")}]))
        self.assertIsNone(records[0]["last_price"])
        self.assertIsNone(records[0]["change_rate"])
        json.dumps(records, allow_nan=False)

    def test_missing_names_remain_renderable_with_code_fallback(self):
        df = clean(pd.DataFrame([stock(name=None), stock("US.B", name=" ")]))
        self.assertEqual(df["name"].tolist(), ["US.AAPL", "US.B"])


class StrategyTests(unittest.TestCase):
    def test_mixed_turnover_uses_each_stocks_own_availability(self):
        df = clean(pd.DataFrame([
            stock("US.RATE", turnover_rate=0.7, turnover=1e6),
            stock("US.FALLBACK", turnover_rate=None),
            stock("US.LOWRATE", turnover_rate=0.1, turnover=1e9),
            stock("US.LOWTURN", turnover_rate=None, turnover=1e6),
        ]))
        hits = momentum_breakout.run(df, {})
        self.assertEqual(set(hits["code"]), {"US.RATE", "US.FALLBACK"})
        self.assertIn("成交额", hits.set_index("code").loc["US.FALLBACK", "reason"])
        self.assertIn("换手", hits.set_index("code").loc["US.RATE", "reason"])

    def test_unavailable_value_data_is_distinct_from_zero_matches(self):
        missing = run_strategies(clean(pd.DataFrame([stock()])), [value_dividend])[0]
        self.assertEqual(missing["meta"]["execution_status"], "unavailable")
        self.assertEqual(set(missing["meta"]["missing_fields"]), {"US:pb_ratio", "US:dividend_ratio_ttm"})
        complete = run_strategies(clean(pd.DataFrame([
            stock(pb_ratio=2, dividend_ratio_ttm=1),
        ])), [value_dividend])[0]
        self.assertEqual(complete["meta"]["execution_status"], "ok")
        self.assertEqual(complete["meta"]["hit_count"], 0)

    def test_partial_value_coverage_counts_only_eligible_stocks(self):
        result = run_strategies(clean(pd.DataFrame([
            stock("US.VALID", pb_ratio=1, dividend_ratio_ttm=6), stock("US.MISSING"),
        ])), [value_dividend])[0]
        self.assertEqual(result["meta"]["eligible_count"], 1)
        self.assertEqual(result["meta"]["unavailable_count"], 1)
        self.assertEqual(result["hits"][0]["code"], "US.VALID")
        self.assertIn("TTM 缺失", result["hits"][0]["reason"])

    def test_paused_strategy_is_not_called(self):
        strategy = SimpleNamespace(META={"id": "paused", "status": "paused"}, run=Mock())
        result = run_strategies(clean(pd.DataFrame([stock()])), [strategy])[0]
        strategy.run.assert_not_called()
        self.assertEqual(result["meta"]["execution_status"], "paused")

    def test_declared_market_is_enforced_and_failure_is_isolated(self):
        hk = SimpleNamespace(META={"id": "hk", "markets": ["HK"]}, run=lambda df, params: df)
        broken = SimpleNamespace(META={"id": "broken"}, run=Mock(side_effect=ValueError("fixture")))
        results = run_strategies(clean(pd.DataFrame([stock(), stock("HK.00001")])), [broken, hk])
        self.assertEqual(results[0]["meta"]["execution_status"], "error")
        self.assertEqual([hit["code"] for hit in results[1]["hits"]], ["HK.00001"])

    def test_candidates_are_capped_after_ranking_and_totals_remain_honest(self):
        strategy = SimpleNamespace(META={"id": "all"}, run=lambda df, params: df)
        df = clean(pd.DataFrame([stock(f"US.A{i:03d}") for i in range(75)]))
        results = run_strategies(df, [strategy])
        self.assertEqual(len(results[0]["hits"]), 75)
        results[0]["hits"].reverse()
        finalize_results(results, limit=50)
        self.assertEqual(results[0]["hits"][0]["code"], "US.A074")
        self.assertEqual(results[0]["meta"]["hit_count"], 75)
        self.assertEqual(results[0]["meta"]["displayed_count"], 50)
        self.assertTrue(results[0]["meta"]["truncated"])

    def test_optional_profit_filter_does_not_claim_unprofitable_stock_is_profitable(self):
        df = clean(pd.DataFrame([stock(pe_ratio=-1)]))
        self.assertTrue(oversold_watch.run(df, {}).empty)
        hits = oversold_watch.run(df, {"require_profitable": False})
        self.assertEqual(len(hits), 1)
        self.assertNotIn("仍盈利", hits.iloc[0]["reason"])


class CloudSnapshotTests(unittest.TestCase):
    def test_main_ranks_all_hits_before_truncation_and_can_skip_history(self):
        snap = pd.DataFrame([stock(f"US.A{i:03d}") for i in range(75)])
        us = snap[["code", "name"]].assign(market="US")
        hk = pd.DataFrame(columns=["code", "name", "market"])

        def rank_all(results):
            self.assertEqual(len(results[0]["hits"]), 75)
            results[0]["hits"].reverse()
            return {"applied": True}

        with patch.object(cloud_engine, "fetch_hk_universe", return_value=hk), \
                patch.object(cloud_engine, "fetch_us_universe", return_value=us), \
                patch.object(cloud_engine, "fetch_tx_snapshots", return_value=snap), \
                patch.object(cloud_engine, "load_strategies", return_value=[momentum_breakout]), \
                patch("screener.factor_rank.rerank", side_effect=rank_all), \
                patch.object(cloud_engine, "save_payload") as save, \
                patch("screener.tracking.freeze_snapshot", return_value={"id": "fixture", "strategy_version": "fixture"}), \
                patch("screener.tracking.update_tracking"), \
                patch("screener.history_fetch.main") as history:
            cloud_engine.main(output_path="isolated.json", include_history=False)
        payload = save.call_args.args[0]
        self.assertEqual(save.call_args.kwargs["path"], "isolated.json")
        self.assertEqual(len(payload["strategies"][0]["hits"]), 50)
        self.assertEqual(payload["strategies"][0]["meta"]["hit_count"], 75)
        self.assertEqual(payload["strategies"][0]["hits"][0]["code"], "US.A074")
        self.assertTrue(payload["generated_at"].endswith("+00:00"))
        history.assert_not_called()

    def test_tencent_parser_rejects_nonfinite_fields(self):
        rec = cloud_engine.parse_tx_line(tx_line(**{"3": "Infinity", "39": "NaN"}))
        self.assertIsNone(rec["last_price"])
        self.assertIsNone(rec["pe_ratio"])
        self.assertEqual(rec["lowest52weeks_price"], 95)

    @patch("screener.cloud_engine.time.sleep")
    @patch("screener.cloud_engine.requests.get")
    def test_empty_snapshot_response_fails_before_any_output_is_written(self, get, sleep):
        get.return_value = Mock(text='v_pv_none_match="1";')
        with self.assertRaisesRegex(RuntimeError, "无有效记录"):
            cloud_engine.fetch_tx_snapshots(["US.AAPL"])

    @patch("screener.cloud_engine.time.sleep")
    @patch("screener.cloud_engine.requests.get")
    def test_http_errors_are_retried_and_partial_coverage_is_recorded(self, get, sleep):
        failed = Mock()
        failed.raise_for_status.side_effect = requests.HTTPError("502")
        good = Mock(text=tx_line())
        get.side_effect = [failed, failed, failed, good]
        with patch.object(cloud_engine, "TX_BATCH", 1):
            df = cloud_engine.fetch_tx_snapshots(["US.MISSING", "US.AAPL"])
        self.assertEqual(get.call_count, 4)
        self.assertEqual(df.attrs["snapshot_quality"], {
            "requested_count": 2, "received_count": 1, "coverage_pct": 50.0, "failed_batches": 1,
        })


if __name__ == "__main__":
    unittest.main()
