from pathlib import Path

backend = Path("d:/Capstone Project/backend")
for pyfile in backend.rglob("*.py"):
    if ".venv" in pyfile.parts:
        continue
    try:
        content = pyfile.read_text(encoding="utf-8", errors="ignore")
        if "experiments" in content or "data_external" in content or "research_uploads" in content:
            print(f"Referenced in: {pyfile.relative_to(backend.parent)}")
    except Exception:
        pass

