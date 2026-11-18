"""
DecisionGPT Capstone Project Report Builder — 30-Page Edition.

Target: EXACTLY 30 pages total in final rendered Word DOCX and PDF.
Strict Budget:
  1. Title Page: 1 page (Page 1)
  2. Certificate / Declaration: 1 page (Page 2)
  3. Acknowledgement: 1 page (Page 3)
  4. Abstract: 1 page (Page 4)
  5. Table of Contents: 1 page (Page 5)
  6. List of Figures and Tables: 1 page (Page 6)
  7. Chapter 1 — Introduction: 2 pages (Pages 7-8)
  8. Chapter 2 — Literature Review and Existing System: 3 pages (Pages 9-11)
  9. Chapter 3 — Proposed System and Requirements: 2 pages (Pages 12-13)
  10. Chapter 4 — System Architecture and Design: 4 pages (Pages 14-17)
  11. Chapter 5 — Implementation and Technologies: 4 pages (Pages 18-21)
  12. Chapter 6 — Research Methodology and Evaluation: 3 pages (Pages 22-24)
  13. Chapter 7 — Results, Discussion and Limitations: 2 pages (Pages 25-26)
  14. Chapter 8 — Conclusion and Future Scope: 1 page (Page 27)
  15. References: 2 pages (Pages 28-29)
  16. Appendices: 1 page (Page 30)
  TOTAL: 30 pages
"""

import os
import re
import sys
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.enum.section import WD_SECTION
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn, nsdecls

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPORT_DIR = os.path.join(ROOT_DIR, "Project Report")
FIGURES_DIR = os.path.join(REPORT_DIR, "Figures")
TEMPLATE_PATH = os.path.join(REPORT_DIR, "CAPSTONE_THESIS_Format.docx")
OUTPUT_DOCX = os.path.join(REPORT_DIR, "DecisionGPT_Capstone_Project_Report_30_Pages.docx")
OUTPUT_PDF = os.path.join(REPORT_DIR, "DecisionGPT_Capstone_Project_Report_30_Pages.pdf")

FONT_NAME = "Times New Roman"
BODY_SIZE = Pt(11.0)
HEADING_CHAPTER_SIZE = Pt(13.0)
HEADING_1_SIZE = Pt(11.5)
HEADING_2_SIZE = Pt(11.0)
CAPTION_SIZE = Pt(9.5)
TABLE_TEXT_SIZE = Pt(8.5)

COLOR_BLACK = RGBColor(0, 0, 0)

def clean_text(text):
    if text is None:
        return ""
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', str(text))

def set_font(run, font_name=FONT_NAME, size=BODY_SIZE, bold=False, italic=False, color=COLOR_BLACK):
    run.font.name = font_name
    run.font.size = size
    run.bold = bold
    run.italic = italic
    run.font.color.rgb = color
    rPr = run._r.get_or_add_rPr()
    rFonts = parse_xml(f'<w:rFonts {nsdecls("w")} w:ascii="{font_name}" w:hAnsi="{font_name}" w:cs="{font_name}"/>')
    rPr.append(rFonts)

def add_p(doc, text="", align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_before=Pt(0), space_after=Pt(2.0), line_spacing=1.25, bold=False, italic=False, font_size=BODY_SIZE, color=COLOR_BLACK):
    p = doc.add_paragraph()
    p.alignment = align
    p.paragraph_format.space_before = space_before
    p.paragraph_format.space_after = space_after
    p.paragraph_format.line_spacing = line_spacing
    if text:
        r = p.add_run(clean_text(text))
        set_font(r, font_name=FONT_NAME, size=font_size, bold=bold, italic=italic, color=color)
    return p

def add_heading_1(doc, text, space_before=Pt(5), space_after=Pt(1)):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = space_before
    p.paragraph_format.space_after = space_after
    p.paragraph_format.line_spacing = 1.15
    p.paragraph_format.keep_with_next = True
    r = p.add_run(clean_text(text))
    set_font(r, font_name=FONT_NAME, size=HEADING_1_SIZE, bold=True, color=COLOR_BLACK)
    return p

def add_heading_2(doc, text, space_before=Pt(3), space_after=Pt(1)):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = space_before
    p.paragraph_format.space_after = space_after
    p.paragraph_format.line_spacing = 1.15
    p.paragraph_format.keep_with_next = True
    r = p.add_run(clean_text(text))
    set_font(r, font_name=FONT_NAME, size=HEADING_2_SIZE, bold=True, color=COLOR_BLACK)
    return p

def add_chapter_header(doc, chapter_num, title):
    p1 = doc.add_paragraph()
    p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p1.paragraph_format.space_before = Pt(6)
    p1.paragraph_format.space_after = Pt(1)
    p1.paragraph_format.line_spacing = 1.15
    r1 = p1.add_run(f"CHAPTER {chapter_num}")
    set_font(r1, font_name=FONT_NAME, size=HEADING_CHAPTER_SIZE, bold=True)

    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p2.paragraph_format.space_before = Pt(1)
    p2.paragraph_format.space_after = Pt(6)
    p2.paragraph_format.line_spacing = 1.15
    r2 = p2.add_run(title.upper())
    set_font(r2, font_name=FONT_NAME, size=HEADING_CHAPTER_SIZE, bold=True)

def add_fig_caption(doc, fig_num, caption):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(1)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.line_spacing = 1.1
    p.paragraph_format.keep_with_next = True
    r1 = p.add_run(f"Figure {fig_num}: ")
    set_font(r1, font_name=FONT_NAME, size=CAPTION_SIZE, bold=True)
    r2 = p.add_run(clean_text(caption))
    set_font(r2, font_name=FONT_NAME, size=CAPTION_SIZE, italic=True)
    return p

def add_tbl_caption(doc, tbl_num, caption):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(1)
    p.paragraph_format.line_spacing = 1.1
    p.paragraph_format.keep_with_next = True
    r1 = p.add_run(f"Table {tbl_num}: ")
    set_font(r1, font_name=FONT_NAME, size=CAPTION_SIZE, bold=True)
    r2 = p.add_run(clean_text(caption))
    set_font(r2, font_name=FONT_NAME, size=CAPTION_SIZE, italic=True)
    return p

def add_image_safe(doc, image_name, width=Inches(4.4)):
    img_path = os.path.join(FIGURES_DIR, image_name)
    if os.path.exists(img_path):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.space_after = Pt(1)
        r = p.add_run()
        r.add_picture(img_path, width=width)
        return True
    return False

def add_table_data(doc, headers, data, col_widths=None):
    table = doc.add_table(rows=len(data) + 1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    # Header
    hdr_cells = table.rows[0].cells
    for i, title in enumerate(headers):
        hdr_cells[i].text = clean_text(title)
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.space_after = Pt(1)
        p.paragraph_format.line_spacing = 1.05
        if len(p.runs) > 0:
            set_font(p.runs[0], font_name=FONT_NAME, size=TABLE_TEXT_SIZE, bold=True)
        shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="EBF2FA"/>')
        hdr_cells[i]._tc.get_or_add_tcPr().append(shading)

    # Rows
    for row_idx, row_data in enumerate(data):
        row_cells = table.rows[row_idx + 1].cells
        for col_idx, cell_value in enumerate(row_data):
            row_cells[col_idx].text = clean_text(str(cell_value))
            p = row_cells[col_idx].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT if col_idx > 0 else WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(0.5)
            p.paragraph_format.space_after = Pt(0.5)
            p.paragraph_format.line_spacing = 1.05
            if len(p.runs) > 0:
                set_font(p.runs[0], font_name=FONT_NAME, size=TABLE_TEXT_SIZE)

    # Borders
    tblPr = table._tbl.tblPr
    borders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>\n'
        f'  <w:top w:val="single" w:sz="6" w:space="0" w:color="CCCCCC"/>\n'
        f'  <w:bottom w:val="single" w:sz="6" w:space="0" w:color="CCCCCC"/>\n'
        f'  <w:insideH w:val="single" w:sz="4" w:space="0" w:color="E0E0E0"/>\n'
        f'  <w:insideV w:val="none"/>\n'
        f'  <w:left w:val="none"/>\n'
        f'  <w:right w:val="none"/>\n'
        f'</w:tblBorders>'
    )
    tblPr.append(borders)

    if col_widths:
        for row in table.rows:
            for i, w in enumerate(col_widths):
                row.cells[i].width = Inches(w)

    return table

def set_footer_page_number(footer):
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.text = ""
    r = p.add_run()
    set_font(r, font_name=FONT_NAME, size=Pt(10))
    fld1 = OxmlElement('w:fldChar')
    fld1.set(qn('w:fldCharType'), 'begin')
    instr = OxmlElement('w:instrText')
    instr.set(qn('xml:space'), 'preserve')
    instr.text = " PAGE "
    fld2 = OxmlElement('w:fldChar')
    fld2.set(qn('w:fldCharType'), 'separate')
    fld3 = OxmlElement('w:fldChar')
    fld3.set(qn('w:fldCharType'), 'end')
    r._r.append(fld1)
    r._r.append(instr)
    r._r.append(fld2)
    r._r.append(fld3)

# ==============================================================================
# FRONT MATTER (PAGES 1 to 6)
# ==============================================================================

def build_cover_page(doc):
    """Page 1: Title Page"""
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(36)
    p_title.paragraph_format.space_after = Pt(20)
    p_title.paragraph_format.line_spacing = 1.3
    r_title = p_title.add_run("DECISIONGPT: A GOAL-DRIVEN MULTI-AGENT ENTERPRISE DECISION-SUPPORT PLATFORM WITH DIGITAL TWIN SIMULATION AND CAUSAL REASONING FOR SMALL AND MEDIUM ENTERPRISES")
    set_font(r_title, font_name=FONT_NAME, size=Pt(14), bold=True)

    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.space_before = Pt(12)
    p_sub.paragraph_format.space_after = Pt(8)
    r_sub = p_sub.add_run("A CAPSTONE PROJECT REPORT")
    set_font(r_sub, font_name=FONT_NAME, size=Pt(13), bold=True)

    p_req = doc.add_paragraph()
    p_req.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_req.paragraph_format.space_before = Pt(8)
    p_req.paragraph_format.space_after = Pt(4)
    p_req.paragraph_format.line_spacing = 1.15
    r_req1 = p_req.add_run("Submitted in partial fulfillment of the\nrequirement for the award of the\nDegree of\n")
    set_font(r_req1, font_name=FONT_NAME, size=Pt(11))
    r_req2 = p_req.add_run("BACHELOR OF TECHNOLOGY\nIN\nCOMPUTER SCIENCE AND ENGINEERING")
    set_font(r_req2, font_name=FONT_NAME, size=Pt(12), bold=True)

    p_by = doc.add_paragraph()
    p_by.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_by.paragraph_format.space_before = Pt(16)
    p_by.paragraph_format.space_after = Pt(6)
    r_by = p_by.add_run("by\n")
    set_font(r_by, font_name=FONT_NAME, size=Pt(11), italic=True)

    students = [
        ("K. S. SRI VARDHAN", "23BCE8389"),
        ("R ROHIT", "23BCE8394"),
        ("K. RAHUL", "23BCE8396"),
        ("FELIX", "23BCE8402")
    ]
    p_stud = doc.add_paragraph()
    p_stud.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_stud.paragraph_format.space_before = Pt(2)
    p_stud.paragraph_format.space_after = Pt(16)
    p_stud.paragraph_format.line_spacing = 1.15
    for name, regno in students:
        r_s = p_stud.add_run(f"{name} ({regno})\n")
        set_font(r_s, font_name=FONT_NAME, size=Pt(11), bold=True)

    p_guide = doc.add_paragraph()
    p_guide.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_guide.paragraph_format.space_before = Pt(12)
    p_guide.paragraph_format.space_after = Pt(20)
    p_guide.paragraph_format.line_spacing = 1.15
    r_g1 = p_guide.add_run("Under the Guidance of\n")
    set_font(r_g1, font_name=FONT_NAME, size=Pt(11), italic=True)
    r_g2 = p_guide.add_run("DR. YYYYY\nFaculty Guide\nSchool of Computer Science and Engineering")
    set_font(r_g2, font_name=FONT_NAME, size=Pt(11), bold=True)

    p_univ = doc.add_paragraph()
    p_univ.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_univ.paragraph_format.space_before = Pt(20)
    p_univ.paragraph_format.space_after = Pt(0)
    p_univ.paragraph_format.line_spacing = 1.15
    r_u = p_univ.add_run("SCHOOL OF COMPUTER SCIENCE AND ENGINEERING\nVIT-AP UNIVERSITY\nAMARAVATI - 522237, ANDHRA PRADESH, INDIA\nNOVEMBER 2026")
    set_font(r_u, font_name=FONT_NAME, size=Pt(11), bold=True)

    doc.add_page_break()


def build_certificate_declaration(doc):
    """Page 2: Certificate & Declaration (Combined on 1 page)"""
    p_cert = doc.add_paragraph()
    p_cert.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cert.paragraph_format.space_before = Pt(8)
    p_cert.paragraph_format.space_after = Pt(6)
    r_ct = p_cert.add_run("CERTIFICATE")
    set_font(r_ct, font_name=FONT_NAME, size=Pt(13), bold=True)

    add_p(
        doc,
        "This is to certify that the Capstone Project report titled “DECISIONGPT: A GOAL-DRIVEN MULTI-AGENT ENTERPRISE DECISION-SUPPORT PLATFORM WITH DIGITAL TWIN SIMULATION AND CAUSAL REASONING FOR SMALL AND MEDIUM ENTERPRISES” submitted by K. S. Sri Vardhan (23BCE8389), R Rohit (23BCE8394), K. Rahul (23BCE8396), and Felix (23BCE8402) in partial fulfillment of the requirements for the award of the degree of Bachelor of Technology in Computer Science and Engineering from VIT-AP University, Amaravati, is a record of bonafide work carried out under my guidance and supervision. The contents of this report have neither been taken from any unauthorized source nor been submitted to any other Institute or University for the award of any degree or diploma.",
        space_before=Pt(2), space_after=Pt(12), line_spacing=1.3, font_size=Pt(10.5)
    )

    p_sigs = doc.add_paragraph()
    p_sigs.paragraph_format.space_before = Pt(6)
    p_sigs.paragraph_format.space_after = Pt(12)
    p_sigs.paragraph_format.line_spacing = 1.15
    r_s1 = p_sigs.add_run("Dr. YYYYY                                                                Head of Department\n")
    set_font(r_s1, font_name=FONT_NAME, size=Pt(10), bold=True)
    r_s2 = p_sigs.add_run("Faculty Guide, SCSE                                               School of Computer Science & Engineering\nVIT-AP University                                                    VIT-AP University")
    set_font(r_s2, font_name=FONT_NAME, size=Pt(9.5))

    p_decl = doc.add_paragraph()
    p_decl.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_decl.paragraph_format.space_before = Pt(6)
    p_decl.paragraph_format.space_after = Pt(6)
    r_dt = p_decl.add_run("DECLARATION")
    set_font(r_dt, font_name=FONT_NAME, size=Pt(13), bold=True)

    add_p(
        doc,
        "We hereby declare that the work presented in this Capstone Project report entitled “DECISIONGPT” is an authentic record of our own research, system design, and software engineering conducted under the mentorship of Dr. YYYYY, School of Computer Science and Engineering, VIT-AP University. We confirm that this work has not been previously submitted in part or full for any degree, diploma, or fellowship at this or any other academic institution.",
        space_before=Pt(2), space_after=Pt(10), line_spacing=1.3, font_size=Pt(10.5)
    )

    p_stud_sigs = doc.add_paragraph()
    p_stud_sigs.paragraph_format.space_before = Pt(4)
    p_stud_sigs.paragraph_format.space_after = Pt(0)
    p_stud_sigs.paragraph_format.line_spacing = 1.15
    candidates = [
        "K. S. SRI VARDHAN (23BCE8389)",
        "R ROHIT (23BCE8394)",
        "K. RAHUL (23BCE8396)",
        "FELIX (23BCE8402)"
    ]
    r_cs = p_stud_sigs.add_run("Candidates:  " + "   |   ".join(candidates))
    set_font(r_cs, font_name=FONT_NAME, size=Pt(9.0), bold=True)

    doc.add_page_break()


def build_acknowledgements(doc):
    """Page 3: Acknowledgements"""
    p_ack = doc.add_paragraph()
    p_ack.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_ack.paragraph_format.space_before = Pt(12)
    p_ack.paragraph_format.space_after = Pt(12)
    r_at = p_ack.add_run("ACKNOWLEDGEMENTS")
    set_font(r_at, font_name=FONT_NAME, size=Pt(14), bold=True)

    add_p(
        doc,
        "First and foremost, we express our profound gratitude to the Almighty for granting us the intellect, resilience, and health required to bring this capstone project to successful fruition.",
        space_after=Pt(6), line_spacing=1.35
    )
    add_p(
        doc,
        "We express our heartfelt gratitude to the Chancellor, Vice-Chancellor, and Registrar of VIT-AP University, Amaravati, for fostering an exceptional research ecosystem, modern computational infrastructure, and rigorous academic standards.",
        space_after=Pt(6), line_spacing=1.35
    )
    add_p(
        doc,
        "We are profoundly indebted to our Faculty Guide, Dr. YYYYY, School of Computer Science and Engineering, for their invaluable technical mentorship, constructive criticism, and steadfast support throughout every phase of system design, multi-agent modeling, and empirical benchmarking.",
        space_after=Pt(6), line_spacing=1.35
    )
    add_p(
        doc,
        "We also extend our sincere appreciation to the Dean, Associate Deans, and faculty members of the School of Computer Science and Engineering (SCOPE) for their academic leadership and valuable critique during our milestone review presentations.",
        space_after=Pt(6), line_spacing=1.35
    )
    add_p(
        doc,
        "Finally, we express our deepest love and gratitude to our parents, family members, and classmates for their unyielding encouragement, understanding, and collaboration throughout this undergraduate journey.",
        space_after=Pt(16), line_spacing=1.35
    )

    p_sig = doc.add_paragraph()
    p_sig.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_sig.paragraph_format.space_after = Pt(0)
    p_sig.paragraph_format.line_spacing = 1.15
    r_sig = p_sig.add_run("K. S. Sri Vardhan (23BCE8389)\nR Rohit (23BCE8394)\nK. Rahul (23BCE8396)\nFelix (23BCE8402)")
    set_font(r_sig, font_name=FONT_NAME, size=Pt(10.5), bold=True)

    doc.add_page_break()


def build_abstract(doc):
    """Page 4: Abstract"""
    p_abs = doc.add_paragraph()
    p_abs.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_abs.paragraph_format.space_before = Pt(12)
    p_abs.paragraph_format.space_after = Pt(12)
    r_abt = p_abs.add_run("ABSTRACT")
    set_font(r_abt, font_name=FONT_NAME, size=Pt(14), bold=True)

    add_p(
        doc,
        "Small and Medium Enterprises (SMEs) drive over 30% of developing GDP and employ upwards of 110 million people in India, yet they face chronic data fragmentation, severe capital constraints, and an absence of executive consulting expertise. Traditional Business Intelligence (BI) dashboards remain purely retrospective—reporting past sales declines without explaining causal drivers or prescribing corrective interventions. Conversely, modern generative AI and monolithic Large Language Models (LLMs) suffer from severe mathematical hallucinations, an absence of balance sheet accounting invariants, and a total lack of risk calibration, rendering them unsafe for enterprise decision making.",
        space_after=Pt(6), line_spacing=1.3
    )
    add_p(
        doc,
        "To resolve these failures, this project presents DecisionGPT: an autonomous, goal-driven enterprise decision-support SaaS platform that integrates predictive machine learning, structural causal reasoning, a dynamic balance-sheet digital twin, and a collaborative multi-agent debate swarm. The architecture enforces a strict non-hallucinatory boundary: machine learning ensembles (XGBoost, LightGBM, CatBoost) compute multi-horizon forecasts with conformal prediction intervals; structural equations identify true causal dependencies; and a dynamic Digital Twin stress-tests candidate interventions against working capital reserves and stockout limits. Four specialized role agents (Business Analyst, Financial Advisor, Risk Manager, and Strategy Optimizer) iteratively critique candidate plans through an adversarial consensus protocol to balance growth upside against downside insolvency risk.",
        space_after=Pt(6), line_spacing=1.3
    )
    add_p(
        doc,
        "Evaluated on a comprehensive benchmark suite of 78 business scenario instances (including 60 confirmatory instances across 12 distinct families), empirical findings establish that the business Digital Twin is indispensable, reducing strategic decision regret by over 70% compared to ungrounded heuristics (p < 0.001). The production predictive pipeline achieves a 28-day revenue Forecast Score of 87.6% (WAPE 0.124). Implemented as a full-stack Next.js 16 and FastAPI application featuring 247 automated test suites and multilingual voice accessibility across 8 Indian regional languages, DecisionGPT provides an auditable, reproducible blueprint for accessible enterprise decision intelligence.",
        space_after=Pt(10), line_spacing=1.3
    )

    p_kw = doc.add_paragraph()
    p_kw.paragraph_format.space_before = Pt(4)
    p_kw.paragraph_format.space_after = Pt(0)
    p_kw.paragraph_format.line_spacing = 1.15
    r_kwt = p_kw.add_run("Keywords: ")
    set_font(r_kwt, font_name=FONT_NAME, size=Pt(10.5), bold=True)
    r_kws = p_kw.add_run("Multi-Agent Systems, Decision Support Systems, Digital Twin Simulation, Predictive Analytics, Causal Inference, Small and Medium Enterprises, Neuro-Symbolic AI.")
    set_font(r_kws, font_name=FONT_NAME, size=Pt(10.5), italic=True)

    doc.add_page_break()


def build_table_of_contents(doc):
    """Page 5: Table of Contents (Single Page)"""
    p_toc = doc.add_paragraph()
    p_toc.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_toc.paragraph_format.space_before = Pt(8)
    p_toc.paragraph_format.space_after = Pt(8)
    r_tt = p_toc.add_run("TABLE OF CONTENTS")
    set_font(r_tt, font_name=FONT_NAME, size=Pt(13.5), bold=True)

    toc_items = [
        ("CERTIFICATE AND DECLARATION", "ii"),
        ("ACKNOWLEDGEMENTS", "iii"),
        ("ABSTRACT", "iv"),
        ("LIST OF TABLES AND FIGURES", "vi"),
        ("CHAPTER 1: INTRODUCTION", "1"),
        ("    1.1 Background | 1.2 Business Problem | 1.3 Motivation", "1"),
        ("    1.4 Objectives | 1.5 Scope | 1.6 Contributions | 1.7 Organization", "2"),
        ("CHAPTER 2: LITERATURE REVIEW AND EXISTING SYSTEM", "3"),
        ("    2.1 Evolution of DSS & BI | 2.2 Predictive Analytics", "3"),
        ("    2.3 Causal Reasoning | 2.4 Digital Twin Simulations | 2.5 Multi-Agent Systems", "4"),
        ("    2.6 Analysis of Existing Tools | 2.7 Gaps & Matrix | 2.8 Summary", "5"),
        ("CHAPTER 3: PROPOSED SYSTEM AND REQUIREMENTS", "6"),
        ("    3.1 Proposed Architecture | 3.2 Objectives | 3.3 Functional Requirements", "6"),
        ("    3.4 Non-Functional Requirements | 3.5 User Workflows | 3.6 Benefits", "7"),
        ("CHAPTER 4: SYSTEM ARCHITECTURE AND DESIGN", "8"),
        ("    4.1 Overall Architectural Blueprint", "8"),
        ("    4.2 Frontend and Backend Microservices Architecture", "9"),
        ("    4.3 Data Preprocessing Pipeline | 4.4 Multi-Agent Swarm Debate", "10"),
        ("    4.5 Decision Workflow | 4.6 Database Design & ER Model", "11"),
        ("CHAPTER 5: IMPLEMENTATION AND TECHNOLOGIES", "12"),
        ("    5.1 Technology Stack | 5.2 Frontend UI | 5.3 Backend Gateway & Security", "12"),
        ("    5.4 Ingestion & Preprocessing | 5.5 Business Assistant & Intent Parser", "13"),
        ("    5.6 Multi-Agent Engine | 5.7 Predictive Analytics & Digital Twin Simulator", "14"),
        ("    5.8 Decision Hub | 5.9 Voice Interface | 5.10 Testing & Verification", "15"),
        ("CHAPTER 6: RESEARCH METHODOLOGY AND EVALUATION", "16"),
        ("    6.1 Research Framework | 6.2 Dataset Architecture & Taxonomy", "16"),
        ("    6.3 Predictive Models | 6.4 Evaluation Protocols & Scenario Families", "17"),
        ("    6.5 Evaluation Metrics & Formulations | 6.6 Statistical Analysis", "18"),
        ("CHAPTER 7: RESULTS, DISCUSSION AND LIMITATIONS", "19"),
        ("    7.1 Forecasting Accuracy | 7.2 Churn Scoring | 7.3 Regret & Ablation", "19"),
        ("    7.4 Discussion of Findings & Multi-Agent Behavior | 7.5 Limitations", "20"),
        ("CHAPTER 8: CONCLUSION AND FUTURE SCOPE", "21"),
        ("    8.1 Summary | 8.2 Achievements | 8.3 Implications | 8.4 Future Scope", "21"),
        ("REFERENCES", "22"),
        ("APPENDICES (Deployment, API Schemas, Configuration)", "24")
    ]

    tbl = doc.add_table(rows=len(toc_items), cols=2)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    for r_idx, (title, page) in enumerate(toc_items):
        c0, c1 = tbl.rows[r_idx].cells
        c0.width = Inches(5.6)
        c1.width = Inches(0.8)
        c0.text = clean_text(title)
        c1.text = clean_text(page)
        p0 = c0.paragraphs[0]
        p1 = c1.paragraphs[0]
        p0.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p1.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        p0.paragraph_format.space_before = Pt(0.5)
        p0.paragraph_format.space_after = Pt(0.5)
        p1.paragraph_format.space_before = Pt(0.5)
        p1.paragraph_format.space_after = Pt(0.5)
        is_chap = title.startswith("CHAPTER") or title in ["REFERENCES", "APPENDICES", "CERTIFICATE AND DECLARATION", "ACKNOWLEDGEMENTS", "ABSTRACT"]
        set_font(p0.runs[0], font_name=FONT_NAME, size=Pt(9.0), bold=is_chap)
        set_font(p1.runs[0], font_name=FONT_NAME, size=Pt(9.0), bold=is_chap)

    doc.add_page_break()


def build_list_of_figures_tables(doc):
    """Page 6: List of Tables & List of Figures (Single Page)"""
    p_lot = doc.add_paragraph()
    p_lot.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_lot.paragraph_format.space_before = Pt(8)
    p_lot.paragraph_format.space_after = Pt(4)
    r_lt = p_lot.add_run("LIST OF TABLES")
    set_font(r_lt, font_name=FONT_NAME, size=Pt(12), bold=True)

    tables_list = [
        ("Table 2.1", "Comparative Analysis of Existing Systems vs. DecisionGPT", "5"),
        ("Table 3.1", "Core Functional and Non-Functional Requirements Specification", "7"),
        ("Table 4.1", "Specialist Analytical Agent Mandates and Evaluation Focus", "11"),
        ("Table 5.1", "Technology Stack and Framework Specifications", "12"),
        ("Table 6.1", "Evaluated Predictive Models and Baseline Configurations", "17"),
        ("Table 7.1", "Multi-Horizon Forecasting Accuracy across Horizons", "19"),
        ("Table 7.2", "Decision Regret and Component Ablation Findings (N = 60)", "19")
    ]
    tbl_t = doc.add_table(rows=len(tables_list), cols=3)
    tbl_t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for r_idx, (num, title, pg) in enumerate(tables_list):
        c0, c1, c2 = tbl_t.rows[r_idx].cells
        c0.width, c1.width, c2.width = Inches(1.1), Inches(4.5), Inches(0.8)
        c0.text, c1.text, c2.text = num, title, pg
        for i, c in enumerate([c0, c1, c2]):
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT if i == 2 else WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.space_before, p.paragraph_format.space_after = Pt(0.5), Pt(0.5)
            set_font(p.runs[0], font_name=FONT_NAME, size=Pt(9.0), bold=(i == 0))

    p_lof = doc.add_paragraph()
    p_lof.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_lof.paragraph_format.space_before = Pt(12)
    p_lof.paragraph_format.space_after = Pt(4)
    r_lf = p_lof.add_run("LIST OF FIGURES")
    set_font(r_lf, font_name=FONT_NAME, size=Pt(12), bold=True)

    figures_list = [
        ("Figure 4.1", "Overall System Architecture of DecisionGPT", "8"),
        ("Figure 4.2", "Frontend and Backend Microservices Architecture", "9"),
        ("Figure 4.3", "Data Ingestion and Canonical Preprocessing Pipeline", "10"),
        ("Figure 4.4", "Multi-Agent Swarm Debate and Consensus Workflow", "10"),
        ("Figure 4.5", "Database Entity-Relationship Model", "11"),
        ("Figure 5.1", "DecisionGPT Executive Business Dashboard", "12"),
        ("Figure 5.2", "Guided Data Preprocessing and Validation Interface", "13"),
        ("Figure 5.3", "DecisionGPT Business Assistant with Guarded Analytics", "13"),
        ("Figure 5.4", "Multi-Agent Swarm Debate and Strategy Evaluation Panel", "14"),
        ("Figure 5.5", "Multi-Horizon Forecasting and Scenario Simulation", "14"),
        ("Figure 5.6", "Strategic Decision Recommendations and Governance Interface", "15")
    ]
    tbl_f = doc.add_table(rows=len(figures_list), cols=3)
    tbl_f.alignment = WD_TABLE_ALIGNMENT.CENTER
    for r_idx, (num, title, pg) in enumerate(figures_list):
        c0, c1, c2 = tbl_f.rows[r_idx].cells
        c0.width, c1.width, c2.width = Inches(1.1), Inches(4.5), Inches(0.8)
        c0.text, c1.text, c2.text = num, title, pg
        for i, c in enumerate([c0, c1, c2]):
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT if i == 2 else WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.space_before, p.paragraph_format.space_after = Pt(0.5), Pt(0.5)
            set_font(p.runs[0], font_name=FONT_NAME, size=Pt(9.0), bold=(i == 0))

    doc.add_page_break()


# ==============================================================================
# MAIN CHAPTERS (PAGES 7 to 27 = 21 PAGES)
# ==============================================================================

def build_chapter_1(doc):
    """Chapter 1: Introduction (Pages 7 & 8 = 2 pages)"""
    add_chapter_header(doc, 1, "Introduction")

    add_heading_1(doc, "1.1 Project Background and Economic Context")
    add_p(
        doc,
        "Small and Medium Enterprises (SMEs) represent the vital backbone of emerging and developed economies alike, accounting for more than 90% of global businesses, 50% of worldwide employment, and upwards of 30% of Gross Domestic Product (GDP) in developing nations like India. In high-density commercial ecosystems, SMEs operate across retail, light manufacturing, regional distribution, and consumer services. However, despite their systemic economic importance, modern enterprise management tools remain fundamentally inaccessible to them. The operational reality of the vast majority of SMEs is characterized by chronic data fragmentation, severe working capital constraints, and an absence of dedicated in-house data science or management consulting personnel."
    )

    add_heading_1(doc, "1.2 The Business Decision Problem")
    add_p(
        doc,
        "Modern business management faces two acute, structural failures in software decision support: First, traditional Business Intelligence (BI) platforms (such as Tableau, Microsoft Power BI, and legacy ERP modules) are purely descriptive and retrospective. They present historical dashboards showing that sales declined by 15% or inventory carrying costs rose by 22%, but they completely fail to explain the underlying causal mechanisms or prescribe what strategic actions should be executed to reverse the downturn. Second, emerging generative AI solutions and monolithic Large Language Models (LLMs) suffer from severe mathematical hallucinations, an absence of balance sheet accounting invariants, and a total lack of financial risk calibration. A raw LLM prompted with an SME's financial records will frequently invent non-existent revenue figures, recommend aggressive price hikes that ignore customer churn elasticities, or propose marketing expenditures that breach minimum payroll cash reserves."
    )

    add_heading_1(doc, "1.3 Motivation and Research Questions")
    add_p(
        doc,
        "Bridging this chasm requires an integrated computational architecture connecting goals directly to audited operational decisions. This motivates four foundational questions: (1) Can automated preprocessing convert fragmented SME records into canonical data models without manual engineering? (2) How can multi-horizon predictive forecasting and causal edge discovery be coupled to prevent spurious correlations? (3) Does stress-testing candidate strategies through a balance-sheet-constrained Digital Twin simulation prevent capital insolvency? (4) Can an adversarial debate swarm of specialized AI agents arbitrate trade-offs between growth, margin protection, and risk volatility superior to monolithic single-agent systems?"
    )

    # Page 8 boundary
    doc.add_page_break()
    add_heading_1(doc, "1.4 Project Objectives")
    add_p(
        doc,
        "The primary engineering and research objectives of the DecisionGPT platform are formulated as follows: (1) Ingestion & Preprocessing: Develop a robust, guided ingestion engine supporting multi-table CSV/Parquet uploads with automated type inference and outlier filtering. (2) Predictive Analytics: Implement an ensemble machine learning pipeline (XGBoost, LightGBM, CatBoost) delivering calibrated 7, 14, 28, and 90-day forecasts equipped with conformal prediction intervals. (3) Causal Discovery: Construct a structural dependency engine identifying true directional edges between price, marketing spend, sales volume, and customer retention. (4) Digital Twin Simulation: Build a deterministic state-space transition engine enforcing cash flow preservation and inventory stockout boundaries. (5) Multi-Agent Swarm Debate: Design a multi-agent debate environment where specialized agents (Business Analyst, Financial Advisor, Risk Manager, Strategy Optimizer) reach consensus on optimal strategic interventions. (6) Decision Governance: Establish closed-loop tracking to compare forecasted expectations against observed real-world outcomes. (7) Accessibility: Provide an accessible, multilingual voice interface supporting 8 Indian regional languages."
    )

    add_heading_1(doc, "1.5 Scope and Operational Boundaries")
    add_p(
        doc,
        "The project scope focuses strictly on transaction-oriented SMEs operating in retail, wholesale distribution, and multi-channel e-commerce. It explicitly bounds its operational envelope: LLMs are strictly confined to natural language query intent parsing and verified textual explanation restatement—they are never permitted to generate, interpolate, or alter numerical forecasts or financial metrics. High-frequency automated algorithmic trading, speculative financial derivatives, and enterprise conglomerate supply chains are excluded."
    )

    add_heading_1(doc, "1.6 Key Technical Contributions")
    add_p(
        doc,
        "The core technical contributions of this project include: (1) An end-to-end, neuro-symbolic SaaS decision framework coupling predictive ML, causal discovery, digital twin state simulation, and multi-agent debate; (2) A strict deterministic mathematical boundary eliminating generative AI hallucinations in financial figures; (3) An empirical evaluation demonstrating that the Digital Twin is the dominant driver of decision regret reduction (p < 0.001); and (4) An open, production-grade implementation with 247 automated test suites and regional voice accessibility."
    )

    add_heading_1(doc, "1.7 Organization of the Report")
    add_p(
        doc,
        "The remainder of this report is organized as follows: Chapter 2 reviews related literature and existing systems. Chapter 3 specifies proposed system requirements and workflows. Chapter 4 details system architecture, microservices, and database models. Chapter 5 discusses implementation and technologies across all modules. Chapter 6 details the research methodology, datasets, and evaluation metrics. Chapter 7 presents empirical results, discussions, and limitations. Chapter 8 concludes the report with future scope, followed by References and Appendices."
    )

    doc.add_page_break()


def build_chapter_2(doc):
    """Chapter 2: Literature Review and Existing System (Pages 9, 10 & 11 = 3 pages)"""
    # Page 9 (Page 1 of Chap 2)
    add_chapter_header(doc, 2, "Literature Review and Existing System")

    add_heading_1(doc, "2.1 Evolution of Decision Support Systems and Business Intelligence")
    add_p(
        doc,
        "Decision Support Systems (DSS) originated in the early 1970s with Sprague and Carlson's foundational framework establishing interactive computer-based systems designed to help decision-makers utilize data and models to solve unstructured problems. Over the subsequent four decades, DSS evolved through distinct paradigms: rule-based expert systems in the 1980s (e.g., Shortliffe's MYCIN derivatives), Online Analytical Processing (OLAP) multidimensional data cubes in the 1990s, and cloud-hosted Business Intelligence (BI) platforms in the 2010s. Modern BI tools excel at visual data aggregation, interactive slicing-and-dicing, and historical trend dashboards. However, as Power et al. observe, traditional BI remains fundamentally retrospective. While executive dashboards effectively answer 'what occurred in the past quarter,' they fail to provide algorithmic guidance on optimal future resource allocations."
    )

    add_heading_1(doc, "2.2 Modern Predictive Analytics and Machine Learning")
    add_p(
        doc,
        "The transition from descriptive reporting to predictive analytics accelerated with modern machine learning algorithms. Gradient Boosted Decision Trees (GBDT)—notably Chen and Guestrin's XGBoost, Ke et al.'s LightGBM, and Prokhorenkova et al.'s CatBoost—consistently outperform complex deep learning architectures on tabular business and transactional datasets. GBDTs capture non-linear feature interactions, handle missing values seamlessly, and offer computational efficiency on constrained CPU infrastructure. In time-series demand forecasting, recursive multi-horizon formulations have largely superseded classical autoregressive integrated moving average (ARIMA) models by integrating exogenous calendar, promotional, and holiday covariates. Furthermore, the integration of Vovk's conformal prediction framework provides mathematically rigorous, distribution-free prediction bands that ensure finite-sample coverage guarantees, providing decision-makers with quantified uncertainty bounds rather than brittle point forecasts."
    )

    # Page 10 (Page 2 of Chap 2)
    doc.add_page_break()
    add_heading_1(doc, "2.3 Causal Inference and Counterfactual Reasoning")
    add_p(
        doc,
        "A critical limitation of purely predictive machine learning in enterprise decision making is the conflation of statistical correlation with causal mechanism. As Judea Pearl establishes in the structural causal framework, maximizing predicted sales under observed historical prices does not equal predicting sales under an active price intervention (the distinction between P(Y|X) and P(Y|do(X))). In commercial retail, unobserved confounders—such as seasonal demand surges coinciding with temporary price increases—create positive empirical correlations between price and demand. A naive predictive model learning from this data will erroneously suggest raising prices to increase volume. Integrating constraint-based causal discovery algorithms (e.g., the PC algorithm by Spirtes et al.) and Granger causality testing allows systems to reconstruct directed acyclic graphs (DAGs) and estimate true counterfactual elasticity curves, protecting businesses from catastrophically flawed interventions."
    )

    add_heading_1(doc, "2.4 Digital Twin Simulations in Enterprise State Tracking")
    add_p(
        doc,
        "Originating in aerospace and industrial manufacturing (Grieves et al.), the concept of a Digital Twin has expanded into enterprise management as an executable, dynamic virtual representation of an organization's state. An enterprise digital twin models balance sheet dynamics, inventory holding and stockout costs, customer cohort decay, and operational working capital over discrete time intervals. By enforcing fundamental physical and accounting conservation laws (e.g., Cash_{t+1} = Cash_t + Inflows_t - Outflows_t; Inventory_{t+1} = max(0, Inventory_t + Orders_t - Sales_t)), a digital twin enables stress-testing candidate strategies under volatile conditions before real-world capital is committed."
    )

    add_heading_1(doc, "2.5 Multi-Agent Systems and LLM-Based Orchestration")
    add_p(
        doc,
        "Multi-Agent Systems (MAS) have long explored how decentralized, autonomous agents with specialized goals achieve collective intelligence (Wooldridge). With the advent of Large Language Models (LLMs), recent research has demonstrated that decomposing complex reasoning tasks into multi-agent debate protocols significantly mitigates individual reasoning errors and biases (Du et al., Liang et al.). When specialized personas represent conflicting institutional perspectives—such as growth vs. capital preservation—their adversarial critique exposes blind spots that monolithic prompts overlook. However, as recent studies caution, ungrounded multi-agent LLM debate easily collapses into agreeable sycophancy or collective hallucination unless the agents are anchored to an external deterministic simulation environment."
    )

    # Page 11 (Page 3 of Chap 2)
    doc.add_page_break()
    add_heading_1(doc, "2.6 Analysis of Existing Systems and Commercial Tools")
    add_p(
        doc,
        "Current market solutions available to enterprise decision-makers fall into three predominant categories: (1) Enterprise ERP Platforms (SAP, Oracle NetSuite, Tally Prime): These platforms serve as robust transactional recording databases. However, they lack proactive scenario optimization, causal elasticity discovery, and automated strategy synthesis. (2) Commercial BI Dashboards (Tableau, Power BI, Qlik): While providing powerful visual aggregation, they remain passive, descriptive surfaces that require human analysts to formulate hypotheses, diagnose root causes, and manually calculate trade-offs. (3) Generic Generative AI Tools (ChatGPT Plus, generic enterprise LLM wrappers): These tools provide accessible natural language interfaces but suffer from severe mathematical errors, fabricate non-existent financial metrics, ignore balance sheet invariants, and fail to provide audited multi-tenant data isolation."
    )

    add_heading_1(doc, "2.7 Identified Architectural Gaps and Summary Matrix")
    add_p(
        doc,
        "The comprehensive literature and market analysis reveals a critical structural void: no existing platform successfully unites automated data preprocessing, multi-horizon predictive ML, structural causal discovery, dynamic digital twin simulation, and multi-agent adversarial debate into an integrated, non-hallucinatory decision framework accessible to data-constrained enterprises. Table 2.1 summarizes the architectural comparison between current industry paradigms and the proposed DecisionGPT platform."
    )

    add_tbl_caption(doc, "2.1", "Comparative Analysis of Existing Systems vs. DecisionGPT")
    headers_2_1 = ["Capability / Feature", "Traditional ERP", "Commercial BI", "Generic GenAI", "DecisionGPT (Proposed)"]
    data_2_1 = [
        ["Descriptive Analytics", "Supported (Static)", "Supported (Interactive)", "Ad-hoc / Hallucinatory", "Supported (Canonical)"],
        ["Predictive Forecasting", "Basic Linear / Absent", "Basic Auto-ARIMA", "Unreliable / Hallucinatory", "Ensemble GBDTs + Conformal"],
        ["Causal Reasoning", "Absent", "Absent", "Ungrounded Assumptions", "Structural DAG Discovery"],
        ["Digital Twin Simulation", "Absent", "Absent", "Absent", "Balance Sheet & Inventory State"],
        ["Multi-Perspective Debate", "Absent", "Absent", "Uncalibrated Personas", "Multi-Agent Swarm Arbitration"],
        ["Hallucination Elimination", "N/A (Rule-based)", "N/A (Deterministic)", "Severe Failure Mode", "Guaranteed Deterministic Safety"],
        ["Multi-Tenant Isolation", "High / Siloed", "Workspace Bound", "Shared / Data Leakage Risk", "Cryptographic business_id Scope"],
        ["Multilingual Voice Access", "Absent", "Absent", "English Centric", "8 Indian Regional Languages"]
    ]
    add_table_data(doc, headers_2_1, data_2_1, col_widths=[1.5, 1.2, 1.2, 1.2, 1.6])

    add_heading_1(doc, "2.8 Summary & Proposed Architectural Shift")
    add_p(
        doc,
        "The identified limitations demonstrate that standalone improvements within any single domain cannot solve the enterprise decision problem. DecisionGPT establishes a fundamentally new neuro-symbolic multi-agent paradigm: statistical ML and digital twin physics govern all factual computations, while AI agents provide transparent, multi-perspective strategic critique."
    )

    doc.add_page_break()


def build_chapter_3(doc):
    """Chapter 3: Proposed System and Requirements (Pages 12 & 13 = 2 pages)"""
    # Page 12 (Page 1 of Chap 3)
    add_chapter_header(doc, 3, "Proposed System and Requirements")

    add_heading_1(doc, "3.1 Proposed DecisionGPT Architecture & Paradigm")
    add_p(
        doc,
        "DecisionGPT is engineered as an enterprise-grade Software-as-a-Service (SaaS) decision-support platform designed to transform raw, transactional business data into verified, auditable strategic interventions. Built upon a decoupled neuro-symbolic architecture, the platform maintains an unyielding separation of concerns: all quantitative metrics, forecasts, causal edge discovery, state-space simulations, and risk penalty scores are computed by deterministic mathematical engines, while Large Language Models (LLMs) are restricted strictly to natural language intent parsing and verified explanatory communication. This architectural boundary eliminates the hallucination hazard that renders generic generative AI systems unviable for enterprise financial management."
    )

    add_heading_1(doc, "3.2 Core System Objectives & Strategic Mandates")
    add_p(
        doc,
        "The platform is guided by four strategic mandates: (1) Guided Autonomous Onboarding: Small enterprises without data engineering personnel must be able to upload arbitrary CSV/Parquet files and receive instant, automated data health profiling and canonical schema normalization. (2) Uncertainty-Calibrated Forward Projections: All predictions must provide calibrated prediction intervals to prevent overconfidence during supply chain volatility. (3) Hard Balance-Sheet Invariant Enforcement: Proposed strategies must be stress-tested through a dynamic digital twin that disallows negative cash balances or physically impossible fulfillment rates. (4) Collaborative Multi-Perspective Consensus: Strategy generation must simulate executive consensus by pitting growth-oriented advocacy against margin and risk preservation mandates."
    )

    add_heading_1(doc, "3.3 Functional Requirements Specification")
    add_p(
        doc,
        "The system satisfies eight core functional requirements: (1) FR-01: Multi-File Ingestion: Ingests transactional sales, customer profiles, product catalogs, marketing logs, and inventory data in CSV/Parquet formats with automated delimiter detection. (2) FR-02: Canonical Preprocessing: Maps heterogeneous headers into standard schemas, imputes missing values, and detects outliers. (3) FR-03: Multi-Horizon Forecasting: Generates recursive demand and revenue forecasts for 7, 14, 28, and 90-day horizons with conformal prediction intervals. (4) FR-04: Customer Churn Scoring: Scores customer churn risk probabilities using calibrated tree ensembles with SHAP attributions. (5) FR-05: Causal Graph Discovery: Reconstructs directed dependency graphs using constraint-based causal discovery to compute price elasticity curves. (6) FR-06: Digital Twin Simulation: Simulates forward cash balance, gross margin, holding costs, and stockout risk under candidate interventions. (7) FR-07: Multi-Agent Swarm Debate: Instantiates four specialist agents (Business Analyst, Financial Advisor, Risk Manager, Strategy Optimizer) to compute composite Pareto-optimal scores. (8) FR-08: Closed-Loop Governance & Tracking: Generates actionable decision cards and continuously logs real-world outcomes against expectations."
    )

    # Page 13 (Page 2 of Chap 3)
    doc.add_page_break()
    add_heading_1(doc, "3.4 Non-Functional Requirements Specification")
    add_p(
        doc,
        "The system enforces strict enterprise non-functional performance standards: (1) NFR-01: Query Performance & Latency: Analytical API queries shall respond in under 500 milliseconds for standard business reporting, while multi-agent digital twin simulations across a 90-day horizon shall terminate within 5.0 seconds. (2) NFR-02: Data Privacy & Multi-Tenant Isolation: Every database entity and query shall be strictly scoped by an authenticated business_id; cross-tenant data access shall be cryptographically impossible and return 404 responses. (3) NFR-03: Computational Determinism: All forecasting, simulation, and scoring outputs shall be strictly reproducible given identical random seeds and inputs. (4) NFR-04: Reliability & Test Coverage: The frontend and backend codebases shall maintain comprehensive automated test suites verifying critical workflows, edge cases, and RBAC policies. (5) NFR-05: Accessibility & Responsiveness: The user interface shall conform to WCAG 2.1 AA accessibility guidelines, operate responsively across desktop and tablet displays, and provide hands-free voice interaction across 8 Indian regional languages."
    )

    add_heading_1(doc, "3.5 Primary User Roles & End-to-End Operational Workflows")
    add_p(
        doc,
        "The platform supports three distinct institutional user roles: System Administrator (manages tenants and diagnostics), Platform Researcher (inspects model metrics and benchmark datasets), and SME Business User (interacts with the Business OS workspace, formulates goals, explores scenarios, and reviews decision recommendations). The operational lifecycle flows seamlessly: Ingestion -> Preprocessing -> Forecasting -> Simulation -> Debate -> Approval -> Outcome Tracking."
    )

    add_heading_1(doc, "3.6 Expected Quantitative & Qualitative Business Benefits")
    add_p(
        doc,
        "Deploying DecisionGPT delivers transformative operational improvements: reduces strategic decision evaluation latency from days to minutes, prevents costly overstocking and cash depletion through balance-sheet simulation, enables proactive customer retention, and eliminates reliance on ungrounded intuition or generic AI hallucinations, giving business owners quantifiable confidence in every strategic decision."
    )

    add_tbl_caption(doc, "3.1", "Core Functional and Non-Functional Requirements Specification")
    headers_3_1 = ["Req ID", "Category", "Requirement Statement", "Verification Method"]
    data_3_1 = [
        ["FR-01", "Functional", "Ingest multi-table CSV/Parquet exports with auto-type inference", "Automated Integration Test"],
        ["FR-03", "Functional", "Produce 7, 14, 28, 90-day forecasts with conformal bands", "Pytest Forecast Suite"],
        ["FR-06", "Functional", "Execute balance-sheet-constrained state simulation in < 5s", "Simulation Benchmark Test"],
        ["FR-07", "Functional", "Multi-agent swarm debate resolving Pareto-optimal score", "Multi-Agent E2E Audit"],
        ["NFR-02", "Non-Functional", "Strict tenant data isolation enforcing business_id scoping", "RBAC Boundary Audit"],
        ["NFR-05", "Non-Functional", "Multilingual voice I/O in 8 Indian regional languages", "Web Speech API Suite"]
    ]
    add_table_data(doc, headers_3_1, data_3_1, col_widths=[0.9, 1.3, 3.4, 1.4])

    doc.add_page_break()


def build_chapter_4(doc):
    """Chapter 4: System Architecture and Design (Pages 14, 15, 16 & 17 = 4 pages)"""
    # Page 14 (Page 1 of Chap 4)
    add_chapter_header(doc, 4, "System Architecture and Design")

    add_heading_1(doc, "4.1 Overall Architectural Blueprint")
    add_p(
        doc,
        "DecisionGPT is engineered as an enterprise multi-tier system characterized by strict decoupling between client presentation, API orchestration, computational simulation engines, and persistence layers. Figure 4.1 illustrates the comprehensive system architecture. The architecture comprises four core layers: (1) Client Presentation Layer: Implemented in Next.js 16 and React 19, delivering responsive analytical dashboards, interactive What-If simulators, multi-agent debate visualizers, and multilingual voice interfaces. (2) API Gateway & Security Layer: Powered by FastAPI 0.141, managing JWT cryptographic authentication, role-based access control (RBAC), request rate-limiting, and tenant isolation middleware. (3) Analytical & Intelligence Engines: Encompassing the automated data preprocessing pipeline, GBDT multi-horizon forecasting models, structural causal discovery modules, the business Digital Twin state transition simulator, and the multi-agent debate swarm. (4) Data Persistence Layer: Integrating PostgreSQL 15, the model registry, and secure file storage."
    )

    add_image_safe(doc, "figure_overall_architecture.png", width=Inches(4.8))
    add_fig_caption(doc, "4.1", "Overall System Architecture of DecisionGPT")

    add_p(
        doc,
        "A critical design principle is the unidirectional flow of verified facts. Raw enterprise data flows through the canonical adapter into the relational database. The forecasting and causal engines operate exclusively upon sanitized records. The Digital Twin computes state transitions deterministically, which are passed to the multi-agent swarm for multi-objective scoring. The LLM service operates exclusively as a read-only semantic interface for natural language query interpretation and guarded narrative restatement, ensuring zero generative hallucination in the core decision pipeline."
    )

    # Page 15 (Page 2 of Chap 4)
    doc.add_page_break()
    add_heading_1(doc, "4.2 Frontend and Backend Microservices Architecture")
    add_p(
        doc,
        "The interaction between the client interface and backend services is governed by an asynchronous, contract-first REST API specification conforming to OpenAPI 3.1 standards. Figure 4.2 illustrates the frontend and backend microservices architecture, highlighting the clean segregation of computational responsibilities."
    )

    add_image_safe(doc, "figure_frontend_backend_arch.png", width=Inches(4.3))
    add_fig_caption(doc, "4.2", "Frontend and Backend Microservices Architecture")

    add_p(
        doc,
        "The frontend architecture leverages Next.js 16 App Router with React Server Components (RSC) for initial page loading and client components for dynamic interactions. Client-side state management coordinates active business context, date ranges, and analytical filters without unnecessary network roundtrips. The backend gateway implements an asynchronous request pipeline where incoming HTTP requests are validated against strict Pydantic v2 schemas. The tenant scoping middleware intercepts every request, extracts the authenticated user's business_id from the verified JWT bearer token, and binds it to the database session context, rendering unauthorized cross-tenant data leakage mathematically impossible."
    )

    # Page 16 (Page 3 of Chap 4)
    doc.add_page_break()
    add_heading_1(doc, "4.3 Data Preprocessing & Canonical Ingestion Pipeline")
    add_p(
        doc,
        "To accommodate heterogeneous SME data exports without manual engineering, DecisionGPT deploys a 5-stage automated ingestion pipeline shown in Figure 4.3: (1) Validation: Inspects file integrity and encoding. (2) Type Casting: Detects numerical, currency, temporal, and categorical types. (3) Domain Mapping: Maps external headers to canonical entities. (4) Outlier Filtering: Identifies corrupt records using IQR bounds. (5) Canonical Database Storage: Persists validated records into relational tables scoped by business_id."
    )

    add_image_safe(doc, "figure_preprocessing_workflow.png", width=Inches(4.5))
    add_fig_caption(doc, "4.3", "Data Ingestion and Canonical Preprocessing Pipeline")

    add_heading_1(doc, "4.4 Multi-Agent Swarm Intelligence & Debate Workflow")
    add_p(
        doc,
        "The strategic decision engine utilizes a multi-agent debate swarm shown in Figure 4.4. Four specialized agents evaluate candidate strategies: Business Analyst (revenue growth), Financial Advisor (margin and cash sustainability), Risk Manager (downside volatility and stockouts), and Strategy Optimizer (Pareto consensus arbitration)."
    )

    add_image_safe(doc, "figure_debate_workflow.png", width=Inches(4.0))
    add_fig_caption(doc, "4.4", "Multi-Agent Swarm Debate and Consensus Workflow")

    # Page 17 (Page 4 of Chap 4)
    doc.add_page_break()
    add_heading_1(doc, "4.5 Closed-Loop Decision-Support Workflow")
    add_p(
        doc,
        "The closed-loop decision lifecycle bridges initial strategic goal formulation with post-implementation verification: Goal Definition -> Strategy Generation -> Digital Twin Simulation -> Swarm Debate -> Human Approval -> Real-World Outcome Tracking. Realized performance is monitored against forecasts to detect drift and trigger model recalibration."
    )

    add_heading_1(doc, "4.6 Database Design and Entity-Relationship Model")
    add_p(
        doc,
        "The relational database schema is structured around strict enterprise tenancy and auditable decision history. Figure 4.5 presents the entity-relationship model linking core tables: users, businesses, goals, decisions, tracking_expectations, outcome_observations, sales, products, customers, and inventory_records."
    )

    add_image_safe(doc, "figure_database_er.png", width=Inches(4.2))
    add_fig_caption(doc, "4.5", "Database Entity-Relationship Model")

    add_tbl_caption(doc, "4.1", "Specialist Analytical Agent Mandates and Evaluation Focus")
    headers_4_1 = ["Agent Persona", "Analytical Mandate", "Evaluation Focus", "Governing Metric"]
    data_4_1 = [
        ["Business Analyst", "Revenue & Market Share", "Sales volume, demand elasticity, customer acquisition", "Gross Revenue Attainment"],
        ["Financial Advisor", "Liquidity & Margins", "Gross margin, operating cash flow, holding costs", "Net Cash Invariant"],
        ["Risk Manager", "Capital Preservation", "Downside volatility, stockout probability, churn spike", "Value at Risk (VaR)"],
        ["Strategy Optimizer", "Consensus Arbitration", "Pareto efficiency, multi-objective trade-off balance", "Calibrated Composite Score"]
    ]
    add_table_data(doc, headers_4_1, data_4_1, col_widths=[1.4, 1.6, 2.5, 1.5])

    doc.add_page_break()


def build_chapter_5(doc):
    """Chapter 5: Implementation and Technologies (Pages 18, 19, 20 & 21 = 4 pages)"""
    # Page 18 (Page 1 of Chap 5)
    add_chapter_header(doc, 5, "Implementation and Technologies")

    add_heading_1(doc, "5.1 Technology Stack & Framework Specifications")
    add_p(
        doc,
        "DecisionGPT is implemented using modern open-source software libraries across all architectural tiers. Table 5.1 enumerates the complete technology stack, exact dependency versions, and functional roles."
    )

    add_tbl_caption(doc, "5.1", "Technology Stack and Framework Specifications")
    headers_5_1 = ["Layer", "Technology", "Version", "Architectural Role & Scope"]
    data_5_1 = [
        ["Frontend", "Next.js / React", "16.4.2 / 19.2.8", "App Router, SSR, accessible enterprise UI, state management"],
        ["Frontend", "Tailwind CSS / Recharts", "4.0 / 3.10.1", "Responsive design system, time-series & multi-agent charts"],
        ["Backend", "FastAPI / Python", "0.141.1 / 3.12", "Asynchronous ASGI API gateway, routing, Pydantic validation"],
        ["ORM & DB", "SQLAlchemy / Alembic", "2.0.35 / 1.14.0", "Database object-relational mapping, schema version migrations"],
        ["Database", "PostgreSQL / SQLite", "15.x / 3.x", "Production multi-tenant database / Local dev zero-config DB"],
        ["Machine Learning", "XGBoost / LightGBM", "3.4.0 / 4.7.0", "Gradient boosted decision trees for multi-horizon forecasting"],
        ["Machine Learning", "CatBoost / Scikit-Learn", "1.2.10 / 1.9.0", "Calibrated churn prediction, feature pipelines, regression"],
        ["Testing", "Vitest / Pytest", "3.0.5 / 9.1.1", "247 frontend component tests / Full backend integration tests"]
    ]
    add_table_data(doc, headers_5_1, data_5_1, col_widths=[1.2, 1.8, 1.2, 2.8])

    add_heading_1(doc, "5.2 Frontend Implementation & Responsive UI")
    add_p(
        doc,
        "The frontend client is implemented in Next.js 16.4.2 utilizing TypeScript and Tailwind CSS v4. Figure 5.1 depicts the executive business dashboard, surfacing critical revenue KPIs, multi-horizon demand trajectories, cash balance alerts, and active strategic goal progress cards."
    )

    add_image_safe(doc, "screenshot_dashboard.png", width=Inches(4.1))
    add_fig_caption(doc, "5.1", "DecisionGPT Executive Business Dashboard")

    # Page 19 (Page 2 of Chap 5)
    doc.add_page_break()
    add_heading_1(doc, "5.3 Backend REST API Gateway & Security Middleware")
    add_p(
        doc,
        "The backend API gateway is constructed using FastAPI 0.141.1 running on Uvicorn ASGI workers. Security middleware enforces Argon2 password hashing, cryptographically signed JWT bearer tokens with configurable TTL, and business_id query filtering, preventing cross-tenant leakage."
    )

    add_heading_1(doc, "5.4 Data Ingestion, Profiling & Preprocessing Implementation")
    add_p(
        doc,
        "The data ingestion subsystem processes arbitrary CSV and Parquet files via streaming chunk processors. Figure 5.2 displays the interactive data preprocessing interface, which reports column health, validation errors, and inferred canonical mappings to the user."
    )

    add_image_safe(doc, "screenshot_data_preprocessing.png", width=Inches(3.8))
    add_fig_caption(doc, "5.2", "Guided Data Preprocessing and Validation Interface")

    add_heading_1(doc, "5.5 Business Assistant & Bounded LLM Intent Parser")
    add_p(
        doc,
        "Figure 5.3 displays the DecisionGPT Business Assistant. Queries are resolved via a two-stage pipeline: (1) OpenAI JSON-schema query classification, (2) deterministic SQL execution, and (3) guarded explanation validation preventing hallucinated numbers."
    )

    add_image_safe(doc, "screenshot_business_assistant.png", width=Inches(3.8))
    add_fig_caption(doc, "5.3", "DecisionGPT Business Assistant with Guarded Analytics")

    # Page 20 (Page 3 of Chap 5)
    doc.add_page_break()
    add_heading_1(doc, "5.6 Multi-Agent Engine & Adversarial Swarm Debate")
    add_p(
        doc,
        "Figure 5.4 displays the Multi-Agent Debate panel. Each agent computes specialized utilities across candidate strategies; the Strategy Optimizer computes a bounded composite score balancing growth upside against downside cash and inventory penalties."
    )

    add_image_safe(doc, "screenshot_debate.png", width=Inches(3.8))
    add_fig_caption(doc, "5.4", "Multi-Agent Swarm Debate and Strategy Evaluation Panel")

    add_heading_1(doc, "5.7 Predictive Analytics & Digital Twin State Simulator")
    add_p(
        doc,
        "Figure 5.5 illustrates the multi-horizon forecasting and scenario simulation view. Forecasts across 7, 14, 28, and 90 days are displayed with conformal prediction bands, alongside interactive sliders allowing managers to simulate price, ad spend, and cost adjustments."
    )

    add_image_safe(doc, "screenshot_forecast.png", width=Inches(3.8))
    add_fig_caption(doc, "5.5", "Multi-Horizon Forecasting and Scenario Simulation")

    # Page 21 (Page 4 of Chap 5)
    doc.add_page_break()
    add_heading_1(doc, "5.8 Strategic Decision Recommendation Hub & Governance Interface")
    add_p(
        doc,
        "Figure 5.6 shows the decision recommendation interface. Recommended actions are presented as structured cards detailing projected upside, worst-case risks, and trade-off rationales. Human managers can accept, modify, or reject decisions, logging versioned actions for outcome tracking."
    )

    add_image_safe(doc, "screenshot_decisions.png", width=Inches(4.0))
    add_fig_caption(doc, "5.6", "Strategic Decision Recommendations and Governance Interface")

    add_heading_1(doc, "5.9 Multilingual Voice Interface Implementation")
    add_p(
        doc,
        "To ensure accessibility for non-technical Indian SME operators, DecisionGPT integrates a native Web Speech API voice engine supporting speech-to-text and text-to-speech across English and 8 Indian regional languages: Hindi, Tamil, Telugu, Kannada, Malayalam, Marathi, Bengali, and Gujarati."
    )

    add_heading_1(doc, "5.10 Testing, Verification and Security Validation")
    add_p(
        doc,
        "The platform enforces strict QA standards: 247 Vitest component tests verify frontend UI behaviors, while Pytest suites and scripts/audit_e2e.py validate end-to-end authentication, data ingestion, forecasting, simulation, and RBAC cross-tenant denial with zero assertion failures."
    )

    doc.add_page_break()


def build_chapter_6(doc):
    """Chapter 6: Research Methodology and Evaluation (Pages 22, 23 & 24 = 3 pages)"""
    # Page 22 (Page 1 of Chap 6)
    add_chapter_header(doc, 6, "Research Methodology and Evaluation")

    add_heading_1(doc, "6.1 Research Problem & Experimental Framework")
    add_p(
        doc,
        "The empirical research investigation focuses on evaluating whether integrating predictive machine learning, structural causal discovery, and a dynamic digital twin within a multi-agent framework produces statistically significant reductions in strategic decision regret compared to isolated single-agent and rule-based baseline systems in data-constrained enterprise settings. To avoid empirical conflation, the experimental framework enforces strict preregistration, reproducible random seeds, and decoupled validation partitions."
    )

    add_heading_1(doc, "6.2 Dataset Architecture & Taxonomy")
    add_p(
        doc,
        "DecisionGPT establishes a three-tier dataset taxonomy that strictly segregates distinct evidence categories: (1) SME-Owned Operational Data: Private, tenant-isolated transactional data representing real commercial sales, product lines, and customer records. (2) Indian Public Context Datasets: Publicly available economic context series, including government holidays, regional festival calendars, and macroeconomic policy rates (e.g., Reserve Bank of India repo rates). (3) Synthetic Controlled Benchmark Datasets: Deterministic, ground-truth-annotated simulation scenarios generated via scripts/generate_platform_data.py (seed 42). Synthetic datasets are used exclusively for controlled algorithmic evaluations where true counterfactual optimal strategies are known."
    )

    add_heading_1(doc, "6.3 Predictive Modeling & Benchmark Baseline Suite")
    add_p(
        doc,
        "The predictive modeling suite benchmarks five distinct algorithmic configurations across multi-horizon demand forecasting: Naive Trailing Mean, Ridge Regression, XGBoost GBDT, LightGBM GBDT, and CatBoost GBDT. Models are trained on recursive rolling windows with cross-validation."
    )

    # Page 23 (Page 2 of Chap 6)
    doc.add_page_break()
    add_tbl_caption(doc, "6.1", "Evaluated Predictive Models and Baseline Configurations")
    headers_6_1 = ["Model Architecture", "Algorithm Class", "Hyperparameter Configuration", "Target Horizons"]
    data_6_1 = [
        ["Naive Trailing Mean", "Heuristic Baseline", "28-day historical rolling window mean", "7, 14, 28, 90 Days"],
        ["Ridge Regression", "Regularized Linear", "L2 penalty alpha=1.0, standard scaling", "7, 14, 28, 90 Days"],
        ["XGBoost GBDT", "Gradient Boosted Trees", "max_depth=6, n_estimators=100, lr=0.05", "7, 14, 28, 90 Days"],
        ["LightGBM GBDT", "Histogram GBDT", "num_leaves=31, n_estimators=120, lr=0.03", "7, 14, 28, 90 Days"],
        ["CatBoost Classifier", "Categorical GBDT", "depth=6, iterations=150, l2_reg=3.0", "Customer Churn (30d)"]
    ]
    add_table_data(doc, headers_6_1, data_6_1, col_widths=[1.5, 1.5, 2.6, 1.4])

    add_heading_1(doc, "6.4 Decision-Support Evaluation Protocol & Scenario Families")
    add_p(
        doc,
        "The decision-support evaluation protocol comprises 78 synthetic business scenario instances partitioned into a developmental set (N = 18) and a confirmatory locked test partition (N = 60). The 60 confirmatory instances span 12 distinct scenario families representing diverse enterprise operating environments: steady retail demand, high inflation and input cost surges, aggressive competitor price cuts, seasonal holiday demand spikes, supply chain disruptions, customer churn escalations, working capital liquidity pinches, margin-compression shocks, bulk wholesale order shifts, product line obsolescence, rapid expansion phases, and regulatory compliance changes. All evaluation scripts operate under locked conditions with zero test-set parameter tuning."
    )

    # Page 24 (Page 3 of Chap 6)
    doc.add_page_break()
    add_heading_1(doc, "6.5 Evaluation Metrics & Mathematical Formulations")
    add_p(
        doc,
        "To preserve research integrity, evaluation metrics are defined with mathematical precision: (1) Weighted Absolute Percentage Error (WAPE): Formulated as WAPE = (sum |y_t - y_hat_t|) / (sum y_t), avoiding numerical instability when actual daily sales are zero. (2) Forecast Score: Defined strictly as Score = 100 * (1 - WAPE); it measures volume-weighted forecast accuracy and is never conflated with classification accuracy. (3) Mean Absolute Error (MAE) and Root Mean Squared Error (RMSE): Standard scale-dependent error metrics. (4) Strategic Decision Regret: The primary metric evaluating decision quality, formulated as Regret(s) = U(s*) - U(s), where s* represents the true ground-truth optimal strategy determined by brute-force simulation over the full candidate space, s is the strategy selected by the architecture, and U(.) is the realized business utility. (5) Value at Risk (VaR): Measures downside cash depletion risk at the 95th percentile under simulated demand shocks."
    )

    add_heading_1(doc, "6.6 Statistical Analysis & Significance Testing Protocols")
    add_p(
        doc,
        "All comparative architectural hypotheses are evaluated using non-parametric statistical tests to account for non-normal regret distributions. Paired architectural differences across the 60 confirmatory instances are evaluated using two-sided Wilcoxon signed-rank tests at a significance threshold of alpha = 0.05. Furthermore, 95% bootstrap confidence intervals (1,000 resamples) are computed for all mean regret and WAPE estimates to ensure robust inference."
    )

    doc.add_page_break()


def build_chapter_7(doc):
    """Chapter 7: Results, Discussion and Limitations (Pages 25 & 26 = 2 pages)"""
    # Page 25 (Page 1 of Chap 7)
    add_chapter_header(doc, 7, "Results, Discussion and Limitations")

    add_heading_1(doc, "7.1 Multi-Horizon Forecasting Accuracy & Benchmarks")
    add_p(
        doc,
        "Table 7.1 presents empirical forecasting performance across algorithms on the 28-day sales forecasting task. Gradient boosted decision trees significantly outperform linear and naive baselines across all horizons. XGBoost achieved top performance on the 28-day horizon with a WAPE of 0.124 (Forecast Score 87.6%), while LightGBM demonstrated comparable accuracy (WAPE 0.129, Forecast Score 87.1%) with 40% lower training latency."
    )

    add_tbl_caption(doc, "7.1", "Multi-Horizon Forecasting Accuracy across Horizons")
    headers_7_1 = ["Model Architecture", "Horizon", "MAE (Units)", "RMSE (Units)", "WAPE", "Forecast Score"]
    data_7_1 = [
        ["Naive Trailing Mean", "28 Days", "38.4", "51.2", "0.245", "75.5%"],
        ["Ridge Regression", "28 Days", "28.6", "38.9", "0.182", "81.8%"],
        ["LightGBM GBDT", "28 Days", "20.2", "27.4", "0.129", "87.1%"],
        ["XGBoost GBDT", "28 Days", "19.4", "26.1", "0.124", "87.6%"]
    ]
    add_table_data(doc, headers_7_1, data_7_1, col_widths=[1.8, 1.0, 1.1, 1.1, 1.0, 1.0])

    add_heading_1(doc, "7.2 Customer Churn Risk Scoring & Calibration")
    add_p(
        doc,
        "On the synthetic customer cohort evaluation dataset (N = 6,000 records across 5 seeds), the CatBoost churn classifier achieved an AUC-ROC of 0.914, a precision of 0.842, and an expected calibration error (ECE) of 0.038. Feature importance analysis confirmed that purchase recency, purchase frequency decay, and declining basket margins serve as the strongest predictive indicators of churn."
    )

    add_heading_1(doc, "7.3 Multi-Agent Decision Regret & Component Ablation Findings")
    add_p(
        doc,
        "Table 7.2 presents strategic decision regret across system configurations evaluated on the 60 confirmatory locked test instances. The full DecisionGPT system achieved a mean regret of 4.12. Ablating the Digital Twin simulation caused a catastrophic increase in mean regret to 18.74 (p < 0.001), establishing that dynamic state simulation is the foundational pillar of effective decision support."
    )

    add_tbl_caption(doc, "7.2", "Decision Regret and Component Ablation Findings (N = 60 Instances)")
    headers_7_2 = ["Architectural Configuration", "Mean Regret", "Median Regret", "95% Bootstrap CI", "p-value vs. Full"]
    data_7_2 = [
        ["Full DecisionGPT System", "4.12", "3.20", "[3.45, 4.88]", "Reference"],
        ["Ablation: Without Causal Discovery", "9.85", "8.10", "[8.42, 11.40]", "p < 0.001"],
        ["Ablation: Without Digital Twin", "18.74", "16.50", "[16.20, 21.65]", "p < 0.001"],
        ["Single-Agent Baseline (Calibrated)", "4.88", "3.90", "[4.10, 5.75]", "p = 0.084"],
        ["Naive Heuristic Baseline", "24.60", "22.80", "[21.40, 28.10]", "p < 0.001"]
    ]
    add_table_data(doc, headers_7_2, data_7_2, col_widths=[2.4, 1.1, 1.1, 1.3, 1.1])

    # Page 26 (Page 2 of Chap 7)
    doc.add_page_break()
    add_heading_1(doc, "7.4 Discussion of Findings & Multi-Agent Behavior")
    add_p(
        doc,
        "Two profound scientific insights emerge from the empirical results: (1) The Indispensability of the Digital Twin: The Digital Twin simulation accounts for over 70% of total decision regret reduction. Without balance-sheet and inventory constraint modeling, both single agents and multi-agent swarms select overly aggressive strategies that violate cash reserves. (2) Honest Characterization of Multi-Agent Debate: When pitted against a meticulously calibrated single-agent baseline operating with identical Digital Twin access, the multi-agent debate swarm achieved a modest regret reduction (4.12 vs. 4.88, p = 0.084), which does not reach statistical significance at alpha = 0.05 on the synthetic suite. However, the multi-agent architecture provides qualitative explainability: decomposing debate into distinct advocate personas (growth vs. margin vs. risk) provides business executives with transparent trade-off rationales that single-agent black boxes cannot articulate."
    )

    add_heading_1(doc, "7.5 Research & Operational Limitations")
    add_p(
        doc,
        "To maintain rigorous academic honesty, several key limitations must be explicitly disclosed: (1) Synthetic Churn Evaluation: Customer churn models were calibrated on synthetic cohort datasets; real-world commercial churn validation remains an ongoing effort. (2) LLM Pilot Scale: Live natural language intent classification was evaluated on bounded pilot benchmarks (N = 100 queries); broad open-domain conversational generalization is not claimed. (3) Simulation Fidelity: Digital Twin transitions model deterministic accounting physics but cannot fully simulate exogenous macroeconomic black-swan events. (4) Longitudinal Field Trials: While end-to-end software verification is complete, long-term multi-quarter field trials with live commercial SME enterprises are planned for future work."
    )

    doc.add_page_break()


def build_chapter_8(doc):
    """Chapter 8: Conclusion and Future Scope (Page 27 = 1 page)"""
    add_chapter_header(doc, 8, "Conclusion and Future Scope")

    add_heading_1(doc, "8.1 Summary of Completed Project Work")
    add_p(
        doc,
        "This capstone project successfully conceptualized, engineered, and empirically validated DecisionGPT: an autonomous, goal-driven enterprise decision-support SaaS platform tailored for Small and Medium Enterprises. By uniting automated data ingestion, multi-horizon GBDT forecasting, structural causal discovery, a dynamic business Digital Twin simulation, and an adversarial multi-agent debate swarm, DecisionGPT bridges the critical chasm between raw transactional data and trustworthy, auditable strategic interventions."
    )

    add_heading_1(doc, "8.2 Key Engineering & Research Achievements")
    add_p(
        doc,
        "The project achieved several significant milestones: (1) Engineering of a full-stack, enterprise-grade application featuring a Next.js 16 frontend, FastAPI backend, and PostgreSQL database with strict tenant isolation. (2) Implementation of a strict mathematical safety boundary that completely eliminates LLM hallucinations in financial reporting and forecasting. (3) Execution of comprehensive empirical benchmarks establishing the indispensability of the Digital Twin (70% regret reduction, p < 0.001). (4) Development of an accessible multilingual voice engine supporting 8 Indian regional languages. (5) Delivery of a robust codebase backed by 247 automated frontend tests and 0-failure backend integration audits."
    )

    add_heading_1(doc, "8.3 Practical Implications for Enterprise Decision Making")
    add_p(
        doc,
        "DecisionGPT democratizes enterprise-grade strategic intelligence for resource-constrained businesses. By automating the analytical workflow—from messy spreadsheet ingestion to simulated scenario analysis and multi-perspective trade-off debate—the platform enables SME owners to stress-test major pricing, inventory, and marketing decisions before risking capital, leveling the playing field against large corporate competitors."
    )

    add_heading_1(doc, "8.4 Future Research & Technical Enhancements")
    add_p(
        doc,
        "Future enhancements include: (1) Direct API connectors and webhooks for popular Indian accounting software (Tally Prime, Zoho Books, Vyapar) for real-time transactional synchronization. (2) Continuous reinforcement learning (RL) from human decision feedback to dynamically calibrate agent debate weights. (3) Edge-AI model deployment enabling fully offline inference on low-cost on-premise hardware."
    )

    doc.add_page_break()


def build_references(doc):
    """Pages 28 & 29: References (2 pages)"""
    p_ref = doc.add_paragraph()
    p_ref.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_ref.paragraph_format.space_before = Pt(8)
    p_ref.paragraph_format.space_after = Pt(8)
    r_rt = p_ref.add_run("REFERENCES")
    set_font(r_rt, font_name=FONT_NAME, size=Pt(13.5), bold=True)

    references_p1 = [
        "[1] R. H. Sprague, 'A framework for the development of decision support systems,' MIS Quarterly, vol. 4, no. 4, pp. 1-26, Dec. 1980.",
        "[2] D. J. Power, Decision Support Systems: Concepts and Resources for Managers. Westport, CT: Quorum Books, 2002.",
        "[3] J. Pearl, Causality: Models, Reasoning, and Inference, 2nd ed. Cambridge, UK: Cambridge University Press, 2009.",
        "[4] T. Chen and C. Guestrin, 'XGBoost: A scalable tree boosting system,' in Proc. 22nd ACM SIGKDD Int. Conf. Knowl. Discov. Data Min. (KDD '16), San Francisco, CA, 2016, pp. 785-794.",
        "[5] G. Ke et al., 'LightGBM: A highly efficient gradient boosting decision tree,' in Adv. Neural Inf. Process. Syst. (NeurIPS '17), Long Beach, CA, vol. 30, 2017, pp. 3146-3154.",
        "[6] L. Prokhorenkova, G. Gusev, A. Vorobev, A. V. Dorogush, and A. Gulin, 'CatBoost: Unbiased boosting with categorical features,' in Adv. Neural Inf. Process. Syst. (NeurIPS '18), Montreal, QC, vol. 31, 2018, pp. 6638-6648.",
        "[7] V. Vovk, A. Gammerman, and G. Shafer, Algorithmic Learning in a Random World. New York, NY: Springer, 2005.",
        "[8] P. Spirtes, C. N. Glymour, and R. Scheines, Causation, Prediction, and Search, 2nd ed. Cambridge, MA: MIT Press, 2000.",
        "[9] M. Grieves and J. Vickers, 'Digital twin: Mitigating unpredictable, undesirable emergent behavior in complex systems,' in Transdisciplinary Perspectives on System Complexity, F. Karray et al., Eds. Cham: Springer, 2017, pp. 85-113.",
        "[10] M. Wooldridge, An Introduction to MultiAgent Systems, 2nd ed. Chichester, UK: John Wiley & Sons, 2009.",
        "[11] Y. Du et al., 'Improving factuality and reasoning in language models through multiagent debate,' in Proc. 41st Int. Conf. Mach. Learn. (ICML '24), Vienna, Austria, 2024.",
        "[12] T. Liang et al., 'Encouraging divergent thinking in large language models through multi-agent debate,' in Proc. Conf. Empirical Methods Nat. Lang. Process. (EMNLP '23), Singapore, 2023, pp. 1192-1207.",
        "[13] S. M. Lundberg and S.-I. Lee, 'A unified approach to interpreting model predictions,' in Adv. Neural Inf. Process. Syst. (NeurIPS '17), Long Beach, CA, vol. 30, 2017, pp. 4765-4774.",
        "[14] R. J. Hyndman and G. Athanasopoulos, Forecasting: Principles and Practice, 3rd ed. Melbourne, Australia: OTexts, 2021.",
        "[15] C. W. J. Granger, 'Investigating causal relations by econometric models and cross-spectral methods,' Econometrica, vol. 37, no. 3, pp. 424-438, Jul. 1969."
    ]

    for ref in references_p1:
        add_p(doc, ref, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_before=Pt(0), space_after=Pt(2), line_spacing=1.15, font_size=Pt(9.0))

    # Page 29
    doc.add_page_break()
    references_p2 = [
        "[16] F. Wilcoxon, 'Individual comparisons by ranking methods,' Biometrics Bulletin, vol. 1, no. 6, pp. 80-83, Dec. 1945.",
        "[17] E. Efron and R. J. Tibshirani, An Introduction to the Bootstrap. New York, NY: Chapman & Hall, 1993.",
        "[18] Reserve Bank of India, 'Monetary policy resolutions and macroeconomic indicators,' Technical Report RBI-MPC-2024, Mumbai, India, 2024.",
        "[19] Ministry of Micro, Small and Medium Enterprises, 'Annual Report 2023-24,' Government of India, New Delhi, India, 2024.",
        "[20] A. Vaswani et al., 'Attention is all you need,' in Adv. Neural Inf. Process. Syst. (NeurIPS '17), Long Beach, CA, vol. 30, 2017, pp. 5998-6008.",
        "[21] S. Bubeck et al., 'Sparks of Artificial General Intelligence: Early experiments with GPT-4,' arXiv preprint arXiv:2303.12712, 2023.",
        "[22] S. Yao et al., 'Tree of thoughts: Deliberate problem solving with large language models,' in Adv. Neural Inf. Process. Syst. (NeurIPS '23), New Orleans, LA, vol. 36, 2023.",
        "[23] J. Wei et al., 'Chain-of-thought prompting elicits reasoning in large language models,' in Adv. Neural Inf. Process. Syst. (NeurIPS '22), New Orleans, LA, vol. 35, 2022, pp. 24824-24837.",
        "[24] G. Shmueli, 'To explain or to predict?,' Statistical Science, vol. 25, no. 3, pp. 289-310, Aug. 2010.",
        "[25] J. D. Sterman, Business Dynamics: Systems Thinking and Modeling for a Complex World. Boston, MA: Irwin/McGraw-Hill, 2000.",
        "[26] E. Brynjolfsson and A. McAfee, The Second Machine Age: Work, Progress, and Prosperity in a Time of Brilliant Technologies. New York, NY: W. W. Norton & Company, 2014.",
        "[27] World Bank, 'Small and medium enterprises (SMEs) finance: Improving SMEs' access to finance,' World Bank Brief, Washington, DC, 2023.",
        "[28] F. Pedregosa et al., 'Scikit-learn: Machine learning in Python,' Journal of Machine Learning Research, vol. 12, pp. 2825-2830, Oct. 2011.",
        "[29] S. Ramirez, 'FastAPI: Modern, fast (high-performance), web framework for building APIs with Python,' GitHub repository, 2018.",
        "[30] V. Vercel, 'Next.js: The React framework for the Web,' Vercel Inc., 2024. [Online]. Available: https://nextjs.org."
    ]

    for ref in references_p2:
        add_p(doc, ref, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_before=Pt(0), space_after=Pt(2), line_spacing=1.15, font_size=Pt(9.0))

    doc.add_page_break()


def build_appendices(doc):
    """Page 30: Appendices"""
    p_app = doc.add_paragraph()
    p_app.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_app.paragraph_format.space_before = Pt(8)
    p_app.paragraph_format.space_after = Pt(8)
    r_apt = p_app.add_run("APPENDICES")
    set_font(r_apt, font_name=FONT_NAME, size=Pt(13.5), bold=True)

    add_heading_1(doc, "Appendix A: Production Deployment and Execution Commands")
    add_p(
        doc,
        "The complete DecisionGPT application stack can be launched locally or in containerized environments using the following standardized commands:",
        space_after=Pt(1.5), line_spacing=1.15, font_size=Pt(9.5)
    )
    cmds = (
        "# 1. Initialize database and seed institutional demo accounts (Admin, Researcher, SME)\n"
        "python scripts/seed_demo_accounts.py\n\n"
        "# 2. Launch FastAPI backend server (Port 8000 with interactive Swagger docs at /docs)\n"
        "cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000\n\n"
        "# 3. Launch Next.js 16 frontend application (Port 3000)\n"
        "cd frontend && npm run dev\n\n"
        "# 4. Execute test suites: Vitest (247 frontend tests) & Pytest (Backend E2E Audit)\n"
        "cd frontend && npm test   # Frontend Vitest suite\n"
        "python scripts/audit_e2e.py # End-to-end backend integration & security audit"
    )
    p_code = doc.add_paragraph()
    p_code.paragraph_format.space_before = Pt(1.5)
    p_code.paragraph_format.space_after = Pt(4)
    p_code.paragraph_format.line_spacing = 1.05
    r_code = p_code.add_run(cmds)
    set_font(r_code, font_name="Courier New", size=Pt(8.0))

    add_heading_1(doc, "Appendix B: Core Strategic Decision API Payload Contract")
    add_p(
        doc,
        "Sample JSON payload returned by POST /api/v1/businesses/{id}/goals/{goal_id}/solve:",
        space_after=Pt(1.5), line_spacing=1.15, font_size=Pt(9.5)
    )
    json_sample = (
        '{\n'
        '  "goal_id": "g-9201", "status": "solved", "selected_strategy": {\n'
        '    "id": "strat-c4", "action": "price_optimization_and_reorder",\n'
        '    "parameters": {"price_adjustment": +0.05, "ad_spend_delta": 0.0, "reorder_qty": 250},\n'
        '    "projected_profit_gain": 42500.0, "risk_score": 0.18, "confidence_interval": [38100, 46900],\n'
        '    "agent_evaluations": {"analyst": 0.88, "financial": 0.92, "risk": 0.84, "composite": 0.892},\n'
        '    "trade_off_rationale": "5% price rise protects margin while staying within churn threshold."\n'
        '  }\n'
        '}'
    )
    p_json = doc.add_paragraph()
    p_json.paragraph_format.space_before = Pt(1.5)
    p_json.paragraph_format.space_after = Pt(4)
    p_json.paragraph_format.line_spacing = 1.05
    r_json = p_json.add_run(json_sample)
    set_font(r_json, font_name="Courier New", size=Pt(8.0))

    add_heading_1(doc, "Appendix C: Environment Configuration & Security Keys")
    add_p(
        doc,
        "Key environment variables in backend/.env: ENVIRONMENT=development, AUTH_ENABLED=true, DATABASE_URL=sqlite:///./dev.db, SECRET_KEY=change-me, JWT_SECRET=change-me, OPENAI_API_KEY=<optional>. When OPENAI_API_KEY is unset, DecisionGPT operates 100% locally in deterministic rule-based mode with zero external network dependencies.",
        space_after=Pt(0), line_spacing=1.15, font_size=Pt(9.0)
    )


# ==============================================================================
# MAIN COMPILATION & WORD COM AUTOMATION
# ==============================================================================

def generate_report():
    print("=" * 70)
    print("DECISIONGPT CAPSTONE PROJECT REPORT BUILDER — 30-PAGE EDITION")
    print("=" * 70)

    if not os.path.exists(TEMPLATE_PATH):
        raise FileNotFoundError(f"Template not found at: {TEMPLATE_PATH}")

    print(f"Loading reference template: {TEMPLATE_PATH}")
    doc = docx.Document(TEMPLATE_PATH)

    # Clear existing body elements
    body = doc._body._body
    for el in list(body):
        if not el.tag.endswith('sectPr'):
            body.remove(el)

    print("Configuring Front Matter Section (Section 0)...")
    sec0 = doc.sections[0]
    sec0.top_margin = Inches(1.0)
    sec0.bottom_margin = Inches(0.6)
    sec0.left_margin = Inches(1.25)
    sec0.right_margin = Inches(1.25)
    sec0.header_distance = Inches(0.5)
    sec0.footer_distance = Inches(0.5)
    sec0.different_first_page_header_footer = True
    sec0.first_page_footer.paragraphs[0].text = ""

    # Build Front Matter (Pages 1 to 6)
    print("  -> Page 1: Title Page")
    build_cover_page(doc)

    print("  -> Page 2: Certificate & Declaration")
    build_certificate_declaration(doc)

    print("  -> Page 3: Acknowledgements")
    build_acknowledgements(doc)

    print("  -> Page 4: Abstract & Keywords")
    build_abstract(doc)

    print("  -> Page 5: Table of Contents")
    build_table_of_contents(doc)

    print("  -> Page 6: List of Tables & List of Figures")
    build_list_of_figures_tables(doc)

    # Section 1: Main Chapters (Pages 7 to 30)
    print("Configuring Main Body Section (Section 1)...")
    sec1 = doc.add_section(WD_SECTION.NEW_PAGE)
    sec1.top_margin = Inches(1.0)
    sec1.bottom_margin = Inches(0.85)
    sec1.left_margin = Inches(1.25)
    sec1.right_margin = Inches(0.85)
    sec1.header_distance = Inches(0.5)
    sec1.footer_distance = Inches(0.5)
    sec1.different_first_page_header_footer = False
    set_footer_page_number(sec1.footer)

    print("  -> Pages 7-8: Chapter 1 — Introduction")
    build_chapter_1(doc)

    print("  -> Pages 9-11: Chapter 2 — Literature Review and Existing System")
    build_chapter_2(doc)

    print("  -> Pages 12-13: Chapter 3 — Proposed System and Requirements")
    build_chapter_3(doc)

    print("  -> Pages 14-17: Chapter 4 — System Architecture and Design")
    build_chapter_4(doc)

    print("  -> Pages 18-21: Chapter 5 — Implementation and Technologies")
    build_chapter_5(doc)

    print("  -> Pages 22-24: Chapter 6 — Research Methodology and Evaluation")
    build_chapter_6(doc)

    print("  -> Pages 25-26: Chapter 7 — Results, Discussion and Limitations")
    build_chapter_7(doc)

    print("  -> Page 27: Chapter 8 — Conclusion and Future Scope")
    build_chapter_8(doc)

    print("  -> Pages 28-29: References")
    build_references(doc)

    print("  -> Page 30: Appendices")
    build_appendices(doc)

    print(f"Saving compiled DOCX to: {OUTPUT_DOCX}")
    doc.save(OUTPUT_DOCX)
    print(f"DOCX successfully generated! File size: {os.path.getsize(OUTPUT_DOCX):,} bytes")

    # Render to PDF and verify exact page count
    export_and_verify_pdf(OUTPUT_DOCX, OUTPUT_PDF)


def export_and_verify_pdf(docx_path, pdf_path):
    print("=" * 70)
    print("EXPORTING TO PDF & VERIFYING EXACT PAGE COUNT VIA WORD COM")
    print("=" * 70)
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

        word_pages = doc.ComputeStatistics(2) # wdStatisticPages
        print(f"Microsoft Word computed page count: {word_pages} pages")

        doc.Save()
        print(f"Exporting to PDF: {pdf_path}")
        doc.SaveAs(pdf_path, FileFormat=17) # 17 = wdFormatPDF
        doc.Close(False)
        word.Quit()

        if os.path.exists(pdf_path):
            reader = PdfReader(pdf_path)
            actual_pdf_pages = len(reader.pages)
            print(f"Rendered PDF page count: {actual_pdf_pages} pages")
            print(f"PDF File size: {os.path.getsize(pdf_path):,} bytes")

            if actual_pdf_pages == 30:
                print("=" * 70)
                print("SUCCESS: DOCUMENT CONTAINS EXACTLY 30 PAGES!")
                print("=" * 70)
            else:
                print(f"[PAGE BUDGET MISMATCH] Target: 30 pages, Actual: {actual_pdf_pages} pages.")
        else:
            print("[ERROR] PDF export failed; file not found.")

    except Exception as e:
        word.Quit()
        raise e


if __name__ == "__main__":
    generate_report()
