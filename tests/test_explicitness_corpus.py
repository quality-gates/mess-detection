"""Check the shared corpus structure: closed-world owners, twins, effect lines, and required coverage."""

import ast
import json
import unittest

from explicitness_conformance import CORPUS, corpus_errors


CASES = json.loads(CORPUS.read_text())
LANGUAGES = ("python", "typescript", "go", "fsharp", "csharp", "rust")
STORAGE = ("conditional_copy", "loop_carried_alias", "escaped_allocation", "unknown_cycle", "mutual_recursion", "long_chain")


def of(language):
    return {case["id"]: case for case in CASES if case["language"] == language}


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

    def test_python_cases_declare_every_callable(self):
        for identity, case in of("python").items():
            tree = ast.parse(case["source"])
            names = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
            if any(isinstance(node, ast.Lambda) for node in ast.walk(tree)):
                names.add("<lambda>")
            self.assertEqual(names, {*case["outcomes"], *case["quiet_owners"]}, identity)

    def test_every_language_covers_storage_convergence_variants_and_suppression(self):
        for language in LANGUAGES:
            cases = of(language)
            for identity in STORAGE:
                self.assertIn(identity, cases, language)
            self.assertGreaterEqual(sum("variant_of" in case for case in cases.values()), 3, language)
            self.assertEqual(language != "go", "suppression_marker" in cases, language)

    def test_go_defer_and_scheduling_are_attributed(self):
        cases = of("go")
        self.assertTrue(any("defer " in case["source"] and case["exit"] == 2 for case in cases.values()))
        self.assertTrue(any("\tgo " in case["source"] or "{ go " in case["source"] for case in cases.values()))

    def test_lifecycle_constructs_are_attributed_where_they_exist(self):
        expected = {
            "python": ("yield", "async def", "def send(value, prefix=input())"),
            "typescript": ("function*", "async function", "static"),
            "fsharp": ("seq {", "async {"),
            "csharp": ("yield return", "async "),
            "rust": ("async fn", ".map("),
        }
        for language, fragments in expected.items():
            sources = [case["source"] for case in of(language).values() if case["exit"] == 2]
            for fragment in fragments:
                self.assertTrue(any(fragment in source for source in sources), f"{language} {fragment}")


if __name__ == "__main__":
    unittest.main()
