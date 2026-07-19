"""Tests for the spike agent loop.

Seam under test: `run_loop`, the loop's single public entry point. The
provider transport is injected as a callable, so these tests script it
with canned Anthropic-Messages-API-shaped responses — no network, no
mocking of loop internals.
"""

from typing import Any

import pytest

from loop import LoopLimitExceeded, Tool, run_loop

Json = dict[str, Any]


def scripted_model(*responses: Json):
    """A fake transport that replays canned API responses in order.

    Records every (messages, tool_specs) call so tests can assert on
    what the loop actually sent to the provider.
    """

    calls: list[Json] = []

    def call_model(messages: list[Json], tool_specs: list[Json]) -> Json:
        calls.append({"messages": [dict(m) for m in messages], "tool_specs": tool_specs})
        return responses[len(calls) - 1]

    call_model.calls = calls  # type: ignore[attr-defined]
    return call_model


def text_response(text: str) -> Json:
    return {
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": text}],
    }


def tool_use_response(tool_use_id: str, name: str, tool_input: Json) -> Json:
    return {
        "stop_reason": "tool_use",
        "content": [
            {"type": "tool_use", "id": tool_use_id, "name": name, "input": tool_input}
        ],
    }


ADD_TOOL = Tool(
    name="add",
    description="Add two integers.",
    input_schema={
        "type": "object",
        "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
        "required": ["a", "b"],
    },
    run=lambda args: str(args["a"] + args["b"]),
)


def test_model_answering_directly_returns_its_text() -> None:
    model = scripted_model(text_response("Paris is the capital of France."))

    result = run_loop(model, tools=[], prompt="What is the capital of France?")

    assert result.final_text == "Paris is the capital of France."
    assert result.model_calls == 1
    # The one and only request carried the user prompt and no tools.
    assert model.calls[0]["messages"] == [
        {"role": "user", "content": "What is the capital of France?"}
    ]
    assert model.calls[0]["tool_specs"] == []


def test_tool_call_is_dispatched_and_result_fed_back() -> None:
    model = scripted_model(
        tool_use_response("toolu_01", "add", {"a": 2, "b": 3}),
        text_response("2 + 3 = 5"),
    )

    result = run_loop(model, tools=[ADD_TOOL], prompt="What is 2 + 3?")

    assert result.final_text == "2 + 3 = 5"
    assert result.model_calls == 2
    # The tool's JSON spec was advertised to the model.
    assert model.calls[0]["tool_specs"] == [
        {
            "name": "add",
            "description": "Add two integers.",
            "input_schema": ADD_TOOL.input_schema,
        }
    ]
    # The second request carried the assistant's tool_use turn followed by
    # our tool_result, correlated by id.
    assert model.calls[1]["messages"][1] == {
        "role": "assistant",
        "content": [
            {"type": "tool_use", "id": "toolu_01", "name": "add", "input": {"a": 2, "b": 3}}
        ],
    }
    assert model.calls[1]["messages"][2] == {
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": "toolu_01", "content": "5"}
        ],
    }


def test_chained_tool_calls_loop_until_done() -> None:
    model = scripted_model(
        tool_use_response("toolu_01", "add", {"a": 1, "b": 2}),
        tool_use_response("toolu_02", "add", {"a": 3, "b": 4}),
        text_response("The answers are 3 and 7."),
    )

    result = run_loop(model, tools=[ADD_TOOL], prompt="Add 1+2, then 3+4.")

    assert result.final_text == "The answers are 3 and 7."
    assert result.model_calls == 3
    # Third request has the full alternating history: user, assistant,
    # tool_result, assistant, tool_result.
    roles = [m["role"] for m in model.calls[2]["messages"]]
    assert roles == ["user", "assistant", "user", "assistant", "user"]
    assert model.calls[2]["messages"][4] == {
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": "toolu_02", "content": "7"}
        ],
    }


def test_unknown_tool_returns_error_result_and_loop_survives() -> None:
    model = scripted_model(
        tool_use_response("toolu_01", "subtract", {"a": 5, "b": 2}),
        text_response("I don't have a subtract tool."),
    )

    result = run_loop(model, tools=[ADD_TOOL], prompt="What is 5 - 2?")

    assert result.final_text == "I don't have a subtract tool."
    assert model.calls[1]["messages"][2] == {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": "toolu_01",
                "content": "Unknown tool: subtract",
                "is_error": True,
            }
        ],
    }


def test_loop_stops_at_max_iterations() -> None:
    model = scripted_model(
        tool_use_response("toolu_01", "add", {"a": 1, "b": 1}),
        tool_use_response("toolu_02", "add", {"a": 2, "b": 2}),
        tool_use_response("toolu_03", "add", {"a": 3, "b": 3}),
    )

    with pytest.raises(LoopLimitExceeded):
        run_loop(model, tools=[ADD_TOOL], prompt="Add forever.", max_iterations=3)

    assert len(model.calls) == 3
