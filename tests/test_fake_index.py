import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zlib

from explicitness_fake_detector import build_index


TESTS = Path(__file__).parent
FAKE = TESTS / "explicitness_fake_detector.py"
CORPUS = json.loads((TESTS / "explicitness_cases.json").read_text())


class FakeIndexTests(unittest.TestCase):
    def run_fake(self, fixture, mode, index=None):
        command = [sys.executable, str(FAKE)]
        if index is not None:
            command += ["--index", str(index)]
        command += [mode, "python", str(fixture.parent), str(fixture), "json", "explicitness", "--strict"]
        return subprocess.run(command, capture_output=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})

    def test_index_matches_standalone_for_source_id_and_missing_cases(self):
        case = next(case for case in CORPUS if case["language"] == "python" and case["exit"] == 2)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            index = root / "index"
            build_index(CORPUS, index)
            fixture = root / (case["id"] + ".py")
            for source, mode in ((case["source"], "correct"), (case["source"], "oracle"),
                                 ("not in the corpus\n", "correct")):
                with self.subTest(source=source, mode=mode):
                    fixture.write_text(source)
                    original = self.run_fake(fixture, mode)
                    indexed = self.run_fake(fixture, mode, index)
                    self.assertEqual((original.returncode, original.stdout, original.stderr),
                                     (indexed.returncode, indexed.stdout, indexed.stderr))

    def test_source_hash_bucket_checks_equality_and_preserves_first_match(self):
        case = next(case for case in CORPUS if case["language"] == "python" and case["exit"] == 2)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            index = root / "index"
            build_index(CORPUS, index)
            fixture = root / "fixture.py"
            fixture.write_text(case["source"])
            expected = self.run_fake(fixture, "correct")
            digest = f"{zlib.crc32(case['source'].encode('utf-8')):08x}"
            bucket = index / "python" / "source" / (digest + ".json")
            decoy = {**case, "source": "different\n", "outcomes": {}}
            duplicate = {**case, "outcomes": {}}
            bucket.write_text(json.dumps([decoy, case, duplicate]))
            actual = self.run_fake(fixture, "correct", index)
            self.assertEqual((expected.returncode, expected.stdout), (actual.returncode, actual.stdout))
            bucket.write_text(json.dumps([decoy]))
            missing = self.run_fake(fixture, "correct", index)
            self.assertEqual(0, missing.returncode)
            self.assertEqual([], json.loads(missing.stdout)["findings"])


if __name__ == "__main__":
    unittest.main()
