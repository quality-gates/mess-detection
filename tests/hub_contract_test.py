#!/usr/bin/env python3
"""Contract for the quality-gates mess-detection org hub README."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")

REQUIRED_HEADINGS = [
    "# Mess detection",
    "## Why you need it",
    "## Pain points it hits",
    "## Language map",
    "## Start here",
    "## Related quality gates",
]

LANGUAGE_ROWS = [
    ("Python", "https://github.com/quality-gates/messpy", "messpy"),
    ("Rust", "https://github.com/quality-gates/messrust", "messrust"),
    ("Go", "https://github.com/quality-gates/messgo", "messgo"),
    ("JavaScript / TypeScript", "https://github.com/quality-gates/messcript", "messcript"),
    ("C#", "https://github.com/quality-gates/messharp", "messharp"),
    ("F#", "https://github.com/quality-gates/messfsharp", "messfsharp"),
]

START_COMMANDS = [
    "python -m pip install messpy",
    "messpy src text python --ignore-tests",
    "cargo install messrust",
    "messrust src text rust --ignore-tests",
    "go install github.com/quality-gates/messgo/cmd/messgo@latest",
    "messgo ./... text go --ignore-tests",
    "git clone https://github.com/quality-gates/messcript.git",
    "node dist/cli.js src text typescript --ignore-tests",
    "scripts/dotnet.sh run --project src/MessSharp",
    "csharp --ignore-tests",
    "dotnet tool install --global messfsharp",
    "messfsharp src text fsharp --ignore-tests",
]

AI_SLOP_MARKERS = [
    "AI",
    "slop",
    "calcif",
]


class HubContractTest(unittest.TestCase):
    def test_required_headings_in_order(self) -> None:
        positions = []
        for heading in REQUIRED_HEADINGS:
            pos = README.find(heading)
            self.assertGreaterEqual(pos, 0, f"missing heading: {heading}")
            positions.append(pos)
        self.assertEqual(positions, sorted(positions), "headings must stay in hub order")

    def test_ai_code_slop_message_is_front_and_center(self) -> None:
        why = self._section("## Why you need it", "## Pain points it hits")
        for marker in AI_SLOP_MARKERS:
            self.assertIn(marker, why)
        self.assertLess(README.find("## Why you need it"), 900)
        # Core claim appears in the opening, not only buried in a table.
        opening = README[: README.find("## Pain points it hits")]
        self.assertIn("AI code slop", opening)

    def test_language_map_lists_org_tools(self) -> None:
        section = self._section("## Language map", "## Start here")
        for language, url, tool in LANGUAGE_ROWS:
            self.assertRegex(
                section,
                rf"\|\s*{re.escape(language)}\s*\|",
                f"language map must include {language}",
            )
            self.assertIn(url, section, f"language map must link {url}")
            self.assertIn(tool, section, f"language map must name {tool}")

    def test_start_here_has_real_install_commands(self) -> None:
        section = self._section("## Start here", "## Related quality gates")
        for command in START_COMMANDS:
            self.assertIn(command, section)

    def test_no_first_person_blog_voice(self) -> None:
        banned = [
            r"\bI should\b",
            r"\bin my opinion\b",
            r"\bI've found\b",
            r"\blet's step back\b",
        ]
        for pattern in banned:
            self.assertIsNone(
                re.search(pattern, README, flags=re.IGNORECASE),
                f"hub should not use blog voice: {pattern}",
            )

    def test_related_gates_point_at_mutation_family(self) -> None:
        section = self._section("## Related quality gates", None)
        for name in ("mutago", "mutarust", "mutaskell", "mutation-testing"):
            self.assertIn(f"quality-gates/{name}", section)

    def _section(self, start: str, end: str | None) -> str:
        start_pos = README.find(start)
        self.assertGreaterEqual(start_pos, 0, f"missing section {start}")
        if end is None:
            return README[start_pos:]
        end_pos = README.find(end, start_pos + 1)
        self.assertGreaterEqual(end_pos, 0, f"missing section end {end}")
        return README[start_pos:end_pos]


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(HubContractTest)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
