"""Job note I/O: minting postings into the vault's `jobs/` folder and listing them.

Per the job-fit-analysis spec: the filename is a minted kebab slug
(`jobs/<company>-<title>.md`), and the pasted body is the untouched source of
truth - the agent never edits it, and every mint fully overwrites the note
(frontmatter and body together) rather than merging into what's there.
"""

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from assistant.modules.job_search.models import JobPosting

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)
_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")

FIT_SECTION_HEADING = "## Fit analysis"
_FIT_SECTION_RE = re.compile(rf"\n{re.escape(FIT_SECTION_HEADING)}\n.*\Z", re.DOTALL)


@dataclass(frozen=True)
class JobNoteSummary:
    """The frontmatter fields `pa jobs list` renders, one row per job note."""

    slug: str
    company: str | None
    title: str | None
    verdict: str | None
    direction: str | None
    analyzed: str | None


@dataclass(frozen=True)
class JobNote:
    """A job note's frontmatter and its verbatim posting text - any prior
    `## Fit analysis` section stripped, since that section is derived output,
    never the source of truth `pa jobs fit` re-analyzes."""

    slug: str
    frontmatter: dict[str, Any]
    posting_text: str


def slugify(text: str) -> str:
    return _SLUG_STRIP_RE.sub("-", text.lower()).strip("-")


def job_slug(posting: JobPosting) -> str:
    return slugify(f"{posting.company}-{posting.title}")


def _jobs_dir(vault_path: Path) -> Path:
    return vault_path / "jobs"


def job_note_path(vault_path: Path, slug: str) -> Path:
    return _jobs_dir(vault_path) / f"{slug}.md"


def job_note_exists(vault_path: Path, slug: str) -> bool:
    return job_note_path(vault_path, slug).exists()


def _parse_note(content: str) -> tuple[dict[str, Any], str]:
    match = _FRONTMATTER_RE.match(content)
    if match is None:
        return {}, content
    frontmatter: dict[str, Any] = yaml.safe_load(match.group(1)) or {}
    return frontmatter, match.group(2)


def render_job_note(
    posting: JobPosting, raw_text: str, *, captured: date, url: str | None = None
) -> str:
    frontmatter: dict[str, Any] = {
        "type": "job",
        "company": posting.company,
        "title": posting.title,
        "market": posting.market,
        "url": url,
        "captured": captured.isoformat(),
        "verdict": None,
        "direction": None,
        "analyzed": None,
    }
    header = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True)
    return f"---\n{header}---\n{raw_text}"


def mint_job_note(
    vault_path: Path,
    posting: JobPosting,
    raw_text: str,
    *,
    today: date | None = None,
    url: str | None = None,
) -> str:
    """Write `posting`'s job note, replacing any note already at the same slug; returns the slug."""
    slug = job_slug(posting)
    _jobs_dir(vault_path).mkdir(parents=True, exist_ok=True)
    note = render_job_note(posting, raw_text, captured=today or date.today(), url=url)
    job_note_path(vault_path, slug).write_text(note)
    return slug


def list_job_notes(vault_path: Path) -> list[JobNoteSummary]:
    """The frontmatter of every job note in `jobs/`, for `pa jobs list`."""
    jobs_dir = _jobs_dir(vault_path)
    if not jobs_dir.exists():
        return []

    summaries: list[JobNoteSummary] = []
    for path in sorted(jobs_dir.glob("*.md")):
        frontmatter, _ = _parse_note(path.read_text())
        summaries.append(
            JobNoteSummary(
                slug=path.stem,
                company=frontmatter.get("company"),
                title=frontmatter.get("title"),
                verdict=frontmatter.get("verdict"),
                direction=frontmatter.get("direction"),
                analyzed=frontmatter.get("analyzed"),
            )
        )
    return summaries


def read_job_note(vault_path: Path, slug: str) -> JobNote:
    """Read a job note's frontmatter and posting text, stripping any prior fit section."""
    content = job_note_path(vault_path, slug).read_text()
    frontmatter, body = _parse_note(content)
    return JobNote(slug=slug, frontmatter=frontmatter, posting_text=_FIT_SECTION_RE.sub("", body))


def write_fit_report(
    vault_path: Path,
    slug: str,
    fit_section: str,
    *,
    verdict: str,
    direction: str,
    analyzed: date,
) -> None:
    """Replace the note's `## Fit analysis` section wholesale and lift
    verdict/direction/analyzed into frontmatter; the posting text is untouched
    - re-runs overwrite the section, earlier runs live in git history.
    """
    note = read_job_note(vault_path, slug)
    frontmatter = {
        **note.frontmatter,
        "verdict": verdict,
        "direction": direction,
        "analyzed": analyzed.isoformat(),
    }
    header = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True)
    body = f"{note.posting_text.rstrip('\n')}\n\n{fit_section.strip()}\n"
    job_note_path(vault_path, slug).write_text(f"---\n{header}---\n{body}")
