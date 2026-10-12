import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest


RUNNER = Path(__file__).with_name("explicitness_conformance.py")


def report(*findings, errors=None):
    return json.dumps({"files": [{"file": "fixture.go", "violations": list(findings)}], "errors": errors or []})


def finding(owner, rule="ImplicitOutput", line=2, detail=None):
    return {"function": owner, "method": "", "beginLine": line, "rule": rule,
            "description": detail or f"The function {owner} has {rule}."}


class ExplicitnessRunnerTests(unittest.TestCase):
    def invoke(self, directory, case, output=None, errors="", status=0):
        native = Path(directory) / "native.py"
        native.write_text(
            "import sys\nfrom pathlib import Path\nassert Path(sys.argv[1]).is_file()\n"
            "assert sys.argv[2:] == ['json', 'explicitness']\n"
            f"sys.stdout.write({report() if output is None else output!r}.replace('fixture.go', sys.argv[1]))\n"
            f"sys.stderr.write({errors!r})\nsys.exit({status})\n"
        )
        output_path = Path(directory) / "observations.json"
        command = shlex.join([sys.executable, str(native)])
        result = subprocess.run(
            [sys.executable, str(RUNNER), "--language", "go", "--cases", case,
             "--command", command, "--output", str(output_path),
             "--fixture-root", str(Path(directory) / "fixtures")],
            capture_output=True, text=True, timeout=20,
        )
        return result, json.loads(output_path.read_text()) if output_path.exists() else None

    def test_calculation_and_unresolved_effect_have_distinct_outcomes(self):
        with tempfile.TemporaryDirectory() as directory:
            result, records = self.invoke(directory, "control")
            self.assertEqual((0, "PASS control\n", ""), (result.returncode, result.stdout, result.stderr))
            self.assertEqual([], records[0]["failures"])
            self.assertEqual([], records[0]["records"])
            result, records = self.invoke(directory, "injected", report(finding("Send", "UnknownEffect")), status=2)
            self.assertEqual((0, "PASS injected\n", ""), (result.returncode, result.stdout, result.stderr))
            self.assertEqual([], records[0]["failures"])
            result, records = self.invoke(directory, "injected")
            self.assertEqual(1, result.returncode)
            self.assertIn("exit 0, expected 2", records[0]["failures"])
            self.assertIn("Send effects [], expected ['UnknownEffect']", records[0]["failures"])

    def test_a_caller_name_in_one_finding_does_not_prove_propagation(self):
        with tempfile.TemporaryDirectory() as directory:
            result, records = self.invoke(directory, "spread", report(finding("Leaf", detail="Leaf calls Wrapper")), status=2)
            self.assertEqual(1, result.returncode)
            self.assertIn("Wrapper effects [], expected ['ImplicitOutput']", records[0]["failures"])
            self.assertIn("ImplicitOutput owners 1, expected at least 2", records[0]["failures"])
            result, records = self.invoke(directory, "spread", report(finding("Leaf"), finding("Wrapper", line=4)), status=2)
            self.assertEqual((0, "PASS spread\n", ""), (result.returncode, result.stdout, result.stderr))

    def test_duplicate_records_and_two_caller_records_do_not_prove_a_leaf_effect(self):
        with tempfile.TemporaryDirectory() as directory:
            result, records = self.invoke(directory, "spread", report(finding("Wrapper"), finding("Wrapper")), status=2)
            self.assertEqual(1, result.returncode)
            self.assertTrue(any("Duplicate findings" in item for item in records[0]["failures"]))
            result, records = self.invoke(directory, "spread", report(finding("Wrapper"), finding("Wrapper", line=4)), status=2)
            self.assertEqual(1, result.returncode)
            self.assertIn("Leaf effects [], expected ['ImplicitOutput']", records[0]["failures"])

    def test_unknown_does_not_fabricate_a_known_action(self):
        with tempfile.TemporaryDirectory() as directory:
            output = report(finding("Send", "UnknownEffect"), finding("Send", "ImplicitOutput"))
            result, records = self.invoke(directory, "injected", output, status=2)
            self.assertEqual(1, result.returncode)
            self.assertIn("unexpected effect kinds ['ImplicitOutput']", records[0]["failures"])

    def test_factory_metadata_cannot_be_hidden_in_a_callback_message(self):
        with tempfile.TemporaryDirectory() as directory:
            result, records = self.invoke(directory, "factory", report(finding("Build", detail="ImplicitOutput in <lambda>")), status=2)
            self.assertEqual(1, result.returncode)
            self.assertIn("Build must not own a finding", records[0]["failures"])
            result, records = self.invoke(directory, "factory", report(finding("<lambda>")), status=2)
            self.assertEqual(0, result.returncode)

    def test_stderr_and_tool_failures_are_not_semantic_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            result, records = self.invoke(directory, "control", errors="broken compiler\n", status=1)
            self.assertEqual(1, result.returncode)
            self.assertEqual(["exit 1, expected 0", "stderr broken compiler"], records[0]["failures"])
            result, records = self.invoke(directory, "control", report(errors=[{"message": "parse failed"}]))
            self.assertEqual(1, result.returncode)
            self.assertTrue(any("processing errors" in item for item in records[0]["failures"]))
            result, records = self.invoke(directory, "control", "")
            self.assertEqual(1, result.returncode)
            self.assertTrue(any("invalid native report" in item for item in records[0]["failures"]))

    def test_wrong_source_locations_do_not_establish_effects(self):
        with tempfile.TemporaryDirectory() as directory:
            output = report(finding("Send", "UnknownEffect", line=999))
            result, records = self.invoke(directory, "injected", output, status=2)
            self.assertEqual(1, result.returncode)
            self.assertTrue(any("outside this fixture" in item for item in records[0]["failures"]))
            output = report(finding("Send", "UnknownEffect", line=2)).replace("fixture.go", "other.go")
            result, records = self.invoke(directory, "injected", output, status=2)
            self.assertEqual(1, result.returncode)
            self.assertTrue(any("outside this fixture" in item for item in records[0]["failures"]))

    def test_invalid_selection_never_succeeds(self):
        with tempfile.TemporaryDirectory() as directory:
            result, records = self.invoke(directory, "does_not_exist")
            self.assertEqual(2, result.returncode)
            self.assertIsNone(records)
            self.assertIn("selection does not exist", result.stderr)


if __name__ == "__main__":
    unittest.main()
