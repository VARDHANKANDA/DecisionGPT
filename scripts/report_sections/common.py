"""
Common styles, constants, and helper primitives for the Capstone Project Report.
Authoritative Formatting Reference: CAPSTONE_THESIS_Format.docx
Supports comprehensive, in-depth academic reporting (up to 60 pages).
"""

import os
import re
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn, nsdecls

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
REPORT_DIR = os.path.join(ROOT_DIR, "Project Report")
FIGURES_DIR = os.path.join(REPORT_DIR, "Figures")
TEMPLATE_PATH = os.path.join(REPORT_DIR, "CAPSTONE_THESIS_Format.docx")
OUTPUT_DOCX = os.path.join(REPORT_DIR, "DecisionGPT_Final_Capstone_Project_Report.docx")
OUTPUT_PDF = os.path.join(REPORT_DIR, "DecisionGPT_Final_Capstone_Project_Report.pdf")

# Standard Thesis Typography (Times New Roman, standard academic sizing)
FONT_NAME = "Times New Roman"
BODY_SIZE = Pt(11.5)
HEADING_CHAPTER_SIZE = Pt(14.0)
HEADING_1_SIZE = Pt(13.0)
HEADING_2_SIZE = Pt(12.0)
HEADING_3_SIZE = Pt(11.5)
CAPTION_SIZE = Pt(10.0)
TABLE_TEXT_SIZE = Pt(9.0)

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

def add_p(doc, text="", align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_before=Pt(0), space_after=Pt(3.0), line_spacing=1.18, bold=False, italic=False, font_size=BODY_SIZE, color=COLOR_BLACK):
    p = doc.add_paragraph()
    p.alignment = align
    p.paragraph_format.space_before = space_before
    p.paragraph_format.space_after = space_after
    p.paragraph_format.line_spacing = line_spacing
    if text:
        r = p.add_run(clean_text(text))
        set_font(r, font_name=FONT_NAME, size=font_size, bold=bold, italic=italic, color=color)
    return p

def add_heading_1(doc, text, space_before=Pt(8), space_after=Pt(3)):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = space_before
    p.paragraph_format.space_after = space_after
    p.paragraph_format.line_spacing = 1.15
    p.paragraph_format.keep_with_next = True
    r = p.add_run(clean_text(text))
    set_font(r, font_name=FONT_NAME, size=HEADING_1_SIZE, bold=True, color=COLOR_BLACK)
    return p

def add_heading_2(doc, text, space_before=Pt(6), space_after=Pt(2)):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = space_before
    p.paragraph_format.space_after = space_after
    p.paragraph_format.line_spacing = 1.15
    p.paragraph_format.keep_with_next = True
    r = p.add_run(clean_text(text))
    set_font(r, font_name=FONT_NAME, size=HEADING_2_SIZE, bold=True, color=COLOR_BLACK)
    return p

def add_heading_3(doc, text, space_before=Pt(4), space_after=Pt(1.5)):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = space_before
    p.paragraph_format.space_after = space_after
    p.paragraph_format.line_spacing = 1.15
    p.paragraph_format.keep_with_next = True
    r = p.add_run(clean_text(text))
    set_font(r, font_name=FONT_NAME, size=HEADING_3_SIZE, bold=True, italic=True, color=COLOR_BLACK)
    return p

def add_chapter_header(doc, chapter_num, title):
    p1 = doc.add_paragraph()
    p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p1.paragraph_format.space_before = Pt(8)
    p1.paragraph_format.space_after = Pt(2)
    p1.paragraph_format.line_spacing = 1.15
    r1 = p1.add_run(f"CHAPTER {chapter_num}")
    set_font(r1, font_name=FONT_NAME, size=HEADING_CHAPTER_SIZE, bold=True)

    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p2.paragraph_format.space_before = Pt(2)
    p2.paragraph_format.space_after = Pt(8)
    p2.paragraph_format.line_spacing = 1.15
    r2 = p2.add_run(title.upper())
    set_font(r2, font_name=FONT_NAME, size=HEADING_CHAPTER_SIZE, bold=True)

def add_fig_caption(doc, fig_num, caption):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing = 1.15
    p.paragraph_format.keep_with_next = True
    r1 = p.add_run(f"Figure {fig_num}: ")
    set_font(r1, font_name=FONT_NAME, size=CAPTION_SIZE, bold=True)
    r2 = p.add_run(clean_text(caption))
    set_font(r2, font_name=FONT_NAME, size=CAPTION_SIZE, italic=True)
    return p

def add_tbl_caption(doc, tbl_num, caption):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.15
    p.paragraph_format.keep_with_next = True
    r1 = p.add_run(f"Table {tbl_num}: ")
    set_font(r1, font_name=FONT_NAME, size=CAPTION_SIZE, bold=True)
    r2 = p.add_run(clean_text(caption))
    set_font(r2, font_name=FONT_NAME, size=CAPTION_SIZE, italic=True)
    return p

def add_image_safe(doc, image_name, width=Inches(5.6)):
    img_path = os.path.join(FIGURES_DIR, image_name)
    if os.path.exists(img_path):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(3)
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run()
        r.add_picture(img_path, width=width)
        return True
    else:
        print(f"Warning: Image not found: {img_path}")
        return False

def add_code_block(doc, code_lines, font_name="Consolas", font_size=Pt(8.0), bg_fill="F8FAFC", border_color="CBD5E1"):
    """
    Renders a formatted, syntax-appropriate source code box.
    Uses a single-cell table with subtle background shading, soft borders, and monospace font.
    """
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    cell = table.cell(0, 0)
    cell.width = Inches(6.1)

    # Background shading
    shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{bg_fill}"/>')
    cell._tc.get_or_add_tcPr().append(shading)

    # Padding inside cell
    tcMar = parse_xml(
        f'<w:tcMar {nsdecls("w")}>'
        f'  <w:top w:w="120" w:type="dxa"/>'
        f'  <w:bottom w:w="120" w:type="dxa"/>'
        f'  <w:left w:w="160" w:type="dxa"/>'
        f'  <w:right w:w="160" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    cell._tc.get_or_add_tcPr().append(tcMar)

    # Borders
    borders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        f'  <w:top w:val="single" w:sz="4" w:space="0" w:color="{border_color}"/>'
        f'  <w:bottom w:val="single" w:sz="4" w:space="0" w:color="{border_color}"/>'
        f'  <w:left w:val="single" w:sz="4" w:space="0" w:color="{border_color}"/>'
        f'  <w:right w:val="single" w:sz="4" w:space="0" w:color="{border_color}"/>'
        f'  <w:insideH w:val="none"/>'
        f'  <w:insideV w:val="none"/>'
        f'</w:tblBorders>'
    )
    table._tbl.tblPr.append(borders)

    # Paragraphs inside the box
    p0 = cell.paragraphs[0]
    for i, line in enumerate(code_lines):
        p = p0 if i == 0 else cell.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1.05
        r = p.add_run(clean_text(line))
        set_font(r, font_name=font_name, size=font_size, color=RGBColor(30, 41, 59))
    return table

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
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(2)
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
            p.paragraph_format.space_before = Pt(1.5)
            p.paragraph_format.space_after = Pt(1.5)
            p.paragraph_format.line_spacing = 1.05
            if len(p.runs) > 0:
                set_font(p.runs[0], font_name=FONT_NAME, size=TABLE_TEXT_SIZE)

    # Borders
    tblPr = table._tbl.tblPr
    borders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        f'  <w:top w:val="single" w:sz="6" w:space="0" w:color="B0C4DE"/>'
        f'  <w:bottom w:val="single" w:sz="6" w:space="0" w:color="B0C4DE"/>'
        f'  <w:insideH w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>'
        f'  <w:insideV w:val="none"/>'
        f'  <w:left w:val="none"/>'
        f'  <w:right w:val="none"/>'
        f'</w:tblBorders>'
    )
    tblPr.append(borders)

    if col_widths:
        for row in table.rows:
            for i, w in enumerate(col_widths):
                row.cells[i].width = Inches(w)

    return table

def add_hyperlink(paragraph, url, text, font_name=FONT_NAME, size=Pt(9.5), color="004B87", underline=True):
    """
    Creates a genuine Word hyperlink (w:hyperlink) pointing to an external relationship ID.
    Preserved as a clickable PDF annotation upon Word export.
    """
    part = paragraph.part
    r_id = part.relate_to(url, docx.opc.constants.RELATIONSHIP_TYPE.HYPERLINK, is_external=True)

    hyperlink = parse_xml(
        f'<w:hyperlink {nsdecls("w")} r:id="{r_id}" {nsdecls("r")}/>'
    )
    new_run = parse_xml(f'<w:r {nsdecls("w")}/>')
    rPr = parse_xml(f'<w:rPr {nsdecls("w")}/>')
    rPr.append(parse_xml(f'<w:rFonts {nsdecls("w")} w:ascii="{font_name}" w:hAnsi="{font_name}"/>'))
    if color:
        rPr.append(parse_xml(f'<w:color {nsdecls("w")} w:val="{color}"/>'))
    if underline:
        rPr.append(parse_xml(f'<w:u {nsdecls("w")} w:val="single"/>'))
    sz_val = int(size.pt * 2)
    rPr.append(parse_xml(f'<w:sz {nsdecls("w")} w:val="{sz_val}"/>'))
    new_run.append(rPr)
    text_node = parse_xml(f'<w:t {nsdecls("w")} xml:space="preserve"/>')
    text_node.text = clean_text(text)
    new_run.append(text_node)
    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)
    return hyperlink

def set_footer_page_number(footer):
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.text = ""
    r = p.add_run()
    set_font(r, font_name=FONT_NAME, size=Pt(10.0))
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
