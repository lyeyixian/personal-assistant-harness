"""The render seam: a fixture `ResumeContent` compiled through the real Typst
template, round-tripped back through `pdftotext`.

This is the spec's CI guard - it tests the glyph-to-Unicode property ATS
parsers depend on, not a snapshot of the layout.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from assistant.modules.job_search.models import ResumeBullet, ResumeExperience
from assistant.modules.job_search.render import (
    TEMPLATE_PATH,
    ResumeOverflowError,
    render_resume_pdf,
)
from tests.modules.job_search._helpers import make_resume_content

needs_pdftotext = pytest.mark.skipif(
    shutil.which("pdftotext") is None and not os.environ.get("CI"),
    reason="pdftotext (poppler-utils) is not installed; CI always has it",
)
"""Only the extraction tests need the binary - the rest must never skip silently."""


def extract_text(pdf: bytes, tmp_path: Path) -> str:
    """The PDF's text as an ATS parser would read it, whitespace normalized."""
    pdf_path = tmp_path / "resume.pdf"
    pdf_path.write_bytes(pdf)
    completed = subprocess.run(["pdftotext", str(pdf_path), "-"], capture_output=True, check=True)
    return re.sub(r"\s+", " ", completed.stdout.decode("utf-8"))


@needs_pdftotext
class TestPdftotextRoundTrip:
    def test_every_bullet_survives_extraction_verbatim(self, tmp_path: Path) -> None:
        content = make_resume_content()

        text = extract_text(render_resume_pdf(content), tmp_path)

        for bullet in content.bullets():
            assert re.sub(r"\s+", " ", bullet.text) in text

    def test_header_summary_skills_and_education_survive_extraction(self, tmp_path: Path) -> None:
        content = make_resume_content()

        text = extract_text(render_resume_pdf(content), tmp_path)

        assert content.header.name in text
        assert content.header.email in text
        assert re.sub(r"\s+", " ", content.summary) in text
        assert "PostgreSQL" in text
        assert "University of Nowhere" in text
        assert "AWS Certified Cloud Practitioner (2025)" in text

    def test_source_refs_are_never_rendered(self, tmp_path: Path) -> None:
        content = make_resume_content()

        text = extract_text(render_resume_pdf(content), tmp_path)

        assert "acme-payments-rotation#" not in text
        assert "oss-contribution#" not in text

    def test_current_role_reads_as_present(self, tmp_path: Path) -> None:
        text = extract_text(render_resume_pdf(make_resume_content()), tmp_path)

        assert "Mar 2025 – Present" in text


@needs_pdftotext
class TestWorkAuthorizationToggle:
    def test_the_line_is_rendered_for_a_singapore_posting(self, tmp_path: Path) -> None:
        content = make_resume_content(market="sg")

        text = extract_text(render_resume_pdf(content), tmp_path)

        assert "Singapore Citizen" in text

    def test_the_line_is_dropped_for_a_remote_posting(self, tmp_path: Path) -> None:
        content = make_resume_content(market="remote")

        text = extract_text(render_resume_pdf(content), tmp_path)

        assert "Singapore Citizen" not in text
        assert content.header.name in text


class TestDeterministicOutput:
    def test_the_same_content_renders_byte_identical_pdfs(self) -> None:
        content = make_resume_content()

        assert render_resume_pdf(content) == render_resume_pdf(content)

    def test_fonts_are_embedded(self) -> None:
        pdf = render_resume_pdf(make_resume_content())

        assert b"FontFile" in pdf

    def test_the_pdf_is_tagged(self) -> None:
        pdf = render_resume_pdf(make_resume_content())

        assert b"/MarkInfo" in pdf

    def test_the_template_disables_ligatures(self) -> None:
        # Not observable through pdftotext - it maps ligature glyphs back via
        # ToUnicode - but the spec wants extraction to not depend on that being
        # right, so the setting itself is the guard.
        assert "ligatures: false" in TEMPLATE_PATH.read_text()


class TestTwoPageCap:
    def test_content_overflowing_two_pages_is_rejected(self) -> None:
        content = make_resume_content()
        long_bullet = ResumeBullet(
            text=" ".join(["Delivered a great deal of prose that fills the page."] * 40),
            source="acme-payments-rotation#settlement-service-refactor",
        )
        content.experience = [
            ResumeExperience(
                company="Acme Corp",
                title="Software Engineer",
                start="2025-03",
                bullets=[long_bullet] * 5,
            )
        ] * 3

        with pytest.raises(ResumeOverflowError) as exc_info:
            render_resume_pdf(content)

        assert "fewer bullets" in str(exc_info.value)
