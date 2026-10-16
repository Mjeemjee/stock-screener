import tempfile
import unittest
from pathlib import Path

from verify_public_build import verify


class PublicBuildTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "index.html").write_text("<html></html>", encoding="utf-8")
        (self.root / "data").mkdir()
        for name in ("screener_results.json", "tracking.json"):
            (self.root / "data" / name).write_text("{}", encoding="utf-8")

    def test_accepts_only_reviewed_public_data(self):
        self.assertEqual(verify(self.root), ["screener_results.json", "tracking.json"])

    def test_rejects_private_files_anywhere(self):
        for name in ("positions.json", "quotes.json", ".env.local", "secret.pem", "secret.key"):
            with self.subTest(name=name):
                file = self.root / name
                file.write_text("private", encoding="utf-8")
                with self.assertRaises(ValueError):
                    verify(self.root)
                file.unlink()

    def test_rejects_unreviewed_data(self):
        (self.root / "data/accounts.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(ValueError):
            verify(self.root)

    def test_requires_built_entry_and_valid_payloads(self):
        (self.root / "data/tracking.json").write_text("[]", encoding="utf-8")
        with self.assertRaises(ValueError):
            verify(self.root)
        (self.root / "index.html").unlink()
        with self.assertRaises(ValueError):
            verify(self.root)
