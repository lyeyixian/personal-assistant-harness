"""Deterministic posting parser: pasted job-posting text -> the typed `JobPosting`.

Shared by `pa jobs add` (and, per the job-fit and resume-generation specs, later by
`pa jobs fit` / `pa jobs resume`) so every v1 feature reads the identical parse.
No LLM call here - title/company/requirements extraction is pattern-based on
purpose, so the same posting always parses the same way.
"""

import re

from assistant.modules.job_search.models import JobPosting, Market

_LABEL_PATTERNS = {
    "title": [r"job\s*title", r"title"],
    "company": [r"company"],
}
_TITLE_AT_COMPANY_RE = re.compile(r"(?i)^(.*?)\s+at\s+(.+)$")
_BULLET_RE = re.compile(r"^\s*[-*•–]\s+(.*\S)\s*$")
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.#-]*")
_SINGAPORE_RE = re.compile(r"(?i)\bsingapore\b")

_KEYWORD_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "excellent",
        "experience",
        "for",
        "in",
        "of",
        "or",
        "proven",
        "requirements",
        "strong",
        "the",
        "to",
        "with",
        "years",
    }
)


class PostingParseError(ValueError):
    """Raised when a title and company can't be determined from the posting text."""


def infer_market(text: str) -> Market:
    """`sg` if the posting mentions Singapore, `remote` otherwise."""
    return "sg" if _SINGAPORE_RE.search(text) else "remote"


def _extract_labeled(text: str, field: str) -> str | None:
    for pattern in _LABEL_PATTERNS[field]:
        match = re.search(rf"(?im)^\s*{pattern}\s*:\s*(.+?)\s*$", text)
        if match:
            return match.group(1)
    return None


def _first_two_lines(text: str) -> tuple[str, str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return (lines[0] if lines else "", lines[1] if len(lines) > 1 else "")


def _extract_title_and_company(text: str) -> tuple[str, str]:
    title = _extract_labeled(text, "title")
    company = _extract_labeled(text, "company")

    first_line, second_line = _first_two_lines(text)
    if title is None:
        inline_match = _TITLE_AT_COMPANY_RE.match(first_line)
        if inline_match:
            title = inline_match.group(1).strip()
            company = company or inline_match.group(2).strip()
        else:
            title = first_line
    if not company:
        company = second_line

    if not title or not company:
        raise PostingParseError(
            "Could not determine a title and company from the posting text - "
            "add explicit 'Title:' and 'Company:' lines."
        )
    return title, company


def _extract_requirements(text: str) -> list[str]:
    return [match.group(1) for line in text.splitlines() if (match := _BULLET_RE.match(line))]


def _extract_keywords(requirements: list[str]) -> list[str]:
    # Skip each line's first word positionally - bullets conventionally open on a
    # sentence-case filler verb ("Strong", "Familiarity"), not the keyword itself.
    seen: dict[str, None] = {}
    for line in requirements:
        for index, word in enumerate(_WORD_RE.findall(line)):
            if index == 0 or word.lower() in _KEYWORD_STOPWORDS or not word[0].isupper():
                continue
            seen.setdefault(word, None)
    return list(seen)


def parse_posting(text: str, *, market: Market | None = None) -> JobPosting:
    """Parse pasted posting text into a `JobPosting`; `market` overrides inference."""
    title, company = _extract_title_and_company(text)
    requirements = _extract_requirements(text)

    return JobPosting(
        title=title,
        company=company,
        market=market or infer_market(text),
        requirements=requirements,
        keywords=_extract_keywords(requirements),
    )
