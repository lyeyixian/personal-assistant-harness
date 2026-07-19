"""Gemini transport: adapts the Gemini REST API to the loop's Anthropic shape.

The loop speaks the Anthropic Messages wire shape (tool_use / tool_result
blocks, stop_reason). This module translates that to and from Gemini's
generateContent shape (functionCall / functionResponse parts) — the same
provider-normalization work an SDK like Pydantic AI does behind one
call site.

Gemini function calls carry no id, so the transport mints its own
(gemini_call_N) and keeps an id → function-name map to translate
tool_result blocks back into named functionResponse parts.
"""

from typing import Any

import httpx

from loop import CallModel, Json

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"


def available_models(client: httpx.Client, api_key: str) -> list[str]:
    """List model ids this API key can call generateContent on."""
    response = client.get(
        MODELS_URL, params={"pageSize": 1000}, headers={"x-goog-api-key": api_key}
    )
    response.raise_for_status()
    models: list[Json] = response.json().get("models", [])
    return [
        m["name"].removeprefix("models/")
        for m in models
        if "generateContent" in m.get("supportedGenerationMethods", [])
    ]


def to_gemini_request(
    messages: list[Json], tool_specs: list[Json], id_to_name: dict[str, str]
) -> Json:
    contents: list[Json] = []
    for message in messages:
        role = "model" if message["role"] == "assistant" else "user"
        content: str | list[Json] = message["content"]
        parts: list[Json] = []
        if isinstance(content, str):
            parts.append({"text": content})
        else:
            for block in content:
                if block["type"] == "text":
                    parts.append({"text": block["text"]})
                elif block["type"] == "tool_use":
                    parts.append(
                        {"functionCall": {"name": block["name"], "args": block["input"]}}
                    )
                elif block["type"] == "tool_result":
                    name = id_to_name[block["tool_use_id"]]
                    parts.append(
                        {
                            "functionResponse": {
                                "name": name,
                                "response": {"result": block["content"]},
                            }
                        }
                    )
        contents.append({"role": role, "parts": parts})

    request: Json = {"contents": contents}
    if tool_specs:
        request["tools"] = [
            {
                "functionDeclarations": [
                    {
                        "name": spec["name"],
                        "description": spec["description"],
                        "parameters": spec["input_schema"],
                    }
                    for spec in tool_specs
                ]
            }
        ]
    return request


def from_gemini_response(body: Json, id_to_name: dict[str, str]) -> Json:
    parts: list[Json] = body["candidates"][0]["content"]["parts"]
    blocks: list[Json] = []
    has_call = False
    for part in parts:
        if "functionCall" in part:
            has_call = True
            call_id = f"gemini_call_{len(id_to_name) + 1}"
            call: Json = part["functionCall"]
            id_to_name[call_id] = call["name"]
            blocks.append(
                {
                    "type": "tool_use",
                    "id": call_id,
                    "name": call["name"],
                    "input": call.get("args", {}),
                }
            )
        elif "text" in part:
            blocks.append({"type": "text", "text": part["text"]})
    return {
        "stop_reason": "tool_use" if has_call else "end_turn",
        "content": blocks,
    }


def gemini_transport(api_key: str, model: str) -> CallModel:
    """Build a call_model closure that POSTs to the Gemini generateContent API."""
    client = httpx.Client(timeout=60)
    id_to_name: dict[str, str] = {}
    round_no = 0

    def call_model(messages: list[Json], tool_specs: list[Json]) -> Json:
        nonlocal round_no
        round_no += 1
        print(f"--- model call {round_no} ({len(messages)} messages) ---")
        response = client.post(
            API_URL.format(model=model),
            headers={"x-goog-api-key": api_key, "content-type": "application/json"},
            json=to_gemini_request(messages, tool_specs, id_to_name),
        )
        if response.status_code == 404:
            names = "\n  ".join(available_models(client, api_key))
            raise SystemExit(
                f"Model '{model}' not found for this API key.\n"
                f"Models your key can use:\n  {names}\n"
                f"Re-run with: SPIKE_MODEL=<model-id> uv run main.py"
            )
        response.raise_for_status()
        raw: dict[str, Any] = response.json()
        translated = from_gemini_response(raw, id_to_name)
        print(f"    stop_reason={translated['stop_reason']}")
        for block in translated["content"]:
            if block["type"] == "tool_use":
                print(f"    tool_use: {block['name']}({block['input']})")
        return translated

    return call_model
