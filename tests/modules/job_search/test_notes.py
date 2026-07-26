from datetime import date
from pathlib import Path

from assistant.modules.job_search.models import JobPosting
from assistant.modules.job_search.notes import job_slug, list_job_notes, mint_job_note

RAW_TEXT = "AI Engineer at Anthropic\n\nRequirements:\n- 5+ years of Python\n"


def _posting(**overrides: object) -> JobPosting:
    fields: dict[str, object] = {
        "title": "AI Engineer",
        "company": "Anthropic",
        "market": "remote",
        "requirements": ["5+ years of Python"],
        "keywords": ["Python"],
        "url": None,
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
        _, _, body = content.partition("---\n")
        _, _, body = body.partition("---\n")
        assert body == RAW_TEXT

    def test_frontmatter_carries_the_typed_fields(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"

        mint_job_note(
            vault,
            _posting(market="sg", url="https://example.com/job"),
            RAW_TEXT,
            today=date(2026, 7, 19),
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
        _, _, body = content.partition("---\n")
        _, _, body = body.partition("---\n")
        assert body == RAW_TEXT


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
