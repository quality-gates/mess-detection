from dataclasses import dataclass
from pathlib import Path
import re


RULES = ("ImplicitInput", "ImplicitOutput", "UnknownEffect")


@dataclass(frozen=True)
class Observation:
    owner: str
    path: str
    line: int
    rule: str
    detail: str
    suppressed: bool = False


def owner_name(context: str) -> str:
    name = re.sub(r"^(?:arrow function|function|method|accessor|constructor)\s+", "", context).removesuffix("()")
    return "<lambda>" if name == "anonymous" else name


def _object(value, where: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{where} must be a JSON object, not {type(value).__name__}.")
    return value


def _array(value, where: str) -> list:
    if not isinstance(value, list):
        raise ValueError(f"{where} must be a JSON array, not {type(value).__name__}.")
    return value


def _text(value, where: str, empty: bool = False) -> str:
    if not isinstance(value, str) or (not empty and not value):
        raise ValueError(f"{where} must be a non-empty string.")
    return value


def _line(value, where: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{where} must be a positive integer line.")
    return value


def _suppressed(finding: dict) -> bool:
    value = finding.get("suppressed", False)
    if not isinstance(value, bool):
        raise ValueError("A suppressed marker must be a boolean.")
    return value


def observations(language: str, payload) -> tuple[Observation, ...]:
    """Return every finding in a native JSON report, or raise ValueError for a malformed report."""
    payload = _object(payload, "The native report")
    errors = payload.get("errors", [])
    if errors:
        raise ValueError("The native JSON report contains processing errors.")
    records = []
    if language in {"python", "typescript"}:
        for finding in _array(payload.get("findings"), "findings"):
            finding = _object(finding, "A finding")
            records.append(Observation(
                owner_name(_text(finding.get("context"), "context")), _text(finding.get("path"), "path"),
                _line(finding.get("line"), "line"), _text(finding.get("ruleName"), "ruleName"),
                _text(finding.get("message"), "message"), _suppressed(finding)))
    elif language == "fsharp":
        for finding in _array(payload.get("violations"), "violations"):
            finding = _object(finding, "A violation")
            context = _object(finding.get("context"), "context")
            owner = _text(context.get("member"), "context.member")
            description = _text(finding.get("description"), "description")
            subject = re.match(r"^'([^']+)'", description)
            if subject and owner != subject.group(1):
                raise ValueError("The F# finding context disagrees with its execution owner.")
            for qualifier in ("type", "module", "namespace"):
                scope = _text(context.get(qualifier) or "", f"context.{qualifier}", empty=True)
                if scope and not owner.startswith(scope + "."):
                    owner = scope + "." + owner
            records.append(Observation(
                owner_name(owner), _text(finding.get("file"), "file"), _line(finding.get("startLine"), "startLine"),
                _text(finding.get("rule"), "rule"), description, _suppressed(finding)))
    elif language in {"go", "csharp", "rust"}:
        for file in _array(payload.get("files"), "files"):
            file = _object(file, "A file report")
            path = _text(file.get("file"), "file")
            for finding in _array(file.get("violations"), "violations"):
                finding = _object(finding, "A violation")
                method = _text(finding.get("method") or "", "method", empty=True)
                function = _text(finding.get("function") or "", "function", empty=True)
                owner = _text(method or function, "method or function")
                if language in {"go", "csharp"} and method:
                    scope = _text(finding.get("class", ""), "class", empty=True)
                    if scope and not owner.startswith(scope + "."):
                        owner = scope + "." + owner
                records.append(Observation(
                    owner_name(owner), path,
                    _line(finding.get("beginLine"), "beginLine"), _text(finding.get("rule"), "rule"),
                    _text(finding.get("description"), "description"), _suppressed(finding)))
    else:
        raise ValueError("Unknown native report format.")
    if len(records) != len(set(records)):
        raise ValueError("Duplicate findings do not prove propagation.")
    return tuple(records)


ROOTS = {"<locals>"}
LEADING_ROOTS = {"crate", "self", "super"}


def _segments(name: str) -> list[str]:
    name = name.replace("::", ".")
    name = re.sub(r"^\(\*?([^()]+)\)\.", r"\1.", name)
    segments, current, depth = [], "", 0
    for character in name:
        if character == "<":
            depth += 1
        elif character == ">":
            depth = max(0, depth - 1)
        if character == "." and depth == 0:
            segments.append(current)
            current = ""
        else:
            current += character
    segments.append(current)
    return [re.sub(r"^<([A-Za-z]+)@.*>$", r"<\1>", segment) for segment in segments]


def owner_segments(actual: str, stem: str = "") -> list[str]:
    """Normalize a native owner: drop language roots and a leading module named after the fixture file."""
    segments = [segment for segment in _segments(actual) if segment not in ROOTS]
    while len(segments) > 1 and (segments[0] in LEADING_ROOTS or (stem and segments[0].lower() == stem.lower())):
        segments = segments[1:]
    return segments


def declared_owner(actual: str, declared: list[str], scopes=(), stem: str = "") -> str | None:
    """Map a native owner to exactly one declared callable, or return None when it matches none or several.

    A declared owner may be qualified, such as ``A.run``. A native owner matches it when its trailing segments
    equal the declared segments and every extra leading qualifier is a declared scope or a segment of a declared
    owner. An exact spelling wins; otherwise the most specific match wins, and a tie is ambiguous.
    """
    segments = owner_segments(actual, stem)
    allowed = set(scopes) | {segment for owner in declared for segment in _segments(owner)}
    candidates = []
    for owner in declared:
        expected = _segments(owner)
        if segments == expected:
            return owner
        extra = segments[:len(segments) - len(expected)]
        if len(segments) > len(expected) and segments[len(extra):] == expected and set(extra) <= allowed:
            candidates.append((len(expected), owner))
    if not candidates:
        return None
    best = max(length for length, _ in candidates)
    winners = [owner for length, owner in candidates if length == best]
    return winners[0] if len(winners) == 1 else None


def map_path(path: str, mappings: list[tuple[str, str]], cwd: Path) -> Path:
    for container, host in mappings:
        if path == container or path.startswith(container.rstrip("/") + "/"):
            path = host.rstrip("/") + path[len(container.rstrip("/")):]
            break
    candidate = Path(path)
    return (candidate if candidate.is_absolute() else cwd / candidate).resolve()


def attribution_failures(case: dict, records: tuple[Observation, ...], fixture: Path,
                         mappings: list[tuple[str, str]] = (), cwd: Path | None = None) -> list[str]:
    """Judge records against the closed set of callables, effect kinds, and designated effect lines a case declares."""
    failures = []
    outcomes = case["outcomes"]
    declared = [*outcomes, *case["quiet_owners"]]
    seen = set()
    fixture = fixture.resolve()
    for record in records:
        where = f"{record.owner} {record.rule} at {record.path}:{record.line}"
        try:
            inside = map_path(record.path, list(mappings), cwd or Path.cwd()) == fixture
        except (OSError, ValueError, RuntimeError) as error:
            failures.append(f"{where} has an unusable path: {type(error).__name__}")
            inside = True
        if not inside:
            failures.append(f"{where} is outside the fixture")
        owner = declared_owner(record.owner, declared, case.get("scopes", ()), fixture.stem)
        if owner is None:
            failures.append(f"{where} has an undeclared or ambiguous owner")
        elif owner not in outcomes:
            failures.append(f"{where} is on quiet owner {owner}")
        elif record.rule not in outcomes[owner]:
            failures.append(f"{where} is not an expected effect of {owner} {sorted(outcomes[owner])}")
        elif record.line != outcomes[owner][record.rule]:
            failures.append(f"{where} is not on the effect line {outcomes[owner][record.rule]}")
        else:
            seen.add((owner, record.rule))
    for owner, rules in outcomes.items():
        for rule, line in rules.items():
            if (owner, rule) not in seen:
                failures.append(f"missing {owner} {rule} at line {line}")
    return failures
