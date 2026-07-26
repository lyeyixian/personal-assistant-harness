from pathlib import Path

from assistant.core.store.loader import load_store


def test_load_store_returns_every_curated_note(fixture_vault_path: Path) -> None:
    store = load_store(fixture_vault_path)

    slugs = {note.slug for note in store.notes}
    assert slugs == {
        "profile",
        "direction",
        "skills",
        "acme-payments-rotation",
        "acme-platform-team",
        "oss-contribution",
        "prod-migration-rollback",
    }


def test_load_store_excludes_journal_and_jobs(fixture_vault_path: Path) -> None:
    store = load_store(fixture_vault_path)

    slugs = {note.slug for note in store.notes}
    assert "2026-07-17" not in slugs
    assert "anthropic-ai-engineer" not in slugs
    for note in store.notes:
        assert "SENTINEL-JOURNAL-CONTENT" not in note.body
        assert "SENTINEL-JOBS-CONTENT" not in note.body


def test_load_store_assigns_note_types_from_vault_location(fixture_vault_path: Path) -> None:
    store = load_store(fixture_vault_path)

    types_by_slug = {note.slug: note.type for note in store.notes}
    assert types_by_slug["profile"] == "profile"
    assert types_by_slug["direction"] == "direction"
    assert types_by_slug["skills"] == "skills"
    assert types_by_slug["acme-payments-rotation"] == "role"
    assert types_by_slug["oss-contribution"] == "project"
    assert types_by_slug["prod-migration-rollback"] == "story"


def test_load_store_parses_role_note_frontmatter_and_achievements(
    fixture_vault_path: Path,
) -> None:
    store = load_store(fixture_vault_path)

    role = store.note("acme-payments-rotation")

    assert role is not None
    assert role.frontmatter["company"] == "Acme Corp"
    assert role.frontmatter["skills"] == [
        "csharp",
        "dotnet-core",
        "postgresql",
        "testcontainers",
        "ci-cd",
    ]
    assert [a.slug for a in role.achievements] == [
        "settlement-service-refactor",
        "partner-bank-onboarding-automation",
    ]


def test_load_store_handles_notes_without_frontmatter(fixture_vault_path: Path) -> None:
    store = load_store(fixture_vault_path)

    profile = store.note("profile")

    assert profile is not None
    assert profile.frontmatter == {}
    assert "Jamie Rivera" in profile.body


def test_experience_store_note_lookup_returns_none_for_unknown_slug(
    fixture_vault_path: Path,
) -> None:
    store = load_store(fixture_vault_path)

    assert store.note("does-not-exist") is None
