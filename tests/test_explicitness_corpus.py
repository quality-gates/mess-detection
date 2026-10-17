import ast
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from explicitness_conformance import CORPUS, corpus_errors
from explicitness_observations import declared_owner
from explicitness_shapes import declaration_line, segments


CASES = json.loads(CORPUS.read_text())
LANGUAGES = ("python", "typescript", "go", "fsharp", "csharp", "rust")
STORAGE = ("conditional_copy", "loop_carried_alias", "escaped_allocation", "unknown_cycle", "mutual_recursion", "long_chain")
SHARED = ("known_callback", "known_effect_callback", "dead_action", "same_short_name")
UNANALYSED = {"go": "interface_dispatch", "rust": "dyn_callback", "csharp": "event_subscribers", "fsharp": "active_pattern_parameter"}
PRECISE = {"rust": ("mut_self_method",)}
GO_RECEIVER_POLICY = ("value_receiver", "pointer_receiver")
DECLARATIONS = {
    "go": [r"^func\s+(?:\([^)]*\)\s*)?(\w+)"],
    "rust": [r"\bfn\s+(\w+)"],
    "typescript": [r"\bfunction\s*\*?\s*(\w+)\s*[<(]",
                   r"^\s+(?:(?:static|async|public|private|protected|readonly|override)\s+)*\*?\s*(\w+)\s*\([^)]*\)\s*(?::[^{=]*)?\{\s*$"],
}
ANONYMOUS = {"go": r"\bfunc\s*\([^)]*\)(?!\s*\w+\s*\()\s*[^(){}\n]*\{", "rust": r"(?:^|[^|\w])\|[^|]*\|(?!\|)", "typescript": r"=>"}


def of(language):
    return {case["id"]: case for case in CASES if case["language"] == language}


def short(owner):
    return segments(owner)[-1]


class ExplicitnessCorpusTests(unittest.TestCase):
    def test_the_corpus_is_structurally_valid(self):
        self.assertEqual([], corpus_errors(CASES))

    def test_every_calculation_has_one_action_twin(self):
        for language in LANGUAGES:
            cases = of(language)
            for identity, case in cases.items():
                if case["exit"] == 0:
                    twins = [twin for twin in cases.values() if twin.get("twin_of") == identity]
                    self.assertEqual(1, len(twins), f"{language}/{identity}")
                    self.assertEqual(2, twins[0]["exit"])

    def test_python_cases_declare_every_callable_and_put_one_statement_on_a_line(self):
        for identity, case in of("python").items():
            tree = ast.parse(case["source"])
            names = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
            if any(isinstance(node, ast.Lambda) for node in ast.walk(tree)):
                names.add("<lambda>")
            if any(isinstance(node, ast.GeneratorExp) for node in ast.walk(tree)):
                names.add("<genexpr>")
            declared = {short(owner) for owner in [*case["outcomes"], *case["quiet_owners"]]}
            self.assertEqual(set(), names - declared, identity)
            seen = {}
            for node in ast.walk(tree):
                if isinstance(node, ast.stmt) and not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if node.lineno in seen:
                        self.assertIsInstance(seen[node.lineno], (ast.If, ast.For, ast.While, ast.With, ast.Try), identity)
                    seen.setdefault(node.lineno, node)

    def test_typescript_go_and_rust_cases_declare_every_callable(self):
        for language, patterns in DECLARATIONS.items():
            for identity, case in of(language).items():
                declared = {short(owner) for owner in [*case["outcomes"], *case["quiet_owners"]]}
                names = {match.group(1) for line in case["source"].splitlines() for pattern in patterns
                         for match in [re.search(pattern, line)] if match}
                names -= {"if", "for", "while", "switch", "catch", "constructor", "function", "main"}
                self.assertEqual(set(), names - declared, f"{language}/{identity}")
                if re.search(ANONYMOUS[language], case["source"]):
                    self.assertTrue(any(owner.startswith("<") or ".<" in owner for owner in declared)
                                    or language == "typescript", f"{language}/{identity} has an undeclared literal")

    def test_typescript_parser_checks_every_callable_and_statement_line(self):
        node = shutil.which("node")
        compiler = Path(os.environ.get("TYPESCRIPT_MODULE", CORPUS.parents[2] / "messcript/node_modules/typescript"))
        if node is None or not (compiler / "lib/typescript.js").is_file():
            if os.environ.get("REQUIRE_HOST_TOOLS"):
                self.fail("Node and the TypeScript compiler module are required")
            self.skipTest("Node or the TypeScript compiler module is not installed")
        cases = of("typescript")
        result = subprocess.run([node, str(CORPUS.with_name("typescript_fixture_owners.cjs")), str(compiler)],
                                input=json.dumps(list(cases.values())), capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        for parsed in json.loads(result.stdout):
            case = cases[parsed["id"]]
            declared = [*case["outcomes"], *case["quiet_owners"]]
            self.assertEqual([], parsed["parse_errors"], parsed["id"])
            self.assertEqual([], parsed["statement_collisions"], parsed["id"])
            for owner in parsed["owners"]:
                self.assertIsNotNone(declared_owner(owner, declared, case.get("scopes", ())),
                                     f"typescript/{parsed['id']} leaves {owner} undeclared")

    def test_no_outcome_sits_on_its_owners_declaration_line(self):
        for case in CASES:
            name = f"{case['language']}/{case['id']}"
            models = {"truth": case["outcomes"], **case.get("contrasts", {})}
            for model, outcomes in models.items():
                for owner, rules in outcomes.items():
                    if owner == "<module>":
                        continue
                    declared = declaration_line(case["language"], case["source"], owner)
                    self.assertIsNotNone(declared, f"{name} {model} {owner}")
                    if case["language"] == "python" and short(owner) == "<lambda>":
                        continue
                    for rule, line in rules.items():
                        self.assertNotEqual(declared, line, f"{name} {model} {owner} {rule}")

    def test_go_fixtures_are_gofmt_clean(self):
        gofmt = shutil.which("gofmt")
        if gofmt is None:
            if os.environ.get("REQUIRE_HOST_TOOLS"):
                self.fail("gofmt is required")
            self.skipTest("gofmt is not installed")
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for identity, case in of("go").items():
                path = Path(directory) / f"{identity}.go"
                path.write_text(case["source"])
                paths.append(str(path))
            result = subprocess.run([gofmt, "-l", *paths], capture_output=True, text=True)
            self.assertEqual(("", ""), (result.stdout, result.stderr))

    def test_go_cases_state_the_language_version(self):
        for identity, case in of("go").items():
            self.assertTrue(any("Go 1.23" in item for item in case["binding_assumptions"]), identity)

    def test_every_language_covers_storage_convergence_variants_and_suppression(self):
        for language in LANGUAGES:
            cases = of(language)
            for identity in (*STORAGE, *SHARED):
                self.assertTrue(identity in cases, f"{language}/{identity}")
            self.assertGreaterEqual(sum("variant_of" in case for case in cases.values()), 3, language)
            self.assertEqual(language != "go", "suppression_marker" in cases, language)
        for language in ("python", "typescript"):
            self.assertIn("shared_helper", of(language))

    def test_known_effect_callbacks_transfer_and_have_a_wrong_model(self):
        for language in LANGUAGES:
            case = of(language)["known_effect_callback"]
            self.assertIn("known_argument_clean", case["contrasts"], language)
            self.assertEqual(2, case["exit"], language)

    def test_same_short_name_owners_have_different_outcomes(self):
        for language in LANGUAGES:
            case = of(language)["same_short_name"]
            owners = [*case["outcomes"], *case["quiet_owners"]]
            pairs = [(a, b) for a in owners for b in owners if a < b and short(a) == short(b)]
            self.assertTrue(pairs, language)
            self.assertTrue(any(case["outcomes"].get(a) != case["outcomes"].get(b) for a, b in pairs), language)
            self.assertTrue(case.get("scopes"), language)

    def test_lifecycle_cases_have_an_eager_contrast_that_moves_an_effect(self):
        for language in LANGUAGES:
            lifecycle = [case for case in of(language).values() if "eager" in case.get("contrasts", {})]
            self.assertGreaterEqual(len(lifecycle), 3, language)
            for case in lifecycle:
                eager = case["contrasts"]["eager"]
                moved = set(eager) != set(case["outcomes"]) or any(
                    eager[owner] != case["outcomes"].get(owner) for owner in eager)
                self.assertTrue(moved, f"{language}/{case['id']}")

    def test_load_time_code_is_owned_by_the_module(self):
        for language in LANGUAGES:
            owners = [case for case in of(language).values() if "<module>" in case["outcomes"]]
            self.assertEqual(language != "rust", bool(owners), language)

    def test_unanalysed_and_precise_dispatch_cases_exist(self):
        for language, identity in UNANALYSED.items():
            case = of(language)[identity]
            self.assertTrue(any("UnknownEffect" in rules for rules in case["outcomes"].values()), f"{language}/{identity}")
        for language, identities in PRECISE.items():
            for identity in identities:
                self.assertIn(identity, of(language), language)
        for identity in GO_RECEIVER_POLICY:
            case = of("go")[identity]
            self.assertEqual({"Bump": {"UnknownEffect": 8}}, case["outcomes"], identity)
            self.assertIn("Pure", case["quiet_owners"], identity)

    def test_all_unknown_cases_have_a_precision_anchor_where_the_construct_allows_one(self):
        for case in CASES:
            if case["exit"] == 2 and all(set(rules) == {"UnknownEffect"} for rules in case["outcomes"].values()):
                self.assertTrue(case["quiet_owners"], f"{case['language']}/{case['id']}")


if __name__ == "__main__":
    unittest.main()
