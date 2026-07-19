"""Tests for the Gemini translation adapter.

Seam under test: the pure translation functions that map between the
loop's Anthropic wire shape and the Gemini generateContent REST shape.
The HTTP call itself stays untested, same as the Anthropic transport.
"""

from typing import Any

from gemini import from_gemini_response, to_gemini_request

Json = dict[str, Any]

ADD_SPEC: Json = {
    "name": "add",
    "description": "Add two integers.",
    "input_schema": {
        "type": "object",
        "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
        "required": ["a", "b"],
    },
}


def test_plain_user_message_and_tools_translate_to_gemini_shape() -> None:
    request = to_gemini_request(
        messages=[{"role": "user", "content": "What is 2 + 3?"}],
        tool_specs=[ADD_SPEC],
        id_to_name={},
    )

    assert request == {
        "contents": [{"role": "user", "parts": [{"text": "What is 2 + 3?"}]}],
        "tools": [
            {
                "functionDeclarations": [
                    {
                        "name": "add",
                        "description": "Add two integers.",
                        "parameters": ADD_SPEC["input_schema"],
                    }
                ]
            }
        ],
    }


def test_function_call_response_translates_to_tool_use() -> None:
    id_to_name: dict[str, str] = {}
    body: Json = {
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [{"functionCall": {"name": "add", "args": {"a": 2, "b": 3}}}],
                }
            }
        ]
    }

    response = from_gemini_response(body, id_to_name)

    assert response["stop_reason"] == "tool_use"
    (block,) = response["content"]
    assert block["type"] == "tool_use"
    assert block["name"] == "add"
    assert block["input"] == {"a": 2, "b": 3}
    # The generated id is recorded so the tool_result can be mapped back.
    assert id_to_name[block["id"]] == "add"


def test_text_response_translates_to_end_turn() -> None:
    body: Json = {
        "candidates": [
            {"content": {"role": "model", "parts": [{"text": "2 + 3 = 5"}]}}
        ]
    }

    response = from_gemini_response(body, {})

    assert response == {
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": "2 + 3 = 5"}],
    }


def test_tool_use_and_tool_result_history_translates_back() -> None:
    id_to_name = {"gemini_call_1": "add"}
    request = to_gemini_request(
        messages=[
            {"role": "user", "content": "What is 2 + 3?"},
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "gemini_call_1", "name": "add", "input": {"a": 2, "b": 3}}
                ],
            },
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "gemini_call_1", "content": "5"}
                ],
            },
        ],
        tool_specs=[ADD_SPEC],
        id_to_name=id_to_name,
    )

    assert request["contents"][1] == {
        "role": "model",
        "parts": [{"functionCall": {"name": "add", "args": {"a": 2, "b": 3}}}],
    }
    assert request["contents"][2] == {
        "role": "user",
        "parts": [{"functionResponse": {"name": "add", "response": {"result": "5"}}}],
    }
