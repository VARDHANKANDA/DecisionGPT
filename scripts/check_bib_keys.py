import os, re

bib_path = r"D:\Capstone Project\_LOCAL_ARCHIVE_NOT_FOR_GITHUB\research_papers\overleaf1\references.bib"
with open(bib_path, "r", encoding="utf-8") as f:
    text = f.read()

entries = re.findall(r'@(\w+)\s*\{\s*([^,]+),([^@]*)\}', text, re.DOTALL)
print(f"Total entries: {len(entries)}")

bib_dict = {}
for etype, key, body in entries:
    fields = {}
    for line in body.splitlines():
        m = re.match(r'\s*(\w+)\s*=\s*[\{"](.*)[\}"]\s*,?', line)
        if m:
            fields[m.group(1).lower()] = m.group(2).strip('{}," ')
    bib_dict[key] = (etype, fields)

# Print keys
for k in bib_dict:
    print(k)

