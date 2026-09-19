#!/usr/bin/env python3
"""
citation_convert v5 — project-aware mode + CrossRef metadata validation.

New in v5 (--project mode):
  Reads references/cite_map.json + references/key_papers.bib for guaranteed-
  correct DOIs and reference numbers — no reference-list text parsing needed.
  Runs CrossRef validation on every entry: retraction screening, first-author
  surname match, and print-year verification before converting the docx.

Original behaviour (no --project flag) is unchanged for standalone use.

Usage:
    # Project-aware (recommended — uses build_doc.py citation map):
    python3 convert.py manuscript_v1.docx --project /path/to/project

    # Standalone (parses reference list from docx):
    python3 convert.py manuscript_v1.docx [--email EMAIL] [--dry-run]

Outputs:
  <stem>_endnote.docx   — citations replaced with {Author, Year #N}
  <stem>.ris            — combined RIS file for EndNote import
"""

import argparse
import json
import re
import shutil
import sys
import time
import unicodedata
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

try:
    import requests
except ImportError:
    sys.exit("pip install requests")


# ── 0. BibTeX parser (mirrors build_doc_template.py load_bib) ───────────────

def bib_parse(bib_path):
    """
    Parse key_papers.bib → {slug: {doi, year, author, annote}} dict.
    Identical logic to load_bib() in build_doc_template.py.
    """
    p = Path(bib_path)
    if not p.exists():
        return {}
    raw = p.read_text(encoding="utf-8")
    entries = {}
    for block in re.split(r'\n(?=@)', raw):
        block = block.strip()
        if not block:
            continue
        m = re.match(r'@\w+\{([^,]+),', block)
        if not m:
            continue
        key = m.group(1).strip()

        def _field(name, text):
            pat = re.search(rf'\b{name}\s*=\s*\{{(.*?)\}}\s*[,\n}}]', text, re.DOTALL)
            return pat.group(1).strip() if pat else ''

        entries[key] = {
            'doi':    _field('doi',    block),
            'year':   _field('year',   block),
            'author': _field('author', block),
            'annote': _field('annote', block),
        }
    return entries


# ── 0b. Project-aware loading ─────────────────────────────────────────────────

def load_cite_map(project_dir):
    """
    Load references/cite_map.json produced by build_doc.py.
    Returns {slug: {"number": int, "doi": str}}.
    """
    p = Path(project_dir) / "references" / "cite_map.json"
    if not p.exists():
        raise FileNotFoundError(
            f"cite_map.json not found at {p}.\n"
            "Run 'python3 build_doc.py' first to generate it."
        )
    return json.loads(p.read_text(encoding="utf-8"))


def project_refs(cite_map, bib):
    """
    Build a refs list from cite_map + bib, bypassing docx reference-list
    parsing. Each entry matches the shape expected by the rest of the pipeline.
    Returns list of dicts sorted by reference number.
    """
    refs = []
    for slug, info in cite_map.items():
        doi = info.get("doi") or bib.get(slug, {}).get("doi") or ""
        annote = bib.get(slug, {}).get("annote", slug)
        refs.append({
            "num":   int(info["number"]),
            "doi":   doi.strip() if doi else None,
            "text":  annote,
            "slug":  slug,
        })
    return sorted(refs, key=lambda r: r["num"])


# ── 1. CrossRef validation ────────────────────────────────────────────────────

def _norm(s):
    """Lowercase + strip diacritics for fuzzy comparison."""
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def crossref_validate(doi, bib_entry, email):
    """
    Fetch CrossRef metadata for doi and compare against bib_entry.

    Checks:
      1. Retraction / expression-of-concern (critical)
      2. First-author surname match
      3. Print-year match (avoids epub-vs-print confusion)
      4. Journal name partial match

    Returns list of issue strings. Empty list = all clear.
    """
    issues = []
    headers = {"User-Agent": f"citation-convert/5.0 mailto:{email}"}

    try:
        r = requests.get(
            f"https://api.crossref.org/works/{doi}",
            headers=headers, timeout=15,
        )
        if r.status_code != 200:
            issues.append(f"CrossRef lookup failed (HTTP {r.status_code})")
            return issues

        data = r.json().get("message", {})

        # 1. Retraction / expression-of-concern
        updates = data.get("update-to", [])
        retracted = [u for u in updates
                     if any(w in u.get("type", "").lower()
                            for w in ("retract", "concern", "correction"))]
        if retracted:
            labels = [u.get("type", "?") for u in retracted]
            issues.append(f"ALERT: {', '.join(labels)}")
            return issues  # no need to validate further

        # 2. First-author surname
        cr_authors = data.get("author", [])
        if cr_authors:
            cr_first = _norm(cr_authors[0].get("family", ""))
            bib_author_raw = bib_entry.get("author", "")
            # BibTeX author field: "Surname, Given and Surname2, Given2 ..."
            bib_first = _norm(bib_author_raw.split(",")[0].strip()) if bib_author_raw else ""
            if cr_first and bib_first:
                if cr_first not in bib_first and bib_first not in cr_first:
                    issues.append(
                        f"Author: CrossRef '{cr_authors[0].get('family')}' "
                        f"≠ bib '{bib_author_raw.split(',')[0].strip()}'"
                    )

        # 3. Print year
        cr_year = None
        for field in ("published-print", "published"):
            parts = data.get(field, {}).get("date-parts", [[]])
            if parts and parts[0]:
                cr_year = parts[0][0]
                break
        bib_year = bib_entry.get("year", "")
        if cr_year and bib_year and str(cr_year) != str(bib_year):
            issues.append(f"Year: CrossRef '{cr_year}' ≠ bib '{bib_year}'")

        # 4. Journal (partial match — allow abbreviations)
        cr_journals = data.get("container-title", [])
        cr_journal = _norm(cr_journals[0]) if cr_journals else ""
        annote = bib_entry.get("annote", "")
        j_match = re.search(r"\*(.+?)\*", annote)
        bib_journal = _norm(j_match.group(1)) if j_match else ""
        if cr_journal and bib_journal:
            cr_words = set(cr_journal.split())
            bib_words = set(bib_journal.split())
            shared = cr_words & bib_words
            threshold = max(1, min(2, len(cr_words) - 1))
            if len(shared) < threshold:
                issues.append(
                    f"Journal: CrossRef '{cr_journals[0]}' "
                    f"vs bib '{j_match.group(1) if j_match else bib_journal}'"
                )

    except requests.RequestException as exc:
        issues.append(f"CrossRef request failed: {exc}")

    return issues


def run_validation(refs, bib, email):
    """
    Run CrossRef validation on all refs. Print a formatted report.
    Returns (n_ok, n_warn, n_alert) counts.
    """
    print("\n" + "═" * 60)
    print("  CrossRef Metadata Validation")
    print("═" * 60)

    n_ok, n_warn, n_alert = 0, 0, 0
    alerts = []

    for ref in refs:
        doi = ref.get("doi")
        slug = ref.get("slug", f"ref-{ref['num']}")
        num  = ref["num"]
        be   = bib.get(slug, {})

        if not doi:
            print(f"  [{num:2d}] {slug:<30}  ⚠  no DOI — skipped")
            n_warn += 1
            continue

        print(f"  [{num:2d}] {slug:<30}", end="", flush=True)
        issues = crossref_validate(doi, be, email)
        time.sleep(0.3)  # polite rate limit

        if not issues:
            print("  ✓ clean")
            n_ok += 1
        else:
            any_alert = any("ALERT" in i for i in issues)
            if any_alert:
                print(f"  ✗ {issues[0]}")
                n_alert += 1
                alerts.append((num, slug, issues))
            else:
                print(f"  ⚠  {' | '.join(issues)}")
                n_warn += 1

    print("─" * 60)
    print(f"  Clean: {n_ok}   Warnings: {n_warn}   Alerts: {n_alert}")
    if alerts:
        print("\n  ACTION REQUIRED:")
        for num, slug, issues in alerts:
            print(f"    [{num}] {slug}: {issues[0]}")
    print("═" * 60 + "\n")
    return n_ok, n_warn, n_alert


# ── 2. Extract plain text from docx ─────────────────────────────────────────

def docx_plain(docx_path):
    with zipfile.ZipFile(docx_path) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    xml = re.sub(r"</w:p>", "\n", xml)
    return re.sub(r"<[^>]+>", "", xml)


# ── 3. Extract reference list (standalone mode) ──────────────────────────────

def _extract_doi_from_text(text):
    for pat in (r"https?://doi\.org/(\S+)", r"\bdoi:\s*(\S+)"):
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).rstrip(".,)")
    return None


def extract_references(docx_path):
    text = docx_plain(docx_path)
    m = re.search(r"\n(?:References|REFERENCES|Bibliography)\n(.+)", text, re.DOTALL)
    if not m:
        raise ValueError("Cannot find 'References' section in document.")
    ref_text = m.group(1)

    refs = []
    bracket = list(re.finditer(r"\[(\d+)\]\s*(.+?)(?=\n\[|\Z)", ref_text, re.DOTALL))
    if bracket:
        for bm in bracket:
            body = " ".join(bm.group(2).split())
            refs.append({"num": int(bm.group(1)), "text": body,
                         "doi": _extract_doi_from_text(body)})
    else:
        for pm in re.finditer(r"(?:^|\n)(\d+)\.\s+(.+?)(?=\n\d+\.|\Z)", ref_text, re.DOTALL):
            body = " ".join(pm.group(2).split())
            refs.append({"num": int(pm.group(1)), "text": body,
                         "doi": _extract_doi_from_text(body)})

    if not refs:
        stop_words = ("figure legends", "figures", "tables", "footnotes", "supplementary")
        for i, line in enumerate(ref_text.splitlines(), 1):
            body = line.strip()
            if not body:
                continue
            if any(body.lower().startswith(w) for w in stop_words):
                break
            refs.append({"num": i, "text": " ".join(body.split()),
                         "doi": _extract_doi_from_text(body)})

    if not refs:
        raise ValueError("No numbered references found. Expected '[N] ...' or 'N. ...' format.")
    return refs


# ── 4. doi_overrides.json (standalone mode) ──────────────────────────────────

def load_overrides(docx_path):
    p = Path(docx_path)
    override_path = p.parent / (p.stem + ".doi_overrides.json")
    if override_path.exists():
        with open(override_path) as f:
            data = json.load(f)
        data.pop("_note", None)
        print(f"  Loaded overrides: {override_path.name} ({len(data)} entries)")
        return data
    return {}


def get_doi(ref, overrides):
    if ref.get("doi"):
        return ref["doi"]
    entry = overrides.get(str(ref["num"]), {})
    return entry.get("doi")


def get_manual_ris(ref, overrides):
    entry = overrides.get(str(ref["num"]), {})
    return entry.get("ris")


# ── 5. Fetch RIS (CrossRef → doi.org → PubMed) ───────────────────────────────

_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def _pubmed_search(query, email):
    try:
        r = requests.get(
            f"{_EUTILS}/esearch.fcgi",
            params={"db": "pubmed", "term": query, "retmode": "json",
                    "retmax": 1, "email": email},
            headers={"User-Agent": f"citation-convert/5.0 mailto:{email}"},
            timeout=15,
        )
        ids = r.json().get("esearchresult", {}).get("idlist", [])
        return ids[0] if ids else None
    except Exception:
        return None


def _pubmed_fetch_ris(pmid, email):
    try:
        r = requests.get(
            f"{_EUTILS}/efetch.fcgi",
            params={"db": "pubmed", "id": pmid, "rettype": "ris",
                    "retmode": "text", "email": email},
            headers={"User-Agent": f"citation-convert/5.0 mailto:{email}"},
            timeout=15,
        )
        if r.status_code == 200 and "TY  -" in r.text:
            return r.text.strip()
    except Exception:
        pass
    return None


def fetch_ris(doi, email):
    headers = {"User-Agent": f"citation-convert/5.0 mailto:{email}"}

    try:
        r = requests.get(
            f"https://api.crossref.org/works/{doi}/transform/application/x-research-info-systems",
            headers=headers, timeout=15,
        )
        if r.status_code == 200 and "TY  -" in r.text:
            return r.text.strip()
    except Exception:
        pass

    try:
        r = requests.get(
            f"https://doi.org/{doi}",
            headers={**headers, "Accept": "application/x-research-info-systems"},
            timeout=15, allow_redirects=True,
        )
        if r.status_code == 200 and "TY  -" in r.text:
            return r.text.strip()
    except Exception:
        pass

    pmid = _pubmed_search(f"{doi}[DOI]", email)
    if pmid:
        ris = _pubmed_fetch_ris(pmid, email)
        if ris:
            print(f"    → found via PubMed PMID:{pmid}")
            return ris

    return None


def fetch_ris_no_doi(ref_text, email):
    author_m = re.search(r"^([A-Z][a-záéíóúñü\-]+)", ref_text.strip())
    year_m   = re.search(r"\b(19|20)\d{2}\b", ref_text)
    if author_m and year_m:
        query = f"{author_m.group(1)}[Author] AND {year_m.group(0)}[PDAT]"
        pmid = _pubmed_search(query, email)
        if pmid:
            ris = _pubmed_fetch_ris(pmid, email)
            if ris:
                return ris, pmid

    words = ref_text.split()[:7]
    query = " ".join(words) + "[Title]"
    pmid = _pubmed_search(query, email)
    if pmid:
        ris = _pubmed_fetch_ris(pmid, email)
        if ris:
            return ris, pmid

    return None, None


# ── 6. Parse RIS entry ────────────────────────────────────────────────────────

def parse_ris(ris_text):
    author, year = "Unknown", 0
    for line in ris_text.splitlines():
        line = line.strip()
        tag = line[:2]
        val = line[6:].strip() if len(line) > 6 else ""
        if tag == "AU" and author == "Unknown" and val:
            author = val.split(",")[0].strip()
        elif tag in ("PY", "DA", "Y1") and not year and val:
            m = re.search(r"\b(19|20)\d{2}\b", val)
            if m:
                year = int(m.group(0))
    return author, year


# ── 7. Auto-detect citation style ────────────────────────────────────────────

def detect_style(docx_path):
    with zipfile.ZipFile(docx_path) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    plain = re.sub(r"<[^>]+>", "", xml)
    brackets = len(re.findall(r"\[\d+\]", plain))
    sups = len(re.findall(r'vertAlign w:val="superscript"', xml))
    parens = len(re.findall(r'\(\d{1,3}(?:,\s*\d{1,3})*\)', plain))
    if parens > brackets and parens > sups:
        return "paren"
    return "bracket" if brackets >= sups else "superscript"


# ── 8. Find citation patterns ─────────────────────────────────────────────────

def _find_body_start(xml):
    for marker in (">Abstract<", ">ABSTRACT<", ">Introduction<",
                   ">INTRODUCTION<", ">Background<", ">Summary<"):
        pos = xml.find(marker)
        if pos > 0:
            para = xml.rfind("<w:p ", 0, pos)
            return para if para > 0 else pos
    return 0


def find_all_patterns(docx_path, style):
    with zipfile.ZipFile(docx_path) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    plain = re.sub(r"<[^>]+>", "", xml)

    patterns = set()
    if style == "bracket":
        patterns |= set(re.findall(r"\[\d+(?:,\s*\d+)+\]", plain))
        for m in re.finditer(r"\[(\d+)\]", plain):
            ctx = plain[m.end():m.end() + 3]
            if not re.match(r"\s+[A-Z]", ctx):
                patterns.add(m.group(0))
    elif style == "paren":
        body_start = _find_body_start(xml)
        ref_start  = xml.find(">References<")
        body_xml   = xml[body_start:ref_start] if ref_start > 0 else xml[body_start:]
        body_plain = re.sub(r"<[^>]+>", "", body_xml)
        patterns |= set(re.findall(r'\(\d{1,3}(?:,\s*\d{1,3})+\)', body_plain))
        for m in re.finditer(r'\((\d{1,3})\)', body_plain):
            n = int(m.group(1))
            if 1 <= n <= 300:
                patterns.add(m.group(0))
    else:
        body_start = _find_body_start(xml)
        ref_start  = xml.find(">References<")
        body_xml   = xml[body_start:ref_start] if ref_start > 0 else xml[body_start:]
        for content in re.findall(
            r'<w:vertAlign w:val="superscript"[^>]*/>(?:[^<]*</w:rPr>)?<w:t[^>]*>([\d,\s]+)</w:t>',
            body_xml
        ):
            content = content.strip()
            nums = [int(n) for n in re.findall(r"\d+", content)]
            if nums and all(1 <= n <= 200 for n in nums):
                patterns.add(content)

    return patterns


# ── 9. Build citation map from RIS data ──────────────────────────────────────

def build_citation_map(refs, ris_data):
    cmap = {}
    for i, ref in enumerate(sorted(refs, key=lambda r: r["num"])):
        num = ref["num"]
        rec = i + 1
        ris = ris_data.get(num, "")
        author, year = parse_ris(ris) if ris else ("Unknown", 0)
        if author == "Unknown":
            m = re.search(r"[A-Z][a-záéíóúñü\-]+", ref["text"])
            author = m.group(0) if m else "Unknown"
        if not year:
            m = re.search(r"\b(19|20)\d{2}\b", ref["text"])
            year = int(m.group(0)) if m else 0
        cmap[num] = {
            "author":     author,
            "year":       year,
            "record_num": rec,
            "temp_cite":  f"{{{author}, {year} #{rec}}}",
        }
    return cmap


# ── 10. Build replacement table ───────────────────────────────────────────────

def build_replacements(patterns, cmap, style):
    repls = {}
    for pat in patterns:
        nums = [int(n) for n in re.findall(r"\d+", pat)]
        missing = [n for n in nums if n not in cmap]
        if missing:
            print(f"  WARNING: ref(s) {missing} in pattern '{pat}' not in reference list")
            continue
        if len(nums) == 1:
            repls[pat] = cmap[nums[0]]["temp_cite"]
        else:
            parts = [
                f"{cmap[n]['author']}, {cmap[n]['year']} #{cmap[n]['record_num']}"
                for n in nums
            ]
            repls[pat] = "{" + "; ".join(parts) + "}"
    return repls


# ── 11. Convert citations in docx XML ────────────────────────────────────────

PROOF = r"(?:<w:proofErr[^/]*/>\s*)*"


def _resolve_author(author_str, cmap):
    al = author_str.strip().lower()
    for num, info in cmap.items():
        if info["author"].lower() == al:
            return info
    return None


def convert_superscript_xml(xml, cmap):
    body_start = _find_body_start(xml)
    ref_start  = xml.find(">References<")
    if ref_start < 0:
        ref_start = len(xml)

    prefix = xml[:body_start]
    body   = xml[body_start:ref_start]
    tail   = xml[ref_start:]

    result = []
    pos = 0
    while pos < len(body):
        run_open = body.find("<w:r", pos)
        if run_open < 0:
            result.append(body[pos:])
            break
        result.append(body[pos:run_open])
        run_close = body.find("</w:r>", run_open)
        if run_close < 0:
            result.append(body[run_open:])
            break
        run_close += len("</w:r>")
        run_xml = body[run_open:run_close]
        pos = run_close

        if 'vertAlign w:val="superscript"' in run_xml:
            tm = re.search(r"<w:t[^>]*>([\d,\s]+)</w:t>", run_xml)
            if tm:
                content = tm.group(1).strip()
                nums  = [int(n) for n in re.findall(r"\d+", content)]
                valid = [n for n in nums if n in cmap]
                if valid:
                    if len(valid) == 1:
                        info = cmap[valid[0]]
                        cite = f"{{{info['author']}, {info['year']} #{info['record_num']}}}"
                    else:
                        parts = [
                            f"{cmap[n]['author']}, {cmap[n]['year']} #{cmap[n]['record_num']}"
                            for n in valid
                        ]
                        cite = "{" + "; ".join(parts) + "}"
                    result.append(f'<w:r><w:t xml:space="preserve"> {cite}</w:t></w:r>')
                    continue
        result.append(run_xml)

    return prefix + "".join(result) + tail


def convert_paren_xml(xml, repls, cmap):
    for old, new in sorted(repls.items(), key=lambda x: -len(x[0])):
        xml = xml.replace(old, new)
    return xml


def convert_bracket_xml(xml, repls, cmap):
    for old, new in sorted(repls.items(), key=lambda x: -len(x[0])):
        xml = xml.replace(old, new)

    def fix3(m):
        tag, pre, author, tail = m.group(1), m.group(2), m.group(3), m.group(4)
        info = _resolve_author(author, cmap)
        if not info:
            return m.group(0)
        cite = f"{{{author}, {info['year']} #{info['record_num']}}}"
        return f"{tag}{pre[:-1]}{cite}</w:t></w:r>"

    xml = re.sub(
        r"(<w:t[^>]*>)([^<]*\{)</w:t></w:r>" + PROOF +
        r"<w:r[^>]*><w:t[^>]*>([^<]+)</w:t></w:r>" + PROOF +
        r"<w:r[^>]*><w:t[^>]*>(, \d{4}[^<]*)\}</w:t></w:r>",
        fix3, xml, flags=re.DOTALL,
    )

    def fix4(m):
        run_open, pre, author, year_str = m.group(1), m.group(2), m.group(3), m.group(5)
        info = _resolve_author(author, cmap)
        if not info:
            return m.group(0)
        cite = f"{{{author}, {info['year']} #{info['record_num']}}}"
        return f'{run_open}<w:t xml:space="preserve">{pre[:-1]}{cite}</w:t></w:r>'

    xml = re.sub(
        r"(<w:r[^>]*><w:t[^>]*>)([^<]*\{)</w:t></w:r>" + PROOF +
        r"<w:r[^>]*><w:t[^>]*>([^<]+)</w:t></w:r>" + PROOF +
        r"<w:r[^>]*><w:t[^>]*>(, )</w:t></w:r>" + PROOF +
        r"<w:r[^>]*><w:t[^>]*>(\d{4}[^<]*)\}</w:t></w:r>",
        fix4, xml, flags=re.DOTALL,
    )
    return xml


# ── 12. Apply to docx ─────────────────────────────────────────────────────────

def apply_to_docx(src, dst, repls, cmap, style):
    import os
    tmp = str(dst) + ".tmp_convert"
    shutil.copy(src, tmp)

    with zipfile.ZipFile(tmp, "r") as zin, \
         zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/document.xml":
                xml = data.decode("utf-8")
                if style == "superscript":
                    xml = convert_superscript_xml(xml, cmap)
                elif style == "paren":
                    xml = convert_paren_xml(xml, repls, cmap)
                else:
                    xml = convert_bracket_xml(xml, repls, cmap)
                data = xml.encode("utf-8")
            zout.writestr(item, data)
    os.remove(tmp)

    with zipfile.ZipFile(dst) as z:
        raw = z.read("word/document.xml")
    try:
        ET.fromstring(raw)
    except ET.ParseError as e:
        print(f"  ERROR: XML invalid — {e}")
        return False

    plain = re.sub(r"<[^>]+>", "", raw.decode("utf-8"))
    bare  = [b for b in re.findall(r"\{[A-ZÀ-ž][^}#]{3,60}\}", plain) if "#" not in b]
    if bare:
        print(f"  WARNING: {len(bare)} citations still lack record numbers:")
        for b in set(bare):
            print(f"    {b}")
    else:
        print("  All citations have record numbers ✓")
    return True


# ── 13. Write combined RIS ────────────────────────────────────────────────────

def write_ris(ris_data, refs, ris_path):
    entries = []
    for ref in sorted(refs, key=lambda r: r["num"]):
        ris = ris_data.get(ref["num"])
        if ris:
            entries.append(ris.strip())
    ris_path.write_text("\n\n".join(entries) + "\n", encoding="utf-8")
    print(f"  RIS file → {ris_path}")


# ── 14. Main ──────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Convert numbered .docx citations to EndNote temp citations (v5)"
    )
    ap.add_argument("docx", help="Input .docx with numbered citations")
    ap.add_argument("--project", metavar="DIR",
                    help="Project root containing references/cite_map.json and "
                         "references/key_papers.bib (recommended for build_doc.py projects)")
    ap.add_argument("--output", help="Output .docx path")
    ap.add_argument("--ris",    help="Combined RIS output path")
    ap.add_argument("--email",  default="fakoredesodiq@gmail.com")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-validation", action="store_true",
                    help="Skip CrossRef validation (faster, but no metadata check)")
    args = ap.parse_args()

    src  = Path(args.docx).expanduser().resolve()
    stem = src.stem
    dst  = Path(args.output).resolve() if args.output else src.parent / f"{stem}_endnote.docx"
    risp = Path(args.ris).resolve()    if args.ris    else src.parent / f"{stem}.ris"

    print(f"\n{'='*60}")
    print("  Citation Converter v5  (CrossRef validated)")
    print(f"  Input : {src}")
    print(f"{'='*60}")

    # ── Project-aware mode ──────────────────────────────────────────────────
    if args.project:
        project_dir = Path(args.project).expanduser().resolve()
        print(f"\n  Mode: project-aware ({project_dir})")

        print("\n[1/4] Loading cite_map + bib...")
        cite_map = load_cite_map(project_dir)
        bib = bib_parse(project_dir / "references" / "key_papers.bib")
        refs = project_refs(cite_map, bib)
        print(f"  {len(refs)} references from cite_map.json")
        print(f"  {len(bib)} entries in key_papers.bib")

        missing_dois = [r for r in refs if not r.get("doi")]
        if missing_dois:
            print(f"  ⚠  {len(missing_dois)} refs have no DOI: "
                  f"{[r['slug'] for r in missing_dois]}")

        # CrossRef validation
        if not args.skip_validation:
            print("\n[2/4] CrossRef validation (author · year · retraction)...")
            n_ok, n_warn, n_alert = run_validation(refs, bib, args.email)
            if n_alert > 0:
                print(f"  ⚠  {n_alert} alert(s) found above. Review before submitting.")
        else:
            print("\n[2/4] CrossRef validation skipped.")

        if args.dry_run:
            print("\n-- Dry run complete (no files written) --")
            return 0

        print("\n[3/4] Fetching RIS for each reference...")
        ris_data = {}
        ok = missing = 0
        for ref in refs:
            num = ref["num"]
            doi = ref.get("doi")
            slug = ref.get("slug", str(num))
            if doi:
                print(f"  [{num:2d}] {slug:<30} {doi}", end="", flush=True)
                ris = fetch_ris(doi, args.email)
                if ris:
                    ris_data[num] = ris
                    print()
                    ok += 1
                else:
                    print(" — FAILED (no DOI sources returned RIS)")
                    missing += 1
            else:
                print(f"  [{num:2d}] {slug:<30} no DOI — PubMed text search...", end="", flush=True)
                ris, pmid = fetch_ris_no_doi(ref["text"], args.email)
                if ris:
                    print(f" found PMID:{pmid}")
                    ris_data[num] = ris
                    ok += 1
                else:
                    print(" not found")
                    missing += 1
            time.sleep(0.25)
        print(f"  {ok} fetched | {missing} missing")

    # ── Standalone mode (original behaviour) ───────────────────────────────
    else:
        print(f"\n  Mode: standalone (parsing reference list from docx)")
        print("  Tip: run with --project <dir> for better accuracy\n")

        print("[1/4] Extracting reference list...")
        refs = extract_references(src)
        overrides = load_overrides(src)
        print(f"  {len(refs)} references found")

        if args.dry_run:
            print("\n-- Dry run: DOI resolution preview --")
            for ref in refs:
                doi = get_doi(ref, overrides)
                manual = "MANUAL-RIS" if get_manual_ris(ref, overrides) else ""
                print(f"  [{ref['num']:2d}] {doi or manual or 'MISSING'}")
            return 0

        if not args.skip_validation:
            print("\n[2/4] CrossRef validation...")
            val_refs = []
            for ref in refs:
                doi = get_doi(ref, overrides)
                if doi:
                    val_refs.append({"num": ref["num"], "doi": doi,
                                     "text": ref["text"], "slug": str(ref["num"])})
            run_validation(val_refs, {}, args.email)
        else:
            print("\n[2/4] CrossRef validation skipped.")

        print("\n[3/4] Fetching RIS...")
        ris_data = {}
        ok = missing = 0
        for ref in refs:
            num = ref["num"]
            manual = get_manual_ris(ref, overrides)
            if manual:
                ris_data[num] = manual
                print(f"  [{num:2d}] manual RIS")
                ok += 1
                continue
            doi = get_doi(ref, overrides)
            if doi:
                print(f"  [{num:2d}] {doi}", end="", flush=True)
                ris = fetch_ris(doi, args.email)
                if ris:
                    ris_data[num] = ris
                    print()
                    ok += 1
                else:
                    print(" — all sources failed, trying PubMed text search...")
                    ris, pmid = fetch_ris_no_doi(ref["text"], args.email)
                    if ris:
                        print(f"       → found via PubMed PMID:{pmid}")
                        ris_data[num] = ris
                        ok += 1
                    else:
                        print(f"       → FAILED")
                        missing += 1
            else:
                print(f"  [{num:2d}] no DOI — PubMed text search...", end="", flush=True)
                ris, pmid = fetch_ris_no_doi(ref["text"], args.email)
                if ris:
                    print(f" found PMID:{pmid}")
                    ris_data[num] = ris
                    ok += 1
                else:
                    print(f" not found")
                    missing += 1
            time.sleep(0.25)
        print(f"  {ok} fetched | {missing} missing")
        bib = {}

    # ── Conversion (shared) ─────────────────────────────────────────────────
    print("\n[4/4] Converting citations and writing outputs...")
    cmap  = build_citation_map(refs, ris_data)
    style = detect_style(src)
    patterns = find_all_patterns(src, style)
    combined = [p for p in patterns if "," in p]
    print(f"  Style: {style} | {len(patterns)} patterns | {len(combined)} combined: {combined}")
    repls = build_replacements(patterns, cmap, style)

    bak = src.parent / f"{stem}.bak.docx"
    if not bak.exists():
        shutil.copy(src, bak)
        print(f"  Backup → {bak.name}")

    write_ris(ris_data, refs, risp)
    ok = apply_to_docx(src, dst, repls, cmap, style)

    if ok:
        print(f"  Converted doc → {dst.name}")
        print(f"\n{'='*60}")
        print("  Done!\n")
        print("  Next steps in EndNote:")
        print("  1. File → New  (fresh library for this paper)")
        print(f"  2. File → Import → File → {risp.name}")
        print("     Import Option: Reference Manager (RIS)")
        print("  3. Open the converted .docx in Word")
        print("  4. Delete the old reference list at the bottom")
        print("  5. EndNote ribbon → Update Citations and Bibliography")
        print(f"{'='*60}\n")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
