# Spike write-up: a from-scratch agent loop, and what Pydantic AI abstracts away

**Ticket:** [Spike: from-scratch agent loop (#18)](https://github.com/lyeyixian/personal-assistant-harness/issues/18) · part of the v1 build spec (#17)
**Placement:** the deliberate learning dip that opens the build phase ([ADR-0002](../../docs/adr/0002-harness-architecture.md)). This code is never imported by the harness.

## What's here

| File | Role |
| --- | --- |
| `loop.py` | The loop itself: ~70 lines, no SDK, no network — the transport is injected |
| `main.py` | Runnable demo against a real provider API (`uv run main.py`; free `GEMINI_API_KEY` from aistudio.google.com/apikey, or `ANTHROPIC_API_KEY`) |
| `gemini.py` | Gemini transport: translates the loop's Anthropic wire shape to/from Gemini's `generateContent` shape |
| `test_loop.py` / `test_gemini.py` | Nine tests: the loop through a scripted fake transport, plus the pure Gemini translation functions |

## The mechanics — what an agent loop actually is

The whole thing reduces to one sentence: **an agent is a while-loop around a stateless HTTP endpoint, and the messages list is the only state.**

Every round trip sends the *entire* conversation so far — the provider remembers nothing. One iteration looks like:

1. POST `messages` + `tools` (name, description, JSON Schema per tool) to `/v1/messages`.
2. The response is a list of content blocks plus a `stop_reason`. If `stop_reason != "tool_use"`, the text blocks are the final answer — done.
3. Otherwise, for each `tool_use` block: run the named tool with the model's `input` dict, and build a `tool_result` block carrying the output, correlated back by `tool_use_id`.
4. Append the assistant's turn verbatim, append the tool results as a `user` turn, go to 1.

The details that weren't obvious until writing it:

- **The assistant's `tool_use` turn must be echoed back verbatim** in the next request. You're not sending a "tool reply"; you're replaying a growing transcript in which the model's own tool request is a turn.
- **Tool results are a `user` message.** There is no third role — the wire format models tool output as "the user speaking on behalf of the tools", correlated by id rather than by position.
- **Tool failure is not an exception, it's a message.** An unknown tool (or a tool error) becomes a `tool_result` with `is_error: true`, and the model recovers or explains — the loop never crashes on the model's mistakes.
- **Nothing guarantees termination.** The model decides when it's done via `stop_reason`; a loop without an iteration cap is an unbounded spend. Hence `max_iterations` and `LoopLimitExceeded`.
- **Context grows every round.** Each tool round replays everything before it, so token cost is roughly quadratic in the number of tool calls. "Barely agentic" (ADR-0002's v1 stance) is also a cost posture.

## What Pydantic AI abstracts away

Mapping each piece of hand-rolled code to what the SDK does instead:

| Hand-rolled in this spike | In Pydantic AI |
| --- | --- |
| The while-loop, `stop_reason` dispatch, transcript bookkeeping | `agent.run()` — the loop *is* the product |
| Anthropic-specific wire shapes (`tool_use`/`tool_result` blocks, `x-api-key` header, version header) | Provider-neutral model classes; the SDK call site doesn't change per vendor (the ADR-0001 reason to pick it). `gemini.py` is this abstraction built by hand once: ~80 lines translating `tool_use`/`tool_result` blocks to `functionCall`/`functionResponse` parts, minting call ids Gemini doesn't provide — multiply by every provider and every wire-format change to price in what the SDK maintains for you |
| Hand-written JSON Schema for every tool | `@agent.tool` derives schema from the function signature and docstring |
| Passing the model's raw `input` dict straight into the tool | Pydantic validation of arguments, with validation errors sent *back to the model* as retryable tool results |
| `final_text: str` — the answer is whatever prose came back | `output_type=SomeModel`: typed, validated outputs, retried on parse failure (what v1 leans on for `FitReport` / `ResumeContent`) |
| `max_iterations` guard | Usage limits (requests *and* tokens), configurable retries |
| Inventing an injectable `call_model` seam to make the loop testable | `TestModel` / `FunctionModel` ship in the box |
| Not handled at all: streaming, async, retries on 429/529, usage accounting | All built in |

The genuinely load-bearing insight for the harness build: **the SDK's value is not the loop — 70 lines replaces it — it's the validation boundary.** Schema generation, argument validation, and typed outputs are where hand-rolled code would accumulate real defects, and they're exactly the features ADR-0002's "LLM writes content behind typed outputs" architecture depends on.

## Timebox

Built well inside the 1–2 day box. Deliberately unpolished per the ticket: no streaming, no retry/backoff, single provider, plain-dict messages (the raw wire shape *is* the learning surface — typing them away would have hidden it).
