# Anti-Hallucination Rules

Six rules enforced mechanically during Phase 4 EXTRACT. These are not suggestions — they are hard gates. Violating any one of them makes the card unreliable and defeats the purpose of the system.

---

## Rule 1 — Quote-locked

**Every pointer in `## Key pointers` must include both a line number and a verbatim quote.**

Format:
```
- {Label}: source.md:L{N} — "{verbatim text}"
```

The verbatim text must be an exact substring of line N in source.md. Verify:
```bash
grep -n "{verbatim_text}" references/cards/{slug}/source.md
```
If this returns 0 matches: the pointer is **invalid**. Do not write it. Use `NR` instead.

**Why:** Line numbers alone drift as source.md is re-converted. Quotes alone are ambiguous across papers. Together they create a two-part anchor that can be machine-checked.

**Violation example (do not do this):**
```
- Main finding: source.md:L142 — "gait speed was significantly reduced"
```
If the actual line says "gait speed was significantly lower", this is a hallucination even though it seems close. Run grep — it will return 0 matches.

---

## Rule 2 — Source-only

**No training data. No external recall. No "I know this paper says..."**

All information in card.md body must come from reading `source.md`, `source.pdf`, or `meta.json` in this session. If you haven't read a section of source.md yet, you don't know what it says.

For papers >500 lines, read in segments before writing any pointers:
```
Read source.md lines 1–300
Read source.md lines 301–600
Read source.md lines 601–end
```
Only after reading all segments may you begin writing pointers.

**Why:** Language models trained on published papers may "recall" findings that were in an earlier version, a different paper by the same author, or a common paraphrase in the literature. The source.md is the authoritative text for this card.

---

## Rule 3 — No-derive

**Never present a derived value as a direct finding.**

If a number appears in source.md, quote it. If you calculate something (e.g., percentage from raw counts, effect size from reported stats), mark it clearly:
```
- Effect size: [derived: Cohen's d = (M1−M2) / SD_pooled = (0.94−0.78)/0.21 = 0.76] — not directly reported
```

**Why:** Derived values are your calculation, not the authors'. Errors propagate invisibly if the derivation is presented as a direct finding.

---

## Rule 4 — NR over guessing

**If information is not explicitly in source.md, write `NR`.**

Do not:
- Infer follow-up duration from study design type
- Assume sample size from a related paper
- Extrapolate effect size from confidence intervals without flagging it as derived

```
- Follow-up: NR
```
Then note it in `## Open questions`:
```
## Open questions
- Follow-up duration not reported — relevant to dose-response interpretation
```

**Why:** `NR` is honest and actionable. A plausible-sounding guess is invisible contamination.

---

## Rule 5 — Self-verify

**After writing each pointer, run grep to confirm the quote exists.**

```bash
grep -n "{quoted_string}" references/cards/{slug}/source.md
```

Do this inline as you write each pointer — not as a batch audit at the end. If grep fails on any pointer, fix it before moving to the next.

The final grep audit at the end of Phase 4 is a second pass, not a substitute for per-pointer verification.

**Why:** OCR errors, encoding differences, and markdown formatting can silently change words. The grep check catches these before they become stale claims in a manuscript.

---

## Rule 6 — Full-paper coverage

**For papers > 500 lines, confirm you have read all sections before writing any pointers.**

Checklist before starting extraction:
- [ ] Abstract / summary read
- [ ] Introduction read
- [ ] Methods read in full
- [ ] Results read in full
- [ ] Discussion / conclusion read
- [ ] Tables and figure captions read (they often contain key numbers)

If any section was skipped: read it before proceeding.

**Why:** The primary finding is often qualified or contradicted in a later section. Reading only the abstract or results section misses these qualifications and produces confident-sounding but incomplete cards.

---

---

## Rule 7 — Claims layer: paraphrase, not copy

**When a card pointer is used to support a manuscript sentence, the sentence must pass the 5-word overlap check before the claim entry is written.**

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

- `PASS` → claim entry is valid
- `FLAG` → rewrite the manuscript sentence before creating the entry

**Why:** Quote-locked pointers are verbatim by design. Without a paraphrase check at the manuscript stage, those exact phrases migrate from source.md into the manuscript prose — correct attribution, but still text duplication. The 5-consecutive-word threshold matches most journal plagiarism detection thresholds (iThenticate, Turnitin).

**Applies only to:** Phase 6 CLAIM entries. Card pointers in `card.md` are verbatim by design (Rules 1 and 5) — Rule 7 does not apply there.

See `references/claims-guide.md` for the full claims layer protocol.

---

## Summary checklist before finalizing card.md

Run this mental check for every pointer before saving:

1. Is the exact quote findable via `grep`? ✓
2. Is it from source.md (not from memory)? ✓
3. If I calculated a value, is it marked `[derived:]`? ✓
4. For missing info, did I write `NR` (not a guess)? ✓
5. Did I grep verify this pointer already? ✓
6. Have I read the full paper before writing this? ✓
7. If writing a manuscript claim, did the paraphrase check return PASS? ✓

All seven must be true. If any is false, fix it first.
