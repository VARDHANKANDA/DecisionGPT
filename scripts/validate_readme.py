import re
import os
import urllib.parse

with open("README.md", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Check all referenced relative file paths
paths = re.findall(r'\[([^\]]+)\]\(([^http#][^\)]+)\)', text)
print(f"Checking {len(paths)} local file links in README.md:")
missing = 0
for text_label, p in paths:
    clean_p = urllib.parse.unquote(p.replace("file:///", "").replace("d:/Capstone Project/", "").replace("D:/Capstone Project/", ""))
    exists = os.path.exists(clean_p) or os.path.exists(p)
    if not exists:
        print(f"  MISSING: {clean_p} (raw: {p})")
        missing += 1
    else:
        print(f"  OK: {clean_p}")
print(f"Total missing paths: {missing}")

# 2. Check for secret patterns
secrets = re.findall(r"sk-[A-Za-z0-9]{20,}", text)
print(f"Exposed API keys found: {len(secrets)}")

# 3. Check Table of Contents against actual headings
toc_matches = re.findall(r"\[(\d+\.\s+[^\]]+)\]\(#([^\)]+)\)", text)
headings = re.findall(r"^##\s+(\d+\.\s+.*)", text, re.MULTILINE)
print(f"TOC items: {len(toc_matches)}, Actual H2 Headings: {len(headings)}")
mismatches = 0
for (title, anchor), h in zip(toc_matches, headings):
    if title.strip() != h.strip():
        print(f"  Mismatch: TOC '{title}' vs Heading '{h}'")
        mismatches += 1
print(f"Total TOC mismatches: {mismatches}")

# 4. Check mermaid code blocks count
mermaid_blocks = re.findall(r"```mermaid(.*?)```", text, re.DOTALL)
print(f"Mermaid diagrams found: {len(mermaid_blocks)}")
for i, b in enumerate(mermaid_blocks):
    first_line = b.strip().split("\n")[0]
    print(f"  Diagram {i+1} type: {first_line}")
