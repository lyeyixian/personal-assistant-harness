from datetime import date
from pathlib import Path

from assistant.modules.job_search.models import JobPosting
from assistant.modules.job_search.notes import (
    job_note_exists,
    job_slug,
    list_job_notes,
    mint_job_note,
    read_job_note,
    write_fit_report,
)
from tests.modules.job_search._helpers import job_note_body

RAW_TEXT = "AI Engineer at Anthropic\n\nRequirements:\n- 5+ years of Python\n"


def _posting(**overrides: object) -> JobPosting:
    fields: dict[str, object] = {
        "title": "AI Engineer",
        "company": "Anthropic",
        "market": "remote",
        "requirements": ["5+ years of Python"],
        "keywords": ["Python"],
    }
    fields.update(overrides)
    return JobPosting.model_validate(fields)


class TestJobSlug:
    def test_combines_company_and_title_as_kebab_case(self) -> None:
        assert job_slug(_posting()) == "anthropic-ai-engineer"

    def test_lowercases_and_strips_punctuation(self) -> None:
        posting = _posting(company="Acme Corp.", title="Sr. Software Engineer!")

        assert job_slug(posting) == "acme-corp-sr-software-engineer"


class TestMintJobNote:
    def test_writes_a_kebab_slug_filename_under_jobs(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"

        slug = mint_job_note(vault, _posting(), RAW_TEXT, today=date(2026, 7, 19))

        assert slug == "anthropic-ai-engineer"
        assert (vault / "jobs" / "anthropic-ai-engineer.md").exists()

    def test_body_is_the_verbatim_paste(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"

        mint_job_note(vault, _posting(), RAW_TEXT, today=date(2026, 7, 19))

        content = (vault / "jobs" / "anthropic-ai-engineer.md").read_text()
        assert job_note_body(content) == RAW_TEXT

    def test_frontmatter_carries_the_typed_fields(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"

        mint_job_note(
            vault,
            _posting(market="sg"),
            RAW_TEXT,
            today=date(2026, 7, 19),
            url="https://example.com/job",
        )

        content = (vault / "jobs" / "anthropic-ai-engineer.md").read_text()
        assert "company: Anthropic" in content
        assert "title: AI Engineer" in content
        assert "market: sg" in content
        assert "url: https://example.com/job" in content
        assert "captured: '2026-07-19'" in content or "captured: 2026-07-19" in content
        assert "verdict: null" in content
        assert "direction: null" in content
        assert "analyzed: null" in content

    def test_rerun_never_alters_the_verbatim_paste(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"

        mint_job_note(vault, _posting(), RAW_TEXT, today=date(2026, 7, 19))
        mint_job_note(vault, _posting(), RAW_TEXT, today=date(2026, 7, 20))

        content = (vault / "jobs" / "anthropic-ai-engineer.md").read_text()
        assert job_note_body(content) == RAW_TEXT


class TestListJobNotes:
    def test_empty_vault_returns_no_notes(self, tmp_path: Path) -> None:
        assert list_job_notes(tmp_path / "vault") == []

    def test_lists_frontmatter_fields_for_each_note(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        mint_job_note(vault, _posting(), RAW_TEXT, today=date(2026, 7, 19))
        mint_job_note(
            vault,
            _posting(company="Acme Corp", title="Backend Engineer", market="sg"),
            "Backend Engineer at Acme Corp\n",
            today=date(2026, 7, 20),
        )

        notes = list_job_notes(vault)

        assert {note.slug for note in notes} == {
            "anthropic-ai-engineer",
            "acme-corp-backend-engineer",
        }
        anthropic = next(note for note in notes if note.slug == "anthropic-ai-engineer")
        assert anthropic.company == "Anthropic"
        assert anthropic.title == "AI Engineer"
        assert anthropic.verdict is None
        assert anthropic.direction is None
        assert anthropic.analyzed is None


class TestJobNoteExists:
    def test_false_when_no_note_at_the_slug(self, tmp_path: Path) -> None:
        assert job_note_exists(tmp_path / "vault", "anthropic-ai-engineer") is False

    def test_true_once_minted(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        mint_job_note(vault, _posting(), RAW_TEXT, today=date(2026, 7, 19))

        assert job_note_exists(vault, "anthropic-ai-engineer") is True


class TestReadJobNote:
    def test_reads_frontmatter_and_the_verbatim_posting_text(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        mint_job_note(vault, _posting(), RAW_TEXT, today=date(2026, 7, 19))

        note = read_job_note(vault, "anthropic-ai-engineer")

        assert note.slug == "anthropic-ai-engineer"
        assert note.frontmatter["company"] == "Anthropic"
        assert note.posting_text == RAW_TEXT

    def test_strips_a_prior_fit_section_out_of_the_posting_text(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        mint_job_note(vault, _posting(), RAW_TEXT, today=date(2026, 7, 19))
        write_fit_report(
            vault,
            "anthropic-ai-engineer",
            "## Fit analysis\n\n**Verdict:** good-fit\n",
            verdict="good-fit",
            direction="aligned",
            analyzed=date(2026, 7, 20),
        )

        note = read_job_note(vault, "anthropic-ai-engineer")

        assert note.posting_text == RAW_TEXT


class TestWriteFitReport:
    def test_lifts_verdict_direction_and_analyzed_into_frontmatter(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        mint_job_note(vault, _posting(), RAW_TEXT, today=date(2026, 7, 19))

        write_fit_report(
            vault,
            "anthropic-ai-engineer",
            "## Fit analysis\n\nSome report body.\n",
            verdict="strong-fit",
            direction="aligned",
            analyzed=date(2026, 7, 20),
        )

        content = (vault / "jobs" / "anthropic-ai-engineer.md").read_text()
        assert "verdict: strong-fit" in content
        assert "direction: aligned" in content
        assert "analyzed: '2026-07-20'" in content or "analyzed: 2026-07-20" in content

    def test_preserves_other_frontmatter_fields(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        mint_job_note(
            vault, _posting(), RAW_TEXT, today=date(2026, 7, 19), url="https://example.com/job"
        )

        write_fit_report(
            vault,
            "anthropic-ai-engineer",
            "## Fit analysis\n",
            verdict="strong-fit",
            direction="aligned",
            analyzed=date(2026, 7, 20),
        )

        content = (vault / "jobs" / "anthropic-ai-engineer.md").read_text()
        assert "company: Anthropic" in content
        assert "url: https://example.com/job" in content

    def test_leaves_the_posting_text_untouched(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        mint_job_note(vault, _posting(), RAW_TEXT, today=date(2026, 7, 19))

        write_fit_report(
            vault,
            "anthropic-ai-engineer",
            "## Fit analysis\n\nSome report body.\n",
            verdict="strong-fit",
            direction="aligned",
            analyzed=date(2026, 7, 20),
        )

        note = read_job_note(vault, "anthropic-ai-engineer")
        assert note.posting_text == RAW_TEXT

    def test_rerun_replaces_the_fit_section_wholesale(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        mint_job_note(vault, _posting(), RAW_TEXT, today=date(2026, 7, 19))

        write_fit_report(
            vault,
            "anthropic-ai-engineer",
            "## Fit analysis\n\nFirst run body.\n",
            verdict="stretch",
            direction="caution",
            analyzed=date(2026, 7, 19),
        )
        write_fit_report(
            vault,
            "anthropic-ai-engineer",
            "## Fit analysis\n\nSecond run body.\n",
            verdict="strong-fit",
            direction="aligned",
            analyzed=date(2026, 7, 20),
        )

        content = (vault / "jobs" / "anthropic-ai-engineer.md").read_text()
        assert content.count("## Fit analysis") == 1
        assert "First run body" not in content
        assert "Second run body" in content
        assert "verdict: strong-fit" in content
