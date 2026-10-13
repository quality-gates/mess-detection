"""Drive the real runner through its CLI with fake detectors for every adapter branch and failure class."""

from concurrent.futures import ThreadPoolExecutor
import json
import hashlib
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import textwrap
import unittest

from explicitness_conformance import load_corpus
from explicitness_fake_detector import TOKENS, swapped
from explicitness_observations import declared_owner
from explicitness_shapes import declaration_line


TESTS = Path(__file__).parent
ROOT = TESTS.parent
RUNNER = TESTS / "explicitness_conformance.py"
FAKE = TESTS / "explicitness_fake_detector.py"
LANGUAGES = ("python", "typescript", "go", "fsharp", "csharp", "rust")
CORPUS = load_corpus()
# All-Unknown cases whose designated sites a blanket detector hits without marking a quiet owner (D10).
BLANKET_PASSES = {
    "blanket_definition": {language: set() for language in LANGUAGES},
    "blanket_call": {
        "python": set(), "typescript": set(), "go": set(), "fsharp": set(), "rust": set(),
        "csharp": {"injected", "injected_variant", "unknown_spread", "shadowed_callable",
                   "shadowed_standard_binding", "unknown_cycle", "event_subscribers"},
    },
}
FULL_RUNS = ("correct", "empty", "lexical", "eager", "cold", "declaration_line", "blanket_definition", "blanket_call",
             "phantom", "phantom_qualifier", "swapped_scope", "ghost", "oracle", "wrong_line", "malformed")


def of(language, predicate=lambda case: True):
    return [case for case in CORPUS if case["language"] == language and predicate(case)]


def ids(language, predicate=lambda case: True):
    return [case["id"] for case in of(language, predicate)]


def run_fake(mode, language, cases=(), mapped=True, command=None):
    selection = hashlib.sha256(repr((cases, mapped, command)).encode()).hexdigest()[:12]
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
        result = subprocess.run(arguments, capture_output=True, timeout=900)
        raw = output.read_bytes() if output.exists() else None
    report = json.loads(raw) if raw is not None else None
    evidence = os.environ.get("EXPLICITNESS_EVIDENCE_DIR")
    if evidence:
        destination = Path(evidence)
        destination.mkdir(parents=True, exist_ok=True)
        stem = f"{mode}-{language}-{selection}"
        if raw is not None:
            (destination / (stem + ".json")).write_bytes(raw)
        (destination / (stem + ".log")).write_bytes(result.stdout + result.stderr)
    return result, report, raw


def verdicts(report):
    return {item["id"]: item["failures"] for item in report["results"]}


def passes(report):
    return {identity for identity, failures in verdicts(report).items() if not failures}


class ExplicitnessRunnerTests(unittest.TestCase):
    runs = {}

    @classmethod
    def setUpClass(cls):
        jobs = [(mode, language) for mode in FULL_RUNS for language in LANGUAGES]
        with ThreadPoolExecutor(max_workers=max(2, min(8, os.cpu_count() or 2))) as pool:
            for job, value in zip(jobs, pool.map(lambda job: run_fake(*job), jobs)):
                cls.runs[job] = value

    def full(self, mode, language):
        result, report, _ = self.runs[(mode, language)]
        self.assertEqual("", result.stderr.decode(), (mode, language))
        self.assertTrue(report["complete"], (mode, language))
        self.assertEqual(sorted(ids(language)), sorted(verdicts(report)), (mode, language))
        return result, report

    def test_a_correct_detector_passes_every_case_in_every_adapter_branch(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                result, report = self.full("correct", language)
                self.assertEqual(0, result.returncode, verdicts(report))
                self.assertFalse(any(verdicts(report).values()))

    def test_an_oracle_by_source_passes_everything_as_the_contract_discloses(self):
        # The correct fake looks each fixture up by its exact source text. The public corpus cannot stop that.
        contract = (ROOT / "docs" / "explicitness-contract.md").read_text()
        self.assertIn("looks each fixture up by its exact source", contract)
        for language in LANGUAGES:
            self.assertEqual(set(ids(language)), passes(self.full("correct", language)[1]))

    def test_a_fixture_name_oracle_learns_nothing(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                result, report = self.full("oracle", language)
                self.assertEqual(1, result.returncode)
                self.assertEqual(set(), passes(report))
                fixtures = [Path(item["fixture"]) for item in report["results"]]
                self.assertFalse(any(path.stem in verdicts(report) or path.parent.name in verdicts(report) for path in fixtures))
                self.assertEqual(len(fixtures), len({path.name for path in fixtures}))

    def test_an_empty_report_fails_every_calculation_pair(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                result, report = self.full("empty", language)
                self.assertEqual(1, result.returncode)
                self.assertEqual(set(), passes(report))
                for case in of(language, lambda case: case["exit"] == 0):
                    self.assertTrue(any("did not pass in this run" in item for item in verdicts(report)[case["id"]]), case["id"])

    def test_a_lexical_detector_fails_every_calculation_pair(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                result, report = self.full("lexical", language)
                self.assertEqual(1, result.returncode)
                for case in of(language, lambda case: case["exit"] == 0):
                    twin = next(item for item in of(language) if item.get("twin_of") == case["id"])
                    self.assertTrue(verdicts(report)[twin["id"]], twin["id"])
                    self.assertTrue(verdicts(report)[case["id"]], case["id"])

    def test_every_twin_has_an_outcome_on_a_line_without_a_direct_io_token(self):
        for language in LANGUAGES:
            for case in of(language, lambda case: "twin_of" in case):
                lines = case["source"].splitlines()
                quiet_lines = [line for rules in case["outcomes"].values() for line in rules.values()
                               if not any(token in lines[line - 1] for token in TOKENS[language])]
                self.assertTrue(quiet_lines, f"{language}/{case['id']}")

    def test_an_eager_lifecycle_model_fails_every_lifecycle_case(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                lifecycle = ids(language, lambda case: "eager" in case.get("contrasts", {}))
                self.assertTrue(lifecycle, language)
                result, report = self.full("eager", language)
                self.assertEqual(1, result.returncode)
                for identity in lifecycle:
                    self.assertTrue(verdicts(report)[identity], identity)

    def test_a_cold_model_fails_every_hot_async_timing_case(self):
        for language in ("typescript", "fsharp", "csharp"):
            with self.subTest(language=language):
                selection = ids(language, lambda case: "cold" in case.get("contrasts", {}))
                self.assertTrue(selection, language)
                result, report = self.full("cold", language)
                self.assertEqual(1, result.returncode)
                for identity in selection:
                    self.assertTrue(verdicts(report)[identity], identity)

    def test_a_model_that_drops_parameter_mutation_transfer_fails_shared_helpers(self):
        for language in ("python", "typescript"):
            with self.subTest(language=language):
                result, report, _ = run_fake("drop_mutation_transfer", language, ["shared_helper"])
                self.assertEqual(1, result.returncode)
                self.assertTrue(any("missing wrapper ImplicitOutput" in failure
                                    for failure in verdicts(report)["shared_helper"]))

    def test_a_known_argument_clean_model_fails_the_known_effect_callback(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                cases = ids(language, lambda case: "known_argument_clean" in case.get("contrasts", {}))
                self.assertIn("known_effect_callback", cases)
                result, report, _ = run_fake("known_argument_clean", language, cases)
                self.assertEqual(1, result.returncode)
                for identity in cases:
                    self.assertTrue(verdicts(report)[identity], identity)
                self.assertIn("known_callback", ids(language))
                result, report, _ = run_fake("known_argument_clean", language, ["known_callback"])
                self.assertEqual(0, result.returncode, verdicts(report))

    def test_a_declaration_line_detector_fails_every_case_whose_effect_is_elsewhere(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                result, report = self.full("declaration_line", language)
                self.assertEqual(1, result.returncode)
                for case in of(language, lambda case: case["exit"] == 2):
                    moved = any((declaration_line(language, case["source"], owner) or 1) != line
                                for owner, rules in case["outcomes"].items() for line in rules.values())
                    self.assertEqual(moved, bool(verdicts(report)[case["id"]]), case["id"])
                    if moved:
                        self.assertTrue(any("is not on the effect line" in item or "missing" in item
                                            for item in verdicts(report)[case["id"]]), case["id"])

    def test_a_blanket_unknown_detector_passes_only_the_enumerated_all_unknown_cases(self):
        for mode in ("blanket_definition", "blanket_call"):
            for language in LANGUAGES:
                with self.subTest(mode=mode, language=language):
                    result, report = self.full(mode, language)
                    self.assertEqual(1, result.returncode)
                    self.assertEqual(BLANKET_PASSES[mode][language], passes(report))
                    for identity in BLANKET_PASSES[mode][language]:
                        case = next(case for case in of(language) if case["id"] == identity)
                        self.assertTrue(all(set(rules) == {"UnknownEffect"} for rules in case["outcomes"].values()), identity)

    def test_a_phantom_owner_fails_every_case(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                result, report = self.full("phantom", language)
                self.assertEqual(1, result.returncode)
                for identity, failures in verdicts(report).items():
                    self.assertTrue(any("undeclared or ambiguous owner" in item for item in failures), identity)

    def test_a_phantom_qualifier_and_a_ghost_owner_fail_every_action(self):
        for mode in ("phantom_qualifier", "ghost"):
            for language in LANGUAGES:
                with self.subTest(mode=mode, language=language):
                    result, report = self.full(mode, language)
                    self.assertEqual(1, result.returncode)
                    for identity in ids(language, lambda case: case["exit"] == 2):
                        failures = verdicts(report)[identity]
                        self.assertTrue(any("undeclared or ambiguous owner" in item for item in failures), identity)

    def test_a_swapped_scope_fails_every_same_short_name_case(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                result, report = self.full("swapped_scope", language)
                self.assertEqual(1, result.returncode)
                affected = [case["id"] for case in of(language) if any(
                    swapped(owner, [*case["outcomes"], *case["quiet_owners"]]) != owner for owner in case["outcomes"])]
                self.assertTrue(affected, language)
                for identity in affected:
                    self.assertTrue(verdicts(report)[identity], identity)

    def test_a_wrong_effect_line_fails_every_action(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                result, report = self.full("wrong_line", language)
                self.assertEqual(1, result.returncode)
                for identity in ids(language, lambda case: case["exit"] == 2):
                    self.assertTrue(any("is not on the effect line" in item for item in verdicts(report)[identity]), identity)

    def test_a_malformed_record_fails_its_case_and_the_run_continues(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                result, report = self.full("malformed", language)
                self.assertEqual(1, result.returncode)
                for failures in verdicts(report).values():
                    self.assertTrue(any("invalid native report" in item for item in failures))

    def test_undecodable_and_unencodable_native_output_fails_per_case(self):
        expected = {"nul_path": "unusable path", "surrogate_owner": "", "bad_utf8_stdout": "native stdout is not UTF-8",
                    "bad_utf8_stderr": "native stderr is not UTF-8", "long_path": ""}
        for mode, message in expected.items():
            for language in LANGUAGES:
                with self.subTest(mode=mode, language=language):
                    selection = ids(language, lambda case: case["exit"] == 2)[:2]
                    result, report, raw = run_fake(mode, language, selection)
                    self.assertEqual((1, b""), (result.returncode, result.stderr), result.stdout)
                    self.assertTrue(report["complete"])
                    raw.decode("ascii")
                    self.assertEqual(selection, [item["id"] for item in report["results"]])
                    for failures in verdicts(report).values():
                        self.assertTrue(failures)
                        self.assertTrue(any(message in item for item in failures), failures)
                    result.stdout.decode("ascii")

    def test_a_dotdot_path_that_resolves_to_the_fixture_passes(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                result, report, _ = run_fake("dotdot_path", language, ids(language, lambda case: case["exit"] == 2)[:3])
                self.assertEqual(0, result.returncode, verdicts(report))

    def test_native_class_and_method_fields_identify_the_execution_owner(self):
        for language in ("go", "csharp"):
            with self.subTest(language=language):
                result, report, _ = run_fake("split_method", language, ["same_short_name"])
                self.assertEqual(0, result.returncode, verdicts(report))

    def test_a_relocated_path_fails_and_container_paths_need_the_declared_mapping(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                selection = ids(language, lambda case: case["exit"] == 2)[:3]
                result, report, _ = run_fake("wrong_path", language, selection)
                self.assertEqual(1, result.returncode)
                for failures in verdicts(report).values():
                    self.assertTrue(any("is outside the fixture" in item for item in failures))
        for language in ("csharp", "rust"):
            with self.subTest(language=language, mapping=False):
                result, report, _ = run_fake("correct", language, ids(language, lambda case: case["exit"] == 2)[:3], mapped=False)
                self.assertEqual(1, result.returncode)
                self.assertTrue(all(verdicts(report).values()))

    def test_a_detector_that_hides_suppressed_findings_fails_the_marker_case(self):
        for language in ("python", "typescript", "fsharp", "csharp", "rust"):
            with self.subTest(language=language):
                self.assertIn("suppression_marker", ids(language))
                result, report, _ = run_fake("hide_suppressed", language, ["suppression_marker"])
                self.assertEqual(1, result.returncode)
                self.assertTrue(verdicts(report)["suppression_marker"])
                result, report, _ = run_fake("correct", language, ["suppression_marker"])
                self.assertEqual(0, result.returncode, verdicts(report))

    def crashing_native(self, directory, at):
        native = Path(directory) / "native.py"
        counter = Path(directory) / "count"
        native.write_text(
            "import os, subprocess, sys\nfrom pathlib import Path\n"
            f"counter = Path({str(counter)!r})\n"
            "count = int(counter.read_text()) if counter.exists() else 0\ncounter.write_text(str(count + 1))\n"
            f"if count == {at}:\n    os.kill(os.getppid(), 9)\n"
            f"sys.exit(subprocess.run([sys.executable, {str(FAKE)!r}, 'correct', 'go', '/', *sys.argv[1:]]).returncode)\n")
        return shlex.join([sys.executable, str(native)])

    def test_the_output_file_exists_before_the_first_case_and_survives_a_crash(self):
        for at, count in ((0, 0), (2, 2)):
            with self.subTest(crash_at=at), tempfile.TemporaryDirectory() as directory:
                result, report, _ = run_fake("correct", "go", command=self.crashing_native(directory, at))
                self.assertNotEqual(0, result.returncode)
                self.assertFalse(report["complete"])
                self.assertEqual(count, len(report["results"]))

    def test_usage_errors_exit_two(self):
        result, report, _ = run_fake("correct", "go", ["no_such_case"])
        self.assertEqual(2, result.returncode)
        self.assertIsNone(report)
        result, report, _ = run_fake("correct", "go", command=" ")
        self.assertEqual(2, result.returncode)
        result = subprocess.run([sys.executable, str(RUNNER), "--language", "rust", "--command", "true",
                                 "--path-map", "relative=/tmp"], capture_output=True)
        self.assertEqual(2, result.returncode)


class OwnerMatchingTests(unittest.TestCase):
    def test_qualifiers_must_be_declared_scopes_or_owner_segments(self):
        declared = ["A.run", "B.run", "helper", "<lambda>"]
        self.assertEqual("A.run", declared_owner("A.run", declared))
        self.assertEqual("B.run", declared_owner("probe.B.run", declared, ["probe"]))
        self.assertIsNone(declared_owner("run", declared))
        self.assertIsNone(declared_owner("Phantom.Elsewhere.helper", declared, ["Probe"]))
        self.assertEqual("helper", declared_owner("Probe.helper", declared, ["Probe"]))
        self.assertEqual("<lambda>", declared_owner("Probe.<lambda@12>", declared, ["Probe"]))
        self.assertEqual("<lambda>", declared_owner("A.<lambda>", declared))

    def test_native_spellings_normalize(self):
        self.assertEqual("inner", declared_owner("outer.<locals>.inner", ["inner", "outer"]))
        self.assertEqual("Box.Run", declared_owner("(*Box).Run", ["Box.Run"]))
        self.assertEqual("run", declared_owner("crate::Probe::run", ["run"], ["Probe"]))
        self.assertEqual("leaf", declared_owner("f12ab.leaf", ["leaf"], (), "f12ab"))
        self.assertIsNone(declared_owner("f12ab.leaf", ["leaf"], (), "other"))


class WorkflowPinTests(unittest.TestCase):
    def test_the_workflow_accepts_its_own_commit_and_descendants_only(self):
        workflow = (ROOT / ".github" / "workflows" / "explicitness.yml").read_text()
        check = textwrap.dedent(workflow.split("          workflow_sha=", 1)[1].split(
            "          python3 contract/tests/", 1)[0])
        check = "set -euo pipefail\nworkflow_sha=" + check
        with tempfile.TemporaryDirectory() as directory:
            contract = Path(directory) / "contract"
            contract.mkdir()
            def git(*arguments):
                return subprocess.run(["git", "-C", str(contract), *arguments], capture_output=True, text=True, check=True).stdout.strip()
            git("init", "--quiet")
            git("config", "user.name", "Workflow test")
            git("config", "user.email", "test@example.invalid")
            git("config", "core.hooksPath", "/dev/null")
            artifact = contract / "artifact"
            def commit(content):
                artifact.write_text(content)
                git("add", "artifact")
                git("commit", "--quiet", "-m", content)
                return git("rev-parse", "HEAD")
            old = commit("older runner")
            own = commit("workflow and runner")
            descendant = commit("newer runner")
            git("switch", "--quiet", "--detach", old)
            sibling = commit("unrelated runner")
            env = {**os.environ, "WORKFLOW_CONTEXT": json.dumps({"workflow_sha": own})}
            def run(candidate):
                return subprocess.run(["bash", "-c", check], cwd=directory,
                                      env={**env, "CONTRACT_REF": candidate}, capture_output=True).returncode
            for candidate, expected in ((old, False), (own, True), (descendant, True), (sibling, False)):
                git("switch", "--quiet", "--detach", candidate)
                self.assertEqual(expected, run(candidate) == 0, candidate)
            git("switch", "--quiet", "--detach", own)
            artifact.write_text("changed after checkout")
            self.assertNotEqual(0, run(own))

    def test_the_workflow_validates_the_reusable_workflow_identity_and_sha(self):
        workflow = (ROOT / ".github" / "workflows" / "explicitness.yml").read_text()
        validation = textwrap.dedent(workflow.split("python3 - <<'PY'\n", 1)[1].split("          PY", 1)[0])
        context = {"workflow_sha": "a" * 40, "workflow_repository": "quality-gates/mess-detection",
                   "workflow_file_path": ".github/workflows/explicitness.yml"}
        env = {**os.environ, "LANGUAGE": "go", "CALLER": "quality-gates/messgo", "CONTRACT_REF": "b" * 40}
        for change, expected in (({}, True), ({"workflow_sha": "old-tag"}, False),
                                 ({"workflow_repository": "other/repository"}, False),
                                 ({"workflow_file_path": "other.yml"}, False)):
            result = subprocess.run([sys.executable, "-c", validation], capture_output=True,
                                    env={**env, "WORKFLOW_CONTEXT": json.dumps({**context, **change})})
            self.assertEqual(expected, result.returncode == 0, result.stderr)

    def test_the_contract_checkout_follows_the_build_and_keeps_no_credentials(self):
        workflow = (ROOT / ".github" / "workflows" / "explicitness.yml").read_text()
        self.assertLess(workflow.index("name: Build the native CLI"), workflow.index("name: Check out the pinned shared contract"))
        self.assertLess(workflow.index("name: Check out the pinned shared contract"), workflow.index("name: Exercise the native CLI"))
        self.assertEqual(2, workflow.count("persist-credentials: false"))


if __name__ == "__main__":
    unittest.main()
