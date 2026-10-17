"""Meaningful failure, timing and strategy-identity checks for the free HK source."""
from datetime import datetime, timezone
import unittest
from unittest.mock import Mock, patch

import pandas as pd
import requests

from screener import free_hk_fundamentals as hk
from screener.common import clean, run_strategies
from screener.strategies import value_dividend
from screener.tests.test_strategy_pipeline import stock

NOW = datetime(2026, 10, 17, 12, tzinfo=timezone.utc)


def raw(code="00941", **overrides):
    return {"SECURITY_CODE": code, "SECUCODE": code + ".HK", "IS_CNY_CODE": "0",
            "REPORT_DATE": "2026-06-30", "PE_TTM": 8, "PB_TTM": 1,
            "DIVIDEND_TTM": .6, "DIVIDEND_RATE": 6, "HKSK_MARKET_CAP": 50e9,
            "HK_COMMON_SHARES": 5e9, **overrides}


def snapshot(**overrides):
    return stock("HK.00941", **{"last_price": 10, "quote_time": "2026/10/16 16:08:22", **overrides})


def response(rows, count=None, pages=1):
    return Mock(json=Mock(return_value={"success": True, "result": {
        "data": rows, "count": len(rows) if count is None else count, "pages": pages}}))


class FetchTests(unittest.TestCase):
    def test_complete_pagination(self):
        get = Mock(side_effect=[response([raw(), raw("00005")], 3, 2), response([raw("00700")], 3, 2)])
        with patch.object(hk, "PAGE_SIZE", 2):
            rows = hk.fetch_rows(get=get, sleep=lambda _: None)
        self.assertEqual(len(rows), 3)
        self.assertEqual(get.call_count, 2)
        self.assertEqual(get.call_args.kwargs["params"]["columns"], "ALL")

    def test_truncated_and_duplicate_batches_fail_closed(self):
        for result in [response([raw()], 2), response([raw(), raw()], 2)]:
            with self.subTest(result=result), self.assertRaises(ValueError):
                hk.fetch_rows(get=Mock(return_value=result), sleep=lambda _: None)

    def test_changing_count_is_rejected(self):
        get = Mock(side_effect=[response([raw(), raw("00005")], 3, 2),
                               response([raw("00700")], 4, 2), response([raw("00700")], 4, 2)])
        with patch.object(hk, "PAGE_SIZE", 2), self.assertRaises(ValueError):
            hk.fetch_rows(get=get, sleep=lambda _: None)

    def test_http_json_and_api_failures_have_bounded_retries(self):
        bad_json = Mock(); bad_json.json.side_effect = ValueError("not JSON")
        bad_http = Mock(); bad_http.raise_for_status.side_effect = requests.HTTPError("503")
        for bad in [bad_json, bad_http, Mock(json=Mock(return_value={"success": False})),
                    response([{"SECURITY_CODE": "00941"}])]:
            get = Mock(return_value=bad)
            with self.subTest(bad=bad), self.assertRaises((ValueError, requests.RequestException)):
                hk.fetch_rows(get=get, sleep=lambda _: None)
            self.assertEqual(get.call_count, 2)


class EnrichmentTests(unittest.TestCase):
    def enrich(self, rows=None, snaps=None):
        return hk.enrich(pd.DataFrame(snaps or [snapshot()]), ["HK.00941"], now=NOW,
                         fetch=lambda: [raw()] if rows is None else rows)

    def test_valid_weekend_quote_keeps_original_market_cap_and_source_dates(self):
        original = pd.DataFrame([snapshot()])
        result, summary = hk.enrich(original, ["HK.00941"], now=NOW, fetch=lambda: [raw()])
        self.assertEqual(result.iloc[0]["dividend_ratio_ttm"], 6)
        self.assertEqual(result.iloc[0]["circular_market_val"], original.iloc[0]["circular_market_val"])
        self.assertEqual(result.iloc[0]["hk_market_val"], 50e9)
        self.assertEqual(result.iloc[0]["fundamentals_quote_date"], "2026-10-16")
        self.assertEqual(result.iloc[0]["fundamentals_report_date"], "2026-06-30")
        self.assertEqual(summary["verified_count"], 1)
        self.assertIsNone(original.iloc[0]["pb_ratio"])

    def test_stale_future_quote_and_mismatched_price_are_not_used(self):
        for snap, row, status in [
            (snapshot(quote_time="2026/10/15 16:08:22"), raw(), "stale_quote"),
            (snapshot(quote_time="2026/10/17 16:08:22"), raw(), "stale_quote"),
            (snapshot(), raw(HKSK_MARKET_CAP=80e9), "price_mismatch"),
            (snapshot(), raw(REPORT_DATE="2027-01-01"), "invalid_report_period"),
            (snapshot(), raw(REPORT_DATE="2020-01-01"), "invalid_report_period"),
        ]:
            with self.subTest(status=status):
                result, _ = self.enrich([row], [snap])
                self.assertEqual(result.iloc[0]["fundamentals_status"], status)
                self.assertTrue(pd.isna(result.iloc[0]["pb_ratio"]))

    def test_missing_yield_is_unknown_and_mismatch_is_not_scaled_into_a_hit(self):
        for row in [raw(DIVIDEND_RATE=None), raw(DIVIDEND_RATE=.06),
                    raw(DIVIDEND_TTM=None), raw(DIVIDEND_RATE=float("inf"))]:
            result, summary = self.enrich([row])
            self.assertTrue(pd.isna(result.iloc[0]["dividend_ratio_ttm"]))
            self.assertEqual(summary["dividend_available_count"], 0)

    def test_negative_pe_and_pb_remain_negative_and_do_not_hit(self):
        for row in [raw(PE_TTM=-8), raw(PB_TTM=-1)]:
            result, summary = self.enrich([row])
            strategy = hk.cloud_strategy(summary)
            output = run_strategies(clean(result), [strategy])[0]
            self.assertEqual(output["meta"]["hit_count"], 0)
            self.assertEqual(output["meta"]["execution_status"], "ok")

    def test_rmb_wrong_security_and_outside_official_pool_are_excluded(self):
        for row in [raw(IS_CNY_CODE="1"), raw(SECUCODE="00941.US")]:
            result, _ = self.enrich([row])
            self.assertTrue(pd.isna(result.iloc[0]["pb_ratio"]))
        original = pd.DataFrame([snapshot(), stock("HK.09999"), stock("US.AAPL")])
        result, _ = hk.enrich(original, ["HK.00941"], now=NOW, fetch=lambda: [raw(), raw("09999")])
        self.assertTrue(pd.isna(result.loc[result.code == "HK.09999", "pb_ratio"].iloc[0]))
        self.assertTrue(pd.isna(result.loc[result.code == "US.AAPL", "pb_ratio"].iloc[0]))

    def test_failure_does_not_reuse_values_or_change_other_markets(self):
        snaps = pd.DataFrame([snapshot(pb_ratio=1, dividend_ratio_ttm=8), stock("US.AAPL", pe_ttm_ratio=22)])
        fetch = Mock(side_effect=requests.Timeout("offline"))
        result, summary = hk.enrich(snaps, ["HK.00941"], now=NOW, fetch=fetch)
        self.assertEqual(summary["status"], "error")
        self.assertTrue(pd.isna(result.iloc[0]["dividend_ratio_ttm"]))
        self.assertEqual(result.iloc[1]["pe_ttm_ratio"], 22)
        self.assertEqual(result.iloc[0]["last_price"], 10)
        self.assertEqual(result.iloc[0]["fundamentals_status"], "source_error")

    def test_no_hk_does_not_request_network(self):
        fetch = Mock()
        _, summary = hk.enrich(pd.DataFrame([stock()]), [], now=NOW, fetch=fetch)
        fetch.assert_not_called()
        self.assertEqual(summary["status"], "not_applicable")

    def test_future_time_on_same_completed_session_is_rejected(self):
        friday = datetime(2026, 10, 16, 12, tzinfo=timezone.utc)
        result, _ = hk.enrich(pd.DataFrame([snapshot(quote_time="2026/10/16 23:00:00")]),
                             ["HK.00941"], now=friday, fetch=lambda: [raw()])
        self.assertEqual(result.iloc[0]["fundamentals_status"], "stale_quote")
        self.assertTrue(pd.isna(result.iloc[0]["pb_ratio"]))

    def test_stale_values_cannot_enter_strategy_or_public_serialization(self):
        result, summary = self.enrich(snaps=[snapshot(quote_time="2026/10/15 16:08:22",
                                                    pb_ratio=1, dividend_ratio_ttm=8)])
        output = run_strategies(clean(result), [hk.cloud_strategy(summary)])[0]
        self.assertEqual(output["meta"]["execution_status"], "unavailable")
        self.assertEqual(output["hits"], [])
        self.assertEqual(output["meta"]["unavailable_count"], 1)

    def test_probe_rejects_production_output_before_network(self):
        from scripts.probe_free_hk_value import main
        with patch("scripts.probe_free_hk_value.fetch_hk_universe") as fetch:
            with self.assertRaises(ValueError):
                main("portfolio-board/public/data/screener_results.json")
            fetch.assert_not_called()

    def test_cloud_strategy_is_separate_and_uses_listed_cap_not_legacy_cap(self):
        result, summary = self.enrich()
        result.loc[:, "circular_market_val"] = 1
        strategy = hk.cloud_strategy(summary)
        output = run_strategies(clean(result), [strategy])[0]
        self.assertEqual(output["meta"]["id"], "value_dividend_hk")
        self.assertEqual(output["meta"]["status"], "watch")
        self.assertEqual(output["meta"]["hit_count"], 1)
        self.assertEqual(output["hits"][0]["market_cap_basis"], "hk_listed")
        self.assertEqual(output["hits"][0]["hk_market_val"], 50e9)
        self.assertEqual(output["hits"][0]["circular_market_val"], 1)
        self.assertEqual(value_dividend.META["id"], "value_dividend")
        self.assertNotIn("market_value_field", value_dividend.META["params"])


if __name__ == "__main__":
    unittest.main()
