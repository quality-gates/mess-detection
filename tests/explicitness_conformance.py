"""Run the shared semantic examples through a native detector's public CLI."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

from explicitness_observations import attribution_failures, observations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", required=True)
    parser.add_argument("--command", required=True)
    parser.add_argument("--cases", default="")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fixture-root", type=Path)
    args = parser.parse_args()
    corpus = json.loads(Path(__file__).with_name("explicitness_cases.json").read_text())
    identities = [(case["language"], case["id"]) for case in corpus]
    if len(identities) != len(set(identities)) or any(not case["id"].isidentifier() for case in corpus):
        parser.error("Corpus case identities must be unique and safe file names.")
    selected = set(filter(None, args.cases.split(",")))
    cases = [case for case in corpus if case["language"] == args.language and (not selected or case["id"] in selected)]
    if not cases or selected - {case["id"] for case in cases}:
        parser.error("The language or case selection does not exist in the corpus.")
    command = shlex.split(args.command)
    if not command:
        parser.error("The detector command must not be empty.")
    results = []
    if args.fixture_root:
        args.fixture_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="explicitness-conformance-", dir=args.fixture_root) as temporary:
        for case in cases:
            path = Path(temporary) / (case["id"] + case["suffix"])
            path.write_text(case["source"])
            try:
                result = subprocess.run([*command, str(path), "json", "explicitness"], capture_output=True, text=True, timeout=60)
                failures = []
                records = ()
                if result.returncode != case["exit"]:
                    failures.append(f"exit {result.returncode}, expected {case['exit']}")
                if result.stderr:
                    failures.append(f"stderr {result.stderr.strip()}")
                try:
                    records = observations(args.language, json.loads(result.stdout))
                    for record in records:
                        if Path(record.path).name != path.name or record.line > len(case["source"].splitlines()):
                            failures.append(f"finding location {record.path}:{record.line} is outside this fixture")
                    failures.extend(attribution_failures(case, records))
                except (ValueError, TypeError, KeyError) as error:
                    failures.append(f"invalid native report: {error}")
                for fragment in case["present"]:
                    if fragment not in result.stdout:
                        failures.append(f"missing {fragment!r}")
                for fragment in case["absent"]:
                    if fragment in result.stdout:
                        failures.append(f"unexpected {fragment!r}")
                if case["exit"] == 0 and records:
                    failures.append("a calculation must have no findings")
                observation = {
                    "id": case["id"], "failures": failures,
                    "records": [asdict(record) for record in records],
                    "stdout": result.stdout, "stderr": result.stderr, "exit": result.returncode,
                }
            except (OSError, subprocess.TimeoutExpired) as error:
                observation = {"id": case["id"], "failures": [str(error)]}
            results.append(observation)
            verdict = "FAIL" if observation["failures"] else "PASS"
            print(f"{verdict} {case['id']}")
            for failure in observation["failures"]:
                print(f"  {failure}")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(results, indent=2) + "\n")
    return int(any(observation["failures"] for observation in results))


if __name__ == "__main__":
    sys.exit(main())
