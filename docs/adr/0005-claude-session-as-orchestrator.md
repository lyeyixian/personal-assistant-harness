# ADR-0005: Claude session as orchestrator, thin `pa`, three skills

**Status:** Accepted (2026-08-01)
**Ticket:** [Spec: re-scope — Claude session as orchestrator, thin `pa`, three skills (#36)](https://github.com/lyeyixian/personal-assistant-harness/issues/36)
**Supersedes:** [ADR-0001: Pydantic AI as the agent SDK](0001-pydantic-ai-as-agent-sdk.md)
**Amends:** [ADR-0002: Harness architecture & project structure](0002-harness-architecture.md)

## Context

Three green, reviewed pull requests sat unmerged because each needed the agent layer finished
before any of it could be used. `pa` was not installed on the driving dev's machine. The repo had
never once produced a resume.

v1 routed every feature through a Python agent framework — a factory, typed per-task agents,
dependency injection, usage limits, an eval harness sized for an autonomous pipeline (ADR-0001,
ADR-0002). But v1 was specced *barely agentic* from the start: no tool loop, code-orchestrated
pipelines, full-context reads (ADR-0004), one typed call per task. The framework was supplying
typed output parsing and a model client for a system that had already designed the agency out of
itself — and in exchange made every feature undeliverable until the whole scaffold stood up.

Meanwhile, a coding agent already runs against this exact vault: it reads markdown, reasons over
it, writes markdown back, and runs a shell. The framework was carrying no weight.

## Decision

**The Claude Code session becomes the orchestrator.** `pa` shrinks to the two things a language
model must not be trusted to do for itself, plus the one thing it cannot do at all: a shape gate,
a provenance gate, and Typst compilation, all behind one command, `pa render <dir>`. Three skills
— `/fit`, `/resume`, `/fold` — carry the reasoning that used to be agent prompts, and live in the
Experience Store vault while they're iterated on. Golden-set evals are deferred: with the session
orchestrating, there is no stable programmatic seam left to grade, and a human reviews every
output before it's used.

### Why the agent framework carried no weight

Restated plainly, because it's the hinge the rest of this decision turns on: nothing in v1's
barely-agentic design (Context, above) used the parts of an agent SDK that justify owning one —
tool dispatch, multi-step reasoning, memory across turns. What Pydantic AI supplied in practice was
typed output parsing and a model client. Removing it doesn't trade away agentic behavior v1 had; it
removes a layer that was never load-bearing.

### Return condition

The agent harness comes back when there's a loop worth owning — not before. Concretely, any of:

- **Unattended runs** — the pipeline needs to execute without a human watching each step, which is
  exactly what a session gives up.
- **Genuine tool use** — a task needs the model to decide, mid-task, to call something (fetch a
  URL, query an API, re-read a specific file) rather than reading a fixed context assembled up
  front.
- **Volume that needs golden-set grading** — enough throughput that eyeballing each output stops
  being reliable, and regression needs a programmatic seam to grade against.

Absent one of these, the framework would again be solving a problem the design doesn't have.
"Later" is this condition, not a vague intention.

### The intermediate representation is unchanged

`ResumeContent` remains the seam between content and layout, exactly as ADR-0002 designed it: the
model writes content, a fixed Typst template owns every layout decision. Only the thing filling it
changes — a Claude session today, an agent harness later, behind the same contract.

### Amendment to ADR-0002

Two points of ADR-0002 no longer apply; the rest stands.

- **The Pydantic AI mapping section** (one `Agent` per task, the core-provided agent factory,
  `Deps` injected via `RunContext`) no longer applies — there are no agents, no factory, no
  `RunContext`. The session holds the reasoning that section described distributing across typed
  agents.
- **The noun-verb CLI grammar**, where each noun is a module mount point, is dropped. At one
  module (`render`) with one verb, a noun is ceremony: the CLI collapses to `pa render <dir>`
  mounted at the root, not `pa jobs render <dir>`.

### ADR-0004 unchanged, now native

ADR-0004's decision — full-context retrieval, no filtering layer, no index — is unchanged and now
satisfied natively: the session reads the vault directly instead of an agent assembling a prompt
from a `load_store()` call. The measurements and revisit thresholds in ADR-0004 still hold; nothing
here reopens them.

## Consequences

- `pa` needs no API key and makes no model calls; installing it costs nothing.
- The eval harness ADR-0001 and ADR-0002 sized for is not built. What survives as the automated
  honesty check is the provenance gate — the entailment hard-fail, not tier-and-extraction grading
  against golden labels.
- Skills are markdown instructions, not code — they're read and revised in a session, not
  typechecked or unit tested. Golden-set grading of their output is deferred, returning under the
  condition above.
- ADR-0001 is superseded outright: Pydantic AI, the agent factory, and the pinned SDK dependency
  are removed from the codebase.
- ADR-0002 stands amended only on the two points above; its core/module boundary and facade
  discipline are otherwise untouched by this decision.
- The three closed pull requests' branches are preserved; the fit and Fold agent implementations
  are recoverable when the harness returns.
