"""Journal file I/O — the per-day capture inbox described in the store schema.

A journal file is `---\\nfolded: <bool>\\n---\\n` frontmatter followed by pending
bullets, optionally followed by a `## Folded` heading and already-folded bullets.
Capture written directly in Obsidian follows the same convention, so the harness
must read/write it without relying on anything `pa journal add` itself produced -
appending never rewrites existing text, only inserts a new bullet, so hand-written
content (continuation lines, blank lines, prose) survives untouched.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

_FRONT_MATTER_FENCE = "---\n"
_CLOSING_FENCE = f"\n{_FRONT_MATTER_FENCE}"
_FOLDED_HEADING = "## Folded"
_FOLDED_FIELD_RE = re.compile(r"^folded:\s*(true|false)\s*$", re.MULTILINE | re.IGNORECASE)
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class JournalAddResult:
    path: Path
    created: bool
    reset_from_folded: bool


@dataclass(frozen=True)
class JournalEntry:
    date: date
    text: str
    folded: bool


@dataclass(frozen=True)
class _ParsedJournalFile:
    folded: bool
    pending_text: str
    folded_text: str


def add_entry(vault_path: Path, text: str, *, now: datetime | None = None) -> JournalAddResult:
    """Append a timestamped bullet to today's journal file.

    Creating the file sets `folded: false`; appending to an already-folded
    day resets the flag to `false`. Existing pending/folded text is preserved
    verbatim - only the new bullet is inserted - so hand-written content that
    isn't itself a flush `- ` bullet is never dropped.
    """
    moment = now if now is not None else datetime.now()
    journal_dir = vault_path / "journal"
    journal_dir.mkdir(parents=True, exist_ok=True)
    path = journal_dir / f"{moment:%Y-%m-%d}.md"
    bullet = f"- {moment:%H:%M} {text}"

    if path.exists():
        parsed = _parse_journal_file(path.read_text())
        created = False
        was_folded = parsed.folded
        pending_text = parsed.pending_text
        folded_text = parsed.folded_text
    else:
        created = True
        was_folded = False
        pending_text = ""
        folded_text = ""

    pending_text = f"{pending_text.rstrip()}\n{bullet}".lstrip("\n")
    path.write_text(_render_journal_file(pending_text, folded_text))
    return JournalAddResult(path=path, created=created, reset_from_folded=was_folded)


def list_entries(vault_path: Path, *, limit: int = 20) -> list[JournalEntry]:
    """Recent Journal Entries, newest day first, each tagged pending/folded."""
    journal_dir = vault_path / "journal"
    if not journal_dir.is_dir():
        return []

    files = sorted(
        (f for f in journal_dir.glob("*.md") if _DATE_RE.match(f.stem)),
        key=lambda f: f.stem,
        reverse=True,
    )

    entries: list[JournalEntry] = []
    for file in files:
        parsed = _parse_journal_file(file.read_text())
        day = date.fromisoformat(file.stem)
        for bullet in _extract_bullets(parsed.pending_text):
            entries.append(JournalEntry(date=day, text=_bullet_text(bullet), folded=False))
        for bullet in _extract_bullets(parsed.folded_text):
            entries.append(JournalEntry(date=day, text=_bullet_text(bullet), folded=True))
        if len(entries) >= limit:
            break
    return entries[:limit]


def _bullet_text(bullet: str) -> str:
    return bullet.removeprefix("- ")


def _parse_journal_file(content: str) -> _ParsedJournalFile:
    if not content.startswith(_FRONT_MATTER_FENCE):
        raise ValueError("journal file is missing its opening frontmatter fence (`---`)")
    try:
        header_end = content.index(_CLOSING_FENCE, len(_FRONT_MATTER_FENCE))
    except ValueError:
        raise ValueError("journal file's frontmatter fence is never closed") from None

    front_matter = content[len(_FRONT_MATTER_FENCE) : header_end]
    body = content[header_end + len(_CLOSING_FENCE) :]

    folded_match = _FOLDED_FIELD_RE.search(front_matter)
    if folded_match is None:
        raise ValueError("journal frontmatter is missing a `folded:` field")
    folded = folded_match.group(1).lower() == "true"

    if _FOLDED_HEADING in body:
        pending_text, heading, rest = body.partition(_FOLDED_HEADING)
        folded_text = heading + rest
    else:
        pending_text = body
        folded_text = ""

    return _ParsedJournalFile(folded=folded, pending_text=pending_text, folded_text=folded_text)


def _extract_bullets(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip().startswith("- ")]


def _render_journal_file(pending_text: str, folded_text: str) -> str:
    header = f"{_FRONT_MATTER_FENCE}folded: false\n{_FRONT_MATTER_FENCE}"
    pending_block = pending_text.rstrip()

    if folded_text:
        return f"{header}{pending_block}\n\n{folded_text}"
    return f"{header}{pending_block}\n" if pending_block else header
