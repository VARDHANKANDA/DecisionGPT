"""references.bib from literature/references_crossref.json (keys = FirstAuthorYear). Metadata as recorded in REFERENCE_AUDIT.csv; see REFERENCE_CLAIM_CHECK.csv for claim-level support."""
import html, json, re
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
refs = json.loads((HERE / "literature" / "references_crossref.json").read_text(encoding="utf-8"))
FIX = {"L17": 2022, "L21": 2023}
SPECIAL = {
 "L27": "@inproceedings{Ke2017,\n  author = {Ke, Guolin and Meng, Qi and Finley, Thomas and Wang, Taifeng and Chen, Wei and Ma, Weidong and Ye, Qiwei and Liu, Tie-Yan},\n  title = {{LightGBM}: A Highly Efficient Gradient Boosting Decision Tree},\n  booktitle = {Advances in Neural Information Processing Systems},\n  volume = {30},\n  year = {2017}\n}",
 "L29": "@misc{Damato2026,\n  author = {Damato, Stefano and Rubattu, Nicol{\`o} and Azzimonti, Dario and Corani, Giorgio},\n  title = {Intermittent time series forecasting: local vs global models},\n  year = {2026},\n  eprint = {2601.14031},\n  archivePrefix = {arXiv},\n  note = {Preprint}\n}",
 "L32": "@misc{Chen2012,\n  author = {Chen, Daqing},\n  title = {Online Retail {II} [Dataset]},\n  year = {2012},\n  howpublished = {UCI Machine Learning Repository},\n  doi = {10.24432/C5CG6D},\n  note = {CC BY 4.0}\n}"}
out, seen = [], {}
for e in refs:
    if e["id"] in SPECIAL:
        out.append(SPECIAL[e["id"]]); continue
    fam = re.sub(r"[^A-Za-z]", "", e["authors"][0].split(",")[0])
    yr = FIX.get(e["id"], e["year"])
    key = f"{fam}{yr}"; seen[key] = seen.get(key, 0) + 1
    if seen[key] > 1: key += chr(96 + seen[key])
    au = " and ".join(a.replace(", ", ", ") for a in e["authors"])
    title = html.unescape(e["title"]).rstrip(".")
    if e["id"] == "L28": title = "{XGBoost}: A Scalable Tree Boosting System"
    pages = "33--50" if e["id"] == "L22" else e["page"].replace("-", "--")
    kind = "inproceedings" if e["id"] == "L28" else "article"
    jf = "booktitle" if kind == "inproceedings" else "journal"
    fields = [f"  author = {{{au}}}", f"  title = {{{title}}}", f"  {jf} = {{{html.unescape(e['journal'])}}}", f"  year = {{{yr}}}"]
    if e["volume"]: fields.append(f"  volume = {{{e['volume']}}}")
    if e["issue"]: fields.append(f"  number = {{{e['issue']}}}")
    if pages: fields.append(f"  pages = {{{pages}}}")
    fields.append(f"  doi = {{{e['doi']}}}")
    out.append(f"@{kind}{{{key},\n" + ",\n".join(fields) + "\n}")
(HERE / "submission_prep" / "references.bib").write_text("\n\n".join(out) + "\n", encoding="utf-8")
print(len(out), "entries")
