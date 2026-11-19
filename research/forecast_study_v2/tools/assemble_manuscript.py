"""Assemble MANUSCRIPT_FINAL_DRAFT.md from manuscript_parts/*.md and the reference list (literature/references_crossref.json), and check citation keys.

    python research/forecast_study_v2/tools/assemble_manuscript.py
"""
import html
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
refs = json.loads((HERE / "literature" / "references_crossref.json").read_text(encoding="utf-8"))
KEY = {"L01": "Gneiting|2011", "L02": "Kolassa|2020", "L03": "Kolassa|2016", "L04": "Prestwich|2014", "L05": "Kourentzes|2014", "L06": "Hyndman|2006", "L07": "Croston|1972", "L08": "Syntetos|2005", "L09": "Teunter|2011", "L10": "Nikolopoulos|2011",
       "L11": "Athanasopoulos|2017", "L12": "Hyndman|2011", "L13": "Spiliotis|2021", "L14": "Makridakis|2022", "L15": "Januschowski|2022", "L16": "Bojer|2021", "L17": "Spiliotis|2022", "L18": "Makridakis|2018", "L19": "Makridakis|2020", "L20": "Fildes|2022",
       "L21": "Hewamalage|2023", "L22": "Koenker|1978", "L23": "Friedman|2001", "L24": "Cameron|2011", "L25": "Owen|2007", "L26": "Owen|2012", "L27": "Ke|2017", "L28": "Chen|2016", "L29": "Damato|2026", "L30": "Diebold|1995", "L31": "Politis|1994", "L32": "Chen|2012"}
FIX = {"L17": 2022, "L21": 2023}  # print years (the registry lists online-first years); see REFERENCE_AUDIT.csv notes


def fmt(e):
    i = e["id"]
    if "authors" in e:
        au = e["authors"]
        a = ", ".join(au[:-1]) + (", & " if len(au) > 1 else "") + au[-1] if len(au) <= 10 else ", ".join(au[:10]) + ", et al."
        yr = FIX.get(i, e["year"])
        vol = f", {e['volume']}" if e["volume"] else ""
        pg = f", {e['page']}" if e["page"] else ""
        title = {"L28": "XGBoost: A scalable tree boosting system"}.get(i, html.unescape(e['title']).rstrip('.'))
        pgs = {"L22": "33-50"}.get(i, e['page'])
        pg = f", {pgs}" if pgs else ""
        s = f"{a} ({yr}). {title}. *{html.unescape(e['journal'])}*{vol}{pg}. https://doi.org/{e['doi']}"
    else:
        s = {"L27": "Ke, G., Meng, Q., Finley, T., Wang, T., Chen, W., Ma, W., Ye, Q., & Liu, T.-Y. (2017). LightGBM: A highly efficient gradient boosting decision tree. *Advances in Neural Information Processing Systems*, 30 (authors and title checked on the NeurIPS proceedings page, 2026-10-22).",
             "L29": "Damato, S., Rubattu, N., Azzimonti, D., & Corani, G. (2026). Intermittent time series forecasting: local vs global models. arXiv:2601.14031 (preprint; authors and title per the arXiv API, 2026-10-22).",
             "L32": "Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5CG6D  (CC BY 4.0)."}[i]
    return s


order = sorted(refs, key=lambda e: (KEY[e["id"]].split("|")[0], KEY[e["id"]].split("|")[1]))
body = "\n\n".join(fmt(e) for e in order)
parts = [(HERE / "manuscript_parts" / f).read_text(encoding="utf-8") for f in ("part0_front.md", "part1_front_and_methods.md", "part2_results_and_discussion.md")]
text = "\n\n".join(p.strip() for p in parts) + "\n\n## References\n\n*Metadata from Crossref (checked 2026-10-22; see `REFERENCE_AUDIT.csv`). Entries marked \"verify\" must be checked by the author against the original source.*\n\n" + body + "\n"
# citation check: every [..., YYYY] key group must map to a reference
cited = set()
for grp in re.findall(r"\[([^\]]*\d{4}[^\]]*)\]", text.split("## References")[0]):
    for m in re.finditer(r"([A-Z][A-Za-z\-]+)(?: et al\.|(?: & [A-Z][A-Za-z\-]+))?,? (\d{4})", grp):
        cited.add(f"{m.group(1)}|{m.group(2)}")
for m in re.finditer(r"([A-Z][A-Za-z\-]+)(?: et al\.|(?: & [A-Z][A-Za-z\-]+))? \[(\d{4})\]", text.split("## References")[0]):
    cited.add(f"{m.group(1)}|{m.group(2)}")
have = set(KEY.values())
print("cited but not in list:", sorted(cited - have))
print("in list but never cited:", sorted(have - cited))
(HERE / "MANUSCRIPT_FINAL_DRAFT.md").write_text(text, encoding="utf-8")
print("words:", len(text.split()), "| replacement chars:", text.count("�"))
