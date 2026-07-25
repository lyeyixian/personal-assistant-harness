from collections.abc import Callable

import pytest
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.models.test import TestModel

from assistant.core.agents import create_agent, usage_limits
from assistant.core.config import Settings


class Greeting(BaseModel):
    text: str


def _model_of(agent: Agent[None, Greeting]) -> Model:
    model = agent.model
    assert isinstance(model, Model)
    return model


async def test_create_agent_produces_a_working_agent(
    make_settings: Callable[..., Settings],
) -> None:
    settings = make_settings(default_model="test")

    agent = create_agent(Greeting, deps_type=type(None), settings=settings)
    result = await agent.run("hello")

    assert isinstance(result.output, Greeting)
    assert isinstance(_model_of(agent), TestModel)


def test_switching_model_is_config_only(
    make_settings: Callable[..., Settings], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy-anthropic-key")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-openai-key")

    anthropic_settings = make_settings(default_model="anthropic:claude-sonnet-5")
    openai_settings = make_settings(default_model="openai:gpt-5")
    anthropic_agent = create_agent(Greeting, deps_type=type(None), settings=anthropic_settings)
    openai_agent = create_agent(Greeting, deps_type=type(None), settings=openai_settings)

    assert _model_of(anthropic_agent).system == "anthropic"
    assert _model_of(openai_agent).system == "openai"
    assert _model_of(anthropic_agent).model_name != _model_of(openai_agent).model_name


def test_secret_only_read_from_env_reaches_the_provider(
    make_settings: Callable[..., Settings], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy-anthropic-key")
    settings = make_settings(default_model="anthropic:claude-sonnet-5")

    agent = create_agent(Greeting, deps_type=type(None), settings=settings)

    assert _model_of(agent).system == "anthropic"


def test_retries_come_from_settings(make_settings: Callable[..., Settings]) -> None:
    settings = make_settings(default_model="test", agent_retries=7)

    agent = create_agent(Greeting, deps_type=type(None), settings=settings)

    # No public accessor for the configured retry budget; this is the SDK's own attribute.
    assert agent._max_output_retries == 7  # pyright: ignore[reportPrivateUsage]
    assert agent._max_tool_retries == 7  # pyright: ignore[reportPrivateUsage]


def test_usage_limits_come_from_settings(make_settings: Callable[..., Settings]) -> None:
    settings = make_settings(usage_request_limit=5, usage_total_tokens_limit=1000)

    limits = usage_limits(settings)

    assert limits.request_limit == 5
    assert limits.total_tokens_limit == 1000
