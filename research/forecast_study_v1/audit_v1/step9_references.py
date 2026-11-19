"""Step 9: verify every reference in MANUSCRIPT.md section 22 against the publisher-deposited Crossref record (DOI references) or the arXiv API (arXiv references).
Writes work/step9_refs.json. References without a DOI/arXiv id are listed for manual verification (not guessed)."""
import json
import re
import sys
import time
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import ind_core as ic  # noqa: E402

AUD = Path(__file__).parent
ms = (ic.STUDY / "manuscript" / "MANUSCRIPT.md").read_text(encoding="utf-8")
sec = ms[ms.index("## 22. References"):]
refs = [l[2:].strip() for l in sec.splitlines() if l.startswith("* ") and not l.startswith("* *")]
refs = [r for r in refs if re.match(r"[A-Z]", r)]


def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]", " ", s).split()


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "audit/1.0 (mailto:solasa.dev@gmail.com)"})
    for k in range(4):
        try:
            return urllib.request.urlopen(req, timeout=30).read()
        except Exception as e:  # rate limit -> back off
            time.sleep(2 + 3 * k)
            err = e
    raise err


out = []
for i, r in enumerate(refs, 1):
    e = {"n": i, "manuscript_text": r}
    m_doi = re.search(r"doi:\s*(10\.\S+)", r)
    m_ax = re.search(r"arXiv:\s*([0-9]{4}\.[0-9]{4,5})", r)
    yr = re.search(r"\((\d{4})[a-z]?\)", r)
    e["manuscript_year"] = yr.group(1) if yr else None
    first_family = norm(r.split(",")[0])
    e["manuscript_first_author_family"] = " ".join(first_family)
    pages = re.search(r"(\d+)[–-](\d+)", r.split("doi:")[0].split(")", 1)[-1])
    e["manuscript_pages"] = f"{pages.group(1)}-{pages.group(2)}" if pages else None
    try:
        if m_doi:
            doi = m_doi.group(1).rstrip(".")
            j = json.loads(get(f"https://api.crossref.org/works/{doi}"))["message"]
            title = (j.get("title") or [""])[0]
            e["source"] = f"Crossref doi:{doi}"
            e["registry_title"] = title
            e["registry_container"] = (j.get("container-title") or [""])[0]
            e["registry_year"] = str((j.get("issued", {}).get("date-parts") or [[None]])[0][0])
            e["registry_volume"], e["registry_issue"], e["registry_pages"] = j.get("volume"), j.get("issue"), j.get("page")
            e["registry_authors"] = [f"{a.get('family', a.get('name', ''))}, {a.get('given', '')}" for a in j.get("author", [])]
            e["registry_first_author_family"] = " ".join(norm(j["author"][0].get("family", ""))) if j.get("author") else ""
            e["title_in_manuscript"] = all(w in " ".join(norm(r)) for w in norm(title)[:6])
        elif m_ax:
            ax = m_ax.group(1)
            xml = get(f"http://export.arxiv.org/api/query?id_list={ax}")
            ns = {"a": "http://www.w3.org/2005/Atom"}
            ent = ET.fromstring(xml).find("a:entry", ns)
            e["source"] = f"arXiv:{ax}"
            e["registry_title"] = " ".join(ent.find("a:title", ns).text.split())
            e["registry_authors"] = [a.find("a:name", ns).text for a in ent.findall("a:author", ns)]
            e["registry_year"] = ent.find("a:published", ns).text[:4]
            e["registry_first_author_family"] = " ".join(norm(e["registry_authors"][0].split()[-1]))
            e["title_in_manuscript"] = all(w in " ".join(norm(r)) for w in norm(e["registry_title"])[:6])
        else:
            e["source"] = "NO DOI/arXiv id in manuscript: manual verification required"
    except Exception as ex:
        e["error"] = str(ex)[:200]
    # automatic field verdicts
    if "registry_title" in e:
        e["first_author_matches"] = e["manuscript_first_author_family"].split()[-1] == (e["registry_first_author_family"].split()[-1] if e["registry_first_author_family"] else "")
        e["year_matches_registry"] = (e["manuscript_year"] == e["registry_year"]) if e["manuscript_year"] else None
        rp = (e.get("registry_pages") or "").replace("–", "-")
        e["pages_match_registry"] = (e["manuscript_pages"] == rp) if (e["manuscript_pages"] and rp) else None
    out.append(e)
    print(i, e.get("source"), "| title ok:", e.get("title_in_manuscript"), "| author:", e.get("first_author_matches"), "| year:", e.get("year_matches_registry"), "| pages:", e.get("pages_match_registry"), flush=True)
    time.sleep(0.4)
(AUD / "work" / "step9_refs.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
