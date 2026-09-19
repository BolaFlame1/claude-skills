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

## Tier 3 — Sci-Hub

**When it works:** Paper exists in Sci-Hub's database (most published journal articles ≥ 2010).

Sci-Hub mirror reachability changes day-to-day (DNS blocks, certificate issues, robot checks). Always try **Step A** first (MCP tool, fast); if it fails fall through to **Step B** (Playwright, more robust).

### Step A — Sci-Hub MCP tool (try first)

**Prerequisite:** `mcp__sci-hub` must be connected (`claude mcp list` shows it with ✓). The actual tool names are:
- `mcp__sci-hub__download_pdf` — downloads PDF to a path
- `mcp__sci-hub__get_paper_link` — returns a download URL without downloading

**Tool call:**
```
mcp__sci-hub__download_pdf
  doi: "{doi}"
  download_location: "{project_root}/references/cards/{slug}/source.pdf"
```

**If it succeeds** (no "all domains are unreachable" error):
```bash
uvx opencite convert {project_root}/references/cards/{slug}/source.pdf -o {project_root}/references/cards/{slug}/source.md
```
Done — skip Step B.

**If it returns "all domains are unreachable"** → proceed to Step B.

---

### Step B — Playwright on sci-hub.ru (fallback, always works)

sci-hub.ru resolves reliably. Use the Playwright browser to navigate there — it handles SSL and robot checks that curl and the MCP cannot.

**Step B1 — Navigate:**
```
mcp__playwright__browser_navigate
  url: "https://sci-hub.ru/{doi}"
```

**Step B2 — Check for robot page:**
Take a snapshot. If the title contains "are you a robot", click the "No" button:
```
mcp__playwright__browser_click
  target: {ref of the "No" element from snapshot}
```
Then navigate to `https://sci-hub.ru/{doi}` again.

**Step B3 — Extract PDF URL from snapshot:**
The snapshot will contain a link whose `/url` ends in `.pdf`. It may be on `sci-hub.ru` or `sci-hub.red` storage. Example:
```yaml
- link [ref=fXXXeYY]:
    /url: //sci-hub.red/storage/moscow/1234/abc.../paper.pdf
```
Prepend `https:` if the URL starts with `//`.

**Step B4 — Download with curl:**
```bash
curl -Lk -A "Mozilla/5.0" "{pdf_url}" \
  -o "{project_root}/references/cards/{slug}/source.pdf" \
  --max-time 60
```
The `-k` flag is needed because sci-hub.red uses a self-signed certificate. `-L` follows redirects.

**Step B5 — Convert:**
```bash
uvx opencite convert {project_root}/references/cards/{slug}/source.pdf \
  -o {project_root}/references/cards/{slug}/source.md
```

**Common failures:**
- sci-hub.ru robot check loops (click "No" repeatedly doesn't help) → wait 30 seconds and retry once
- No PDF link appears in snapshot → paper not in Sci-Hub database → move to Tier 4
- `curl` gets a 403 or HTML page instead of PDF (check file size < 10KB) → the storage URL expired; re-navigate in Playwright to get a fresh link
- PDF is scanned image-only, OCR quality poor → `md_quality: partial`, note in INTEGRITY_ISSUES.md, proceed with caution

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
