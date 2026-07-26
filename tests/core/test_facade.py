"""The store's read path and the Fold must be reachable through
`assistant.core` alone - per ADR-0002, modules never import
`assistant.core.store`/`assistant.core.journal` directly.
"""

from collections.abc import Callable
from pathlib import Path

from assistant.core import (
    ExperienceStore,
    FoldResult,
    Settings,
    load_store,
    run_fold,
    validate_provenance,
)


def test_store_read_path_is_reachable_through_the_core_facade(fixture_vault_path: Path) -> None:
    store = load_store(fixture_vault_path)

    assert isinstance(store, ExperienceStore)
    result = validate_provenance(store, "acme-payments-rotation#settlement-service-refactor")
    assert result.valid is True


def test_fold_is_reachable_through_the_core_facade(
    tmp_path: Path, make_settings: Callable[..., Settings]
) -> None:
    settings = make_settings(vault_path=tmp_path)

    result = run_fold(tmp_path, settings)

    assert isinstance(result, FoldResult)
    assert result.files == ()
