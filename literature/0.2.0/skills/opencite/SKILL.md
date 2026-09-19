# OpenCite Skill

Discovers papers for the manuscript pipeline using the opencite CLI, then
hands off each result to `/literature:card` for full intake.

## Triggers

Invoke when the user says any of:
- "find papers on", "search for papers", "look up papers"
- "opencite", "discover references", "find references"
- "what papers should I cite for", "find me papers about"
- "canonical papers on", "foundational papers"
- "who cites this", "papers citing"

---

## API keys — check before doing anything

```bash
uvx opencite config show 2>/dev/null | grep -i "openalex\|semantic\|pubmed"
```

| Key | Where to get | Impact if missing |
|-----|-------------|-------------------|
| `openalex_api_key` | **https://openalex.org** (free) | `search` and `canonical` fail — required since Feb 2026 |
| `semantic_scholar_api_key` | https://www.semanticscholar.org/product/api | Rate-limited to 1 req/sec without it |
| `pubmed_api_key` | https://www.ncbi.nlm.nih.gov/account/ | Slower without it, but works |
| `mistral_api_key` | Optional — only for enhanced PDF tables/math | Falls back to markitdown (free) |

**If `openalex_api_key` is not set:**
Stop and tell the user:
> OpenAlex key not configured — `search` and `canonical` will fail.
> Get a free key at https://openalex.org, then run:
> `uvx opencite config init`
> and add the key to `~/.opencite/config.toml`.

PDF fetch (`uvx opencite batch-fetch`) and identifier lookup (`uvx opencite ids`) still
work without any keys — they use PMC and CrossRef.

---

## Phase 1 — Identify the project root

Look for `references/` and `build_doc.py` in the current directory tree.
If found, note the project root — search results will be staged for card intake there.
If not found, proceed without a project root (results shown only, no card prompt).

---

## Phase 2 — Run the search

Choose the right command based on user intent:

### Discovery — new topic, finding what to cite
```bash
uvx opencite canonical "{topic}" --max 10
```
Use `canonical` first for established topics — returns the most-cited foundational papers.

### Recent work
```bash
uvx opencite search "{query}" --max 15 --sort citations
```

### Citation graph — papers that cite a known paper
```bash
uvx opencite cite "{doi_or_pmid}" --direction both --max 20
```

### Single paper lookup
```bash
uvx opencite ids "{title or doi or pmid}"
```
Returns canonical DOI. Then hand off to `/literature:card doi:{doi}`.

---

## Phase 3 — Present results

After the search, show a numbered list:
```
Papers found ({N} results):

  [1] {first_author} ({year}) — {journal}
      {title}
      doi: {doi}    citations: {N}    OA: {yes/no}

  [2] ...
```

Ask the user: **"Which of these should I retrieve full text for? (say 'all', '1,3,5', or 'none')"**

---

## Phase 4 — Fetch full text and hand off to card intake

For each selected paper, run `/literature:card doi:{doi}` (the card skill handles
full-text retrieval and extraction automatically).

If the user wants batch fetch first (multiple PDFs at once):
```bash
uvx opencite search "{query}" --max 10 -f json -o /tmp/search_results.json
uvx opencite batch-fetch --from-json /tmp/search_results.json --convert \
    -o {project_root}/references/cards/raw/
```
Then run `/literature:card doi:{doi}` for each paper to complete intake into the
structured card system.

---

## Phase 5 — Report

Tell the user:
- How many papers found
- How many selected for intake
- For each: "Card ready — run `/literature:card doi:{doi}` to extract"
  (or confirm card intake already ran)

---

## Quick reference

| Command | Effect |
|---------|--------|
| `/literature:opencite {topic}` | Canonical papers on a topic |
| `/literature:opencite search {query}` | Broad search |
| `/literature:opencite cite {doi}` | Citation graph for a paper |
| `/literature:opencite doi {doi_or_title}` | Resolve a single identifier |

---

## Notes on opencite commands used in `/literature:card`

The `/literature:card` skill already uses opencite internally for:
- `uvx opencite ids "{input}"` — resolve DOI from title/PMID (Phase 1)
- `uvx opencite batch-fetch --from-stdin --convert -o {dir}/` — full-text fetch (Phase 2, Tier 1)

These work without API keys (PMC + CrossRef). This skill adds the **discovery** step
that comes before card intake.
