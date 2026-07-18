#!/usr/bin/env python3
"""PROTOTYPE — throwaway. Answers wayfinder ticket #6: retrieval strategy.

Measures the real experience-vault corpus and simulates the two candidate
retrieval strategies on a real fit-analysis prompt:

  A. full-context  — load every curated note into one prompt
  B. structured    — frontmatter/skill filtering: keep only notes whose
                     `skills:` overlap the posting's keywords

Run:  python3 prototypes/retrieval_strategy/measure_retrieval.py [posting.txt]

Token counts are chars/4 estimates (no API key in this environment; Claude's
tokenizer differs, but the decision margin is 11k vs a 200k+ window, so a
±30% error cannot flip the outcome). Assembled prompts are written to out/
(gitignored — vault content stays out of this repo).
"""

import re
import sys
from pathlib import Path

VAULT = Path.home() / "Documents/repo/experience-vault"
OUT = Path(__file__).parent / "out"
EXCLUDE = {"README.md"}  # journal/ excluded by the spec's retrieval contract

# Pricing per MTok (platform.claude.com, 2026-07): input / cached-read
PRICING = {
    "claude-sonnet-5": (3.00, 0.30, 200_000_0 // 10),  # 1M ctx
    "claude-haiku-4-5": (1.00, 0.10, 200_000),
}
CONTEXT = {"claude-sonnet-5": 1_000_000, "claude-haiku-4-5": 200_000}


def est_tokens(text: str) -> int:
    return len(text) // 4


def parse_frontmatter(text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        val = val.strip()
        if val.startswith("[") and val.endswith("]"):
            fm[key.strip()] = [v.strip() for v in val[1:-1].split(",") if v.strip()]
        else:
            fm[key.strip()] = val
    return fm


def load_corpus() -> list[dict]:
    notes = []
    for p in sorted(VAULT.rglob("*.md")):
        rel = p.relative_to(VAULT)
        if rel.parts[0] == "journal" or rel.name in EXCLUDE:
            continue
        text = p.read_text()
        notes.append({
            "path": str(rel),
            "text": text,
            "tokens": est_tokens(text),
            "fm": parse_frontmatter(text),
        })
    # stable reading order: profile, direction, skills, then roles/projects/stories
    order = {"profile.md": 0, "direction.md": 1, "skills.md": 2,
             "roles": 3, "projects": 4, "stories": 5}
    notes.sort(key=lambda n: (order.get(Path(n["path"]).parts[0], 9), n["path"]))
    return notes


def skill_registry(notes: list[dict]) -> dict[str, str]:
    """slug -> display name, from skills.md's `slug` — Display lines."""
    skills_note = next(n for n in notes if n["path"] == "skills.md")
    reg = {}
    for m in re.finditer(r"`([a-z0-9.+-]+)`\s*[—-]+\s*(.+)", skills_note["text"]):
        reg[m.group(1)] = m.group(2).strip()
    return reg


def match_posting_skills(posting: str, registry: dict[str, str]) -> set[str]:
    """Slugs whose slug or display name appears in the posting text."""
    hay = posting.lower()
    hits = set()
    for slug, display in registry.items():
        names = {display.lower(), slug.replace("-", " "), slug.replace("-", ".")}
        if any(re.search(r"(?<![a-z0-9])" + re.escape(n) + r"(?![a-z0-9])", hay)
               for n in names if len(n) > 1):
            hits.add(slug)
    return hits


FIT_SYSTEM = (
    "You are a job-fit analyst. Using the candidate's experience store below, "
    "produce a fit & gap analysis for the job posting: overall verdict, "
    "strong matches (with evidence from the store), partial/transferable "
    "matches, genuine gaps, and how to position the candidacy. Read "
    "direction.md as the lens for what the candidate wants.\n\n"
)


def assemble(notes: list[dict], posting: str) -> str:
    body = "\n\n".join(f"<note path=\"{n['path']}\">\n{n['text']}\n</note>"
                       for n in notes)
    return (FIT_SYSTEM + "# EXPERIENCE STORE\n\n" + body
            + "\n\n# JOB POSTING\n\n" + posting
            + "\n\nProduce the fit & gap analysis.")


def structured_select(notes: list[dict], matched: set[str]) -> tuple[list[dict], list[dict]]:
    keep, drop = [], []
    kept_role_slugs = set()
    for n in notes:
        top = Path(n["path"]).parts[0]
        if top in ("profile.md", "direction.md", "skills.md"):
            keep.append(n)
        elif top in ("roles", "projects"):
            overlap = set(n["fm"].get("skills", [])) & matched
            (keep if overlap else drop).append(n)
            if top == "roles" and overlap:
                kept_role_slugs.add(Path(n["path"]).stem)
    for n in notes:  # stories: keep if they reference a kept role
        if Path(n["path"]).parts[0] == "stories":
            refs = set(n["fm"].get("roles", []))
            (keep if refs & kept_role_slugs else drop).append(n)
    return keep, drop


def cost_line(model: str, tokens: int) -> str:
    inp, cached, _ = PRICING[model]
    return (f"    {model}: ${tokens * inp / 1e6:.4f}/call cold, "
            f"${tokens * cached / 1e6:.4f}/call with prompt-cache read "
            f"({tokens / CONTEXT[model]:.1%} of {CONTEXT[model] // 1000}k window)")


def main() -> None:
    posting_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    posting = posting_path.read_text() if posting_path else "(no posting supplied)"

    notes = load_corpus()
    total = sum(n["tokens"] for n in notes)
    OUT.mkdir(exist_ok=True)
    (OUT / ".gitignore").write_text("*\n")

    print("=" * 72)
    print("A. CORPUS MEASUREMENT (curated notes; journal + README excluded)")
    print("=" * 72)
    for n in notes:
        print(f"  {n['tokens']:>6,} tok  {n['path']}")
    print(f"  {total:>6,} tok  TOTAL  ({sum(len(n['text']) for n in notes):,} chars)")

    print()
    print("=" * 72)
    print("B. FULL-CONTEXT: one fit-analysis prompt = system + corpus + posting")
    print("=" * 72)
    full_prompt = assemble(notes, posting)
    full_tokens = est_tokens(full_prompt)
    print(f"  assembled prompt: {full_tokens:,} tok (est.)")
    for model in PRICING:
        print(cost_line(model, full_tokens))
    (OUT / "full_context_prompt.txt").write_text(full_prompt)
    print(f"  written to {OUT / 'full_context_prompt.txt'}")

    print()
    print("=" * 72)
    print("C. STRUCTURED RETRIEVAL: frontmatter skill-filter against the posting")
    print("=" * 72)
    registry = skill_registry(notes)
    matched = match_posting_skills(posting, registry)
    print(f"  skill registry size: {len(registry)} slugs")
    print(f"  posting-matched slugs: {sorted(matched) or '(none)'}")
    keep, drop = structured_select(notes, matched)
    keep_tokens = sum(n["tokens"] for n in keep)
    print(f"  kept   {len(keep):>2} notes, {keep_tokens:,} tok")
    for n in keep:
        print(f"      + {n['path']}")
    print(f"  dropped {len(drop):>2} notes, {sum(n['tokens'] for n in drop):,} tok")
    for n in drop:
        print(f"      - {n['path']}")
    filtered_prompt = assemble(keep, posting)
    filtered_tokens = est_tokens(filtered_prompt)
    print(f"  assembled filtered prompt: {filtered_tokens:,} tok "
          f"(saves {full_tokens - filtered_tokens:,} tok, "
          f"{1 - filtered_tokens / full_tokens:.0%})")
    for model in PRICING:
        print(cost_line(model, filtered_tokens))
    (OUT / "structured_prompt.txt").write_text(filtered_prompt)
    print(f"  written to {OUT / 'structured_prompt.txt'}")


if __name__ == "__main__":
    main()
