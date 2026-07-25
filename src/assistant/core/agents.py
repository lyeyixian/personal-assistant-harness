"""The core agent factory, per ADR-0002.

Core provides the factory, not the agents: model, retries, and usage limits
all come from `Settings`, so provider/model choice stays pure runtime config -
never a code change. Modules call `create_agent` once per task to get a
focused, typed-output agent.
"""

from pydantic_ai import Agent
from pydantic_ai.usage import UsageLimits

from assistant.core.config import Settings, export_secrets_to_environ


def create_agent[DepsT, OutputT](
    output_type: type[OutputT],
    *,
    deps_type: type[DepsT],
    settings: Settings,
    system_prompt: str = "",
) -> Agent[DepsT, OutputT]:
    """Build a task agent configured from `settings` (model, retries)."""
    export_secrets_to_environ(settings)
    return Agent(
        settings.default_model,
        output_type=output_type,
        deps_type=deps_type,
        system_prompt=system_prompt,
        retries=settings.agent_retries,
    )


def usage_limits(settings: Settings) -> UsageLimits:
    """The `UsageLimits` a caller should pass to `agent.run(usage_limits=...)`."""
    return UsageLimits(
        request_limit=settings.usage_request_limit,
        total_tokens_limit=settings.usage_total_tokens_limit,
    )
