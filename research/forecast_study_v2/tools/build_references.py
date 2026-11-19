"""Build REFERENCES.md from REFERENCE_AUDIT.csv using Crossref metadata (full author lists). Network access: Crossref public API only.

    python research/forecast_study_v2/tools/build_references.py
"""
import csv
import json
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
rows = list(csv.DictReader(open(HERE / "REFERENCE_AUDIT.csv", encoding="utf-8")))
out, cache = [], {}
for r in rows:
    doi = r["doi_or_id"]
    entry = {"id": r["id"], "doi": doi, "stated": f"{r['stated_first_author']} ({r['stated_year']}) {r['stated_title']}", "status": r["status"], "notes": r["notes"]}
    if doi.startswith("10."):
        try:
            u = "https://api.crossref.org/works/" + urllib.parse.quote(doi)
            with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "forecast_study_v2 (mailto:solasa.dev@gmail.com)"}), timeout=30) as f:
                m = json.load(f)["message"]
            authors = [f"{a.get('family', a.get('name', ''))}, {''.join(w[0] + '.' for w in a.get('given', '').replace('-', ' ').split())}".strip().rstrip(",") for a in m.get("author", [])]
            entry.update(authors=authors, title=(m.get("title") or [""])[0], journal=(m.get("container-title") or [""])[0], volume=m.get("volume", ""), issue=m.get("issue", ""), page=m.get("page", m.get("article-number", "")),
                         year=(m.get("issued", {}).get("date-parts") or [[""]])[0][0], publisher=m.get("publisher", ""))
        except Exception as e:  # keep the audit row if the lookup fails
            entry["lookup_error"] = str(e)
    out.append(entry)
(HERE / "literature" / "references_crossref.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
print(len(out), "entries;", sum(1 for e in out if "authors" in e), "with Crossref metadata;", [e["id"] for e in out if "lookup_error" in e])
