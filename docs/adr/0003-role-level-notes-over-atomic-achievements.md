# Role-level notes over atomic achievement notes

The experience store's unit of note is the role/project — achievements are structured subsections, not the Obsidian-community "notes as database rows" pattern of one note per achievement. The corpus is small (~10k tokens seeded, slow growth), so v1 retrieval reads the whole vault into context, where fewer narrative-intact notes beat fragmented atoms — and capture/curation friction stays low. Per-achievement `###` headings with labeled `**Impact:**`/`**Lessons:**` fields are deliberate seams that keep later atomization a mechanical refactor if the retrieval strategy (issue #6) ever demands it.

## Considered Options

- **Atomic achievement notes** — maximally queryable frontmatter, natural vector chunks; rejected for now: ~40 small files, write amplification, fragmented role narrative, and no retrieval payoff at this corpus size.
- **Hybrid (promote significant work to its own note)** — rejected: adds a "is this note-worthy?" judgment call to every capture.
