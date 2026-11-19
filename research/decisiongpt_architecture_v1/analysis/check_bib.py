"""Consistency check: every \\cite key exists in references.bib and every bib entry is cited."""
import glob
import re
from pathlib import Path

P = Path(__file__).resolve().parents[3] / "overleaf" / "architecture_paper_v1"
bib = re.findall(r"^@\w+\{([^,]+),", (P / "references.bib").read_text(encoding="utf-8"), re.M)
tex = "".join(Path(f).read_text(encoding="utf-8") for f in glob.glob(str(P / "sections" / "*.tex")))
cited = {k.strip() for m in re.findall(r"\\cite\{([^}]*)\}", tex) for k in m.split(",")}
bbl = (P / "main.bbl").read_text(encoding="utf-8") if (P / "main.bbl").exists() else ""
print("bib entries", len(bib), "| cited keys", len(cited), "| bibitems in compiled .bbl", bbl.count("\\bibitem"))
print("uncited bib entries:", sorted(set(bib) - cited))
print("cited but missing:", sorted(cited - set(bib)))
