from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Observation:
    owner: str
    path: str
    line: int
    rule: str
    detail: str


def owner_name(context: str) -> str:
    name = re.sub(r"^(?:arrow function|function|method|accessor|constructor)\s+", "", context).removesuffix("()")
    return "<lambda>" if name == "anonymous" else name


def observations(language: str, payload: dict) -> tuple[Observation, ...]:
    if not isinstance(payload, dict) or payload.get("errors"):
        raise ValueError("The native JSON report contains processing errors or is not an object.")
    records = []
    if language in {"python", "typescript"}:
        for finding in payload["findings"]:
            if finding.get("suppressed"):
                raise ValueError("A suppressed finding cannot establish a classification.")
            records.append(Observation(owner_name(finding["context"]), finding["path"], finding["line"], finding["ruleName"], finding["message"]))
    elif language == "fsharp":
        for finding in payload["violations"]:
            owner = finding["context"]["member"]
            subject = re.match(r"^'([^']+)'", finding["description"])
            if subject and owner != subject.group(1):
                raise ValueError("The F# finding context disagrees with its execution owner.")
            records.append(Observation(owner_name(owner or ""), finding["file"], finding["startLine"], finding["rule"], finding["description"]))
    elif language in {"go", "csharp", "rust"}:
        for file in payload["files"]:
            for finding in file["violations"]:
                if finding.get("suppressed"):
                    raise ValueError("A suppressed finding cannot establish a classification.")
                owner = finding.get("method") or finding.get("function") or ""
                records.append(Observation(owner_name(owner), file["file"], finding["beginLine"], finding["rule"], finding["description"]))
    else:
        raise ValueError("Unknown native report format.")
    for record in records:
        if not isinstance(record.path, str) or not record.path:
            raise ValueError("Every finding needs a source path.")
        if not record.owner or not isinstance(record.line, int) or isinstance(record.line, bool) or record.line < 1:
            raise ValueError("Every finding needs an execution owner and a positive source line.")
        if not isinstance(record.detail, str) or not record.detail:
            raise ValueError("Every finding needs effect evidence.")
        if not isinstance(record.rule, str) or not record.rule:
            raise ValueError("Every finding needs a rule identity.")
    if len(records) != len(set(records)):
        raise ValueError("Duplicate findings do not prove propagation.")
    return tuple(records)


def matches_owner(actual: str, expected: str) -> bool:
    if expected == "<lambda>":
        return actual == "<lambda>" or "<lambda@" in actual or actual.endswith(("::<lambda>", ".<lambda>"))
    return actual == expected or actual.endswith("." + expected) or actual.endswith("::" + expected)


def attribution_failures(case: dict, records: tuple[Observation, ...]) -> list[str]:
    failures = []
    for owner, rules in case.get("outcomes", {}).items():
        found = {record.rule for record in records if matches_owner(record.owner, owner)}
        if found != set(rules):
            failures.append(f"{owner} effects {sorted(found)}, expected {sorted(rules)}")
    for owner in case.get("quiet_owners", []):
        if any(matches_owner(record.owner, owner) for record in records):
            failures.append(f"{owner} must not own a finding")
    allowed = case.get("allowed_rules")
    if allowed is not None:
        unexpected = {record.rule for record in records} - set(allowed)
        if unexpected:
            failures.append(f"unexpected effect kinds {sorted(unexpected)}")
    for rule, minimum in case.get("minimum_findings", {}).items():
        count = len({record.owner for record in records if record.rule == rule})
        if count < minimum:
            failures.append(f"{rule} owners {count}, expected at least {minimum}")
    return failures
