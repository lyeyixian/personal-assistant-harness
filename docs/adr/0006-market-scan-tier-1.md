# ADR-0006: Market scan as a fourth skill; ADR-0005's return condition does not fire

**Status:** Accepted (2026-08-14)
**Ticket:** [Design: market scan — `/scan` skill, `market/` directory, tier-1 board sweeps (#47)](https://github.com/lyeyixian/personal-assistant-harness/issues/47)
**Builds on:** [ADR-0005: Claude session as orchestrator, thin `pa`, three skills](0005-claude-session-as-orchestrator.md)
**Defers:** [Tier 2: criteria-driven job discovery across untracked companies (#48)](https://github.com/lyeyixian/personal-assistant-harness/issues/48)

## Context

`/fit` analyses one hand-pasted posting at a time. Nothing answers the question that comes
*before* it: what is open at a given company right now, and which of it is worth one of a small
number of application slots.

A manual sweep of Google Singapore in August 2026 established the shape of the work and produced
two facts the design has to live with.

**Enumeration and retrieval need different mechanisms.** The board's results pages are
client-rendered — a plain fetch returns navigation chrome and nothing else, so listing them needs
a real browser. Job *detail* pages are server-rendered, so all 51 bodies came back from two
in-page `fetch` calls without driving the UI.

**Triaging from results-list snippets is unsafe.** *SWE, Acceleration Platform* was initially
binned as an ML role, because its minimum quals read "1 year in a core ML domain" and "1 year ML
infrastructure" and its sibling posting is titled *Senior SWE, **Machine Learning**, Acceleration
Platform*. The body is agentic systems, prompt engineering, RAG, and evaluation pipelines — the
single best match in the whole sweep. Big-tech postings inherit their org's boilerplate minimums,
so the structured fields actively mislead. Any sweep must fetch bodies.

The second fact is what makes this more than a scraper. The expensive part is judgement over
prose, and it has already been demonstrated to be wrong when it works from metadata.

## Decision

**A fourth skill, `/scan`, alongside `/fold`, `/fit`, and `/resume`. `pa` is untouched.**

Scope is **tier 1**: sweep a company already named in a hand-maintained watchlist, fetch every
listing body, triage each against `direction.md`. Human-triggered, one company or a few per run.
Tier 2 — supply criteria and have the discovery find companies you have not named — is deferred
to #48 for the reason in the next section.

### ADR-0005's return condition does not fire

ADR-0005 collapsed the agent layer and named a three-part condition for bringing it back. Tier 1
is the first module since that could plausibly trip it, so it is worth answering point by point
rather than assuming.

- **Unattended runs** — no. A scan is invoked deliberately, its output is read in-session, and
  its writes go through the same `git diff` gate as every other vault write.
- **Genuine mid-task tool use** — *present, and it still does not fire.* A scan decides mid-task
  what to fetch next: which result pages to page through, which detail URLs follow from them. That
  is exactly the behaviour ADR-0005 said a session gives up — except the driving session is Claude
  Code, which has a browser and a shell and *is* the tool loop. The condition was about reviving a
  Python agent framework inside `pa`; a markdown skill with tools already satisfies the need that
  framework would have served. Rebuilding it here would re-run ADR-0005's original mistake:
  standing up a framework to supply agency the environment already provides.
- **Volume that needs golden-set grading** — not yet. One sweep is tens of listings, read by a
  human the same session. Tier 2 is where this changes.

So the return condition is answered *no* for tier 1 and *plainly yes* for tier 2, which is the
substantive reason #48 is a separate decision rather than a follow-up increment.

### A deterministic `pa scan` was considered and rejected

The tempting seam is the ADR-0005 one: deterministic work into `pa`, judgement into the skill.
Fetching looks deterministic, so `pa scan <company>` looks right.

It is not, because of the first Context fact. Enumeration needs a browser, so `pa scan` would
have to take a headless-browser dependency — reintroducing a heavyweight dependency and an
install burden to `pa`, whose entire post-ADR-0005 value is that it needs no API key and costs
nothing to install — in order to duplicate a browser the session already has. The gate-shaped
work `pa` exists for (shape, provenance, compilation) has no analogue here: there is no artifact
a model must be prevented from fabricating, because the listing body is stored verbatim and the
triage is advisory.

### Board adapters are data, not code

Everything learned about Google's board is a string: a URL, four query parameters, "results
client-rendered, details server-rendered", "caps ~3 active applications". These live as one
section per company in `market/watchlist.md`, hand-edited in Obsidian. Adding a company is
appending a section, not shipping a code change — which matters because the company list is
expected to grow continuously.

### Volatile and immutable are separate files

The vault's core rule is that `git diff` is the human gate. A durable per-listing record with a
`last-seen` field would break that rule by construction: re-sweeping Google in October would
touch ~51 files to bump dates, producing a diff nobody reads, which is worse than no gate.

So the listing record is written once and never rewritten — frontmatter plus the body verbatim,
plus `first-seen`. Every churning field (`last-seen`, open/closed status, triage verdict, the
back-reference to a `jobs/` note) lives in a per-company `index.md` table. A re-sweep's diff is
one file per company, and it reads as "four rows changed", which is the actual question.

The triage verdict is volatile for a non-obvious reason: it is a judgement against `direction.md`,
and `direction.md` changes. A verdict stored beside an immutable body would silently rot.

### Triage has its own vocabulary

`/scan` grades `shortlist | maybe | reject` with a one-line reason. It deliberately does not
reuse `/fit`'s `strong-fit | good-fit | stretch | skip`, which are defined as the output of a full
requirements-by-requirements analysis against the whole curated corpus. A scan reads one body
against `direction.md` and takes seconds. Sharing the words would make a skim indistinguishable
from an analysis six months later.

### Criteria split into filterable and aspirational

Board parameters that demonstrably work (location, target level, employment type, category) are
**filterable** and narrow the sweep. Compensation, remote policy, and working-hours flexibility
are **aspirational**: Singapore postings essentially never state them — the Google sweep pulled 51
full bodies and captured zero salary figures — so they are recorded as `stated | unknown` and
annotated, never used to drop a listing. Filtering on them would have discarded the top pick for
lack of evidence.

Where such a fact is worth having, it is enriched from outside the posting onto the **company**
row, on demand, for shortlisted listings only. Compensation bands are a property of a company and
level, not of a requisition, and re-scraping a third-party site once per listing per sweep buys
nothing.

### `/scan` proposes calibration; it never writes `direction.md`

The Google sweep's durable output was not the 51 rows. It was three rules — Google's Early/Mid to
L3/L4 mapping, the Core-org filter, and the tell that separates a genAI-in-an-ML-wrapper posting
from real ML work — which graduated by hand into `direction.md` and now govern `/fit` too.

That graduation is the valuable path, so `/scan` ends by *raising* candidate `direction.md` edits
in-session and writing none of them. This mirrors `/fold`, which raises a bullet it cannot place
rather than guessing. `direction.md` is the lens every other skill judges against; a scraper does
not get to rewrite it.

### `/fit` gains a `--listing` mode

Promotion from a scanned listing to a candidate is `/fit --listing <company>/<slug>`, which copies
the stored body verbatim into `jobs/<slug>.md`, stamps `source-listing:`, and analyses as normal.
`market/` and `jobs/` stay separate directories on **write-authority** grounds: `/scan` rewrites
`market/` wholesale and repeatedly, while a `jobs/` note is a decision record reviewed and
committed deliberately. Merging them would drop 51 machine-written notes into the folder that
holds hand-fed candidates, and the promotion boundary is precisely where a human said "this one
deserves attention".

This is not a workaround for `/fit`'s "never read other postings" rule. That rule binds `/fit`,
not the directory; `/scan` is a different skill and was never governed by it.

## Consequences

- `pa` still needs no API key, makes no model calls, and takes no browser dependency. ADR-0005's
  shape holds for a fourth module.
- The vault gains a `market/` directory that is **quarantined**: `/fit`, `/fold`, and `/resume`
  never read it, so the curated corpus stays experience-only and machine-generated market data
  cannot leak into a resume or a fit analysis.
- Scans are markdown instructions, not code — revised in a session, not typechecked. The
  misclassification lesson survives as an instruction to fetch bodies, enforced by nothing but the
  skill text.
- Closure is inferred, not verified: a listing absent from a fresh sweep is marked closed **only**
  when that sweep used the same parameter recipe, and `unknown` otherwise. Recording the recipe per
  sweep is therefore load-bearing, not bookkeeping.
- The funnel is modelled from board listing to candidate and no further. There is still no
  representation of *applied* or of any outcome anywhere in the vault (#49). `source-listing:`
  keeps that path traceable so the gap can be closed without rework.
- Tier 2 remains unbuilt, and ADR-0005's return condition is the explicit gate on it.
