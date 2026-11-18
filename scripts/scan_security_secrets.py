import os
import re
from pathlib import Path

ROOT = Path(r"D:\Capstone Project")
IGNORE_DIRS = {".git", "_LOCAL_ARCHIVE_NOT_FOR_GITHUB", "node_modules", ".venv", "__pycache__", ".next"}
IGNORE_FILES = {".env", ".env.local"}

PATTERNS = [
    ("OpenAI Key", re.compile(r"sk-[a-zA-Z0-9_-]{20,}")),
    ("Generic API Key", re.compile(r"apikey_[a-zA-Z0-9_-]{20,}")),
    ("GitHub Token", re.compile(r"ghp_[a-zA-Z0-9]{20,}")),
    ("AWS Key", re.compile(r"AKIA[0-9A-Z]{16}")),
]

SAFE_SUBSTRINGS = ["change-me", "your_", "placeholder", "test_", "dummy", "fake", "example"]

findings = []
scanned_count = 0

for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
    for fname in filenames:
        if fname in IGNORE_FILES or fname.endswith((".pyc", ".png", ".ico", ".jpg", ".woff", ".woff2", ".ttf")):
            continue
        fpath = Path(dirpath) / fname
        rel_path = fpath.relative_to(ROOT)
        scanned_count += 1
        try:
            content = fpath.read_text(encoding="utf-8", errors="ignore")
            for name, pat in PATTERNS:
                matches = pat.findall(content)
                for m in matches:
                    if any(safe in m.lower() for safe in SAFE_SUBSTRINGS):
                        continue
                    findings.append((str(rel_path), name, m[:15] + "..."))
        except Exception as e:
            print(f"Error reading {rel_path}: {e}")

print(f"Files scanned: {scanned_count}")
print(f"Potential secrets found: {len(findings)}")
for path, name, preview in findings:
    print(f"  [{name}] {path} -> {preview}")

