from pathlib import Path

import pytest
import yaml

from assistant.core import ExperienceStore
from assistant.modules.render.pipeline import (
    PDF_FILENAME,
    YAML_FILENAME,
    ProvenanceError,
    ShapeError,
    load_resume_content,
    render,
    unresolved_refs,
    validate_resume_provenance,
)
from tests.modules.render._helpers import make_resume_content, write_resume_yaml


class TestShapeGate:
    def test_a_valid_yaml_round_trips_into_the_ir(self, tmp_path: Path) -> None:
        content = make_resume_content()
        write_resume_yaml(tmp_path, content)

        assert load_resume_content(tmp_path) == content

    def test_a_missing_yaml_is_a_clear_error(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match=YAML_FILENAME):
            load_resume_content(tmp_path)

    def test_malformed_yaml_syntax_fails_legibly_not_as_a_traceback(self, tmp_path: Path) -> None:
        (tmp_path / YAML_FILENAME).write_text("market: [unclosed\n")

        with pytest.raises(ShapeError):
            load_resume_content(tmp_path)

    def test_a_missing_required_field_names_it(self, tmp_path: Path) -> None:
        write_resume_yaml(tmp_path, {"market": "sg"})

        with pytest.raises(ShapeError) as exc_info:
            load_resume_content(tmp_path)

        assert "header" in str(exc_info.value)
        assert "summary" in str(exc_info.value)

    def test_an_unknown_field_is_an_error_not_a_silent_drop(self, tmp_path: Path) -> None:
        document = make_resume_content().model_dump()
        document["summry"] = document.pop("summary")
        write_resume_yaml(tmp_path, document)

        with pytest.raises(ShapeError) as exc_info:
            load_resume_content(tmp_path)

        assert "summry" in str(exc_info.value)


class TestProvenanceGate:
    def test_content_whose_refs_all_resolve_passes(self, store: ExperienceStore) -> None:
        validate_resume_provenance(store, make_resume_content())

    def test_a_malformed_ref_is_reported_as_such(self, store: ExperienceStore) -> None:
        content = make_resume_content(project_source="malformed-ref-without-a-heading")

        failures = unresolved_refs(store, content)

        assert [failure.reason for failure in failures] == ["malformed-ref"]

    def test_an_unknown_note_is_reported_as_such(self, store: ExperienceStore) -> None:
        content = make_resume_content(project_source="no-such-note#some-heading")

        failures = unresolved_refs(store, content)

        assert [failure.reason for failure in failures] == ["unknown-note"]

    def test_an_unknown_heading_is_reported_as_such(self, store: ExperienceStore) -> None:
        content = make_resume_content(experience_source="acme-payments-rotation#invented-win")

        failures = unresolved_refs(store, content)

        assert [failure.reason for failure in failures] == ["unknown-heading"]

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


class TestRender:
    def test_writes_the_pdf_beside_the_yaml(self, tmp_path: Path, fixture_vault_path: Path) -> None:
        write_resume_yaml(tmp_path, make_resume_content())

        pdf_path = render(tmp_path, fixture_vault_path)

        assert pdf_path == tmp_path / PDF_FILENAME
        assert pdf_path.read_bytes().startswith(b"%PDF")

    def test_a_shape_gate_failure_leaves_no_pdf(
        self, tmp_path: Path, fixture_vault_path: Path
    ) -> None:
        write_resume_yaml(tmp_path, {"market": "sg"})

        with pytest.raises(ShapeError):
            render(tmp_path, fixture_vault_path)

        assert not (tmp_path / PDF_FILENAME).exists()

    def test_a_provenance_gate_failure_leaves_no_pdf(
        self, tmp_path: Path, fixture_vault_path: Path
    ) -> None:
        write_resume_yaml(
            tmp_path,
            make_resume_content(experience_source="acme-payments-rotation#invented-win"),
        )

        with pytest.raises(ProvenanceError):
            render(tmp_path, fixture_vault_path)

        assert not (tmp_path / PDF_FILENAME).exists()

    def test_rerendering_a_hand_edited_yaml_reruns_both_gates(
        self, tmp_path: Path, fixture_vault_path: Path
    ) -> None:
        write_resume_yaml(tmp_path, make_resume_content())
        render(tmp_path, fixture_vault_path)

        document = yaml.safe_load((tmp_path / YAML_FILENAME).read_text())
        document["experience"][0]["bullets"][0]["source"] = "acme-payments-rotation#invented-win"
        write_resume_yaml(tmp_path, document)

        with pytest.raises(ProvenanceError):
            render(tmp_path, fixture_vault_path)
