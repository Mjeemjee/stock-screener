from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from restore_screening_archive import restore
from screener.tracking import freeze_snapshot, read_archives


class ArchiveRestoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source, self.target = self.root / "download", self.root / "checkout"
        self.payload = {"generated_at": "2026-10-15T00:00:00Z", "strategies": [
            {"meta": {"id": "test", "hit_count": 0}, "hits": []}]}
        self.record = freeze_snapshot(self.payload, self.source,
                                      frozen_at=datetime(2026, 10, 15, 1, tzinfo=timezone.utc))

    def test_merges_seed_collision_idempotently_without_replacing_original_bytes(self):
        restore(self.source, self.target)
        file = self.target / "snapshots" / f"{self.record['id']}.json"
        file.write_bytes(file.read_bytes().replace(b"\n", b"\r\n"))
        before = file.read_bytes()
        self.assertEqual(restore(self.source, self.target), 1)
        self.assertEqual(file.read_bytes(), before)

    def test_adds_new_snapshots_and_refreshes_only_derived_state(self):
        restore(self.source, self.target)
        payload = deepcopy(self.payload)
        payload["generated_at"] = "2026-10-16T00:00:00Z"
        freeze_snapshot(payload, self.source, frozen_at=datetime(2026, 10, 16, 1, tzinfo=timezone.utc))
        (self.source / "prices").mkdir()
        (self.source / "prices/example.json").write_text('{"code":"US.TEST","bars":[]}', encoding="utf-8")
        (self.source / "fetch_attempts.json").write_text('{"US.TEST":"2026-10-16"}', encoding="utf-8")
        self.assertEqual(restore(self.source, self.target), 2)
        self.assertTrue((self.target / "prices/example.json").exists())
        self.assertEqual(json.loads((self.target / "fetch_attempts.json").read_text())["US.TEST"], "2026-10-16")

    def test_rejects_conflicting_freeze_metadata_before_copying(self):
        restore(self.source, self.target)
        file = self.source / "snapshots" / f"{self.record['id']}.json"
        changed = json.loads(file.read_text())
        changed["frozen_at"] = "2026-10-15T02:00:00Z"
        file.write_text(json.dumps(changed), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            restore(self.source, self.target)
        self.assertEqual(read_archives(self.target)[0]["frozen_at"], self.record["frozen_at"])

    def test_rejects_tampered_payload(self):
        file = self.source / "snapshots" / f"{self.record['id']}.json"
        changed = json.loads(file.read_text())
        changed["payload"]["generated_at"] = "2026-01-01T00:00:00Z"
        file.write_text(json.dumps(changed), encoding="utf-8")
        with self.assertRaises(ValueError):
            restore(self.source, self.target)
        self.assertFalse((self.target / "snapshots").exists())

    def test_rejects_empty_or_same_directory_backup(self):
        with self.assertRaises(ValueError):
            restore(self.root / "empty", self.target)
        with self.assertRaises(ValueError):
            restore(self.source, self.source)

    def test_long_study_is_cumulative_and_immutable(self):
        from screener.factor_research import sealed, read_sealed
        sealed(self.source / 'long_study/definition.json', {'version': 'fixed-test'})
        sealed(self.source / 'long_study/settled/a.json', {'net': 1})
        restore(self.source, self.target)
        restore(self.source, self.target)
        self.assertEqual(read_sealed(self.target / 'long_study/settled/a.json'), {'net': 1})
        sealed(self.target / 'long_study/settled/b.json', {'net': 2})
        with self.assertRaisesRegex(ValueError, 'roll back long-horizon'):
            restore(self.source, self.target)

    def test_model_request_reservations_are_immutable_and_cannot_be_rolled_back(self):
        from screener.factor_research import load_state, save_state, sealed, read_sealed
        save_state(self.source, load_state(self.source))
        sealed(self.source / 'research/ai_requests/a.request.json', {'model': 'deepseek-flash', 'max_attempts': 2})
        restore(self.source, self.target)
        restore(self.source, self.target)
        self.assertEqual(read_sealed(self.target / 'research/ai_requests/a.request.json')['max_attempts'], 2)
        sealed(self.target / 'research/ai_requests/b.request.json', {'model': 'deepseek-flash'})
        with self.assertRaisesRegex(ValueError, 'model request budget'):
            restore(self.source, self.target)

    def test_rejects_snapshot_ids_that_are_not_safe_filenames(self):
        file = self.source / "snapshots" / f"{self.record['id']}.json"
        changed = json.loads(file.read_text())
        changed["id"] = "../outside"
        file.write_text(json.dumps(changed), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "snapshot ID"):
            restore(self.source, self.target)
        self.assertFalse((self.target / "snapshots").exists())
