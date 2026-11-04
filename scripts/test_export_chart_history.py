from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from scripts.export_chart_history import export
from scripts.prepare_public_build import prepare
from scripts.verify_public_build import verify


class CandleExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "data"
        (self.data / "history").mkdir(parents=True)
        self.cache = self.root / "cache"
        self.cache.mkdir()
        self.now = datetime(2026, 10, 23, 22, tzinfo=timezone.utc)
        self.rows = [[20261021, 10, 12, 9, 11, 100], [20261022, 11, 13, 10, 12, 0], [20261023, 12, 14, 11, 13, 200]]
        self.write(self.data / "tracking.json", {"securities": {"US.TEST": {}, "HK.00700": {}}})
        self.write(self.data / "screener_results.json", {})
        self.write(self.data / "history/us.json", {"stocks": [{"code": "US.TEST", "bars": self.rows}]})
        (self.root / "index.html").write_text("html", encoding="utf-8")

    def write(self, path, value):
        path.write_text(json.dumps(value), encoding="utf-8")

    def read(self, code="US.TEST"):
        return json.loads((self.data / "candles" / f"{code}.json").read_text(encoding="utf-8"))

    def run_export(self):
        return export(self.data, self.cache, as_of=self.now)

    def test_exports_exact_ohlcv_and_keeps_tracking_unchanged(self):
        before = (self.data / "tracking.json").read_bytes()
        counts = self.run_export()
        self.assertEqual(counts, {"securities": 2, "available": 1, "unavailable": 1, "fetched": 0})
        self.assertEqual(self.read()["bars"], self.rows)
        self.assertEqual(self.read("HK.00700")["bars"], [])
        self.assertEqual((self.data / "tracking.json").read_bytes(), before)
        verify(self.root)

    def test_unclosed_session_and_future_bars_excluded(self):
        self.now = datetime(2026, 10, 23, 18, tzinfo=timezone.utc)
        self.run_export()
        self.assertEqual(self.read()["bars"], self.rows[:2])

    def test_newer_cache_replaces_whole_series_without_splicing(self):
        cached = [[20261023, 20, 22, 19, 21, 50], [20261026, 21, 23, 20, 22, 60]]
        self.write(self.cache / "price.json", {"code": "US.TEST", "bars": cached})
        self.run_export()
        self.assertEqual(self.read()["bars"], cached[:1])

    def test_same_end_date_uses_base_source_like_tracking(self):
        self.write(self.cache / "price.json", {"code": "US.TEST", "bars": [[20261023, 1, 2, 1, 1, 50]]})
        self.run_export()
        self.assertEqual(self.read()["bars"], self.rows)

    def test_bad_geometry_is_excluded_and_disclosed_without_fabrication(self):
        self.rows[1][2] = 1
        self.write(self.data / "history/us.json", {"stocks": [{"code": "US.TEST", "bars": self.rows}]})
        self.run_export()
        self.assertEqual(self.read()["bars"], [self.rows[0], self.rows[2]])
        self.assertEqual(self.read()["rejected_rows"], 1)

    def test_display_fetch_never_mutates_tracking_price_cache(self):
        count = export(self.data, self.cache, as_of=self.now, fetch_missing=True, fetcher=lambda code: self.rows)
        self.assertEqual(count["fetched"], 1)
        self.assertEqual(list(self.cache.glob("*.json")), [])
        self.assertEqual(self.read("HK.00700")["source"], "chart_history")
        self.run_export()
        self.assertTrue(self.read("HK.00700")["bars"])

    def test_fetch_failure_keeps_unknown_instead_of_filling(self):
        count = export(self.data, self.cache, as_of=self.now, fetch_missing=True, fetcher=lambda code: None)
        self.assertEqual(count["fetched"], 0)
        self.assertEqual(self.read("HK.00700")["bars"], [])

    def test_publish_rejects_extra_fields_and_untracked_prices(self):
        self.run_export()
        value = self.read()
        value["account"] = "private"
        self.write(self.data / "candles/US.TEST.json", value)
        with self.assertRaises(ValueError):
            verify(self.root)
        self.run_export()
        value = self.read()
        value["code"] = "US.OTHER"
        self.write(self.data / "candles/US.OTHER.json", value)
        with self.assertRaises(ValueError):
            verify(self.root)

    def test_staging_copies_reviewed_candles_but_no_account_files(self):
        self.run_export()
        (self.root / "assets").mkdir()
        self.write(self.data / "positions.json", {"private": True})
        output = self.root.parent / (self.root.name + "-public")
        self.addCleanup(lambda: __import__('shutil').rmtree(output, ignore_errors=True))
        names = prepare(self.root, output)
        self.assertIn("candles/US.TEST.json", names)
        self.assertFalse((output / "data/positions.json").exists())

    def test_rejects_path_traversal_codes(self):
        self.write(self.data / "tracking.json", {"securities": {"US.A/../../secret": {}}})
        with self.assertRaises(ValueError):
            self.run_export()


if __name__ == "__main__":
    unittest.main()
