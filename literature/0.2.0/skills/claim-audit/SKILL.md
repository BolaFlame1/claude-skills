---
name: claim-audit
description: "Use this skill for \"audit citations\", \"check citations\", \"validate claims\", \"check my references\", \"audit my manuscript\", \"claim audit\", \"citation check\", \"plagiarism check\", \"verify citations\", or when the user wants to verify that manuscript citations are accurate and that no sentences copy verbatim from source papers."
version: 0.2.0
---

# Claim Audit Skill

Scans a `build_doc.py` manuscript builder for all `[@slug]` citations, extracts the sentence around each one, loads the cited card's `source.md`, and checks:
1. **Plagiarism gate** — does the manuscript sentence share ≥5 consecutive words with any quote in the card's `source.md`?
2. **Hallucination gate** — does the card exist and have a `source.md` with content?

Produces a report: pass / flag per citation, plus a summary.

---

## Prerequisite

- `build_doc.py` exists in the project directory and uses `[@slug]` citation format
- `references/cards/{slug}/source.md` exists for each cited slug (created by `/literature:card`)

---

## Phase 1 — Locate files

```bash
# Find build_doc.py
ls {project_dir}/build_doc.py

# Find references directory
ls {project_dir}/references/cards/
```

If `build_doc.py` not found → ask user for the correct path.
If `references/cards/` not found → abort: "No cards directory found. Run `/literature:card` to add papers first."

---

## Phase 2 — Extract all citations

Run this Python script to extract every `[@slug]` citation and its surrounding sentence:

```bash
python3 - <<'PYEOF'
import re, sys

with open("{project_dir}/build_doc.py", encoding="utf-8") as f:
    source = f.read()

# Extract string content from add_para() calls
para_pattern = re.compile(r'add_para\s*\(\s*doc\s*,\s*((?:"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'))', re.MULTILINE)
cite_pattern  = re.compile(r'\[@([^\]]+)\]')

results = []
for pm in para_pattern.finditer(source):
    raw = pm.group(1).strip().strip('"""').strip("'''").strip('"').strip("'")
    # Flatten multiline string concatenations
    raw = re.sub(r'"\s*\n\s*"', ' ', raw)
    raw = re.sub(r"'\s*\n\s*'", ' ', raw)
    for cm in cite_pattern.finditer(raw):
        slugs = [s.strip() for s in cm.group(1).split(';')]
        # Extract sentence around the citation
        before = raw[:cm.start()]
        after  = raw[cm.end():]
        sent_start = max(before.rfind('. ') + 2, before.rfind('\n') + 1, 0)
        sent_end_rel = after.find('. ')
        sent_end = cm.end() + (sent_end_rel + 1 if sent_end_rel >= 0 else len(after))
        sentence = raw[sent_start:sent_end].strip()
        for slug in slugs:
            results.append((slug, sentence))

for slug, sentence in results:
    print(f"SLUG: {slug}")
    print(f"SENT: {sentence}")
    print("---")
PYEOF
```

Parse the output into a list of `(slug, sentence)` pairs.

---

## Phase 3 — Audit each citation

For each `(slug, sentence)` pair:

### Step 3.1 — Check card exists

```bash
ls {project_dir}/references/cards/{slug}/source.md 2>/dev/null
```

- Found → proceed to Step 3.2
- Not found → mark as `MISSING_CARD` and continue to next

### Step 3.2 — Extract text from source.md

```bash
grep -v "^#\|^---\|^\s*$" {project_dir}/references/cards/{slug}/source.md | head -200
```

Store all non-blank, non-heading lines as the card's text corpus.

### Step 3.3 — Run 5-word overlap check

```bash
python3 - <<'PYEOF'
import re

ms_raw  = """{sentence}"""
src_raw = """{card_text}"""

def tokenise(t):
    return re.sub(r'[^\w\s]', '', t.lower()).split()

ms_words  = tokenise(ms_raw)
src_words = tokenise(src_raw)

hits = []
for i in range(len(src_words) - 4):
    window = tuple(src_words[i:i+5])
    for j in range(len(ms_words) - 4):
        if tuple(ms_words[j:j+5]) == window:
            hits.append(' '.join(window))
            break

if hits:
    print("FLAG")
    for h in set(hits):
        print(f"  overlap: \"{h}\"")
else:
    print("PASS")
PYEOF
```

- `PASS` → record as clean
- `FLAG` → record overlapping phrase(s) — the sentence needs rewriting

---

## Phase 4 — Report

Print a structured report:

```
══════════════════════════════════════════════
  CLAIM AUDIT — {project_dir}
  {date}
══════════════════════════════════════════════

Total citations found:    {N}
Cards present:            {N_present}
Missing cards (no source.md): {N_missing}

Plagiarism check:
  PASS:   {N_pass}
  FLAG:   {N_flag}

──────────────────────────────────────────────
FLAGGED CITATIONS
──────────────────────────────────────────────
{For each FLAG:}
  Slug:      {slug}
  Sentence:  "{sentence}"
  Overlap:   "{overlapping phrase}"
  Action:    Rewrite the sentence to remove the overlap, then re-run.

──────────────────────────────────────────────
MISSING CARDS
──────────────────────────────────────────────
{For each MISSING_CARD:}
  [@{slug}] — no source.md found.
  Action: run /literature:card doi:{doi} to retrieve full text.

══════════════════════════════════════════════
{N_flag} flag(s), {N_missing} missing card(s). {"CLEAN" if both 0 else "ACTION REQUIRED"}
══════════════════════════════════════════════
```

---

## What this does NOT check

- Whether the cited paper actually supports the manuscript's claim (hallucination at the semantic level) — that requires human judgment
- Citations in tables or figure legends (not inside `add_para()` calls)
- Whether the BibTeX entry is correct — use `/literature:card bib {slug}` for that

---

## Quick reference

| Command | Effect |
|---------|--------|
| `/literature:claim-audit {project_dir}` | Full audit of all citations in build_doc.py |
| `/literature:claim-audit {project_dir} --slug {slug}` | Audit only citations to one card |
