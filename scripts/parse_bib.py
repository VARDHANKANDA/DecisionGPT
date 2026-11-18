import os
import re

bib_path = r"D:\Capstone Project\_LOCAL_ARCHIVE_NOT_FOR_GITHUB\research_papers\overleaf1\references.bib"

with open(bib_path, "r", encoding="utf-8") as f:
    content = f.read()

entries = re.findall(r'@(\w+)\s*\{\s*([^,]+),([^@]*)\}', content, re.DOTALL)
print(f"Total entries found: {len(entries)}")

parsed = []
for entry_type, key, body in entries:
    fields = {}
    for line in body.splitlines():
        m = re.match(r'\s*(\w+)\s*=\s*[\{"](.*)[\}"]\s*,?', line)
        if m:
            fields[m.group(1).lower()] = m.group(2).strip('{}," ')
    parsed.append((key, entry_type, fields))

for key, etype, fields in parsed:
    title = fields.get('title', 'NO TITLE')[:60]
    author = fields.get('author', 'NO AUTHOR')[:40]
    year = fields.get('year', 'NO YEAR')
    doi = fields.get('doi', '')
    url = fields.get('url', '')
    print(f"[{key}] ({year}) {author} - {title} | DOI: {doi} | URL: {url[:30]}")

