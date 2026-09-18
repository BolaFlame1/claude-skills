---
name: card
description: "Use this skill for \"add a card\", \"create a card for this paper\", \"card for DOI\", \"card for PMID\", \"retrieve this paper\", \"add this paper to the cards\", \"update the card\", \"verify the card\", \"check the BibTeX\", \"make a card\", \"pull this paper\", \"download this paper to cards\", or when the user mentions card.md, source.md, meta.json, card slug, key_papers.bib, or asks to add a paper to a project's reference library."
version: 0.1.0
---

# Literature Card Skill

Creates and maintains hallucination-proof literature cards for academic research projects. Every claim in a card traces to a verbatim quote from a full-text `source.md`. No summaries. No paraphrase. No training-data recall.

## Prerequisite: locate the project root

Before any phase, identify where `references/` lives. Look for:
- A `card-config.yaml` file anywhere in the current directory tree
- An existing `references/cards/` directory
- An existing `references/key_papers.bib` file

If none found, ask the user: "Which project folder should this card go in?"

---

## Phase 1 — INIT

**Input:** DOI, PMID, arXiv ID, or free-text title (resolve to DOI first).

### Step 1.1 — Resolve to canonical DOI
```bash
uvx opencite ids "{input}"
```
- Use the returned DOI as the canonical identifier for all downstream steps.
- Never guess or construct a DOI. If the command fails, report to user and stop.

### Step 1.2 — Derive slug
Format: `{firstauthor}-{year}[-{keyword}]`
- `firstauthor` = first author's **surname**, lowercase, no diacritics, no spaces
- `year` = four-digit publication year from metadata
- `keyword` = optional short descriptor (3–8 chars, lowercase, hyphen-separated) — include only when disambiguation is needed or user requests it
- All lowercase, hyphens only, no underscores

Examples: `beauchet-2016`, `livingston-2024-prevention`, `gbd-2022`

### Step 1.3 — Check for duplicates
```bash
grep -r "{doi}" {project_root}/references/cards/ 2>/dev/null
grep "{slug}" {project_root}/references/INDEX.md 2>/dev/null
```
If the DOI or slug already exists → **abort with message**: "Card `{slug}` already exists for this DOI. Use `/literature:card update {slug}` to modify it."

### Step 1.4 — Read project config (if present)
```bash
cat {project_root}/references/card-config.yaml 2>/dev/null
```
Extra frontmatter fields defined here will be included in the skeleton `card.md`. See `references/project-config.md` for format.

### Step 1.5 — Scaffold files
Create `{project_root}/references/cards/{slug}/`:

**`card.md`** — skeleton with frontmatter from metadata, body as `<!-- pending -->`:
```markdown
---
slug: {slug}
doi: {doi}
title: "{title}"
authors: [{surname1}, {surname2}, ...]
year: {year}
journal: "{journal}"
volume: ""
pages: ""
pmid: ""
pmcid: ""
bibtex_verified: pending
md_quality: pending
retrieved_tier: pending
date_added: {today}
tags: []
{extra_fields_from_card_config}
---

## Key pointers
<!-- pending — fill after Phase 4 EXTRACT -->

## Eligibility decision
<!-- pending -->

## Relevance
<!-- pending -->

## Open questions
<!-- pending -->
```

**`meta.json`**:
```json
{
  "slug": "{slug}",
  "doi": "{doi}",
  "retrieved_tier": null,
  "retrieval_date": null,
  "retrieval_tool": null,
  "md_quality": "pending",
  "bibtex_integrity": "pending",
  "source_lines": null,
  "integrity_issues": []
}
```

**Add row to `{project_root}/references/INDEX.md`** (create file if absent):
```
| {slug} | {title truncated to 60 chars} | {year} | intake | {today} |
```

**Add skeleton BibTeX to `{project_root}/references/key_papers.bib`** (create if absent):
```bibtex
@article{{slug},
  author  = {{pending}},
  title   = {{pending}},
  journal = {{pending}},
  year    = {year},
  doi     = {{doi}},
  note    = {{bibtex_verified: pending}}
}
```

---

## Phase 2 — RETRIEVE

Work through tiers in order. Stop at first success. Update `meta.json` after each attempt.

### Tier 1 — opencite open access
```bash
uvx opencite batch-fetch --dois "{doi}" --convert -o {project_root}/references/cards/{slug}/
```
If `source.md` is created → proceed to Phase 3.

### Tier 2 — PMC fulltext
Only if PMCID is known (from Phase 1 opencite ids output):
```bash
uvx opencite convert "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid}/" -o {project_root}/references/cards/{slug}/source.md
```
If `source.md` is created → proceed to Phase 3.

### Tier 3 — Sci-Hub MCP
Only if `mcp__sci-hub` tools are available in this session:
```
mcp__sci-hub__fetch_paper doi="{doi}" output_dir="{project_root}/references/cards/{slug}/"
```
Convert resulting PDF if needed:
```bash
uvx opencite convert {project_root}/references/cards/{slug}/source.pdf -o {project_root}/references/cards/{slug}/source.md
```
If `source.md` is created → proceed to Phase 3.

### Tier 4 — KUMC via Playwright
Only attempt if Tiers 1–3 all failed. Notify user first:
> "Tiers 1–3 failed for `{doi}`. Attempting KUMC login — you will need to complete Duo MFA when prompted."

```
mcp__playwright__browser_navigate url="https://pubmed-ncbi-nlm-nih-gov.kumc.idm.oclc.org/?otool=kumclib"
```
Wait for user to complete Duo MFA. Then navigate to the paper's full-text page, download PDF to `{project_root}/references/cards/{slug}/source.pdf`, convert:
```bash
uvx opencite convert {project_root}/references/cards/{slug}/source.pdf -o {project_root}/references/cards/{slug}/source.md
```

See `references/retrieval-guide.md` for detailed Playwright steps.

### Tier 5 — Manual fallback
If all tiers fail:
- Set `meta.json` fields: `"md_quality": "not-retrieved"`, `"retrieved_tier": null`
- Update INDEX.md status to `blocked: retrieval-failed`
- Report to user: "Could not retrieve full text for `{doi}`. Card scaffold is ready at `references/cards/{slug}/`; please place the PDF at `references/cards/{slug}/source.pdf` and run Phase 2 again."
- **Stop. Do not proceed to Phase 3.**

---

## Phase 3 — VALIDATE (full-text gate — mandatory)

Run all checks before proceeding. Any failure → stop and report.

```bash
# Check 1: line count
wc -l {project_root}/references/cards/{slug}/source.md

# Check 2: Methods heading
grep -ic "^#.*method\|^method" {project_root}/references/cards/{slug}/source.md

# Check 3: Results heading
grep -ic "^#.*result\|^result" {project_root}/references/cards/{slug}/source.md

# Check 4: References section (warn only, don't stop)
grep -ic "^#.*reference" {project_root}/references/cards/{slug}/source.md

# Check 5: First-author surname in first 50 lines
head -50 {project_root}/references/cards/{slug}/source.md | grep -i "{firstauthor_surname}"

# Check 6: DOI in source.md
grep -c "{doi}" {project_root}/references/cards/{slug}/source.md
```

| Check | Threshold | Failure action |
|-------|-----------|----------------|
| Line count < 80 | — | `md_quality: abstract-only` → log → stop, request higher tier |
| Heading count (##) < 3 | — | `md_quality: abstract-only` → log → stop |
| Methods + Results headings present | — | → `md_quality: full-text` |
| ≥ 5 headings but no Methods/Results | — | → `md_quality: full-text-review` (review/seminar paper); continue |
| 3–4 headings, no Methods/Results | — | → `md_quality: partial` → warn, continue |
| Words run together (no spaces in long tokens) | — | `md_quality: garbled-conversion` → log → stop, request re-fetch |
| References section not found | count = 0 | warn only, do not stop |
| Author surname not in first 50 lines | — | `bibtex_integrity: AUTHOR_MISMATCH` → log → stop |
| DOI string in source.md | count = 0 | `bibtex_integrity: DOI_MISMATCH` → log → stop |

**Note on review papers:** Review articles, seminar papers, and guidelines (Lancet Commission reports, AHA statements, STROBE guidelines) do not use Methods/Results headings. They pass as `full-text-review` when ≥ 5 section headings are present. Extraction rules are identical — all pointers must still be quote-locked to source.md line numbers.

On any stop-failure:
1. Update `meta.json` with the failure field
2. Append to `{project_root}/references/INTEGRITY_ISSUES.md`:
   ```
   ## {slug} — {YYYY-MM-DD}
   - Issue: {check name} failed
   - Evidence: {command output}
   - Action needed: {next step}
   ```
3. Report to user. Do not proceed to Phase 4.

---

## Phase 4 — EXTRACT (quote-locked)

**Read source.md in full** before writing any pointers. For files >500 lines, read in segments (lines 1–300, 301–600, etc.) and confirm all sections read before starting extraction.

### What to write in card.md

**Key pointers section** — one line per pointer, format:
```
- {label}: source.md:L{N} — "{verbatim quote from that line}"
```

Required pointer labels (use "NR" if genuinely absent):
- `Study design` — the design statement (RCT, cohort, cross-sectional, etc.)
- `Sample size` — N at enrollment or analysis
- `Population` — who was studied (age, condition, setting)
- `Primary outcome` — the main outcome variable as stated
- `Main finding` — the primary result as stated (use exact numbers if present)
- `Follow-up` — duration, if applicable

**Self-verify each pointer before writing it:**
```bash
grep -n "{verbatim_quote}" {project_root}/references/cards/{slug}/source.md
```
If grep returns 0 matches → do NOT write that pointer. Mark it `NR` and note in Open questions.

**Eligibility decision:**
```
{included | excluded | background-reference} — one sentence reason
```

**Relevance:**
```
{high | medium | low} — one sentence on why
```

**Open questions:**
```
<!-- List specific questions this paper leaves unanswered for the current project -->
```

### What NOT to write

- No prose summaries
- No paraphrased findings
- No values not directly quoted from source.md
- No information from training data or memory — only source.md
- For calculated values (e.g., effect size derived from reported stats): mark `[derived: {formula}]`, not as a direct finding

See `references/anti-hallucination.md` for the full rule set.

### After extraction

1. Update `meta.json`:
   - `"md_quality": "full-text"`
   - `"retrieved_tier": {N}`
   - `"retrieval_date": "{today}"`
   - `"source_lines": {actual line count}`

2. Verify BibTeX entry (see `references/bib-verification.md`):
   - Compare author list, year, journal, DOI in `key_papers.bib` against source.md title page
   - Correct `key_papers.bib` in-place if needed
   - Set `bibtex_verified: true` in both `card.md` frontmatter and `meta.json`
   - Log any corrections to `INTEGRITY_ISSUES.md`

3. Update INDEX.md status: `intake` → `extracted`

4. Final grep audit — run this for each quoted string in card.md body:
   ```bash
   grep -n "{quoted_string}" {project_root}/references/cards/{slug}/source.md
   ```
   Every quote must return at least one match. If any fail, remove or correct the pointer before finishing.

---

## Updating an existing card

Command: `/literature:card update {slug}`

1. Read current `card.md`, `meta.json`, `source.md`
2. Identify what changed (new section read, corrected quote, updated eligibility)
3. Follow Phase 4 extraction rules — all new/changed pointers must be grep-verified
4. Update `meta.json` with `"last_updated": "{today}"`
5. Do not change `bibtex_verified: true` unless BibTeX actually changed

---

## Quick reference

| Command | Effect |
|---------|--------|
| `/literature:card doi:{doi}` | Full intake for new paper |
| `/literature:card pmid:{pmid}` | Resolve PMID → DOI → intake |
| `/literature:card update {slug}` | Update existing card |
| `/literature:card verify {slug}` | Re-run Phase 3 + Phase 4 audit only |
| `/literature:card bib {slug}` | Re-verify BibTeX only |

---

## Reference files

- `references/card-template.md` — blank card.md template with all fields
- `references/retrieval-guide.md` — detailed Playwright/KUMC steps
- `references/anti-hallucination.md` — full rule set with examples of violations
- `references/bib-verification.md` — BibTeX field-by-field verification protocol
- `references/project-config.md` — card-config.yaml format and examples
