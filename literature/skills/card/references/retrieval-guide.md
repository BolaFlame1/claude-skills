# Retrieval Guide

Detailed steps for each retrieval tier. The skill SKILL.md gives the commands; this file explains the decision logic and failure patterns.

---

## Tier 1 — opencite open access

**When it works:** Paper is open access (PubMed Central, PLoS, BioRxiv, MedRxiv, or publisher provides free PDF).

**Command:**
```bash
uvx opencite batch-fetch --dois "{doi}" --convert -o {project_root}/references/cards/{slug}/
```

**Expected output:** `source.md` (markdown) and optionally `source.pdf`.

**Common failures:**
- `404 Not Found` — paper is paywalled, not in OA. Move to Tier 2.
- `source.md` created but < 300 lines — likely fetched landing page or abstract only. Inspect first 20 lines to confirm. If abstract only, move to Tier 2.
- `ConnectionError` — network issue. Retry once, then move to Tier 2.

---

## Tier 2 — PMC fulltext HTML

**When it works:** Paper is on PubMed Central (most NIH-funded research, older papers after embargo).

**Get PMCID from opencite ids output:**
```bash
uvx opencite ids "{doi}"
```
Look for `pmcid: PMC{N}` in the output. If absent, skip Tier 2.

**Command:**
```bash
uvx opencite convert "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid}/" -o {project_root}/references/cards/{slug}/source.md
```

**Inspect result:** Check line count and Methods/Results headings before Phase 3. PMC HTML conversion is usually high quality.

**Common failures:**
- PMCID not in opencite ids output → skip Tier 2
- Page converts to navigation menu only → PMC doesn't have full text for this paper. Move to Tier 3.

---

## Tier 3 — Sci-Hub MCP

**When it works:** Paper exists in Sci-Hub's database (most published journal articles ≥ 2010).

**Prerequisite:** `mcp__sci-hub` must appear in available MCP tools. Check by looking for it in the session's tool list. If absent, skip Tier 3.

**Tool call:**
```
mcp__sci-hub__fetch_paper
  doi: "{doi}"
  output_dir: "{project_root}/references/cards/{slug}/"
```

**If the tool returns a PDF path:**
```bash
uvx opencite convert {project_root}/references/cards/{slug}/source.pdf -o {project_root}/references/cards/{slug}/source.md
```

**Common failures:**
- Sci-Hub doesn't have the paper (error 404 or empty result) → move to Tier 4
- PDF is scanned (image-only), OCR quality poor → `md_quality: partial`, note in INTEGRITY_ISSUES.md, proceed with caution
- MCP not installed → skip to Tier 4

---

## Tier 4 — KUMC via Playwright

**When to use:** Only when Tiers 1–3 all failed. Requires manual Duo MFA — do not attempt silently.

**Step 0 — Notify user:**
> "Tiers 1–3 failed for `{doi}`. Attempting KUMC login — please complete the Duo push when prompted."

**Step 1 — Open KUMC PubMed proxy:**
```
mcp__playwright__browser_navigate
  url: "https://pubmed-ncbi-nlm-nih-gov.kumc.idm.oclc.org/?otool=kumclib"
```

**Step 2 — Wait for login page, then take screenshot:**
```
mcp__playwright__browser_take_screenshot
```
Inspect screenshot to confirm the KUMC SSO login page loaded.

**Step 3 — Fill credentials if prompted:**
The user's KUMC username is their email prefix. Do NOT auto-fill password — ask the user to type it themselves or use the browser if it's saved.

**Step 4 — Wait for Duo push:**
After credential submission, Duo will send a push notification to the user's phone. Poll with screenshots every 10 seconds until the dashboard appears (max 60 seconds).
```
mcp__playwright__browser_take_screenshot
```
Success indicator: URL changes to pubmed.ncbi.nlm.nih.gov domain without the proxy redirect.

**Step 5 — Navigate to paper:**
```
mcp__playwright__browser_navigate
  url: "https://doi-org.kumc.idm.oclc.org/{doi}"
```
Or search PubMed for the paper title and navigate to the publisher full-text link.

**Step 6 — Download PDF:**
Look for a "Download PDF" or "Full Text PDF" button. Click it:
```
mcp__playwright__browser_find
  query: "Download PDF"
```
```
mcp__playwright__browser_click
  element: {result from find}
```
Save to `{project_root}/references/cards/{slug}/source.pdf`.

**Step 7 — Convert:**
```bash
uvx opencite convert {project_root}/references/cards/{slug}/source.pdf -o {project_root}/references/cards/{slug}/source.md
```

**Common failures:**
- Duo push times out → ask user to retry, then try again
- Publisher doesn't serve PDF directly (requires DRM viewer) → note in INTEGRITY_ISSUES.md, ask user to manually download PDF and place at `source.pdf`
- Session expires mid-navigation → restart from Step 1

---

## Tier 5 — Manual fallback

Update `meta.json`:
```json
{
  "md_quality": "not-retrieved",
  "retrieved_tier": null,
  "integrity_issues": ["all tiers failed: {brief reason for each}"]
}
```

Update INDEX.md: change status column to `blocked: retrieval-failed`.

Report to user with exact path: "Place the PDF at `references/cards/{slug}/source.pdf`, then run `/literature:card verify {slug}` to continue from Phase 3."

---

## After retrieval: what format is source.md expected in?

Regardless of tier, `source.md` must be a plain markdown file. The skill never distinguishes between PDF-derived and HTML-derived source.md — they are treated identically in Phase 3 and Phase 4.

Minimum structure for a valid source.md:
- Line 1: title (often as `# Title`)
- Author list within first 50 lines
- DOI string somewhere in the document
- A `## Methods` (or `# Methods`) section
- A `## Results` (or `# Results`) section
- At least 300 lines total
