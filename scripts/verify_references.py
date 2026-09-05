#!/usr/bin/env python3
"""
Verify every DOI in the thesis reference list against Crossref, and print what each one
actually resolves to so you can compare it against your own entry.

Usage:
    python3 scripts/verify_references.py /path/to/Frank_Masabo_..._DRAFT.docx

Output per reference: OK / MISMATCH? / NOT FOUND, plus the registered title and first author.
"MISMATCH?" only means the surname in your entry didn't appear in Crossref's author list --
check it by eye; initials, hyphenated names and organisational authors can trip it.

Uses curl rather than urllib: python.org macOS builds ship their own CA bundle and often fail
with CERTIFICATE_VERIFY_FAILED, while curl uses the system trust store.
"""

import json
import re
import subprocess
import sys


def refs_from_docx(path):
    from docx import Document
    d = Document(path)
    paras = d.paragraphs
    start = max(i for i, p in enumerate(paras) if p.text.strip() == "References")
    out = []
    for p in paras[start + 1:]:
        t = p.text.strip()
        if t.startswith("Appendices"):
            break
        if t:
            out.append(t)
    return out


def crossref(doi):
    p = subprocess.run(
        ["curl", "-sS", "--max-time", "30",
         "-H", "Accept: application/json",
         f"https://api.crossref.org/works/{doi}"],
        capture_output=True, text=True,
    )
    if p.returncode != 0 or not p.stdout.strip().startswith("{"):
        return None
    try:
        m = json.loads(p.stdout)["message"]
    except Exception:
        return None
    title = (m.get("title") or ["(no title)"])[0]
    authors = m.get("author") or []
    first = authors[0].get("family", "?") if authors else "(org author)"
    year = (m.get("issued", {}).get("date-parts") or [[None]])[0][0]
    return {"title": title, "first_author": first, "year": year,
            "container": (m.get("container-title") or [""])[0]}


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: verify_references.py <thesis.docx>")
    refs = refs_from_docx(sys.argv[1])
    print(f"{len(refs)} reference entries found\n")

    ok = mism = missing = nodoi = 0
    for r in refs:
        entry_surname = r.split(",")[0].strip()
        m = re.search(r"doi\.org/(\S+)", r)
        if not m:
            nodoi += 1
            print(f"[no DOI ] {entry_surname[:40]}")
            print(f"           (standard or report - verify the URL/publisher manually)\n")
            continue
        doi = m.group(1).rstrip(".")
        meta = crossref(doi)
        if meta is None:
            missing += 1
            print(f"[NOT FND] {entry_surname[:40]}  {doi}")
            print(f"           Crossref returned nothing - check the DOI is correct\n")
            continue
        surname_ok = entry_surname.split()[0].lower() in meta["first_author"].lower() \
            or meta["first_author"].lower() in entry_surname.lower()
        tag = "[  OK   ]" if surname_ok else "[MISMTCH]"
        ok += surname_ok
        mism += (not surname_ok)
        print(f"{tag} {entry_surname[:40]}  {doi}")
        print(f"           -> {meta['first_author']} ({meta['year']}) {meta['title'][:78]}")
        if meta["container"]:
            print(f"              in: {meta['container'][:70]}")
        print()

    print("-" * 60)
    print(f"resolved & author matches : {ok}")
    print(f"resolved but check author : {mism}")
    print(f"DOI not found in Crossref : {missing}")
    print(f"no DOI (verify by hand)   : {nodoi}")


if __name__ == "__main__":
    main()
