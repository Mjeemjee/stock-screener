import json
from pathlib import Path
import tempfile
import unittest

from scripts.prepare_public_build import prepare


class PublicStagingTests(unittest.TestCase):
    def test_private_and_unexpected_files_never_enter_staging_or_change_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root / "dist"; output = root / "staging"
            (source / "data").mkdir(parents=True)
            (source / "assets").mkdir()
            (source / "index.html").write_text("index", encoding="utf-8")
            (source / "assets/app.js").write_text("app", encoding="utf-8")
            for name in ["screener_results.json", "tracking.json", "positions.json", "quotes.json", "unexpected.json"]:
                (source / "data" / name).write_text(json.dumps({"example": name}), encoding="utf-8")
            result = prepare(source, output)
            self.assertEqual(result, ["screener_results.json", "tracking.json"])
            self.assertTrue((output / "assets/app.js").is_file())
            for name in ["positions.json", "quotes.json", "unexpected.json"]:
                self.assertFalse((output / "data" / name).exists())
                self.assertTrue((source / "data" / name).is_file())

    def test_output_must_be_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for output in [root, root / "inside", root.parent]:
                with self.assertRaises(ValueError):
                    prepare(root, output)


if __name__ == "__main__":
    unittest.main()
