# ADR-0002: Harness architecture & project structure

**Status:** Accepted (2026-07-17)
**Ticket:** [Design: harness architecture & project structure (#11)](https://github.com/lyeyixian/personal-assistant-harness/issues/11)
**Builds on:** [ADR-0001: Pydantic AI as the agent SDK](0001-pydantic-ai-as-agent-sdk.md)

## Context

The harness must host job-search as its *first* module — not its core — so future life-assistant modules slot in without rework. The SDK is Pydantic AI v2.x (ADR-0001), which supplies agents, typed outputs, and DI but no persistence, tools, or CLI: those boundaries are ours to draw. The driving dev is a TypeScript developer learning Python; the build doubles as portfolio evidence, so the architecture should demonstrate judgment (evolution paths over speculative generality).

## Decision

### Core/module boundary

The core owns exactly **one domain concept: the experience store** (Obsidian-vault I/O + document model), with journaling as its core-level write path — every current and future module reads/writes the store, so it is the shared memory substrate, not a module. The core also owns the mechanical substrate: config, secrets, CLI shell, and agent plumbing. Everything else domain-specific lives in modules; `job_search` is the first.

### Module contract

A module is a **convention, not a class**: a subpackage under `assistant/modules/` exposing a Typer sub-app, mounted by one explicit line in the root CLI. The real contract is dependency direction:

- Modules import **only** from the `assistant.core` facade's public API (its `__init__` exports).
- Core never imports from modules, except the single CLI-mounting line.
- Modules never import from each other.

Third-party plugin support (a `Module` Protocol + entry-point discovery) is a **deliberate future extension, not v1 machinery**. The facade discipline above is what makes that retrofit mechanical: our own modules already live under the constraints a third-party plugin would. Migration path when open-sourcing becomes real: (1) write a Protocol describing the existing convention; (2) add `importlib.metadata` entry-point discovery under a `assistant.modules` group; (3) publish the facade as the versioned plugin API. An `import-linter` rule may enforce the dependency direction in the meantime.

### CLI

**Typer** (typed, sub-apps map 1:1 onto module mounting, same mental model as Pydantic/FastAPI). Binary **`pa`**, **noun-verb** grammar where each noun is a module mount point:

```
pa init                   # scaffold ~/.config/pa/config.toml interactively
pa journal add            # core: capture an achievement/experience entry
pa journal list           # core: browse recent entries
pa jobs fit <posting>     # job-search: fit/gap analysis
pa jobs resume <posting>  # job-search: tailored resume PDF
```

### Config & secrets

One **pydantic-settings** `Settings` class in the core facade; modules contribute their own config by nesting a model (e.g. `settings.jobs.*`). Precedence: env vars → `.env` (gitignored) → `~/.config/pa/config.toml` (durable per-machine settings: vault path, default model, output dir) → code defaults. **Secrets (API keys) live in env/`.env` only, never in `config.toml`**, so the config file is always safe to back up. No keychain integration in v1; a keychain-backed settings source is a drop-in later if wanted.

### Pydantic AI mapping

- **One `Agent` per task, owned by its module**: fit-analysis and resume-content agents in `job_search`; a journaling agent in core. No god-agent — per-task agents get focused prompts, typed outputs, and are individually evaluable (per the eval plan, #8).
- **Core provides the agent factory, not the agents**: model, retries, and usage limits come from `Settings`, so provider choice stays pure runtime config (per ADR-0001).
- **Typed outputs everywhere** (`output_type=FitReport`, `ResumeContent`, …). For resumes this mechanically enforces "LLM writes content, deterministic pipeline renders layout" — and structured output is what makes Typst the strong renderer choice (#7).
- **Deps as a dataclass** (`store`, `settings`, `http`) injected via `RunContext`; the store is reached only through the core facade. Evals swap in a fixture store + `TestModel`.
- **v1 stays barely agentic, deliberately**: job postings are fetched/parsed by a deterministic pre-step and passed as input, not fetched by a tool; store reads are full-context (decided at real corpus size in [ADR-0004](0004-full-context-retrieval.md)). Tools enter only where the model must genuinely decide — e.g. per-claim evidence lookup, if full-context proves insufficient.

### Project layout & tooling

src layout, single package `assistant`, console script `pa = assistant.cli:app`:

```
pyproject.toml
src/assistant/
    cli.py              # root Typer app: mounts core commands + module sub-apps
    core/               # the facade — __init__ exports the public API
        config.py       # Settings (pydantic-settings)
        agents.py       # agent factory
        store/          # vault I/O + document model
        journal/        # journaling agent + `pa journal` commands
    modules/
        job_search/     # agents.py, models.py, cli.py, render/
tests/
docs/adr/
experiments/            # learning spikes; never imported by the harness
```

src layout kept (weakly held) for packaging safety ahead of the open-source future; moving from flat would be one commit, staying src costs one directory of nesting. Tooling: **uv** (env + lockfile), **ruff** (lint + format), **pyright strict** (the typed-Python learning surface), **pytest**. Skipped deliberately: pre-commit, tox/nox, docker.

### Learning dip placement

The from-scratch agent loop is the **first act of the build phase**: a timeboxed (1–2 day) spike against the raw provider API — messages list, tool-call dispatch, loop-until-done (~150 lines) — in `experiments/agent_loop/`, with a short write-up of what Pydantic AI abstracts away. Spike code is never imported by the harness.

## Consequences

- The core carries a domain concept (the store); anyone extending the harness must treat "experience/life record" as core vocabulary, not module vocabulary.
- No enforcement of the facade discipline until an `import-linter` rule is added — convention holds it meanwhile.
- Open-source plugin support is a documented intention with a migration path, not a shipped feature.
- A fresh machine needs two touches (`pa init` + API key in env).
- The barely-agentic v1 means some "agentic" portfolio flash is traded for determinism and easier evals; the spike write-up covers the loop-mechanics evidence instead.
