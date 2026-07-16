# ADR-0001: Pydantic AI as the agent SDK

**Status:** Accepted (2026-07-16)
**Ticket:** [Decide: which agent SDK (#3)](https://github.com/lyeyixian/personal-assistant-harness/issues/3)
**Research:** [Python agent SDK comparison](https://github.com/lyeyixian/personal-assistant-harness/blob/research/python-agent-sdks/docs/research/python-agent-sdks.md) (#2)

## Context

The harness needs a production agent SDK for v1 (job-fit/gap analysis + tailored resume generation over a local markdown experience store), extensible to future life-assistant modules without hardcoding job-search into the core. The driving dev is a TypeScript developer learning Python, building this as portfolio evidence for an AI-engineer transition — *how* things are built matters as much as what.

Candidates researched (#2): Claude Agent SDK, OpenAI Agents SDK, Google ADK, Pydantic AI (smolagents as reference only). They split into species: Claude Agent SDK is a complete self-hosted harness (Claude-models-only, ~1 GiB subprocess); OpenAI Agents SDK and Pydantic AI are lightweight libraries; Google ADK is a heavyweight framework whose best features are Gemini/Google-Cloud-gated.

## Decision

**Pydantic AI, pinned to the v2.x line** (v2.9.1 at decision time).

Decided in two steps:

1. **Library over harness/framework.** With a harness, the harness did the building — a library makes the dev own tool design, memory, and orchestration, which is exactly the portfolio evidence and learning surface wanted. v1's features don't need Claude Code's built-in tooling; vault read/write and posting-fetch tools are trivial to write and are themselves portfolio material. ADK's conceptual load and Google-Cloud gating ruled it out.
2. **Pydantic AI over OpenAI Agents SDK.**
   - Only genuinely provider-neutral option: Anthropic/OpenAI/Gemini/Ollama are first-class peers, with `FallbackModel` and offline `TestModel`/`FunctionModel`. Every OpenAI Agents "multi-provider" feature carries an asterisk (hosted tools and server-side sessions are OpenAI-only; tracing phones home to OpenAI by default). The harness core must outlive any one vendor.
   - Best learning surface for a typed-TS dev: `Agent[Deps, Output]` generics checked by pyright, Pydantic ≈ Zod, dependency injection over globals — "FastAPI feeling".
   - Past its v1→v2 break with semver; OpenAI Agents SDK is still 0.x with weekly releases.
   - `TestModel`/`FunctionModel` fit the eval-heavy plan (plain-pytest judges per #8).
   - OpenAI Agents' edges — larger adoption numbers, built-in session backends, handoffs — don't bind here: persistence is a markdown vault (DIY either way) and both are recognizable portfolio names.

## Consequences

- **We own persistence.** No built-in store — fits the local-first Obsidian-vault design; message-history serialization is DIY.
- **We own tools.** No built-in tool set — vault access, job-posting ingestion, etc. are written in-repo (deliberate).
- **Pin exactly.** v2 restructured the API in June 2026; tutorials older than ~6 months are stale and doc deep-links from the old ai.pydantic.dev site have rotted — trust primary docs at pydantic.dev/docs/ai only.
- Model/provider choice stays a runtime configuration concern, not an architecture concern.
