from pathlib import Path

root = Path("d:/Capstone Project")
matches = []
for p in root.rglob("*"):
    if any(part in p.parts for part in ["node_modules", ".venv", ".git", ".next"]):
        continue
    name_lower = p.name.lower()
    if any(k in name_lower for k in ["benchmark", "evaluation", "experiment", "ablation", "research"]):
        matches.append(p)

print(f"Found {len(matches)} files/directories related to research/benchmarks/evaluations:")
for m in sorted(matches, key=lambda x: str(x)):
    try:
        size = m.stat().st_size if m.is_file() else "DIR"
        print(f"  {size} : {m.relative_to(root)}")
    except Exception:
        pass

