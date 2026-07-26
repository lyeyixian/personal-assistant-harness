"""Deterministic parsing of a single vault note: frontmatter, body, and
Achievement mini-arcs - the `## Achievements` / `### <heading>` structure the
schema spec calls out as a deliberate seam. Achievement headings are slugged
for the provenance validator; each achievement's labeled fields
(`**Impact:**`/`**Lessons:**`) are kept verbatim in its body, unparsed, for a
future Fold to read and rewrite.
"""

import re
from typing import Any

import yaml

from assistant.core.store.models import Achievement

_FRONTMATTER_DELIMITER = "---"


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split a note's raw text into its frontmatter dict and remaining body.

    Notes without a frontmatter block (`profile.md`, `skills.md` in the
    fixture vault) return an empty dict and the text unchanged.
    """
    lines = text.split("\n")
    if lines[0] != _FRONTMATTER_DELIMITER:
        return {}, text

    for index, line in enumerate(lines[1:], start=1):
        if line == _FRONTMATTER_DELIMITER:
            frontmatter: dict[str, Any] = yaml.safe_load("\n".join(lines[1:index])) or {}
            body = "\n".join(lines[index + 1 :])
            return frontmatter, body

    return {}, text


def slugify(heading: str) -> str:
    """Kebab-case a heading, matching the schema spec's ref examples exactly."""
    lowered = heading.strip().lower()
    stripped = re.sub(r"[^a-z0-9\s-]", "", lowered)
    return re.sub(r"\s+", "-", stripped)


def parse_achievements(body: str) -> tuple[Achievement, ...]:
    """Extract each `###` mini-arc under a note's `## Achievements` heading."""
    achievements: list[Achievement] = []
    in_achievements_section = False
    current_heading: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        if current_heading is not None:
            achievements.append(
                Achievement(
                    heading=current_heading,
                    slug=slugify(current_heading),
                    body="\n".join(current_lines).strip(),
                )
            )

    for line in body.split("\n"):
        if line.startswith("## "):
            flush()
            current_heading = None
            current_lines = []
            in_achievements_section = line.removeprefix("## ").strip().lower() == "achievements"
        elif in_achievements_section and line.startswith("### "):
            flush()
            current_heading = line.removeprefix("### ").strip()
            current_lines = []
        elif current_heading is not None:
            current_lines.append(line)

    flush()
    return tuple(achievements)
