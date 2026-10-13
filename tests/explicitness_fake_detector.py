"""A fake native detector for runner tests. It is never acceptance evidence for a native tool.

Usage: explicitness_fake_detector.py MODE LANGUAGE HOST_ROOT FIXTURE json explicitness --strict

The correct mode looks a case up by its exact source text and reports exactly the declared outcomes. That is
also the oracle-by-source attack: the corpus is public, so it passes everything, as the contract discloses.
Every other mode is one class of defect, or one wrong model of the semantics, that the runner must catch.
"""

import json
import os
from pathlib import Path
import re
import sys

from explicitness_shapes import declaration_line, first_call_line, segments


CORPUS = Path(__file__).with_name("explicitness_cases.json")
TOKENS = {"python": ["input(", "print(", "open(", "os.", "time.", "random.", "sys."],
          "typescript": ["console.", "process.", "Date", "Math.random", "fetch(", "readFileSync"],
          "go": ["fmt.", "os.", "time.", "rand."],
          "fsharp": ["printf", "Console.", "System.", "stdin", "DateTime", "Random", "File."],
          "csharp": ["Console.", "File.", "DateTime", "Random", "Environment."],
          "rust": ["println!", "print!", "std::", "stdin", "env::", "fs::"]}


def spelled(language: str, owner: str) -> str:
    """Spell an owner the way that language's native prints it."""
    if language in {"go", "csharp"}:
        owner = re.sub(r"<(\w+)>$", r"<\1@1>", owner)
    if language == "typescript":
        if owner == "<lambda>":
            return "arrow function anonymous"
        return f"method {owner}" if "." in owner else f"function {owner}()"
    if language == "rust":
        return owner.replace(".", "::")
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


def flatten(outcomes: dict) -> list[dict]:
    return [{"owner": owner, "rule": rule, "line": line} for owner, rules in outcomes.items() for rule, line in rules.items()]


def swapped(owner: str, declared: list[str]) -> str:
    """Attribute an effect to a different declared owner with the same short name, when one exists."""
    twins = [other for other in declared if other != owner and segments(other)[-1] == segments(owner)[-1]]
    return twins[0] if twins else owner


def model(mode: str, language: str, case: dict, source: str) -> tuple[list[dict], int]:
    declared = [*case["outcomes"], *case["quiet_owners"]]
    records = flatten(case["outcomes"])
    if mode in {"eager", "cold", "known_argument_clean"}:
        records = flatten(case.get("contrasts", {}).get(mode, case["outcomes"]))
    elif mode == "drop_mutation_transfer" and case["id"] == "shared_helper":
        records = [record for record in records if record["owner"] != "wrapper"]
    elif mode == "declaration_line":
        records = [{**record, "line": declaration_line(language, source, record["owner"]) or 1} for record in records]
    elif mode == "lexical":
        text = source.splitlines()
        records = [record for record in records if any(token in text[record["line"] - 1] for token in TOKENS[language])]
    elif mode == "blanket_definition":
        records = [{"owner": owner, "rule": "UnknownEffect", "line": declaration_line(language, source, owner) or 1}
                   for owner in declared]
    elif mode == "blanket_call":
        lines = {owner: first_call_line(language, source, owner, declared) for owner in declared}
        records = [{"owner": owner, "rule": "UnknownEffect", "line": line} for owner, line in lines.items() if line]
    elif mode == "phantom_qualifier":
        records = [{**record, "owner": "Phantom.Elsewhere." + record["owner"]} for record in records]
    elif mode == "swapped_scope":
        records = [{**record, "owner": swapped(record["owner"], declared)} for record in records]
    elif mode == "ghost":
        records = [{**record, "line": 1} for record in records]
        if records:
            records.append({"owner": "ghost", "rule": records[0]["rule"], "line": 1})
    elif mode == "wrong_line":
        records = [{**record, "line": record["line"] + 1} for record in records]
    return records, (2 if records else 0)


def main() -> int:
    mode, language, host_root, fixture = sys.argv[1:5]
    assert sys.argv[5:] == ["json", "explicitness", "--strict"], sys.argv
    source = Path(fixture).read_text()
    corpus = [case for case in json.loads(CORPUS.read_text()) if case["language"] == language]
    if mode == "oracle":
        case = next((case for case in corpus if Path(fixture).stem == case["id"]), None)
    else:
        case = next((case for case in corpus if case["source"] == source), None)
    records, status = ([], 0) if case is None or mode == "empty" else model(mode, language, case, source)
    marked = "disable-next-line" in source or "SuppressMessage" in source
    if marked and language in {"python", "typescript", "rust"}:
        records = [{**record, "suppressed": True} for record in records]
    if mode == "phantom":
        records.append({"owner": "Phantom", "rule": "UnknownEffect", "line": 1})
        status = 2
    elif mode == "hide_suppressed" and marked:
        records, status = [], 0
    elif mode == "surrogate_owner":
        records.append({"owner": "\udc80", "rule": "UnknownEffect", "line": 1})
        status = 2
    path = fixture
    if language == "csharp":
        path = "/src/" + os.path.relpath(fixture, host_root)
    elif language == "rust":
        path = "/workspace/" + os.path.relpath(fixture, host_root)
    elif language in {"python", "fsharp"}:
        path = os.path.relpath(fixture)
    if mode == "wrong_path":
        path = str(Path("/tmp/relocated") / Path(fixture).name)
    elif mode == "nul_path":
        path += "\u0000"
    elif mode == "long_path":
        path = "/" + "a" * 5000 + "/" + Path(fixture).name
    elif mode == "dotdot_path" and Path(path).is_absolute():
        path = str(Path(path).parent / ".." / Path(path).parent.name / Path(path).name)
    report = render(language, path, records)
    if mode == "split_method":
        for finding, record in zip(report["files"][0]["violations"], records):
            if "." in record["owner"]:
                scope, method = record["owner"].rsplit(".", 1)
                finding.update({"class": scope, "method": method, "function": ""})
    if mode == "split_context":
        for finding, record in zip(report["violations"], records):
            scope, _, member = record["owner"].rpartition(".")
            finding["context"] = {"member": member, "module": scope or None, "type": None, "namespace": "Probe"}
            finding["description"] = f"'{member}' has {record['rule']}."
    if mode == "malformed":
        report = {"errors": [], "findings": [1]} if language in {"python", "typescript"} else (
            {"errors": [], "violations": ["broken"]} if language == "fsharp" else {"files": [{"file": path, "violations": ["broken"]}]})
    payload = json.dumps(report).encode()
    if mode == "bad_utf8_stdout":
        payload = b"\xff\xfe" + payload
    if mode == "bad_utf8_stderr":
        sys.stderr.buffer.write(b"\xff")
        sys.stderr.flush()
    sys.stdout.buffer.write(payload)
    return status


if __name__ == "__main__":
    sys.exit(main())
