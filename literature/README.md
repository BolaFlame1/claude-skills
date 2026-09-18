# literature:card — Hallucination-Proof Literature Card Skill

A Claude Code skill for managing academic literature in research projects. Every claim traces back to a verbatim quote from a full-text `source.md`. No summaries. No paraphrase. No training-data recall.

## What it does

For each paper you want to use:
1. Resolves DOI → derives a slug (`firstauthor-year`)
2. Downloads full text (open access → PMC → Sci-Hub → KUMC, in that order)
3. Validates it is genuinely full text (≥ 300 lines, Methods + Results headings present)
4. Creates `card.md` with line-number-locked pointers to `source.md`
5. Adds a verified BibTeX entry to `key_papers.bib`

## How to trigger it

Say any of: "add a card", "create a card for this paper", "card for DOI", "use the card skill", "download and card these papers", or mention `card.md`, `source.md`, `meta.json`, `key_papers.bib`.

## Recommended workflow

### Standard manuscript pipeline

```
"Here is my methods and results section. Go online and find papers that are
must-haves for this work — search opencite and use your knowledge of the area.
Show me the list. Once I confirm, use the literature card skill to download all
and save them. Then set up a build_doc.py for this project. When everything is
ready, tell me and we'll write the manuscript — every claim must trace back to
a source.md."
```

This one instruction covers the full pipeline:
- Claude finds candidates via `uvx opencite search` + domain knowledge
- You confirm the shortlist before any downloads happen
- Card skill handles retrieval, full-text validation, and card creation
- `build_doc.py` is scaffolded with the bib-driven citation layer
- Writing proceeds with every claim traced to `source.md:L{N}`

### Step by step

1. **Discovery** — Claude runs `uvx opencite search "your topic"` and presents a shortlist with titles, years, DOIs
2. **Confirmation** — you approve the list (or trim it)
3. **Card creation** — for each approved paper, Claude runs the card skill: download → validate → card
4. **Manuscript setup** — Claude scaffolds or updates `build_doc.py` with `BIB_PATH` pointing to the project's `key_papers.bib`
5. **Writing** — every claim in the prose uses `[@slug]` citation markers; Claude verifies each against `source.md` before committing to text

## Project structure

Each project using this skill needs:

```
{project_root}/
└── references/
    ├── key_papers.bib          ← BibTeX source for build.py citations
    ├── INDEX.md                ← one-row-per-card status table
    ├── INTEGRITY_ISSUES.md     ← log of retrieval or BibTeX problems
    ├── card-config.yaml        ← optional: project-specific extra frontmatter fields
    └── cards/
        └── {slug}/
            ├── card.md         ← metadata + line-number pointers to source.md
            ├── source.md       ← full text (converted PDF or HTML)
            ├── source.pdf      ← original PDF if retrieved
            └── meta.json       ← provenance, retrieval tier, quality flags
```

## Citation key = card slug

The card slug (`beauchet-2016`, `livingston-2024-prevention`) is also the BibTeX key and the `[@key]` marker in manuscript prose. Slugs are permanent once used in a manuscript — changing one breaks all citations to it.

## build.py integration

`build_doc.py` reads citations from `key_papers.bib`:

```python
CITATION_STYLE = "numbered"   # "numbered" | "author-year" | "alpha"
BIB_PATH = "references/key_papers.bib"
```

- **Add a citation**: write `[@slug]` anywhere in the prose → auto-numbered on next build
- **Delete a citation**: remove `[@slug]` from prose → dropped from reference list automatically
- **Change style**: change `CITATION_STYLE` → all markers and the reference list reformat

No manual REFERENCES list. No order constraints.

## Anti-hallucination guarantees

- Every pointer in `card.md` includes `source.md:L{N}` and a verbatim quote
- All quotes are grep-verified against `source.md` before the card is finalized
- If information is not in `source.md`, it is written as `NR` — never inferred
- Papers that fail the full-text gate (abstract-only, <300 lines) are blocked from extraction and flagged in `INTEGRITY_ISSUES.md`

## Reference files

| File | Purpose |
|---|---|
| `skills/card/references/card-template.md` | Blank card.md template |
| `skills/card/references/retrieval-guide.md` | Detailed Playwright/KUMC steps |
| `skills/card/references/anti-hallucination.md` | Full rule set with violation examples |
| `skills/card/references/bib-verification.md` | BibTeX field verification protocol |
| `skills/card/references/project-config.md` | card-config.yaml format and examples |
