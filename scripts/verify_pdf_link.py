import win32com.client
import os
import pypdf

word = win32com.client.DispatchEx("Word.Application")
word.Visible = False
try:
    docx_path = os.path.abspath("scripts/test_hyperlink.docx")
    pdf_path = os.path.abspath("scripts/test_hyperlink.pdf")
    doc = word.Documents.Open(docx_path)
    doc.SaveAs(pdf_path, FileFormat=17) # 17 = wdFormatPDF
    doc.Close(False)
    print("Exported to PDF successfully")
    
    reader = pypdf.PdfReader(pdf_path)
    page = reader.pages[0]
    print("Annotations count:", len(page.annotations) if page.annotations else 0)
    for annot in page.annotations:
        obj = annot.get_object()
        print("URI:", obj.get("/A", {}).get("/URI"))
finally:
    word.Quit()

