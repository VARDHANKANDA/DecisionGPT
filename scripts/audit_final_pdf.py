import pypdf

pdf_path = r"D:\Capstone Project\Project Report\DecisionGPT_Final_Capstone_Project_Report.pdf"
reader = pypdf.PdfReader(pdf_path)
print(f"Total PDF pages: {len(reader.pages)}")

chapter_pages = {}
fig_pages = {}
tbl_pages = {}

for i in range(8, len(reader.pages)):
    page = reader.pages[i]
    text = page.extract_text() or ""
    for ch in range(1, 9):
        target = f"CHAPTER {ch}"
        if target in text and target not in chapter_pages:
            chapter_pages[target] = i + 1
    if "REFERENCES" in text and "REFERENCES" not in chapter_pages:
        chapter_pages["REFERENCES"] = i + 1
    if "APPENDIX A" in text and "APPENDIX A" not in chapter_pages:
        chapter_pages["APPENDIX A"] = i + 1
    if "APPENDIX B" in text and "APPENDIX B" not in chapter_pages:
        chapter_pages["APPENDIX B"] = i + 1
    if "APPENDIX C" in text and "APPENDIX C" not in chapter_pages:
        chapter_pages["APPENDIX C"] = i + 1
    if "APPENDIX D" in text and "APPENDIX D" not in chapter_pages:
        chapter_pages["APPENDIX D"] = i + 1
    for fnum in ["3.1", "4.1", "4.2", "4.3", "4.4", "4.5", "4.6", "5.1", "5.2", "5.3", "5.4", "5.5", "5.6", "5.7", "5.8", "5.9", "5.10", "5.11", "5.12", "5.13", "5.14", "5.15", "7.1", "7.2", "7.3", "7.4"]:
        target = f"Figure {fnum}"
        if target in text and fnum not in fig_pages:
            fig_pages[fnum] = i + 1
    for tnum in ["2.1", "3.1", "3.2", "4.1", "5.1", "5.2", "6.1", "7.1", "7.2", "7.3", "7.4", "7.5"]:
        target = f"Table {tnum}"
        if target in text and tnum not in tbl_pages:
            tbl_pages[tnum] = i + 1

print("\n--- LOCATED SECTIONS (PDF Page / Roman or Arabic) ---")
for k, v in chapter_pages.items():
    arabic = v - 8
    print(f"{k}: PDF page {v} (Arabic {arabic})")

print("\n--- LOCATED FIGURES ---")
for k, v in fig_pages.items():
    arabic = v - 8
    print(f"Figure {k}: PDF page {v} (Arabic {arabic})")

print("\n--- LOCATED TABLES ---")
for k, v in tbl_pages.items():
    arabic = v - 8
    print(f"Table {k}: PDF page {v} (Arabic {arabic})")
