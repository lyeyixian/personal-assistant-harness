"""The store's read path must be reachable through `assistant.core` alone -
per ADR-0002, modules never import `assistant.core.store` directly.
"""

from pathlib import Path

from assistant.core import ExperienceStore, load_store, validate_provenance


def test_store_read_path_is_reachable_through_the_core_facade(fixture_vault_path: Path) -> None:
    store = load_store(fixture_vault_path)

    assert isinstance(store, ExperienceStore)
    result = validate_provenance(store, "acme-payments-rotation#settlement-service-refactor")
    assert result.valid is True
