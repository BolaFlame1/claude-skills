# BibTeX Verification Protocol

Run this during Phase 4 EXTRACT after `source.md` passes the full-text gate. The goal is to ensure `key_papers.bib` contains accurate, complete metadata — not just a skeleton — before the card is marked `extracted`.

---

## What to verify

Cross-check these fields between `key_papers.bib` and the title page of `source.md` (first 50 lines):

| BibTeX field | Source to check against | Common errors |
|---|---|---|
| `author` | Author list in source.md | Initials swapped, surname misspelled, missing co-authors, "et al" instead of full list |
| `year` | Publication year in source.md | Preprint year vs. journal year; epub-ahead-of-print vs. print year |
| `journal` | Journal name in source.md | Abbreviated vs. full name (use the journal's official title exactly) |
| `volume` | Header/footer or source.md metadata | Wrong volume; absent when it should be present |
| `pages` | Same | Page range vs. article number (use article number if journal uses them) |
| `doi` | DOI in source.md | Typo; old DOI vs. current DOI; missing `10.` prefix |
| `title` | Exact title in source.md | Subtitle truncated; capitalization wrong; subtitle separator wrong (`:` vs `—`) |

---

## Verification commands

```bash
# Get first 50 lines of source.md (title page)
head -50 references/cards/{slug}/source.md

# Find DOI in source.md
grep -i "doi\|10\." references/cards/{slug}/source.md | head -5

# Find author list
grep -i "author\|^\*\|^[A-Z][a-z].*,[[:space:]][A-Z]" references/cards/{slug}/source.md | head -10

# Find journal name (usually in header/footer or metadata block)
grep -i "journal\|published\|©\|volume\|vol\." references/cards/{slug}/source.md | head -10
```

---

## Correction procedure

If any field is wrong:

1. **Correct `key_papers.bib` in-place** — do not create a new entry, edit the existing one
2. **Log the correction** in `{project_root}/references/INTEGRITY_ISSUES.md`:
   ```
   ## {slug} — BibTeX correction — {YYYY-MM-DD}
   - Field: {field name}
   - Was: {wrong value}
   - Now: {correct value}
   - Source: source.md:L{N} — "{verbatim evidence}"
   ```
3. **Update `meta.json`**:
   ```json
   "bibtex_integrity": "corrected",
   "integrity_issues": ["BibTeX field '{field}' corrected on {date}"]
   ```
4. **Set `bibtex_verified: true`** in `card.md` frontmatter **only after all fields are confirmed**

---

## Marking verified

After all fields checked and corrected:

In `card.md` frontmatter:
```yaml
bibtex_verified: true
```

In `meta.json`:
```json
"bibtex_integrity": "verified"
```

If a field could not be confirmed (not present in source.md and not in Crossref metadata):
```yaml
bibtex_verified: partial
```
And note which field in `meta.json` `integrity_issues`.

---

## BibTeX entry format

Use this format in `key_papers.bib`:

```bibtex
@article{slug,
  author  = {Surname1, Firstname1 and Surname2, Firstname2 and Surname3, Firstname3},
  title   = {Exact Title of the Paper: Including Subtitle},
  journal = {Full Journal Name},
  year    = {2024},
  volume  = {15},
  pages   = {e0123456},
  doi     = {10.1234/journal.pone.0123456}
}
```

Notes:
- `author` field: `Surname, Firstname and Surname, Firstname` — always full names, never initials-only
- `title` field: Title case unless the journal uses sentence case (match the paper exactly)
- `pages` field: Use article number (e.g., `e0123456`) for journals that publish by article number, not page range
- `doi` field: DOI only, no `https://doi.org/` prefix

---

## The BibTeX key

The BibTeX key (first field after `@article{`) is the card slug: `{firstauthor}-{year}[-{keyword}]`.

This is also the `[@key]` marker used in manuscripts. When `build.py` processes `[@beauchet-2016]`, it looks up the key `beauchet-2016` in `key_papers.bib`. If the key doesn't exist there, build fails.

Never change a slug after it has been used in a manuscript — it will break all `[@slug]` citations in the prose.
