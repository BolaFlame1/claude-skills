# Claims Layer — Anti-Hallucination and Anti-Plagiarism Rules

This guide governs Phase 6 CLAIM in the literature card skill. A claim entry links a specific sentence in a manuscript to the card pointer and source line it is based on. Two failure modes are prevented mechanically: hallucination (the manuscript says something the paper never said) and plagiarism (the manuscript copies the source too closely).

---

## What is claims.md

`{project_root}/references/claims.md` is a reverse index: it maps from manuscript sentences back to card pointers and source lines. It does not replace citations — it audits them.

Each entry proves that:
1. The cited fact exists verbatim in source.md at a known line
2. The manuscript sentence is a genuine paraphrase (not a copy) of that fact

---

## Claim entry format

```markdown
## claim-{N}
- Manuscript section: {section heading or paragraph identifier}
- Manuscript sentence: "{exact sentence as it appears in the manuscript}"
- Card: {slug}
- Pointer: {label from card.md ## Key pointers}
- Source line: source.md:L{N} — "{verbatim quote from that line}"
- Paraphrase distance: {PASS | DIRECT-QUOTE | FLAG}
```

All six fields are required. Do not create a partial entry.

---

## Rule C1 — Source line must be grep-verified

Before writing any claim entry, confirm the source quote exists:

```bash
grep -n "{verbatim_quote}" {project_root}/references/cards/{slug}/source.md
```

- Returns ≥1 match → proceed
- Returns 0 matches → the pointer has drifted. Re-read source.md, find the correct line, update the card pointer, then write the claim entry.

**Never create a claim entry with an unverified source line.** A plausible-sounding quote that is not in source.md is hallucination.

---

## Rule C2 — Anti-plagiarism gate (mandatory before each entry)

Run the overlap check between the manuscript sentence and the verbatim source quote:

```bash
python3 - <<'EOF'
ms_words  = "{manuscript_sentence}".lower().split()
src_words = "{verbatim_quote}".lower().split()
windows   = [tuple(src_words[i:i+5]) for i in range(max(0, len(src_words)-4))]
hits      = [w for w in windows
             for j in range(max(0, len(ms_words)-4))
             if tuple(ms_words[j:j+5]) == w]
print("FLAG" if hits else "PASS")
EOF
```

| Result | Action |
|--------|--------|
| `PASS` | Record `Paraphrase distance: PASS` — proceed |
| `FLAG` | **Stop.** The sentence shares ≥5 consecutive words with the source. Rewrite the manuscript sentence until it passes, then create the entry. |

**Do not bypass this check.** Flagged sentences must be rewritten — not just split or slightly reordered. The test will catch simple rearrangements if the words are the same.

---

## Rule C3 — Direct quotation must be marked

If the manuscript intentionally quotes the source verbatim (block quote or in-text with quotation marks and page/line attribution), record:

```
- Paraphrase distance: DIRECT-QUOTE
```

This is the only valid exception to Rule C2. The quote must be enclosed in `"..."` or presented as a block quote in the manuscript, with explicit attribution including author and year. An unmarked verbatim sentence in running prose is not a direct quote — it is plagiarism.

---

## Rule C4 — One claim entry per cited fact

If a single manuscript sentence cites two cards, create two entries: `claim-{N}a` and `claim-{N}b`, each pointing to its own card and source line.

If a single card supports two separate sentences, create two entries with different `claim-{N}` numbers.

Do not bundle multiple facts into one claim entry.

---

## Rule C5 — Claim entries cannot cite training data

The `Source line` field must point to a line in `source.md`. It may not reference:
- A general claim from memory ("this is well established")
- A textbook or background knowledge
- Another claim entry (claims cannot chain)

If the manuscript sentence is background framing with no specific source, do not create a claim entry. Background framing belongs in the manuscript without a card citation.

---

## Rule C6 — Claim audit (`/literature:card claim-audit`)

Run the audit on the entire `claims.md` file at any time:

```bash
# For each claim entry, re-run Rule C1 (grep check) and Rule C2 (overlap check)
```

The audit reports:
- **Total claims:** N
- **Source link intact:** N (grep returned ≥1 match)
- **Broken source links:** N — list slug + pointer label for each
- **Paraphrase PASS:** N
- **Paraphrase FLAG:** N — list the offending manuscript sentence(s)
- **DIRECT-QUOTE entries:** N

A clean audit = all source links intact + all paraphrase checks PASS or DIRECT-QUOTE.

---

## What claims.md is NOT

- Not a bibliography — `key_papers.bib` is the bibliography
- Not a summary of each paper — card.md is the summary
- Not a replacement for in-text citations — the manuscript still uses `[@slug]` citations
- Not optional — every sentence that makes a specific factual claim attributed to a card should have an entry

---

## Example entry

```markdown
## claim-1
- Manuscript section: Introduction, paragraph 2
- Manuscript sentence: "Slow gait and subjective cognitive complaints co-occur at elevated rates in older adults with white matter hyperintensities."
- Card: beauchet-2016
- Pointer: Main finding
- Source line: source.md:L87 — "gait speed was significantly associated with WMH volume in community-dwelling older adults"
- Paraphrase distance: PASS
```

The manuscript sentence does not copy any 5-word run from the source quote — it reframes a single-variable association as a co-occurrence claim, which is appropriate paraphrase. The grep check on the source line returns a match. The entry is valid.
