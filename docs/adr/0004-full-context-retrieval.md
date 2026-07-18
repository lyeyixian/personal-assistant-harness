# ADR-0004: Full-context retrieval at v1 corpus size

**Status:** Accepted (2026-07-19)
**Ticket:** [Decide: retrieval strategy (#6)](https://github.com/lyeyixian/personal-assistant-harness/issues/6)
**Builds on:** [ADR-0002](0002-harness-architecture.md) (harness architecture), [ADR-0003](0003-role-level-notes-over-atomic-achievements.md) (role-level notes), [experience-store schema](../spec/experience-store-schema.md)
**Prototype:** [`prototypes/retrieval_strategy/` on `prototype/retrieval-strategy`](https://github.com/lyeyixian/personal-assistant-harness/tree/prototype/retrieval-strategy/prototypes/retrieval_strategy)

## Context

The fit-analysis and resume-generation agents need experience-store content in
context. Three candidate strategies: **full-context** (load every curated note),
**structured retrieval** (frontmatter/skill filtering + grep), and a
**vector/RAG index**. ADR-0002 and ADR-0003 provisionally assumed full-context
but explicitly deferred the decision to the real corpus size, to be made by
cheap prototype rather than by reflex — vector/RAG only if the simpler options
demonstrably fail.

## Measurements (real corpus, real posting)

Prototype run against the seeded vault (27 curated notes; journal + README
excluded per the schema's retrieval contract) and a real Singapore AI Engineer
posting (Temus, via the Greenhouse API). Token counts are chars/4 estimates —
Claude's tokenizer differs by roughly ±20–30%, which cannot flip a decision
whose margin is 11k vs a 200k–1M window.

| | notes | tokens | % of 1M window | Sonnet 5 $/call cold | $/call cached |
|---|---|---|---|---|---|
| Corpus (curated) | 27 | ~10.2k | 1.0% | — | — |
| Full-context fit prompt | 27 + posting | ~11.5k | 1.1% | $0.035 | $0.003 |
| Structured-filtered prompt | 11 + posting | ~6.5k | 0.6% | $0.020 | $0.002 |

Structured retrieval saves **43% ≈ $0.015 per cold call** (fractions of a cent
cached). On Haiku 4.5 the full prompt is 5.7% of the 200K window.

## Decision

**Full-context.** Both agents read the whole curated vault into one prompt.
No filtering layer, no index.

Two findings drive this, beyond the trivial cost delta:

1. **The corpus is negligible relative to any current context window.** 11.5k
   tokens is ~1% of the window and ~3.5 cents per cold call at Sonnet 5 input
   pricing; with prompt caching (the corpus is a stable prefix well above the
   minimum cacheable size) repeat calls cost ~$0.003.
2. **Structured retrieval demonstrably failed recall on the real task.** The
   skills-frontmatter filter matched only `ci-cd`, `datadog`, `docker` against
   the AI-engineer posting and **dropped `projects/personal-assistant-harness.md`**
   — the single strongest evidence for the posting's "agentic AI exposure —
   highly desirable" requirement — because the posting's vocabulary (LangChain,
   Anthropic API, RAG pipelines) doesn't lexically match the vault's slugs
   (`pydantic-ai`, `claude-code`, `llm-evals`, `python`). It also dropped 5 of
   9 roles and all projects, gutting exactly the transferable-experience
   picture a fit analysis exists to weigh. Fixing the vocabulary mismatch
   requires semantic matching — i.e. reintroducing RAG-class complexity — to
   save ~$0.015 per call.

## Vector/RAG: evaluated and rejected at this scale

The ticket's bar for RAG was "the simpler options demonstrably fail." They
don't — full-context works outright. Adopting RAG here would buy:

- an embedding index to build and refresh on every journal fold,
- a chunking policy over notes deliberately designed as narrative wholes
  (ADR-0003),
- a new silent failure mode (retrieval recall) plus the eval burden to detect
  it,

in exchange for saving fractions of a cent per call on a corpus that fits in
1% of the context window. Fit analysis is additionally a **whole-corpus
judgment task** — the model weighs transferability across *all* experience —
so any retrieval layer risks silently weakening the analysis, as the prototype
showed concretely.

## Revisit thresholds

- **Corpus ≳ 50k tokens** (~5× current; decades of growth at the observed
  rate, or a scope expansion to life-scale modules): reconsider **structured
  retrieval first** — the schema keeps this mechanical (frontmatter contract,
  ADR-0003's atomization seams). Before that, **prompt caching** is the first
  cost lever, not retrieval.
- **Vector indexing** only at life-scale corpora (per the roadmap), and only
  once grep/frontmatter selection demonstrably misses.

## Consequences

- Agent implementations stay simple: read vault → assemble prompt → one call.
  No retrieval module in v1's core; the `assistant.core` facade can expose
  `load_store()` returning the whole curated corpus.
- The journal stays excluded from agent context (schema retrieval contract).
- Cache the assembled corpus as a stable prompt prefix; the posting and task
  instructions go after the cache breakpoint.
- The prototype is throwaway; it lives on the `prototype/retrieval-strategy`
  branch with its run report, off `main`.
