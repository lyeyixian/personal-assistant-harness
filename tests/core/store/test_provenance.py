from pathlib import Path

import pytest

from assistant.core.store.loader import load_store
from assistant.core.store.models import ExperienceStore
from assistant.core.store.provenance import validate_provenance


@pytest.fixture
def store(fixture_vault_path: Path) -> ExperienceStore:
    return load_store(fixture_vault_path)


@pytest.mark.parametrize(
    ("ref", "expected_valid", "expected_reason"),
    [
        ("acme-payments-rotation#settlement-service-refactor", True, None),
        ("acme-payments-rotation#partner-bank-onboarding-automation", True, None),
        ("oss-contribution#accessible-date-picker-component", True, None),
        ("no-such-note#settlement-service-refactor", False, "unknown-note"),
        ("acme-payments-rotation#no-such-achievement", False, "unknown-heading"),
        ("acme-payments-rotationsettlement-service-refactor", False, "malformed-ref"),
    ],
)
def test_validate_provenance(
    store: ExperienceStore,
    ref: str,
    expected_valid: bool,
    expected_reason: str | None,
) -> None:
    result = validate_provenance(store, ref)

    assert result.ref == ref
    assert result.valid is expected_valid
    assert result.reason == expected_reason


def test_validate_provenance_rejects_a_ref_into_a_note_with_no_achievements(
    store: ExperienceStore,
) -> None:
    result = validate_provenance(store, "profile#education")

    assert result.valid is False
    assert result.reason == "unknown-heading"
