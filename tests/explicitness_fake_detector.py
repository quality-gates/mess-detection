"""A fake native detector for runner tests. It is never acceptance evidence for a native tool.

Usage: explicitness_fake_detector.py MODE LANGUAGE HOST_ROOT FIXTURE json explicitness --strict

The correct mode looks a case up by its exact source text, as a stand-in for a detector that analyzes the
source, and reports exactly the declared outcomes. Every other mode is one class of defect the runner must catch.
"""

import json
import os
from pathlib import Path
import sys


CORPUS = Path(__file__).with_name("explicitness_cases.json")


def spelled(language: str, owner: str) -> str:
    if language == "typescript":
        return "arrow function anonymous" if owner == "<lambda>" else f"function {owner}()"
    if language in {"go", "csharp"} and owner == "<lambda>":
        return "Probe.<lambda@1>"
    return owner


def render(language: str, path: str, records: list[dict]) -> dict:
    if language in {"python", "typescript"}:
        return {"tool": {"name": "fake"}, "errors": [], "findings": [
            {"path": path, "line": record["line"], "column": 1, "ruleName": record["rule"], "priority": 3,
             "message": f"{record['owner']} has {record['rule']}.", "context": spelled(language, record["owner"]),
             "suppressed": record.get("suppressed", False)} for record in records]}
    if language == "fsharp":
        return {"tool": "fake", "errors": [], "violations": [
            {"context": {"member": record["owner"]}, "description": f"'{record['owner']}' has {record['rule']}.",
             "file": path, "startLine": record["line"], "rule": record["rule"]} for record in records]}
    return {"files": [{"file": path, "violations": [
        {"function": spelled(language, record["owner"]), "method": "", "beginLine": record["line"],
         "rule": record["rule"], "description": f"{record['owner']} has {record['rule']}.",
         **({"suppressed": True} if record.get("suppressed") else {})} for record in records]}]}


def main() -> int:
    mode, language, host_root, fixture = sys.argv[1:5]
    assert sys.argv[5:] == ["json", "explicitness", "--strict"], sys.argv
    source = Path(fixture).read_text()
    corpus = [case for case in json.loads(CORPUS.read_text()) if case["language"] == language]
    if mode == "oracle":
        case = next((case for case in corpus if Path(fixture).stem == case["id"]), None)
    else:
        case = next((case for case in corpus if case["source"] == source), None)
    if case is None or mode == "empty":
        records, status = [], 0
    else:
        records = [{"owner": owner, "rule": rule, "line": lines[0]}
                   for owner, rules in case["outcomes"].items() for rule, lines in rules.items()]
        status = case["exit"]
    marked = "disable-next-line" in source or "SuppressMessage" in source
    if marked and language in {"python", "typescript", "rust"}:
        records = [{**record, "suppressed": True} for record in records]
    if mode == "phantom":
        records.append({"owner": "Phantom", "rule": "UnknownEffect", "line": 1})
        status = 2
    elif mode == "blanket" and case is not None:
        owners = [*case["outcomes"], *case["quiet_owners"]]
        records = [{"owner": owner, "rule": "UnknownEffect", "line": 1} for owner in owners]
        status = 2
    elif mode == "wrong_line":
        records = [{**record, "line": record["line"] + 1} for record in records]
    elif mode == "hide_suppressed" and marked:
        records, status = [], 0
    path = fixture
    if language == "csharp":
        path = "/src/" + os.path.relpath(fixture, host_root)
    elif language == "rust":
        path = "/workspace/" + os.path.relpath(fixture, host_root)
    elif language in {"python", "fsharp"}:
        path = os.path.relpath(fixture)
    if mode == "wrong_path":
        path = str(Path("/tmp/relocated") / Path(fixture).name)
    report = render(language, path, records)
    if mode == "malformed":
        report = {"errors": [], "findings": [1]} if language in {"python", "typescript"} else (
            {"errors": [], "violations": ["broken"]} if language == "fsharp" else {"files": [{"file": path, "violations": ["broken"]}]})
    sys.stdout.write(json.dumps(report))
    return status


if __name__ == "__main__":
    sys.exit(main())
