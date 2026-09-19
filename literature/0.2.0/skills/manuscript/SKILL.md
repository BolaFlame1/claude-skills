---
name: manuscript
description: "Use this skill for \"new manuscript\", \"start a paper\", \"scaffold a manuscript\", \"create build_doc\", \"new project manuscript\", \"set up manuscript builder\", \"create manuscript template\", or when the user wants to start writing a new academic paper and needs the build_doc.py infrastructure."
version: 0.2.0
---

# Manuscript Scaffold Skill

Scaffolds a new manuscript project using the standard `build_doc.py` builder. Creates a runnable Python manuscript builder pre-loaded with the correct citation infrastructure (`[@slug]` format), document style (Times New Roman 12pt, 1-inch margins, double spacing), and section structure. Compatible with `/literature:card` (card intake) and `/literature:claim-audit` (citation audit).

---

## What this skill creates

```
{project_dir}/
  build_doc.py          ← manuscript builder (copy of template, customised)
  references/
    key_papers.bib      ← empty, ready for card intake
    INDEX.md            ← empty, ready for card intake
    cards/              ← empty, cards added via /literature:card
```

---

## Phase 1 — Gather inputs

Ask the user for:
1. **Project directory** — absolute path where files should be created
2. **Paper title** — full title (will appear centred, bold, 14pt on title page)
3. **Short title** — running head (≤60 chars)
4. **Output filename** — e.g. `manuscript_v1.docx` (default: `manuscript_v1.docx`)

If the user provides these upfront (e.g. `/literature:manuscript new --title "..." --dir /path/`), skip asking.

---

## Phase 2 — Check for conflicts

```bash
ls {project_dir}/build_doc.py 2>/dev/null
```
If file exists → abort: "A `build_doc.py` already exists at `{project_dir}`. Use `/literature:manuscript update` to modify it."

---

## Phase 3 — Scaffold

### Step 3.1 — Create references directory structure

```bash
mkdir -p {project_dir}/references/cards
```

### Step 3.2 — Create empty key_papers.bib

```
% key_papers.bib — populated by /literature:card
```

### Step 3.3 — Create INDEX.md

```markdown
| slug | title | year | status | date_added |
|------|-------|------|--------|------------|
```

### Step 3.4 — Copy and customise build_doc.py

Read the template from `references/build_doc_template.py` (in this skill's references folder). Then substitute:

| Placeholder | Replace with |
|---|---|
| `MANUSCRIPT_TITLE` | User's paper title |
| `MANUSCRIPT_SHORT_TITLE` | User's short title |
| `OUTFILE_NAME` | User's output filename |
| `AUTHOR_LINE` | Leave as `[Author 1]¹, [Author 2]², ..., [Corresponding Author]†` |
| `AFFILIATION_1` | Leave as `[Affiliation 1]` |
| `CORRESPONDING_DETAILS` | Leave as `[Name, credentials. Institution. Email: email@institution.edu]` |

Write the customised file to `{project_dir}/build_doc.py`.

---

## Phase 4 — Verify

```bash
cd {project_dir} && python3 build_doc.py
```

Should produce `{output_filename}` with Lorem ipsum content and no errors. If it fails, diagnose and fix before reporting success.

---

## Phase 5 — Report

Tell the user:
- Files created and their paths
- How to add the first citation: `/literature:card doi:{doi}`
- How to write citations in prose: `[@slug]` inline in `add_para()` calls
- How to audit citations when done: `/literature:claim-audit {project_dir}`

---

## Updating an existing manuscript

Command: `/literature:manuscript update {project_dir}`

Use this to:
- Add a new section (add `add_heading` + `add_para` block)
- Change citation style (`CITATION_STYLE = "author-year"`)
- Add authors or affiliations to the title page
- Bump output filename (`manuscript_v2.docx`)

Never run this to change prose that is already in `build_doc.py` — edit `build_doc.py` directly for prose changes.

---

## Citation convention (critical — do not deviate)

All citations in `build_doc.py` use this format:
```python
add_para(doc, "Sentence text [@slug] more text [@slug2; @slug3].")
```

- `[@slug]` — single citation
- `[@slug1; @slug2]` — multiple citations, semicolon-separated
- `slug` = BibTeX key = card slug from `/literature:card`

`resolve_cites()` in `build_doc.py` converts these to numbered superscripts at build time. **Do not write formatted citations directly** — always use `[@slug]`.

This convention is what `/literature:claim-audit` scans for. If a different format is used, the audit will not find the citations.
