"""From-scratch agent loop against the raw Anthropic Messages API shape.

Spike for issue #18 — never imported by the harness.

The provider transport is injected as `call_model(messages, tool_specs)`
returning a Messages-API response body, so the loop itself is pure:
it only builds the messages list and dispatches tool calls.
"""

from dataclasses import dataclass
from typing import Any, Callable

Json = dict[str, Any]

CallModel = Callable[[list[Json], list[Json]], Json]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: Json
    run: Callable[[Json], str]

    def spec(self) -> Json:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


@dataclass
class RunResult:
    final_text: str
    messages: list[Json]
    model_calls: int


class LoopLimitExceeded(RuntimeError):
    """The model was still requesting tools after max_iterations rounds."""


def run_loop(
    call_model: CallModel,
    tools: list[Tool],
    prompt: str,
    max_iterations: int = 10,
) -> RunResult:
    tool_specs = [tool.spec() for tool in tools]
    by_name = {tool.name: tool for tool in tools}
    messages: list[Json] = [{"role": "user", "content": prompt}]
    model_calls = 0

    while model_calls < max_iterations:
        response = call_model(messages, tool_specs)
        model_calls += 1
        messages.append({"role": "assistant", "content": response["content"]})

        if response["stop_reason"] != "tool_use":
            text = "".join(
                block["text"] for block in response["content"] if block["type"] == "text"
            )
            return RunResult(final_text=text, messages=messages, model_calls=model_calls)

        results: list[Json] = []
        for block in response["content"]:
            if block["type"] != "tool_use":
                continue
            tool = by_name.get(block["name"])
            result: Json = {"type": "tool_result", "tool_use_id": block["id"]}
            if tool is None:
                result["content"] = f"Unknown tool: {block['name']}"
                result["is_error"] = True
            else:
                result["content"] = tool.run(block["input"])
            results.append(result)
        messages.append({"role": "user", "content": results})

    raise LoopLimitExceeded(f"No final answer after {max_iterations} model calls")
