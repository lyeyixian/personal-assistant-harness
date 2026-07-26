from pathlib import Path

import pytest
import yaml

from assistant.core import ExperienceStore
from assistant.modules.job_search.models import ResumeContent
from assistant.modules.job_search.resume import (
    PDF_FILENAME,
    YAML_FILENAME,
    ProvenanceError,
    load_resume_content,
    resume_output_dir,
    validate_resume_provenance,
    write_resume,
)
from tests.modules.job_search._helpers import POSTING, make_resume_content


class TestProvenanceGate:
    def test_content_whose_refs_all_resolve_passes(self, store: ExperienceStore) -> None:
        validate_resume_provenance(store, make_resume_content())

    def test_an_experience_bullet_with_an_unknown_heading_fails(
        self, store: ExperienceStore
    ) -> None:
        content = make_resume_content(experience_source="acme-payments-rotation#invented-win")

        with pytest.raises(ProvenanceError) as exc_info:
            validate_resume_provenance(store, content)

        assert [failure.ref for failure in exc_info.value.failures] == [
            "acme-payments-rotation#invented-win"
        ]
        assert exc_info.value.failures[0].reason == "unknown-heading"

    def test_a_project_bullet_is_checked_too(self, store: ExperienceStore) -> None:
        content = make_resume_content(
            project_source="no-such-note#accessible-date-picker-component"
        )

        with pytest.raises(ProvenanceError) as exc_info:
            validate_resume_provenance(store, content)

        assert exc_info.value.failures[0].reason == "unknown-note"

    def test_the_error_message_names_every_bad_ref(self, store: ExperienceStore) -> None:
        content = make_resume_content(
            experience_source="acme-payments-rotation#invented-win",
            project_source="malformed-ref-without-a-heading",
        )

        with pytest.raises(ProvenanceError) as exc_info:
            validate_resume_provenance(store, content)

        message = str(exc_info.value)
        assert "acme-payments-rotation#invented-win" in message
        assert "malformed-ref-without-a-heading" in message


class TestOutputDirectory:
    def test_is_the_posting_slug_under_the_configured_root(self, tmp_path: Path) -> None:
        assert resume_output_dir(tmp_path / "pa-output", POSTING) == (
            tmp_path / "pa-output" / "anthropic-ai-engineer"
        )


class TestWriteResume:
    def test_one_run_writes_both_the_yaml_and_the_pdf(
        self, tmp_path: Path, store: ExperienceStore
    ) -> None:
        artifacts = write_resume(tmp_path / "out", make_resume_content(), store)

        assert artifacts.yaml_path == tmp_path / "out" / YAML_FILENAME
        assert artifacts.pdf_path == tmp_path / "out" / PDF_FILENAME
        assert artifacts.yaml_path.exists()
        assert artifacts.pdf_path.read_bytes().startswith(b"%PDF")

    def test_the_yaml_round_trips_back_into_the_ir(
        self, tmp_path: Path, store: ExperienceStore
    ) -> None:
        content = make_resume_content()

        artifacts = write_resume(tmp_path / "out", content, store)

        assert load_resume_content(artifacts.directory) == content

    def test_the_yaml_keeps_source_refs_and_market_hand_editable(
        self, tmp_path: Path, store: ExperienceStore
    ) -> None:
        artifacts = write_resume(tmp_path / "out", make_resume_content(), store)

        document = yaml.safe_load(artifacts.yaml_path.read_text())
        assert document["market"] == "sg"
        assert (
            document["experience"][0]["bullets"][0]["source"]
            == "acme-payments-rotation#partner-bank-onboarding-automation"
        )

    def test_the_yaml_is_the_full_ir(self, tmp_path: Path, store: ExperienceStore) -> None:
        artifacts = write_resume(tmp_path / "out", make_resume_content(), store)

        document = yaml.safe_load(artifacts.yaml_path.read_text())

        assert set(document) == set(ResumeContent.model_fields)

    def test_a_typo_in_a_hand_edited_yaml_is_an_error_not_a_silent_drop(
        self, tmp_path: Path, store: ExperienceStore
    ) -> None:
        artifacts = write_resume(tmp_path / "out", make_resume_content(), store)
        document = yaml.safe_load(artifacts.yaml_path.read_text())
        document["summry"] = document.pop("summary")
        artifacts.yaml_path.write_text(yaml.safe_dump(document, sort_keys=False))

        with pytest.raises(ValueError):
            load_resume_content(artifacts.directory)

    def test_a_missing_yaml_is_a_clear_error(self, tmp_path: Path) -> None:
        (tmp_path / "empty").mkdir()

        with pytest.raises(FileNotFoundError, match=YAML_FILENAME):
            load_resume_content(tmp_path / "empty")

    def test_an_invalid_ref_fails_before_any_artifact_is_written(
        self, tmp_path: Path, store: ExperienceStore
    ) -> None:
        content = make_resume_content(experience_source="acme-payments-rotation#invented-win")

        with pytest.raises(ProvenanceError):
            write_resume(tmp_path / "out", content, store)

        assert not (tmp_path / "out" / PDF_FILENAME).exists()
        assert not (tmp_path / "out" / YAML_FILENAME).exists()

    def test_a_second_run_overwrites_in_place(self, tmp_path: Path, store: ExperienceStore) -> None:
        first = write_resume(tmp_path / "out", make_resume_content(), store)
        edited = make_resume_content()
        edited.summary = "A different summary."

        second = write_resume(tmp_path / "out", edited, store)

        assert {path.name for path in (tmp_path / "out").iterdir()} == {
            YAML_FILENAME,
            PDF_FILENAME,
        }
        assert second.yaml_path == first.yaml_path
        assert load_resume_content(second.directory).summary == edited.summary
