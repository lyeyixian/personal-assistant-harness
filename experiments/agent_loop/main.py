"""Runnable demo: one complete agent loop against the real Anthropic API.

    export ANTHROPIC_API_KEY=sk-ant-...
    uv run main.py [prompt]

Prints each round of wire traffic (model call, tool dispatch) so the
loop mechanics are visible. Model defaults to Haiku; override with
SPIKE_MODEL.
"""

import os
import sys

import httpx

from loop import CallModel, Json, Tool, run_loop

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("SPIKE_MODEL", "claude-haiku-4-5-20251001")

TOOLS = [
    Tool(
        name="add",
        description="Add two integers exactly.",
        input_schema={
            "type": "object",
            "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
            "required": ["a", "b"],
        },
        run=lambda args: str(args["a"] + args["b"]),
    ),
    Tool(
        name="reverse",
        description="Reverse a string exactly, character by character.",
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        run=lambda args: args["text"][::-1],
    ),
]

DEFAULT_PROMPT = (
    "Use the add tool to compute 20260718 + 1, then use the reverse tool "
    "on the word 'harness', and report both results in one sentence."
)


def anthropic_transport(api_key: str) -> CallModel:
    """Build a call_model closure that POSTs to the real Messages API."""
    client = httpx.Client(timeout=60)
    round_no = 0

    def call_model(messages: list[Json], tool_specs: list[Json]) -> Json:
        nonlocal round_no
        round_no += 1
        print(f"--- model call {round_no} ({len(messages)} messages) ---")
        response = client.post(
            API_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": MODEL,
                "max_tokens": 1024,
                "messages": messages,
                "tools": tool_specs,
            },
        )
        response.raise_for_status()
        body: Json = response.json()
        print(f"    stop_reason={body['stop_reason']}")
        for block in body["content"]:
            if block["type"] == "tool_use":
                print(f"    tool_use: {block['name']}({block['input']})")
        return body

    return call_model


def main() -> int:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY is not set", file=sys.stderr)
        return 1
    prompt = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PROMPT
    print(f"prompt: {prompt}\n")
    result = run_loop(anthropic_transport(api_key), TOOLS, prompt)
    print(f"\nfinal answer after {result.model_calls} model calls:\n{result.final_text}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
