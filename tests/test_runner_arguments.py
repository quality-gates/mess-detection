import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest


TESTS = Path(__file__).parent
RUNNER = TESTS / "explicitness_conformance.py"
FAKE = TESTS / "explicitness_fake_detector.py"


class RunnerArgumentTests(unittest.TestCase):
    def test_invalid_arguments_do_not_start_a_run_or_modify_output(self):
        for arguments, message in ((["--command", "'"], "No closing quotation"),
                                   (["--command", "/bin/echo", "--timeout", "NaN"], "timeout"),
                                   (["--command", "/bin/echo", "--timeout", "inf"], "timeout"),
                                   (["--command", "/bin/echo", "--timeout=-inf"], "timeout")):
            for existing in (False, True):
                with self.subTest(arguments=arguments, existing=existing), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    output = root / "report.json"
                    fixtures = root / "fixtures"
                    if existing:
                        output.write_text("unchanged")
                    result = subprocess.run([sys.executable, str(RUNNER), "--language", "python", "--cases", "control",
                                             "--output", str(output), "--fixture-root", str(fixtures), *arguments],
                                            capture_output=True, text=True)
                    self.assertEqual(2, result.returncode, result.stderr)
                    self.assertIn("usage:", result.stderr)
                    self.assertIn(message, result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
                    self.assertEqual("", result.stdout)
                    self.assertFalse(fixtures.exists())
                    if existing:
                        self.assertEqual("unchanged", output.read_text())
                    else:
                        self.assertFalse(output.exists())

    def test_finite_timeout_and_quoted_command_run_selected_cases(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "report.json"
            command = shlex.join([sys.executable, str(FAKE), "correct", "python", str(root)])
            result = subprocess.run([sys.executable, str(RUNNER), "--language", "python", "--cases", "control",
                                     "--command", command, "--timeout", "10.5", "--output", str(output)],
                                    capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            report = json.loads(output.read_text())
            self.assertTrue(report["complete"])
            self.assertIn("control", [case["id"] for case in report["results"]])
            self.assertTrue(all(not case["failures"] for case in report["results"]))


if __name__ == "__main__":
    unittest.main()
