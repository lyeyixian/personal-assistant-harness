"""The deterministic half of the resume contract: `ResumeContent` -> PDF bytes.

The model never crosses this seam. Everything layout-shaped happens here or in
`resume.typ`: dates become display strings, the work-authorization line is
toggled by market, and the two-page hard cap is enforced by rejecting overflow
rather than shrinking anything.

Compiles are byte-reproducible: a pinned Typst version supplies the fonts (no
system fonts are consulted), ligatures are off in the template, and the PDF
timestamp is pinned.
"""

import json
from pathlib import Path
from typing import Any

import typst

from assistant.modules.render.models import ResumeContent

TEMPLATE_PATH = Path(__file__).with_name("resume.typ")
MAX_PAGES = 2
PINNED_TIMESTAMP = 0
"""Unix epoch: a fixed creation date is what makes two compiles byte-identical."""

_PAGE_COUNT_LABEL = "<resume-page-count>"
_MONTH_NAMES = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


class ResumeOverflowError(ValueError):
    """Raised when content doesn't fit the two-page hard cap."""


def _format_month(value: str) -> str:
    """`2025-03` -> `Mar 2025`; anything else is passed through untouched."""
    year, _, month = value.partition("-")
    if not (year.isdigit() and month.isdigit() and 1 <= int(month) <= 12):
        return value
    return f"{_MONTH_NAMES[int(month) - 1]} {year}"


def _format_period(start: str, end: str | None) -> str:
    return f"{_format_month(start)} – {_format_month(end) if end else 'Present'}"


def _build_payload(content: ResumeContent) -> dict[str, Any]:
    """The template's JSON input: the IR, made display-ready.

    The work-authorization line is toggled here rather than in the template so
    the rule stays testable and so editing `market:` in a hand-edited
    `resume.yaml` re-renders correctly.
    """
    header = content.header
    contact = [header.location, header.email, header.phone, header.linkedin, header.github]

    return {
        "header": {
            "name": header.name,
            "title_line": header.title_line,
            "contact": [part for part in contact if part],
            "work_authorization": (header.work_authorization if content.market == "sg" else None),
        },
        "summary": content.summary,
        "skills": [group.model_dump() for group in content.skills],
        "experience": [
            {
                "company": position.company,
                "title": position.title,
                "location": position.location,
                "period": _format_period(position.start, position.end),
                "bullets": [bullet.text for bullet in position.bullets],
            }
            for position in content.experience
        ],
        "projects": [
            {
                "name": project.name,
                "link": project.link,
                "bullets": [bullet.text for bullet in project.bullets],
            }
            for project in content.projects
        ],
        "education": [school.model_dump() for school in content.education],
        "certifications": list(content.certifications),
    }


def _compile_inputs(content: ResumeContent) -> dict[str, str]:
    return {"resume": json.dumps(_build_payload(content), ensure_ascii=False)}


def _page_count(compile_inputs: dict[str, str]) -> int:
    """The rendered page count, read back from the template's own counter."""
    return int(
        # The `typst` wheel ships no type stubs, so pyright can't see `query`'s signature.
        typst.query(  # pyright: ignore[reportUnknownMemberType]
            str(TEMPLATE_PATH),
            _PAGE_COUNT_LABEL,
            field="value",
            one=True,
            sys_inputs=compile_inputs,
            ignore_system_fonts=True,
        )
    )


def render_resume_pdf(content: ResumeContent) -> bytes:
    """Compile `content` through the fixed template; raise if it overflows."""
    compile_inputs = _compile_inputs(content)

    pages = _page_count(compile_inputs)
    if pages > MAX_PAGES:
        raise ResumeOverflowError(
            f"Resume renders to {pages} pages; the hard cap is {MAX_PAGES}. "
            "Fix overflow by selection - fewer bullets, or drop the projects section - "
            "never by shrinking the layout."
        )

    # Same missing-stubs situation as `typst.query` above.
    pdf: bytes = typst.compile(  # pyright: ignore[reportUnknownMemberType]
        str(TEMPLATE_PATH),
        sys_inputs=compile_inputs,
        ignore_system_fonts=True,
        timestamp=PINNED_TIMESTAMP,
        pdf_standards=["ua-1"],
    )
    return pdf
