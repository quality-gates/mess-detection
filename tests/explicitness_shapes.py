"""Approximate fixture shapes for the fake detectors and the corpus line lint. The runner never uses this module.

The fixtures follow one statement per line with block bodies indented under their declaration, so an owner's
declaration line and its body span can be estimated from text. This is test scaffolding for probes such as the
declaration-line and call-line blanket fakes. It is not a parser and it is never acceptance evidence.
"""

import re


NAMED = {
    "python": [r"^\s*(?:async\s+)?def\s+{name}\s*\(", r"^\s*class\s+{name}\b"],
    "typescript": [r"\bfunction\s*\*?\s*{name}\s*[<(]", r"^\s*(?:export\s+)?(?:const|let|var)\s+{name}\s*[=:]",
                   r"^\s*(?:(?:public|private|protected|static|async|readonly|get|set|override)\s+)*\*?\s*{name}\s*\(.*\{{\s*$",
                   r"^\s*(?:export\s+)?class\s+{name}\b"],
    "go": [r"^func\s+(?:\([^)]*\)\s*)?{name}\s*[\[(]", r"^type\s+{name}\b"],
    "fsharp": [r"^\s*(?:let|and|member|static member|override|default|abstract)\s+(?:(?:rec|inline|private|internal|mutable)\s+)*(?:\w+\.)?\(?\|?{name}\b",
               r"^\s*(?:module|type)\s+{name}\b"],
    "csharp": [r"^\s*(?:\[[^\]]*\]\s*)*(?:(?:public|private|internal|protected|static|async|override|virtual|sealed|readonly|extern|unsafe|new|partial|abstract)\s+)*(?:[\w<>\[\],.?]+(?:<[^>]*>)?\s+)?{name}\s*(?:<[^>]*>)?\s*\(",
               r"^\s*(?:(?:public|private|internal|protected|static|sealed|partial|abstract)\s+)*(?:class|struct|record|interface)\s+{name}\b",
               r"^\s*(?:(?:public|private|internal|protected|static|readonly|event)\s+)+[\w<>\[\],.?]+\s+{name}\s*(?:[{=;]|$)"],
    "rust": [r"\bfn\s+{name}\s*[<(]", r"^\s*(?:pub\s+)?(?:struct|enum|trait|mod)\s+{name}\b", r"^\s*impl(?:<[^>]*>)?\s+(?:[\w:<>]+\s+for\s+)?{name}\b",
             r"^\s*(?:pub\s+)?(?:static|const)\s+(?:mut\s+)?{name}\s*:"],
}
ANONYMOUS = {
    "<lambda>": {"python": r"\blambda\b", "typescript": r"=>|\bfunction\s*\(", "go": r"\bfunc\s*\(", "fsharp": r"\bfun\b",
                 "csharp": r"=>|\bdelegate\s*\(", "rust": r"(?:^|[^|\w])\|[^|]*\|(?!\|)"},
    "<seq>": {"fsharp": r"\bseq\s*\{"},
    "<genexpr>": {"python": r"\b(?:return|[A-Za-z_]\w*\s*=)\s*\($"},
    "<async>": {"fsharp": r"\basync\s*\{", "rust": r"\basync\s+(?:move\s+)?\{", "typescript": r"\basync\b.*=>"},
    "<task>": {"fsharp": r"\btask\s*\{"},
    "<lazy>": {"fsharp": r"\blazy\b", "csharp": r"\bnew\s+Lazy\b|\bLazy<"},
}
KEYWORDS = {"if", "for", "while", "switch", "catch", "using", "lock", "foreach", "match", "fn", "func", "function", "elif",
            "lambda", "sizeof", "typeof", "nameof", "return", "await", "yield", "def", "class", "with", "not", "and", "or",
            "in", "is", "of", "let", "then", "else", "fun", "do", "mutable", "rec", "new", "static", "public", "private",
            "async", "const", "var", "type", "module", "member", "open", "import", "from", "package", "use", "mut", "pub",
            "impl", "struct", "where", "go", "defer", "range", "select", "case", "default", "when", "done", "begin", "end",
            "true", "false", "null", "None", "True", "False", "nil", "void", "int", "string", "bool", "seq", "task", "lazy",
            "printf", "ignore"}


def segments(owner: str) -> list[str]:
    return [part for part in re.split(r"\.(?![^<]*>)", owner) if part]


def _indent(text: str) -> int:
    expanded = text.expandtabs(4)
    return len(expanded) - len(expanded.lstrip())


def _matches(language: str, name: str, text: str) -> bool:
    if name.startswith("<"):
        pattern = ANONYMOUS.get(name, {}).get(language)
        return bool(pattern and re.search(pattern, text))
    if not any(re.search(pattern.replace("{name}", re.escape(name)).replace("{{", "{"), text) for pattern in NAMED[language]):
        return False
    # A C# line ending in a semicolon is a call or field unless it is an expression-bodied member.
    return not (language == "csharp" and text.rstrip().endswith(";") and not re.search(r"\)\s*=>", text)
                and not re.search(r"\b(?:event|static|readonly|public|private)\b", text))


def span(lines: list[str], start: int) -> range:
    """Lines (1-based) of the block that begins on line start: deeper-indented lines plus a closing bracket line."""
    base = _indent(lines[start - 1])
    end = start
    for number in range(start + 1, len(lines) + 1):
        text = lines[number - 1]
        if not text.strip():
            continue
        if _indent(text) > base:
            end = number
            continue
        if _indent(text) == base and text.strip() == "{":
            end = number
            continue
        if _indent(text) == base and re.match(r"^\s*(?:[})\]]|\|\]|end\b)", text):
            end = number
        break
    return range(start, end + 1)


def declaration_line(language: str, source: str, owner: str) -> int | None:
    """Estimate the line that declares an owner, using its qualifier to choose among same-named candidates."""
    lines = source.splitlines()
    if owner == "<module>":
        return None
    *scope, name = segments(owner)
    if language == "csharp" and re.match(r"^(?:get|set)_", name):
        accessor, property_name = name.split("_", 1)
        start = declaration_line(language, source, ".".join([*scope, property_name]))
        if start is None:
            return None
        found = [number for number in span(lines, start) if lines[number - 1].strip() == accessor]
        return found[0] if found else None
    if language == "go" and scope:
        receiver = re.escape(scope[-1])
        pattern = rf"^func\s+\(\s*(?:\w+\s+)?\*?{receiver}\s*\)\s+{re.escape(name)}\s*\("
        found = [number for number, text in enumerate(lines, 1) if re.search(pattern, text)]
        return found[0] if found else None
    window = range(1, len(lines) + 1)
    for qualifier in scope:
        found = [number for number in window if _matches(language, qualifier, lines[number - 1])]
        if not found:
            break
        window = max((span(lines, number) for number in found), key=len)
    found = [number for number in window if _matches(language, name, lines[number - 1])]
    return found[0] if found else None


def is_call(language: str, text: str) -> bool:
    code = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//.*$|#.*$', '""', text) if language != "rust" else re.sub(r'"(?:\\.|[^"\\])*"|//.*$', '""', text)
    for match in re.finditer(r"([A-Za-z_][\w.]*)\s*!?\s*\(", code):
        if match.group(1).split(".")[-1] not in KEYWORDS:
            return True
    if language == "fsharp":
        for match in re.finditer(r"\b([A-Za-z_][\w.]*)\s+(?=[A-Za-z_\"(\[0-9])", code):
            if match.group(1).split(".")[-1] not in KEYWORDS and not re.match(r"\s*(?:=|<-|->|:)", code[match.end():]):
                return True
    return False


def owner_lines(language: str, source: str, owners: list[str]) -> dict[str, list[int]]:
    """Assign each line to the innermost declared owner whose span contains it; `<module>` gets top-level lines."""
    lines = source.splitlines()
    spans = {}
    for owner in owners:
        start = declaration_line(language, source, owner)
        if start is not None:
            spans[owner] = span(lines, start)
    assigned = {owner: [] for owner in owners}
    for number in range(1, len(lines) + 1):
        holders = [owner for owner, block in spans.items() if number in block]
        if holders:
            inner = min(holders, key=lambda owner: (len(spans[owner]), -spans[owner].start))
            assigned[inner].append(number)
        elif "<module>" in assigned:
            assigned["<module>"].append(number)
    return assigned


def first_call_line(language: str, source: str, owner: str, owners: list[str]) -> int | None:
    lines = source.splitlines()
    mine = owner_lines(language, source, owners).get(owner, [])
    start = declaration_line(language, source, owner)
    body = [number for number in mine if number != start] or mine
    for number in body:
        if is_call(language, lines[number - 1]):
            return number
    return None
