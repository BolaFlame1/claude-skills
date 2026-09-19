# Project Configuration Guide

Each project can extend the base card.md template with project-specific frontmatter fields by placing a `card-config.yaml` in `references/`. The skill reads this during Phase 1 INIT.

---

## File location

```
{project_root}/references/card-config.yaml
```

The skill looks for this file at the start of Phase 1. If absent, it uses the base template (no extra fields).

---

## Format

```yaml
# references/card-config.yaml
project: {project-identifier}
extra_frontmatter_fields:
  field_name_1: ""
  field_name_2: ""    # optional inline comment for allowed values
  field_name_3: ""
extraction_labels:
  - "{Label 1}"       # replaces or extends the default pointer labels in Phase 4
  - "{Label 2}"
```

- `project` — short identifier (no spaces). Used for display only, not stored in card.md.
- `extra_frontmatter_fields` — dict of field names to default values. Empty string `""` means "to be filled during extraction". Inline comments show allowed values.
- `extraction_labels` — optional list of pointer label names used in Phase 4 Step 4.1. When present, **replaces** the default six labels (Study design, Sample size, Population, Primary outcome, Main finding, Follow-up). List only the labels your project needs — the skill will require all of them to be either filled or marked `NR`.

---

## extraction_labels — when to use

Use `extraction_labels` when your systematic review or project requires standardized data extraction that differs from the generic defaults. For example:
- A neuroimaging SR needs `Neuroimaging modality`, `WMH measure`, `MCR definition` — not `Study design` / `Follow-up`
- A drug trial SR needs `Intervention`, `Comparator`, `Primary endpoint`, `GRADE certainty`

If `extraction_labels` is absent, the default six labels apply.

---

## Existing project configs

### MCR Neuroimaging Systematic Review

```yaml
project: MCR-neuroimaging-SR
extra_frontmatter_fields:
  mcr_definition: ""             # how the paper defines MCR (e.g., slow gait + subjective memory complaint)
  neuroimaging_modality: ""      # MRI | DTI | fMRI | PET | fNIRS | EEG
  neuroimaging_measure: ""       # WMH | cortical thickness | FA | CBF | etc.
  eligibility_status: ""         # included | excluded | background-reference
  exclusion_reason: ""           # only if eligibility_status = excluded
  mcr_n: ""                      # N with MCR
  control_n: ""                  # N in comparison group
```

### HAALSI / SAGE

```yaml
project: HAALSI-SAGE
extra_frontmatter_fields:
  dataset: ""                    # HAALSI | SAGE | HCAP | other
  lmic_country: ""               # South Africa | LMIC-general | etc.
  dementia_outcome: ""           # incident-dementia | cognitive-impairment | MCI | MCR
  gait_measure: ""               # gait-speed | TUG | step-count | none
  hearing_measure: ""            # audiometry | HHIE | self-report | none
  eligibility_status: ""         # included | excluded | background-reference
```

### ARIC / Slow Gait Africa SR

```yaml
project: ARIC
extra_frontmatter_fields:
  exposure: ""                   # gait-speed | gait-variability | MCR | dual-task | etc.
  outcome: ""                    # dementia | MCI | cognitive-decline | mortality
  analysis_type: ""              # cohort | RDD | IV | mediation | descriptive
  population: ""                 # ARIC | general-community | clinical | other
  eligibility_status: ""         # included | excluded | background-reference
```

---

## How extra fields are filled

During Phase 4 EXTRACT, extra fields follow the same quote-locked rules as base fields. For each extra field:

1. Search source.md for the relevant information
2. If found: write the value (exact text or standardized controlled-vocabulary value where specified)
3. If not found: write `NR`
4. Log the source line in `## Key pointers` if the field is substantive (e.g., `mcr_definition`, `neuroimaging_measure`)

For binary/categorical fields with controlled vocabulary (e.g., `eligibility_status`): pick from the allowed values in the inline comment. Do not invent new values.

---

## Adding a new project config

1. Create `{project_root}/references/card-config.yaml` with the fields your project needs
2. Fields should be snake_case, all lowercase
3. Include inline comments for any field with controlled vocabulary
4. Existing cards in that project will not be retroactively updated — new fields only apply to cards created after the config file exists
5. If you need to backfill existing cards: use `/literature:card update {slug}` for each

---

## What NOT to put in card-config.yaml

- Fields that belong in the card body (pointers, eligibility reasoning) — those go in card.md body sections
- Computed or derived fields — mark those with `[derived:]` in card.md
- File paths or system configuration — those belong in the manuscript's own build config
