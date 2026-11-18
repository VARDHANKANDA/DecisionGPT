"""
DecisionGPT Capstone Project Report Builder — Comprehensive Academic Edition (Up to 60 Pages).

Authoritative Formatting Reference: Project Report/CAPSTONE_THESIS_Format.docx
Target Outputs:
  - Project Report/DecisionGPT_Final_Capstone_Project_Report.docx
  - Project Report/DecisionGPT_Final_Capstone_Project_Report.pdf

Target Budget: Up to 60 pages maximum (Target: 50-58 pages).
"""

import os
import sys
import docx
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_SECTION
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

# Ensure scripts directory is on sys.path
sys.path.insert(0, os.path.dirname(__file__))

from report_sections.common import (
    FONT_NAME, ROOT_DIR, REPORT_DIR, TEMPLATE_PATH, OUTPUT_DOCX, OUTPUT_PDF,
    set_font, set_footer_page_number
)
from report_sections.front_matter import (
    build_cover_page, build_certificate, build_declaration,
    build_acknowledgements, build_abstract, build_table_of_contents,
    build_list_of_figures, build_list_of_tables_abbreviations
)
from report_sections.chapter1 import build_chapter_1
from report_sections.chapter2 import build_chapter_2
from report_sections.chapter3 import build_chapter_3
from report_sections.chapter4 import build_chapter_4
from report_sections.chapter5 import build_chapter_5
from report_sections.chapter6 import build_chapter_6
from report_sections.chapter7 import build_chapter_7
from report_sections.chapter8 import build_chapter_8
from report_sections.back_matter import build_references, build_appendices

def generate_report():
    print("=" * 75)
    print("BUILDING COMPREHENSIVE DECISIONGPT CAPSTONE PROJECT REPORT (UP TO 60 PAGES)")
    print("=" * 75)

    if not os.path.exists(TEMPLATE_PATH):
        raise FileNotFoundError(f"Template not found at: {TEMPLATE_PATH}")

    print(f"Loading reference template: {TEMPLATE_PATH}")
    doc = docx.Document(TEMPLATE_PATH)

    # Clear existing placeholder body elements while retaining template styles
    body = doc._body._body
    for el in list(body):
        if not el.tag.endswith('sectPr'):
            body.remove(el)

    print("Configuring Front Matter Section (Section 0)...")
    sec0 = doc.sections[0]
    sec0.top_margin = Inches(1.0)
    sec0.bottom_margin = Inches(0.8)
    sec0.left_margin = Inches(1.25)
    sec0.right_margin = Inches(1.0)
    sec0.header_distance = Inches(0.5)
    sec0.footer_distance = Inches(0.5)
    sec0.different_first_page_header_footer = True

    # Empty header and footer for cover page
    sec0.first_page_footer.paragraphs[0].text = ""
    sec0.first_page_header.paragraphs[0].text = ""

    # Regular footer with Roman numerals
    set_footer_page_number(sec0.footer)
    pg0 = parse_xml(f'<w:pgNumType {nsdecls("w")} w:start="1" w:fmt="lowerRoman"/>')
    sec0._sectPr.append(pg0)

    # Build Front Matter (Pages i to viii)
    print("  -> Building Page i: Title Page (Cover)...")
    build_cover_page(doc)

    print("  -> Building Page ii: Bonafide Certificate...")
    build_certificate(doc)

    print("  -> Building Page iii: Student Declaration...")
    build_declaration(doc)

    print("  -> Building Page iv: Acknowledgements...")
    build_acknowledgements(doc)

    print("  -> Building Page v: Abstract & Keywords...")
    build_abstract(doc)

    print("  -> Building Page vi: Table of Contents...")
    build_table_of_contents(doc)

    print("  -> Building Page vii: List of Figures...")
    build_list_of_figures(doc)

    print("  -> Building Page viii: List of Tables & Technical Abbreviations...")
    build_list_of_tables_abbreviations(doc)

    # Configure Main Matter Section (Section 1)
    print("\nConfiguring Main Body Section (Section 1)...")
    sec1 = doc.add_section(WD_SECTION.NEW_PAGE)
    sec1.top_margin = Inches(1.0)
    sec1.bottom_margin = Inches(0.8)
    sec1.left_margin = Inches(1.25)
    sec1.right_margin = Inches(1.0)
    sec1.header_distance = Inches(0.5)
    sec1.footer_distance = Inches(0.5)

    sec1.header.is_linked_to_previous = False
    sec1.footer.is_linked_to_previous = False

    # Running header - clean and empty matching reference DOCX
    hp = sec1.header.paragraphs[0]
    hp.text = ""

    # Running footer with Arabic numerals starting at 1
    set_footer_page_number(sec1.footer)
    pg1 = parse_xml(f'<w:pgNumType {nsdecls("w")} w:start="1" w:fmt="decimal"/>')
    sec1._sectPr.append(pg1)

    # Build Chapters 1 to 8 + Back Matter
    print("  -> Building Chapter 1: Introduction...")
    build_chapter_1(doc)

    print("  -> Building Chapter 2: Literature Review and Existing Systems...")
    build_chapter_2(doc)

    print("  -> Building Chapter 3: Proposed System and Requirements...")
    build_chapter_3(doc)

    print("  -> Building Chapter 4: System Architecture and Technical Design...")
    build_chapter_4(doc)

    print("  -> Building Chapter 5: System Implementation and Application Features...")
    build_chapter_5(doc)

    print("  -> Building Chapter 6: Research Methodology and Experimental Framework...")
    build_chapter_6(doc)

    print("  -> Building Chapter 7: Results, Analysis and Discussion...")
    build_chapter_7(doc)

    print("  -> Building Chapter 8: Conclusion and Future Scope...")
    build_chapter_8(doc)

    print("  -> Building References...")
    build_references(doc)

    print("  -> Building Appendices...")
    build_appendices(doc)

    print(f"\nSaving generated DOCX report to:\n  {OUTPUT_DOCX}")
    doc.save(OUTPUT_DOCX)
    print(f"DOCX successfully generated! File size: {os.path.getsize(OUTPUT_DOCX):,} bytes")
    return OUTPUT_DOCX

def export_and_verify_pdf(docx_path, pdf_path):
    print("=" * 75)
    print("EXPORTING TO PDF & VERIFYING EXACT PAGE COUNT VIA MICROSOFT WORD COM")
    print("=" * 75)
    import win32com.client
    from pypdf import PdfReader

    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    word.DisplayAlerts = False

    try:
        print(f"Opening DOCX in Word: {docx_path}")
        doc = word.Documents.Open(docx_path)

        print("Updating all Word fields, page numbers, and tables...")
        for field in doc.Fields:
            field.Update()
        for toc in doc.TablesOfContents:
            toc.Update()

        word_pages = doc.ComputeStatistics(2)  # wdStatisticPages
        print(f"Microsoft Word computed page count: {word_pages} pages")

        doc.Save()
        print(f"Exporting to PDF: {pdf_path}")
        doc.SaveAs(pdf_path, FileFormat=17)  # 17 = wdFormatPDF
        doc.Close(False)
        word.Quit()

        if os.path.exists(pdf_path):
            reader = PdfReader(pdf_path)
            actual_pdf_pages = len(reader.pages)
            print(f"Rendered PDF page count: {actual_pdf_pages} pages")
            print(f"PDF File size: {os.path.getsize(pdf_path):,} bytes")

            if actual_pdf_pages <= 60:
                print("=" * 75)
                print(f"SUCCESS: REPORT PAGE COUNT ({actual_pdf_pages} PAGES) PERFECTLY MEETS UP-TO-60 PAGES SPECIFICATION!")
                print("=" * 75)
            else:
                print(f"[PAGE BUDGET NOTICE] Hard Limit: 60 pages, Actual: {actual_pdf_pages} pages")
            return actual_pdf_pages
        else:
            print("Error: PDF was not created.")
            return None
    except Exception as e:
        print(f"Error during Word automation / PDF export: {e}")
        try:
            word.Quit()
        except:
            pass
        return None

if __name__ == "__main__":
    docx_file = generate_report()
    export_and_verify_pdf(docx_file, OUTPUT_PDF)
