# Tailored resume/CV generation — Feature spec

Resolution of [#10 Spec: tailored resume/CV generation feature](https://github.com/lyeyixian/personal-assistant-harness/issues/10).
Builds on the [experience store schema](experience-store-schema.md), [ADR-0002 (harness architecture)](../adr/0002-harness-architecture.md), the [markdown-to-PDF pipeline research (#7)](https://github.com/lyeyixian/personal-assistant-harness/issues/7), and the [eval approaches research (#8)](https://github.com/lyeyixian/personal-assistant-harness/issues/8).

## Contract

**The LLM writes content; a deterministic pipeline owns all layout.** The seam between them is a typed intermediate representation (IR): a `ResumeContent` Pydantic model. The resume-content agent emits it (`output_type=ResumeContent`); a fixed [Typst](https://typst.app) template renders it. Neither side crosses the seam — the model never sees layout, the template never invents content.

**Renderer: Typst**, via the `typst` PyPI wheel — in-process compile, one ~30 MB self-contained dependency, tagged/ATS-safe PDF by default (PDF/UA-1), officially deterministic output (`timestamp` pinned). Chosen over WeasyPrint because structured data is the stricter contract: typed output mechanically enforces the content/layout split where markdown would leak, the typed IR is the natural surface for review and entailment evals, and the zero-native-dep wheel keeps the fresh-machine setup at two touches (ADR-0002).

## Document shape

Single column, **one page target, two pages hard cap**. Overflow is always fixed by *selection* (fewer bullets, cut the projects section), never by shrinking layout — the template's fonts and margins are fixed.

Sections, in order:

1. **Header** — name, title line, location, contact (email, phone, LinkedIn, GitHub). No photo, no date of birth. A **work-authorization line** (citizenship/PR status) is toggled by the posting's market: on for Singapore-market postings (preempts the pass-sponsorship question), off for remote-international.
2. **Summary** — 2–3 lines, tailored per posting; carries the fit narrative.
3. **Skills** — short categorized lines, drawn from `skills.md` pinned skills plus posting-relevant picks. Placed above experience: ATS keyword matching and 6-second human scans both hit it early.
4. **Experience** — one entry per outward-facing position. Team stints regroup into positions via the store's `programme` frontmatter (e.g. rotations merge into one graduate-programme entry). 3–5 tailored achievement bullets per entry.
5. **Projects** *(optional)* — included only when a project earns its place for this posting (`on-profile` flag + relevance).
6. **Education & certifications** — last; the dev is past the fresh-grad line where education leads.

## Pipeline

One agent, one pass, barely agentic (ADR-0002):

1. **Deterministic pre-step** parses the posting — a file or pasted text in v1, no URL fetching — into a typed `JobPosting` model: title, company, market, requirements, keywords. This model is **shared with `pa jobs fit`**, so both v1 features consume identical posting input. The parser **infers the market** (`sg` | `remote`) from company location and remote signals; a `--market` flag overrides, and the value is visible/editable in the output YAML.
2. **One resume-content agent call.** System prompt carries the tailoring and phrasing rules; input is the full curated vault (journal excluded, per the retrieval contract) plus the `JobPosting`; output is `ResumeContent`. No tools — selection and phrasing happen in a single typed generation.
3. **Render**: `ResumeContent` → JSON → `sys.inputs` → the fixed Typst template → PDF.

**Kept-open evolution paths** (adopt if corpus growth or eval results demand; not v1 machinery):

- Splitting into a two-stage select-then-phrase pipeline.
- Chaining resume generation off a `FitReport` from `pa jobs fit` (v1 keeps the features siblings that share only `JobPosting`).

## Honesty enforcement

**Rephrase, never originate.** The agent may freely rephrase achievements for the posting — tailoring is the point — but every bullet must trace to a specific achievement arc, story, or frontmatter fact in the store.

- **Provenance in the IR**: every experience/project bullet carries a non-rendered `source` field — `<note-slug>#<achievement-heading>` (e.g. `acme-payments-rotation#partner-bank-onboarding-automation`). Before render, a deterministic validator checks every `source` resolves to a real note and heading in the vault; an invalid ref fails the run before a PDF exists.
- **Metric qualifiers may be reworded, never removed.** The store's inline caveats travel with the number, compressed to resume register: `~500 txns/month (projection, per go-live email)` becomes "projected to automate ~500 transactions/month" — never "automated 500 transactions/month". If a qualifier makes a bullet too weak to earn its place, the fix is selection, not qualifier-stripping.
- **Entailment is the eval hard-fail** (per the eval research): every bullet checked against its *named* source — a per-bullet judgment against a known target, not a fuzzy whole-corpus search.

## Review / edit loop

Generate and render are **separate commands**; the human is the last gate.

- `pa jobs resume <posting>` runs the pipeline and writes two artifacts to a per-posting output directory (configurable root, e.g. `~/pa-out/<company>-<slug>/`), **outside the vault** — outputs are generated, not stored:
  - `resume.yaml` — the `ResumeContent` serialized as YAML, the hand-editable artifact.
  - `resume.pdf` — rendered immediately, so every run ends with a finished draft.
- **Edit loop**: review the PDF; fix phrasing/ordering/cuts by editing `resume.yaml` directly, then `pa jobs resume render <dir>` — deterministic, LLM-free, sub-second, no API cost. Provenance validation re-runs on every render, so hand-edits can't silently break entailment.
- **Regeneration**: `--regenerate` (optionally with a free-text steer, e.g. "lead with the platform work") re-runs the agent when *selection* is wrong rather than phrasing. It warns that hand-edits to the YAML will be overwritten and asks for confirmation. The cost asymmetry deliberately nudges toward cheap deterministic edits first.
- **No interactive chat-refinement loop** in v1: hand-editing a ~60-line YAML is faster and more precise than steering a model toward the same edit.
- **No output versioning** — regeneration overwrites in place. Outputs are ephemeral and regenerable; the output root can become a git repo later without the harness caring.

## Template

Exactly **one** fixed Typst template, owned by the repo at `src/assistant/modules/job_search/render/`. Fonts pinned and embedded; `set text(ligatures: false)` as extraction belt-and-suspenders; compile with a pinned `timestamp` for byte-reproducible output. No theme options in v1 — every layout variant is an eval surface and an ATS risk.

**CI guard**: a test compiles a fixture `ResumeContent` and round-trips the PDF through `pdftotext`, diffing against the source content — this directly tests the glyph-to-Unicode property ATS parsers depend on (per the pipeline research and vendor docs).

## CLI surface

```
pa jobs resume <posting-file> [--market sg|remote] [--out <dir>]   # full pipeline: parse → agent → YAML + PDF
pa jobs resume render <dir>                                        # deterministic re-render of an edited resume.yaml
pa jobs resume <posting-file> --regenerate [--steer "..."]         # re-run the agent; warns before overwriting hand-edits
```
