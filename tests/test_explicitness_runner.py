"""Drive the real runner through its CLI with fake detectors for every adapter branch and failure class."""

import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

from explicitness_conformance import load_corpus


TESTS = Path(__file__).parent
RUNNER = TESTS / "explicitness_conformance.py"
FAKE = TESTS / "explicitness_fake_detector.py"
LANGUAGES = ("python", "typescript", "go", "fsharp", "csharp", "rust")
CORPUS = load_corpus()


def ids(language, predicate=lambda case: True):
    return [case["id"] for case in CORPUS if case["language"] == language and predicate(case)]


class ExplicitnessRunnerTests(unittest.TestCase):
    def run_fake(self, mode, language, cases=(), mapped=True, command=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            output = root / "observations.json"
            command = command or shlex.join([sys.executable, str(FAKE), mode, language, str(root)])
            arguments = [sys.executable, str(RUNNER), "--language", language, "--command", command,
                         "--output", str(output), "--fixture-root", str(root / "fixtures")]
            if cases:
                arguments += ["--cases", ",".join(cases)]
            if mapped and language == "csharp":
                arguments += ["--path-map", f"/src={root}"]
            if mapped and language == "rust":
                arguments += ["--path-map", f"/workspace={root}"]
            result = subprocess.run(arguments, capture_output=True, text=True, timeout=600)
            report = json.loads(output.read_text()) if output.exists() else None
        return result, report

    def verdicts(self, report):
        return {item["id"]: item["failures"] for item in report["results"]}

    def test_a_correct_detector_passes_every_case_in_every_adapter_branch(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                result, report = self.run_fake("correct", language)
                self.assertEqual(("", 0), (result.stderr, result.returncode), result.stdout)
                self.assertTrue(report["complete"])
                self.assertEqual(sorted(ids(language)), sorted(self.verdicts(report)))
                self.assertFalse(any(self.verdicts(report).values()))

    def test_a_phantom_owner_fails_every_case(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                result, report = self.run_fake("phantom", language)
                self.assertEqual(1, result.returncode)
                for identity, failures in self.verdicts(report).items():
                    self.assertTrue(any("undeclared or ambiguous owner" in item for item in failures), identity)

    def test_a_blanket_unknown_fails_every_case_whose_truth_is_not_blanket(self):
        def blanket_is_true(case):
            return not case["quiet_owners"] and all(
                set(rules) == {"UnknownEffect"} and 1 in rules["UnknownEffect"] for rules in case["outcomes"].values())
        for language in LANGUAGES:
            with self.subTest(language=language):
                result, report = self.run_fake("blanket", language)
                self.assertEqual(1, result.returncode)
                for case in CORPUS:
                    if case["language"] == language:
                        verdict = self.verdicts(report)[case["id"]]
                        self.assertEqual(not blanket_is_true(case), bool(verdict), case["id"])
                self.assertTrue(all(self.verdicts(report)[identity] for identity in ids(language, lambda case: case["exit"] == 0)))
        result, report = self.run_fake("blanket", "python", ["shadowed_callable"])
        self.assertIn("is on quiet owner helper", "\n".join(self.verdicts(report)["shadowed_callable"]))

    def test_an_empty_report_fails_every_calculation_through_its_twin(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                calculations = ids(language, lambda case: case["exit"] == 0)
                result, report = self.run_fake("empty", language, calculations)
                verdicts = self.verdicts(report)
                self.assertEqual(1, result.returncode)
                self.assertEqual(2 * len(calculations), len(verdicts))
                for identity in calculations:
                    self.assertTrue(any("did not pass in this run" in item for item in verdicts[identity]), identity)

    def test_a_fixture_name_oracle_learns_nothing(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                result, report = self.run_fake("oracle", language)
                self.assertEqual(1, result.returncode)
                verdicts = self.verdicts(report)
                for case in CORPUS:
                    if case["language"] == language:
                        self.assertTrue(verdicts[case["id"]], case["id"])
                fixtures = [Path(item["fixture"]) for item in report["results"]]
                self.assertFalse(any(path.stem in verdicts or path.parent.name in verdicts for path in fixtures))
                self.assertEqual(len(fixtures), len({path.name for path in fixtures}))

    def test_a_relocated_path_fails_and_container_paths_need_the_declared_mapping(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                selection = ids(language, lambda case: case["exit"] == 2)[:3]
                result, report = self.run_fake("wrong_path", language, selection)
                self.assertEqual(1, result.returncode)
                for failures in self.verdicts(report).values():
                    self.assertTrue(any("is outside the fixture" in item for item in failures))
        for language in ("csharp", "rust"):
            with self.subTest(language=language, mapping=False):
                result, report = self.run_fake("correct", language, ids(language, lambda case: case["exit"] == 2)[:3], mapped=False)
                self.assertEqual(1, result.returncode)
                self.assertTrue(all(self.verdicts(report).values()))

    def test_a_wrong_effect_line_fails(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                result, report = self.run_fake("wrong_line", language, ["spread"])
                self.assertEqual(1, result.returncode)
                self.assertIn("is not on an effect line", "\n".join(self.verdicts(report)["spread"]))

    def test_a_malformed_record_fails_its_case_and_the_run_continues(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                result, report = self.run_fake("malformed", language)
                self.assertEqual(1, result.returncode)
                self.assertEqual("", result.stderr)
                self.assertTrue(report["complete"])
                self.assertEqual(len(ids(language)), len(report["results"]))
                for failures in self.verdicts(report).values():
                    self.assertTrue(any("invalid native report" in item for item in failures))

    def test_a_detector_that_hides_suppressed_findings_fails_the_marker_case(self):
        for language in ("python", "typescript", "fsharp", "csharp", "rust"):
            with self.subTest(language=language):
                self.assertIn("suppression_marker", ids(language))
                result, report = self.run_fake("hide_suppressed", language, ["suppression_marker"])
                self.assertEqual(1, result.returncode)
                self.assertTrue(self.verdicts(report)["suppression_marker"])
                result, report = self.run_fake("correct", language, ["suppression_marker"])
                self.assertEqual(0, result.returncode, self.verdicts(report))

    def test_the_output_file_survives_a_crash_part_way_through(self):
        with tempfile.TemporaryDirectory() as directory:
            native = Path(directory) / "native.py"
            counter = Path(directory) / "count"
            native.write_text(
                "import os, subprocess, sys\nfrom pathlib import Path\n"
                f"counter = Path({str(counter)!r})\n"
                "count = int(counter.read_text()) if counter.exists() else 0\ncounter.write_text(str(count + 1))\n"
                "if count == 2:\n    os.kill(os.getppid(), 9)\n"
                f"sys.exit(subprocess.run([sys.executable, {str(FAKE)!r}, 'correct', 'go', '/', *sys.argv[1:]]).returncode)\n")
            result, report = self.run_fake("correct", "go", command=shlex.join([sys.executable, str(native)]))
            self.assertNotEqual(0, result.returncode)
            self.assertFalse(report["complete"])
            self.assertEqual(2, len(report["results"]))

    def test_usage_errors_exit_two(self):
        result, report = self.run_fake("correct", "go", ["no_such_case"])
        self.assertEqual(2, result.returncode)
        self.assertIsNone(report)


if __name__ == "__main__":
    unittest.main()
