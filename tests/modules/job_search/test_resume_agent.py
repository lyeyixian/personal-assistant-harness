"""The resume-content agent, exercised offline against the fixture vault."""

from pathlib import Path

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

from assistant.core import ExperienceStore, Settings
from assistant.modules.job_search.agents import (
    ResumeDeps,
    build_task_prompt,
    create_resume_agent,
    generate_resume_content,
    render_corpus,
)
from tests.modules.job_search._helpers import POSTING, make_resume_content


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Offline settings: the `test` model, never a real provider."""
    return Settings(vault_path=tmp_path / "vault", default_model="test")


class TestCorpusPrompt:
    def test_carries_the_curated_notes_and_their_achievement_headings(
        self, store: ExperienceStore
    ) -> None:
        corpus = render_corpus(store)

        assert "acme-payments-rotation" in corpus
        assert "Partner-bank onboarding automation" in corpus

    def test_carries_metric_qualifiers_intact(self, store: ExperienceStore) -> None:
        corpus = render_corpus(store)

        assert "~500 txns/month automated (projection," in corpus

    def test_carries_the_ref_a_bullet_must_cite(self, store: ExperienceStore) -> None:
        corpus = render_corpus(store)

        assert "acme-payments-rotation#partner-bank-onboarding-automation" in corpus

    def test_carries_the_programme_frontmatter_stints_regroup_by(
        self, store: ExperienceStore
    ) -> None:
        corpus = render_corpus(store)

        assert "programme: acme-grad" in corpus

    def test_excludes_the_journal_and_captured_postings(self, store: ExperienceStore) -> None:
        corpus = render_corpus(store)

        assert "praised by the BA" not in corpus
        assert "5+ years of Python" not in corpus


class TestTaskPrompt:
    def test_carries_the_posting_and_its_market(self, store: ExperienceStore) -> None:
        prompt = build_task_prompt(ResumeDeps(store=store, posting=POSTING))

        assert "AI Engineer" in prompt
        assert "Anthropic" in prompt
        assert "sg" in prompt
        assert "5+ years of Python" in prompt


class TestGenerateResumeContent:
    def test_returns_the_agents_typed_content(
        self, store: ExperienceStore, settings: Settings
    ) -> None:
        expected = make_resume_content()
        agent = create_resume_agent(settings)

        with agent.override(model=TestModel(custom_output_args=expected.model_dump())):
            content = generate_resume_content(
                agent, store=store, posting=POSTING, settings=settings
            )

        assert content == expected

    def test_the_postings_market_wins_over_the_models(
        self, store: ExperienceStore, settings: Settings
    ) -> None:
        remote_posting = POSTING.model_copy(update={"market": "remote"})
        agent = create_resume_agent(settings)

        with agent.override(model=TestModel(custom_output_args=make_resume_content().model_dump())):
            content = generate_resume_content(
                agent, store=store, posting=remote_posting, settings=settings
            )

        assert content.market == "remote"

    def test_the_agent_must_fix_a_bullet_whose_ref_does_not_resolve(
        self, store: ExperienceStore, settings: Settings
    ) -> None:
        invented = make_resume_content(experience_source="acme-payments-rotation#invented-win")
        corrected = make_resume_content()
        attempts: list[dict[str, object]] = [invented.model_dump(), corrected.model_dump()]

        def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            assert info.output_tools
            return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, attempts.pop(0))])

        agent = create_resume_agent(settings)
        with agent.override(model=FunctionModel(respond)):
            content = generate_resume_content(
                agent, store=store, posting=POSTING, settings=settings
            )

        assert attempts == []
        assert content == corrected

    def test_the_retry_prompt_names_the_unresolvable_ref(
        self, store: ExperienceStore, settings: Settings
    ) -> None:
        invented = make_resume_content(experience_source="acme-payments-rotation#invented-win")
        corrected = make_resume_content()
        attempts: list[dict[str, object]] = [invented.model_dump(), corrected.model_dump()]
        seen: list[str] = []

        def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            assert info.output_tools
            seen.extend(str(part) for message in messages for part in message.parts)
            return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, attempts.pop(0))])

        agent = create_resume_agent(settings)
        with agent.override(model=FunctionModel(respond)):
            generate_resume_content(agent, store=store, posting=POSTING, settings=settings)

        assert any("acme-payments-rotation#invented-win" in text for text in seen)
