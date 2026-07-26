"""The Fold pipeline: fixture-vault + `TestModel`/`FunctionModel` tests, per
the primary testing seam - a pipeline function called with an injected store
and agent, asserting on written artifacts rather than internals."""

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelResponse
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

from assistant.core.config import Settings
from assistant.core.journal.capture import add_entry
from assistant.core.journal.fold import FoldDeps, run_fold
from assistant.core.journal.fold_types import FoldPlan


def _agent_returning(custom_output_args: dict[str, Any]) -> Agent[FoldDeps, FoldPlan]:
    model = TestModel(custom_output_args=custom_output_args)
    return Agent(model, output_type=FoldPlan, deps_type=FoldDeps)


def _raising_agent() -> Agent[FoldDeps, FoldPlan]:
    def _fail(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        raise AssertionError("the fold agent must not be called when nothing is pending")

    return Agent(FunctionModel(_fail), output_type=FoldPlan, deps_type=FoldDeps)


def test_run_fold_is_a_no_op_when_nothing_is_pending(
    fold_vault: Path, make_settings: Callable[..., Settings]
) -> None:
    settings = make_settings(vault_path=fold_vault)

    result = run_fold(fold_vault, settings, agent=_raising_agent())

    assert result.files == ()
    assert result.entry_count == 0


def test_run_fold_creates_a_new_achievement_for_the_current_role(
    fold_vault: Path, make_settings: Callable[..., Settings]
) -> None:
    add_entry(
        fold_vault,
        "built retry handling for the reporting queue consumer",
        now=datetime(2026, 7, 26, 9, 0),
    )
    settings = make_settings(vault_path=fold_vault)
    agent = _agent_returning(
        {
            "entries": [
                {
                    "source_index": 0,
                    "kind": "achievement",
                    "operation": "new",
                    "heading": "Retry-safe queue consumer",
                    "body": "Added retry handling to the reporting queue consumer.",
                    "impact": "fewer dropped messages during transient outages",
                    "skills": ["kafka"],
                    "new_skill_category": "Infra",
                }
            ]
        }
    )

    result = run_fold(fold_vault, settings, agent=agent)

    assert result.achievements_created == 1
    assert result.skills_registered == 1

    role_text = (fold_vault / "roles" / "acme-platform-team.md").read_text()
    assert "### Retry-safe queue consumer" in role_text
    assert "Added retry handling to the reporting queue consumer." in role_text
    assert "**Impact:** fewer dropped messages during transient outages" in role_text
    assert "skills: [python, pydantic-ai, docker, kafka]" in role_text

    skills_text = (fold_vault / "skills.md").read_text()
    assert "- kafka" in skills_text

    journal_text = (fold_vault / "journal" / "2026-07-26.md").read_text()
    assert "folded: true" in journal_text
    assert "→ [[acme-platform-team]]" in journal_text


def test_run_fold_respects_a_wikilink_hint_over_the_current_role(
    fold_vault: Path, make_settings: Callable[..., Settings]
) -> None:
    add_entry(
        fold_vault,
        "closed out a reconciliation follow-up [[acme-payments-rotation]]",
        now=datetime(2026, 7, 26, 9, 0),
    )
    settings = make_settings(vault_path=fold_vault)
    agent = _agent_returning(
        {
            "entries": [
                {
                    "source_index": 0,
                    "kind": "achievement",
                    "operation": "new",
                    "heading": "Reconciliation follow-up",
                    "body": "Closed out a follow-up item from the partner-bank reconciliation job.",
                }
            ]
        }
    )

    run_fold(fold_vault, settings, agent=agent)

    payments_text = (fold_vault / "roles" / "acme-payments-rotation.md").read_text()
    assert "### Reconciliation follow-up" in payments_text
    platform_text = (fold_vault / "roles" / "acme-platform-team.md").read_text()
    assert "Reconciliation follow-up" not in platform_text

    journal_text = (fold_vault / "journal" / "2026-07-26.md").read_text()
    assert "→ [[acme-payments-rotation]]" in journal_text


def test_run_fold_updates_an_existing_achievement_and_keeps_its_original_heading(
    fold_vault: Path, make_settings: Callable[..., Settings]
) -> None:
    add_entry(
        fold_vault,
        "shipped phase 2 of the settlement refactor [[acme-payments-rotation]]",
        now=datetime(2026, 7, 26, 9, 0),
    )
    settings = make_settings(vault_path=fold_vault)
    agent = _agent_returning(
        {
            "entries": [
                {
                    "source_index": 0,
                    "kind": "achievement",
                    "operation": "update",
                    "existing_heading_slug": "settlement-service-refactor",
                    "heading": "a heading the agent proposed but that must be ignored",
                    "body": (
                        "Collapsed several internal microservices, then extended the "
                        "refactor with a phase 2 covering the ledger service."
                    ),
                    "impact": "the ledger service now shares the same integration-test pattern",
                }
            ]
        }
    )

    result = run_fold(fold_vault, settings, agent=agent)

    assert result.achievements_updated == 1
    assert result.achievements_created == 0
    text = (fold_vault / "roles" / "acme-payments-rotation.md").read_text()
    assert "### Settlement-service refactor" in text
    assert "a heading the agent proposed but that must be ignored" not in text
    assert "phase 2 covering the ledger service" in text
    assert "**Impact:** the ledger service now shares the same integration-test pattern" in text
    # the other achievement in the same note must survive untouched
    assert "### Partner-bank onboarding automation" in text
    assert "## Reflections" in text


def test_run_fold_creates_a_story_note(
    fold_vault: Path, make_settings: Callable[..., Settings]
) -> None:
    add_entry(
        fold_vault,
        "praised by the BA for vetting a story in review - good interview material",
        now=datetime(2026, 7, 26, 9, 0),
    )
    settings = make_settings(vault_path=fold_vault)
    agent = _agent_returning(
        {
            "entries": [
                {
                    "source_index": 0,
                    "kind": "story",
                    "heading": "Story vetting praise",
                    "body": (
                        "During a review, a BA praised how I pressure-tested a proposed "
                        "story before it reached engineering."
                    ),
                    "competencies": ["communication", "ownership"],
                }
            ]
        }
    )

    result = run_fold(fold_vault, settings, agent=agent)

    assert result.stories_created == 1
    story_path = fold_vault / "stories" / "story-vetting-praise.md"
    assert story_path.exists()
    text = story_path.read_text()
    assert "type: story" in text
    assert "competencies: [communication, ownership]" in text
    assert "roles: [acme-platform-team]" in text
    assert "pressure-tested a proposed" in text

    journal_text = (fold_vault / "journal" / "2026-07-26.md").read_text()
    assert "→ [[story-vetting-praise]]" in journal_text


def test_run_fold_adds_a_known_skill_to_frontmatter_without_duplicating_the_registry(
    fold_vault: Path, make_settings: Callable[..., Settings]
) -> None:
    add_entry(
        fold_vault,
        "used docker for local testing [[acme-payments-rotation]]",
        now=datetime(2026, 7, 26, 9, 0),
    )
    settings = make_settings(vault_path=fold_vault)
    agent = _agent_returning(
        {
            "entries": [
                {
                    "source_index": 0,
                    "kind": "achievement",
                    "operation": "new",
                    "heading": "Local docker testing",
                    "body": "Ran the service locally under Docker for faster iteration.",
                    "skills": ["docker"],
                }
            ]
        }
    )

    result = run_fold(fold_vault, settings, agent=agent)

    assert result.skills_registered == 0
    payments_text = (fold_vault / "roles" / "acme-payments-rotation.md").read_text()
    assert (
        "skills: [csharp, dotnet-core, postgresql, testcontainers, ci-cd, docker]" in payments_text
    )
    skills_md = (fold_vault / "skills.md").read_text()
    assert skills_md.count("- docker") == 1


def test_run_fold_is_idempotent(fold_vault: Path, make_settings: Callable[..., Settings]) -> None:
    add_entry(fold_vault, "shipped a small fix", now=datetime(2026, 7, 26, 9, 0))
    settings = make_settings(vault_path=fold_vault)
    agent = _agent_returning(
        {
            "entries": [
                {
                    "source_index": 0,
                    "kind": "achievement",
                    "operation": "new",
                    "heading": "Small fix",
                    "body": "Fixed a small bug.",
                }
            ]
        }
    )

    first = run_fold(fold_vault, settings, agent=agent)
    snapshot = {path: path.read_text() for path in fold_vault.rglob("*.md")}

    second = run_fold(fold_vault, settings, agent=_raising_agent())

    assert first.entry_count == 1
    assert second.files == ()
    assert {path: path.read_text() for path in fold_vault.rglob("*.md")} == snapshot


def test_run_fold_raises_if_the_plan_omits_an_entry(
    fold_vault: Path, make_settings: Callable[..., Settings]
) -> None:
    add_entry(fold_vault, "first", now=datetime(2026, 7, 26, 9, 0))
    add_entry(fold_vault, "second", now=datetime(2026, 7, 27, 9, 0))
    settings = make_settings(vault_path=fold_vault)
    agent = _agent_returning(
        {
            "entries": [
                {
                    "source_index": 0,
                    "kind": "achievement",
                    "operation": "new",
                    "heading": "First",
                    "body": "The first entry.",
                }
            ]
        }
    )

    with pytest.raises(ValueError, match="missing"):
        run_fold(fold_vault, settings, agent=agent)


def test_run_fold_builds_its_own_agent_from_settings_when_none_is_given(
    fold_vault: Path, make_settings: Callable[..., Settings]
) -> None:
    add_entry(fold_vault, "did something small", now=datetime(2026, 7, 26, 9, 0))
    settings = make_settings(vault_path=fold_vault, default_model="test")

    result = run_fold(fold_vault, settings)

    assert result.entry_count == 1
    assert result.achievements_created == 1
