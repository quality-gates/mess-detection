"""Run the shared semantic examples through a native detector's public CLI.

Exit status: 0 when every selected case passes, 1 when any case fails, and 2 for a usage or corpus error.
"""

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import secrets
import shlex
import subprocess
import sys
import tempfile

from explicitness_observations import RULES, attribution_failures, observations


LANGUAGES = {"python": ".py", "typescript": ".ts", "go": ".go", "fsharp": ".fs", "csharp": ".cs", "rust": ".rs"}
CORPUS = Path(__file__).with_name("explicitness_cases.json")
FIELDS = {"id", "language", "suffix", "source", "exit", "semantic", "binding_assumptions", "value_assumptions",
          "outcomes", "quiet_owners", "scopes", "contrasts", "twin_of", "variant_of"}
REQUIRED = {"id", "language", "suffix", "source", "exit", "semantic", "binding_assumptions", "value_assumptions",
            "outcomes", "quiet_owners"}


def outcome_errors(name: str, outcomes: dict, length: int) -> list[str]:
    errors = []
    for owner, rules in outcomes.items():
        if not isinstance(rules, dict) or not rules or set(rules) - set(RULES):
            errors.append(f"{name} {owner} needs effect kinds from {list(RULES)}")
            continue
        for rule, line in rules.items():
            if not isinstance(line, int) or isinstance(line, bool) or not 1 <= line <= length:
                errors.append(f"{name} {owner} {rule} needs one designated effect line inside the source")
    return errors


def corpus_errors(corpus) -> list[str]:
    """Return every structural defect in the corpus; an empty list means the corpus is usable."""
    if not isinstance(corpus, list):
        return ["The corpus must be a JSON array."]
    errors = []
    by_identity = {}
    for index, case in enumerate(corpus):
        if not isinstance(case, dict):
            errors.append(f"case {index} is not an object")
            continue
        name = f"{case.get('language')}/{case.get('id')}"
        if set(case) - FIELDS or REQUIRED - set(case):
            errors.append(f"{name} has fields {sorted(set(case) - FIELDS)} or lacks {sorted(REQUIRED - set(case))}")
            continue
        if not isinstance(case["id"], str) or not case["id"].isidentifier():
            errors.append(f"{name} needs an identifier id")
        if LANGUAGES.get(case["language"]) != case["suffix"]:
            errors.append(f"{name} has an unknown language or suffix")
        if (case["language"], case["id"]) in by_identity:
            errors.append(f"{name} is duplicated")
        by_identity[(case["language"], case["id"])] = case
        if not isinstance(case["source"], str) or not case["source"].endswith("\n"):
            errors.append(f"{name} source must be newline-terminated text")
            continue
        length = len(case["source"].splitlines())
        outcomes, quiet = case["outcomes"], case["quiet_owners"]
        if case["exit"] not in (0, 2) or (case["exit"] == 0) != (outcomes == {}):
            errors.append(f"{name} exit must be 0 exactly when no owner has an effect")
        if not isinstance(quiet, list) or not all(isinstance(owner, str) and owner for owner in quiet):
            errors.append(f"{name} quiet_owners must list callable names")
            continue
        if not isinstance(outcomes, dict) or set(outcomes) & set(quiet) or len(quiet) != len(set(quiet)):
            errors.append(f"{name} declares an owner twice")
            continue
        if not outcomes and not quiet:
            errors.append(f"{name} declares no callable")
        errors.extend(outcome_errors(name, outcomes, length))
        contrasts = case.get("contrasts", {})
        if not isinstance(contrasts, dict):
            errors.append(f"{name} contrasts must map a model name to outcomes")
            contrasts = {}
        for model, wrong in contrasts.items():
            if not isinstance(wrong, dict) or wrong == outcomes or set(wrong) - {*outcomes, *quiet}:
                errors.append(f"{name} contrast {model} must differ from the outcomes and use declared owners")
                continue
            errors.extend(outcome_errors(f"{name} contrast {model}", wrong, length))
        scopes = case.get("scopes", [])
        if not isinstance(scopes, list) or not all(isinstance(scope, str) and scope for scope in scopes):
            errors.append(f"{name} scopes must list scope names")
        if not isinstance(case["semantic"], str) or not case["semantic"].strip():
            errors.append(f"{name} needs a semantic explanation")
        for field in ("binding_assumptions", "value_assumptions"):
            if not isinstance(case[field], list) or not case[field] or not all(isinstance(item, str) for item in case[field]):
                errors.append(f"{name} needs {field.replace('_', ' ')}")
    twins = {}
    for (language, identity), case in by_identity.items():
        for link in ("twin_of", "variant_of"):
            if link in case and (language, case[link]) not in by_identity:
                errors.append(f"{language}/{identity} {link} names a missing case")
        if "twin_of" in case:
            target = by_identity.get((language, case["twin_of"]))
            if case["exit"] != 2 or (target and target["exit"] != 0):
                errors.append(f"{language}/{identity} must be an action twin of a calculation")
            twins.setdefault((language, case["twin_of"]), []).append(identity)
    for (language, identity), case in by_identity.items():
        if case["exit"] == 0 and len(twins.get((language, identity), [])) != 1:
            errors.append(f"{language}/{identity} needs exactly one action twin")
    return errors


def load_corpus() -> list[dict]:
    corpus = json.loads(CORPUS.read_text())
    errors = corpus_errors(corpus)
    if errors:
        raise ValueError("Invalid explicitness corpus: " + "; ".join(errors))
    return corpus


def path_mapping(value: str) -> tuple[str, str]:
    container, separator, host = value.partition("=")
    if not separator or not container.startswith("/") or not host:
        raise argparse.ArgumentTypeError("Use CONTAINER_PREFIX=HOST_PREFIX with an absolute container prefix.")
    return container, str(Path(host).resolve())


def write_atomically(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n")
    temporary.replace(path)


def safe(text: str) -> str:
    """Render native text for a terminal without letting undecodable or surrogate characters end the run."""
    return text.encode("ascii", "backslashreplace").decode("ascii")


def decoded(data: bytes, stream: str, failures: list[str]) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as error:
        failures.append(f"native {stream} is not UTF-8: {error.reason} at byte {error.start}")
        return data.decode("utf-8", "backslashreplace")


def judge(case: dict, args, command: list[str], root: Path) -> dict:
    directory = root / secrets.token_hex(6)
    directory.mkdir()
    path = directory / ("f" + secrets.token_hex(6) + case["suffix"])
    path.write_text(case["source"])
    observation = {"id": case["id"], "fixture": str(path), "failures": [], "records": []}
    try:
        result = subprocess.run([*command, str(path), "json", "explicitness", "--strict"],
                                capture_output=True, timeout=args.timeout)
    except (OSError, subprocess.SubprocessError) as error:
        observation["failures"].append(f"native CLI did not complete: {error}")
        return observation
    failures = observation["failures"]
    stdout = decoded(result.stdout, "stdout", failures)
    stderr = decoded(result.stderr, "stderr", failures)
    observation.update(stdout=stdout, stderr=stderr, exit=result.returncode)
    if result.returncode != case["exit"]:
        failures.append(f"exit {result.returncode}, expected {case['exit']}")
    if stderr:
        failures.append(f"stderr {stderr.strip()}")
    if failures and any(item.startswith("native stdout") for item in failures):
        return observation
    try:
        records = observations(args.language, json.loads(stdout))
        observation["records"] = [asdict(record) for record in records]
        failures.extend(attribution_failures(case, records, path, args.path_map))
    except Exception as error:  # A malformed native report fails this case and never ends the run.
        failures.append(f"invalid native report: {type(error).__name__}: {error}")
    return observation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", required=True, choices=sorted(LANGUAGES))
    parser.add_argument("--command", required=True)
    parser.add_argument("--cases", default="")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fixture-root", type=Path)
    parser.add_argument("--path-map", type=path_mapping, action="append", default=[],
                        help="Map a container path prefix in native reports back to the host prefix.")
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args()
    try:
        corpus = load_corpus()
    except ValueError as error:
        parser.error(str(error))
    by_id = {case["id"]: case for case in corpus if case["language"] == args.language}
    selected = set(filter(None, args.cases.split(",")))
    if selected - set(by_id):
        parser.error("The case selection does not exist in the corpus for this language.")
    selected |= {case["id"] for case in by_id.values() if case.get("twin_of") in selected}
    twins = {case["twin_of"]: case["id"] for case in by_id.values() if "twin_of" in case}
    ordered = sorted(by_id.values(), key=lambda case: "twin_of" not in case)
    cases = [case for case in ordered if not selected or case["id"] in selected]
    command = shlex.split(args.command)
    if not command:
        parser.error("The detector command must not be empty.")
    if args.fixture_root:
        args.fixture_root.mkdir(parents=True, exist_ok=True)
    results = []
    report = {"language": args.language, "complete": False, "results": results}
    verdicts = {}
    if args.output:
        write_atomically(args.output, report)
    with tempfile.TemporaryDirectory(prefix=secrets.token_hex(4), dir=args.fixture_root) as temporary:
        for case in cases:
            observation = judge(case, args, command, Path(temporary))
            twin = twins.get(case["id"])
            if twin and verdicts.get(twin) is not True:
                observation["failures"].append(f"action twin {twin} did not pass in this run")
            verdicts[case["id"]] = not observation["failures"]
            results.append(observation)
            print(f"{'FAIL' if observation['failures'] else 'PASS'} {case['id']}", flush=True)
            for failure in observation["failures"]:
                print(f"  {safe(failure)}", flush=True)
            if args.output:
                write_atomically(args.output, report)
    report["complete"] = True
    if args.output:
        write_atomically(args.output, report)
    return int(not all(verdicts.values()))


if __name__ == "__main__":
    sys.exit(main())
