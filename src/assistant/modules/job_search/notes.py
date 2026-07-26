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


@dataclass(frozen=True)
class JobNoteSummary:
    """The frontmatter fields `pa jobs list` renders, one row per job note."""

    slug: str
    company: str | None
    title: str | None
    verdict: str | None
    direction: str | None
    analyzed: str | None


def slugify(text: str) -> str:
    return _SLUG_STRIP_RE.sub("-", text.lower()).strip("-")


def job_slug(posting: JobPosting) -> str:
    return slugify(f"{posting.company}-{posting.title}")


def _jobs_dir(vault_path: Path) -> Path:
    return vault_path / "jobs"


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
    jobs_dir = _jobs_dir(vault_path)
    jobs_dir.mkdir(parents=True, exist_ok=True)
    note = render_job_note(posting, raw_text, captured=today or date.today(), url=url)
    (jobs_dir / f"{slug}.md").write_text(note)
    return slug


def list_job_notes(vault_path: Path) -> list[JobNoteSummary]:
    """The frontmatter of every job note in `jobs/`, for `pa jobs list`."""
    jobs_dir = _jobs_dir(vault_path)
    if not jobs_dir.exists():
        return []

    summaries: list[JobNoteSummary] = []
    for path in sorted(jobs_dir.glob("*.md")):
        match = _FRONTMATTER_RE.match(path.read_text())
        frontmatter: dict[str, Any] = (yaml.safe_load(match.group(1)) or {}) if match else {}
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
