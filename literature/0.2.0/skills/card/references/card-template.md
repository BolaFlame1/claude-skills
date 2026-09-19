# Card Template

Blank template for `card.md`. Copy this into `references/cards/{slug}/card.md` during Phase 1 INIT. Fill all fields from metadata and source.md — never from memory or training data.

---

```markdown
---
slug: {slug}
doi: {doi}
title: "{title}"
authors: [{surname1}, {surname2}]
year: {year}
journal: "{journal}"
volume: ""
pages: ""
pmid: ""
pmcid: ""
bibtex_verified: pending
md_quality: pending
retrieved_tier: pending
date_added: {YYYY-MM-DD}
tags: []
---

## Key pointers
- Study design: source.md:L{N} — "{verbatim quote}"
- Sample size: source.md:L{N} — "{verbatim quote}"
- Population: source.md:L{N} — "{verbatim quote}"
- Primary outcome: source.md:L{N} — "{verbatim quote}"
- Main finding: source.md:L{N} — "{verbatim quote}"
- Follow-up: NR

## Eligibility decision
{included | excluded | background-reference} — reason in one sentence

## Relevance
{high | medium | low} — one sentence on why

## Open questions
<!-- What this paper does NOT answer, relevant to the current project -->
```

---

## Field-by-field guidance

**`slug`** — `{firstauthor}-{year}[-{keyword}]`. Must be unique in the project. Becomes the BibTeX key in `key_papers.bib`.

**`doi`** — canonical DOI string, no URL prefix (e.g., `10.1016/j.jalz.2024.01.001`). From `uvx opencite ids` — never typed by hand.

**`title`** — exact title as on the paper. Quoted to handle colons and special chars.

**`authors`** — list of surnames only (for brevity). Full author list goes in BibTeX.

**`bibtex_verified`** — `pending` on intake; set to `true` after Phase 4 BibTeX audit; set to `MISMATCH:{field}` if an error was found and logged.

**`md_quality`** — lifecycle values:
- `pending` — source.md not yet retrieved
- `not-retrieved` — all retrieval tiers failed
- `abstract-only` — retrieved but Phase 3 gate failed (< 300 lines or no Methods/Results)
- `partial` — full text but no References section found
- `full-text` — all Phase 3 gates passed

**`retrieved_tier`** — integer 1–4 corresponding to the tier that succeeded, or `null` if not retrieved.

**`tags`** — free-form list; used for filtering in INDEX.md. Examples: `[RCT, dementia, gait, HAALSI, MCR]`.

---

## Pointer format rules

Every line in `## Key pointers` must match this exact format:
```
- {Label}: source.md:L{line_number} — "{verbatim text from that line}"
```

- `{line_number}` is the output of `grep -n "{quote}" source.md | head -1 | cut -d: -f1`
- The quoted string must match `grep` exactly (no ellipsis, no paraphrase, no truncation that changes meaning)
- If the information is not in source.md: write `NR` instead of the pointer
- If the value is calculated: write `[derived: {formula}]` (e.g., `[derived: (47/210)*100]`)

---

## Extra fields from card-config.yaml

When a project has `references/card-config.yaml`, extra frontmatter fields are inserted after `tags`. Example for MCR neuroimaging SR:

```yaml
mcr_definition: ""
neuroimaging_modality: ""   # MRI | DTI | fMRI | PET | fNIRS | EEG
neuroimaging_measure: ""
eligibility_status: ""      # included | excluded | background-reference
mcr_n: ""
control_n: ""
```

These are filled during Phase 4 EXTRACT using the same quote-locked pointer rules.
