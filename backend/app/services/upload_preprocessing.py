"""Reading and cleaning an uploaded business file: transparent, deterministic, and conservative.

Principles (each is enforced by a test in ``tests/unit/test_upload_preprocessing.py``):

* Nothing is guessed silently. Every change is recorded as an ``Action`` the person can read; every uncertain interpretation is a
  ``Warning`` or a question (``DateQuestion``), never a quiet choice.
* Nothing is deleted without being reported. Blank rows and columns that are entirely empty are removed (and counted); exact duplicate rows
  are only COUNTED: repeat transactions are normal in sales data and are never dropped here. A column the analysis does not use is not
  removed from the file; it is listed as "not used".
* Nothing is invented. A missing value stays missing; a text value that is not unambiguously a number or a date is left as an invalid cell,
  and the row is reported as skipped rather than repaired.
* Nothing in the file is ever executed: Excel is read for cached values only (formulas are never evaluated), text is never interpreted.
* Resource use is bounded before data is materialised: file size is checked by the caller, the Excel archive is checked for expansion,
  the number of rows, columns and sheets and the length of any cell are capped.

No function here touches the database, the network or the file system.
"""
from __future__ import annotations

import csv
import io
import math
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import pandas as pd

from app.core.errors import ValidationFailedError

# ------------------------------------------------------------------------------------------------ limits
MAX_COLUMNS = 200
MAX_SHEETS = 20
MAX_CELL_CHARS = 5_000
MAX_ARCHIVE_EXPANSION_BYTES = 250 * 1024 * 1024           # uncompressed size of an .xlsx archive (zip-bomb guard)
MAX_ARCHIVE_MEMBERS = 2_000
SUPPORTED_EXTENSIONS = (".csv", ".xlsx")
NULL_TOKENS = frozenset({"", "na", "n/a", "n.a.", "nan", "null", "nil", "none", "-", "--", "—", "#n/a", "#na", "#null!", "#value!", "#div/0!", "#ref!", "#name?", "#num!"})
_DELIMITERS = (",", ";", "\t", "|")
_NBSP = " ​﻿"


# ------------------------------------------------------------------------------------------------ report types
@dataclass
class Action:
    """One thing that was done to the file, in words a person can check."""
    code: str
    message: str
    count: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "count": self.count}


@dataclass
class FrameReport:
    """What happened to one table (a CSV file, or one worksheet)."""
    name: str
    rows_read: int = 0
    rows_kept: int = 0
    blank_rows_removed: int = 0
    columns_original: list[str] = field(default_factory=list)
    columns_kept: list[str] = field(default_factory=list)
    empty_columns_removed: list[str] = field(default_factory=list)
    renamed_columns: list[dict[str, str]] = field(default_factory=list)
    duplicate_rows: int = 0
    actions: list[Action] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    encoding: str | None = None
    delimiter: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "rows_read": self.rows_read, "rows_kept": self.rows_kept, "blank_rows_removed": self.blank_rows_removed,
            "columns_original": self.columns_original, "columns_kept": self.columns_kept, "empty_columns_removed": self.empty_columns_removed,
            "renamed_columns": self.renamed_columns, "duplicate_rows": self.duplicate_rows,
            "actions": [a.as_dict() for a in self.actions], "warnings": self.warnings, "encoding": self.encoding, "delimiter": self.delimiter,
        }


@dataclass
class ReadResult:
    frames: dict[str, pd.DataFrame]                        # table name (sheet name, or the file's own name) -> cleaned frame (object dtype)
    reports: dict[str, FrameReport]
    ignored_sheets: list[dict[str, str]] = field(default_factory=list)    # sheets that were not read, with the reason


@dataclass
class DateQuestion:
    """Dates like 03/04/2026 can be 3 April or March 4. The person must say which; it is never assumed."""
    column: str
    examples: list[str]
    options: tuple[str, str] = ("day_first", "month_first")


# ------------------------------------------------------------------------------------------------ text decoding and CSV reading
def decode_text(content: bytes) -> tuple[str, str, list[str]]:
    """Return (text, encoding name, warnings). Rejects binary content; falls back to Windows-1252 (Excel's CSV on Windows) with a warning."""
    if not content or not content.strip():
        raise ValidationFailedError("Nothing to import: the file is empty. Choose a file with a header row and at least one row of data.")
    if content[:2] in (b"PK",) or content[:4] == b"\xd0\xcf\x11\xe0":
        raise ValidationFailedError("This looks like an Excel file saved with a .csv name. Open it in Excel and use Save As > .xlsx (or CSV UTF-8).")
    if content[:5] == b"%PDF-" or content[:4] in (b"\x89PNG", b"\xff\xd8\xff\xe0", b"GIF8"):
        raise ValidationFailedError("This is not a spreadsheet or CSV file (it looks like a PDF or an image).")
    warnings: list[str] = []
    for bom, enc in ((b"\xef\xbb\xbf", "utf-8-sig"), (b"\xff\xfe", "utf-16"), (b"\xfe\xff", "utf-16")):
        if content.startswith(bom):
            try:
                return content.decode(enc), enc, warnings
            except UnicodeDecodeError:
                break
    if b"\x00" in content[:65536]:
        raise ValidationFailedError("This file does not look like a CSV file: it contains binary data, not plain text. Save it from Excel as CSV (or upload the .xlsx itself).")
    try:
        return content.decode("utf-8"), "utf-8", warnings
    except UnicodeDecodeError:
        pass
    try:
        text = content.decode("cp1252")
        warnings.append("The file is not UTF-8; it was read as Windows-1252 (the default for Excel on Windows). Check that accented letters and the rupee sign look right.")
        return text, "windows-1252", warnings
    except UnicodeDecodeError as exc:
        raise ValidationFailedError("The file's text encoding could not be read. Save it from Excel as 'CSV UTF-8' and upload it again.") from exc


def sniff_delimiter(text: str) -> str:
    """The delimiter that splits the first lines into the same number (>1) of fields. Comma when nothing is clearer."""
    lines = [ln for ln in text.splitlines()[:30] if ln.strip()]
    best, best_score = ",", 0
    for d in _DELIMITERS:
        try:
            counts = [len(r) for r in csv.reader(lines, delimiter=d)]
        except csv.Error:
            continue
        if not counts or counts[0] < 2:
            continue
        consistent = sum(1 for c in counts if c == counts[0])
        score = consistent * 1000 + counts[0]
        if score > best_score:
            best, best_score = d, score
    return best


def _check_cell(value: Any) -> Any:
    if isinstance(value, str) and len(value) > MAX_CELL_CHARS:
        raise ValidationFailedError(f"A cell holds more than {MAX_CELL_CHARS:,} characters. This does not look like business data in table form; check that the file is a normal spreadsheet export.")
    return value


def read_csv(content: bytes, max_rows: int, name: str = "file") -> tuple[pd.DataFrame, FrameReport]:
    text, encoding, warnings = decode_text(content)
    delimiter = sniff_delimiter(text)
    report = FrameReport(name=name, encoding=encoding, delimiter=delimiter, warnings=list(warnings))
    try:
        rows = []
        for i, r in enumerate(csv.reader(io.StringIO(text), delimiter=delimiter)):
            rows.append(r)
            if i > max_rows + 5:                                   # stop early: the caller refuses anything over the limit
                break
    except csv.Error as exc:
        raise ValidationFailedError(f"The file could not be read as CSV ({exc}). Check for an unclosed quotation mark.") from exc
    nonblank = [r for r in rows if any((c or "").strip(_NBSP + " ") for c in r)]
    if not nonblank:
        raise ValidationFailedError("The file has no data rows.")
    first = next(i for i, r in enumerate(rows) if any((c or "").strip(_NBSP + " ") for c in r))
    blank_after_header = sum(1 for r in rows[first + 1:] if not any((c or "").strip(_NBSP + " ") for c in r))
    rows = nonblank
    header, body = rows[0], rows[1:]
    width = len(header)
    ragged_long, fixed = [], 0
    padded = []
    for n, r in enumerate(body, start=2):
        if len(r) > width:
            extra = [c for c in r[width:] if (c or "").strip()]
            if extra:
                ragged_long.append(n)
            r = r[:width]
        elif len(r) < width:
            r = r + [""] * (width - len(r))
            fixed += 1
        padded.append([_check_cell(c) for c in r])
    if ragged_long:
        raise ValidationFailedError(
            f"{len(ragged_long)} row(s) have more values than the header has columns (first at line {ragged_long[0]}). A text value probably "
            f"contains the separator ('{delimiter}') without quotation marks. Fix those rows or export the file again."
        )
    if fixed:
        report.actions.append(Action("short_rows_padded", "Rows with fewer values than the header were filled with empty cells.", fixed))
    df = pd.DataFrame(padded, columns=[str(c) for c in header], dtype=object)
    report.rows_read = len(df) + blank_after_header
    report.blank_rows_removed = blank_after_header
    return df, report


# ------------------------------------------------------------------------------------------------ Excel reading (values only)
def _check_archive(content: bytes) -> None:
    if content[:2] != b"PK":
        raise ValidationFailedError("This does not look like an .xlsx file (it is not a zip archive). Open the file in Excel and use Save As > .xlsx.")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            infos = z.infolist()
            names = {i.filename for i in infos}
            if "xl/workbook.xml" not in names:
                raise ValidationFailedError("This is a zip file but not an Excel workbook (.xlsx).")
            if len(infos) > MAX_ARCHIVE_MEMBERS or sum(i.file_size for i in infos) > MAX_ARCHIVE_EXPANSION_BYTES:
                raise ValidationFailedError("This workbook expands to far more data than a normal spreadsheet; it was not opened. Split it into smaller files.")
            if any(i.filename.startswith(("/", "..")) or ".." in i.filename.split("/") for i in infos):
                raise ValidationFailedError("This workbook contains unsafe internal paths and was not opened.")
    except zipfile.BadZipFile as exc:
        raise ValidationFailedError("The Excel file is damaged or not a real .xlsx file. Open it in Excel and save it again.") from exc


def _cell_value(v: Any) -> Any:
    """Cached cell value as plain data. Formulas are never evaluated: openpyxl returns the value Excel last stored."""
    if isinstance(v, datetime):
        return v.date().isoformat() if (v.hour, v.minute, v.second, v.microsecond) == (0, 0, 0, 0) else v.isoformat(sep=" ")
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return _check_cell(v)


def read_xlsx(content: bytes, max_rows: int) -> tuple[dict[str, pd.DataFrame], dict[str, FrameReport], list[dict[str, str]]]:
    _check_archive(content)
    from openpyxl import load_workbook

    try:
        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001 - any parser failure is "could not read", never a 500
        raise ValidationFailedError("The Excel file could not be read. Open it in Excel, save it again as .xlsx and retry.") from exc
    frames: dict[str, pd.DataFrame] = {}
    reports: dict[str, FrameReport] = {}
    ignored: list[dict[str, str]] = []
    try:
        sheets = wb.worksheets
        if len(sheets) > MAX_SHEETS:
            raise ValidationFailedError(f"The workbook has {len(sheets)} sheets; the limit is {MAX_SHEETS}. Remove the sheets you do not need.")
        for ws in sheets:
            title = str(ws.title)
            if getattr(ws, "sheet_state", "visible") != "visible":
                ignored.append({"sheet": title, "reason": "hidden sheet (not read)"})
                continue
            rows: list[list[Any]] = []
            for i, r in enumerate(ws.iter_rows(values_only=True)):
                if i > max_rows + 5:
                    break
                if len(r) > MAX_COLUMNS * 2:
                    raise ValidationFailedError(f"Sheet '{title}' has far more than {MAX_COLUMNS} columns; it does not look like a normal data table.")
                rows.append([_cell_value(c) for c in r])
            nonblank = [r for r in rows if any(c not in (None, "") and str(c).strip(_NBSP + " ") for c in r)]
            blank_rows = max(0, len(rows) - len(nonblank))
            if not nonblank:
                ignored.append({"sheet": title, "reason": "empty sheet"})
                continue
            header, body = nonblank[0], nonblank[1:]
            width = max(len(header), max((len(r) for r in body), default=0))
            width = max((i + 1 for i, c in enumerate(header) if c not in (None, "")), default=len(header))   # width = last non-empty header cell
            df = pd.DataFrame([list(r[:width]) + [None] * (width - len(r)) for r in body], columns=[("" if c is None else str(c)) for c in header[:width]], dtype=object)
            rep = FrameReport(name=title, rows_read=len(df) + blank_rows, blank_rows_removed=blank_rows)
            frames[title], reports[title] = df, rep
    finally:
        wb.close()
    return frames, reports, ignored


# ------------------------------------------------------------------------------------------------ cleaning one table
def _clean_text(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, str):
        # Only the ends are trimmed. Spacing INSIDE a value is never changed: two names that differ only by a double space are two different
        # values as far as this function can know, and merging them would silently change what the business recorded (a product count, a total).
        s = v.strip().strip(_NBSP).strip()
        return None if s.lower() in NULL_TOKENS else s
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


def clean_frame(df: pd.DataFrame, report: FrameReport, max_rows: int) -> pd.DataFrame:
    """Header names, whitespace, null spellings, blank rows and empty columns. Returns a new frame; the input is not modified."""
    if len(df) > max_rows:
        raise ValidationFailedError(f"'{report.name}' has more rows than the limit of {max_rows:,} per file. Split it (for example by month) and upload the parts separately.")
    if df.shape[1] > MAX_COLUMNS:
        raise ValidationFailedError(f"'{report.name}' has {df.shape[1]} columns; the limit is {MAX_COLUMNS}. Remove the columns you do not need before uploading.")
    original = [str(c) for c in df.columns]
    report.columns_original = original
    # --- header names: trim, collapse spaces, name blanks, make duplicates unique deterministically
    names: list[str] = []
    seen: dict[str, int] = {}
    for i, raw in enumerate(original, start=1):
        base = re.sub(r"\s+", " ", str(raw).translate({ord(c): " " for c in _NBSP})).strip()
        reason = None
        if not base:
            base, reason = f"Unnamed column {i}", "the header was blank"
        key = base.lower()
        if key in seen:
            seen[key] += 1
            new = f"{base} ({seen[key]})"
            reason = "the same name appears more than once"
        else:
            seen[key] = 1
            new = base
        if new != raw:
            report.renamed_columns.append({"from": raw, "to": new, "reason": reason or "extra spaces removed"})
        names.append(new)
    if report.renamed_columns:
        dup = sum(1 for r in report.renamed_columns if r["reason"] == "the same name appears more than once")
        blank = sum(1 for r in report.renamed_columns if r["reason"] == "the header was blank")
        if dup:
            report.actions.append(Action("duplicate_headers_renamed", "Columns with the same name were kept and given distinct names (the second one became 'Name (2)').", dup))
        if blank:
            report.actions.append(Action("blank_headers_named", "Columns with no header were named 'Unnamed column N' so their data is not lost.", blank))
    out = df.copy()
    out.columns = names
    out = out.apply(lambda col: col.map(_clean_text)).astype(object).where(lambda x: x.notna(), None)
    # cells that WERE text and became missing because of how they are spelled (NA, none, -, ...): counted per column and reported, so a real value
    # that happens to look like a null spelling (a product called "None", a customer code "NA") is visible to the person, never lost silently
    spelled: dict[str, int] = {}
    for i, name in enumerate(names):
        n = sum(1 for a, b in zip(df.iloc[:, i], out.iloc[:, i]) if isinstance(a, str) and a.strip(_NBSP + " \t\r\n") and b is None)
        if n:
            spelled[name] = n
    if spelled:
        where = ", ".join(f"'{c}' ({n:,})" for c, n in list(spelled.items())[:5]) + (" and more" if len(spelled) > 5 else "")
        report.actions.append(Action("null_spellings_read_as_missing",
                                     f"Cells written as NA, n/a, null, none, nil or a dash were read as missing, not as a value: {where}. "
                                     "If one of them is a real value (for example a product called 'None'), rename it in your file and upload again.",
                                     sum(spelled.values())))
    # --- blank rows, empty columns
    blank_mask = out.isna().all(axis=1)
    if blank_mask.any():
        report.blank_rows_removed += int(blank_mask.sum())
        out = out.loc[~blank_mask]
    if report.blank_rows_removed:
        report.actions.append(Action("blank_rows_removed", "Rows with no values at all were removed.", report.blank_rows_removed))
    empty_cols = [c for c in out.columns if out[c].isna().all()]
    if empty_cols:
        report.empty_columns_removed = empty_cols
        report.actions.append(Action("empty_columns_removed", "Columns with no values at all were removed: " + ", ".join(empty_cols[:8]) + (" …" if len(empty_cols) > 8 else ""), len(empty_cols)))
        out = out.drop(columns=empty_cols)
    out = out.reset_index(drop=True)
    report.rows_kept = len(out)
    report.columns_kept = [str(c) for c in out.columns]
    # --- exact duplicates: COUNTED, never removed (a repeat sale is a normal business event)
    if len(out):
        report.duplicate_rows = int(out.astype(str).duplicated().sum())
        if report.duplicate_rows:
            report.warnings.append(
                f"{report.duplicate_rows} row(s) are exact repeats of an earlier row. They were kept: identical sales on the same day are normal. "
                "If they are accidental copies, remove them from your file or in My Data before analysing."
            )
    if len(out) == 0:
        raise ValidationFailedError(f"'{report.name}' has column headings but no data rows.")
    return out


def read_upload(filename: str, content: bytes, max_rows: int) -> ReadResult:
    """Read a CSV or .xlsx file into cleaned text-like tables with a report each. Raises ``ValidationFailedError`` with a plain-language reason."""
    lower = (filename or "").lower().strip()
    if lower.endswith(".xls"):
        raise ValidationFailedError("Old Excel files (.xls) are not supported. Open the file in Excel and use Save As > Excel Workbook (.xlsx), then upload that.")
    if lower.endswith(".xlsx"):
        frames, reports, ignored = read_xlsx(content, max_rows)
        if not frames:
            raise ValidationFailedError("The workbook has no sheet with data in it.")
        cleaned = {name: clean_frame(df, reports[name], max_rows) for name, df in frames.items()}
        return ReadResult(cleaned, reports, ignored)
    if lower.endswith(".csv"):
        df, rep = read_csv(content, max_rows, name=filename)
        return ReadResult({filename: clean_frame(df, rep, max_rows)}, {filename: rep}, [])
    raise ValidationFailedError(f"Unsupported file type: {filename or 'unnamed file'}. Upload a .csv or .xlsx file.")


# ------------------------------------------------------------------------------------------------ typed conversion of mapped columns
_CURRENCY_RE = re.compile(r"^(?:rs\.?|inr|usd|eur|gbp|[₹$€£])\s*|\s*(?:rs\.?|inr|usd|eur|gbp|[₹$€£])$", re.I)
_US_RE = re.compile(r"^-?\d{1,3}(,\d{3})*(\.\d+)?$|^-?\d+(\.\d+)?$")
_INDIAN_RE = re.compile(r"^-?\d{1,2}(,\d{2})*,\d{3}(\.\d+)?$")
_EU_RE = re.compile(r"^-?\d{1,3}(\.\d{3})*,\d+$|^-?\d+,\d{1,2}$")


@dataclass
class NumericResult:
    values: pd.Series                       # float with NaN where invalid or missing
    invalid: pd.Series                      # True where a value was present but could not be read unambiguously
    notes: list[str]
    examples: list[str]                     # up to 5 offending values (truncated)


def _strip_number(s: str) -> tuple[str, bool]:
    neg = False
    s = s.strip()
    if s.startswith("(") and s.endswith(")"):
        neg, s = True, s[1:-1].strip()
    s = _CURRENCY_RE.sub("", s).strip()
    s = _CURRENCY_RE.sub("", s).strip()
    return s, neg


def coerce_numeric(series: pd.Series) -> NumericResult:
    """Text numbers to floats only when the reading is unambiguous. Thousands separators (1,234 / 1,23,456), currency symbols and accounting
    brackets are understood; a column that mixes comma-decimal and dot-decimal conventions is not guessed at (those cells are invalid)."""
    texts = [v for v in series if isinstance(v, str)]
    eu_hits = sum(1 for t in texts if _EU_RE.match(_strip_number(t)[0]) and not _US_RE.match(_strip_number(t)[0]))
    us_hits = sum(1 for t in texts if "." in _strip_number(t)[0] and _US_RE.match(_strip_number(t)[0]))
    european = eu_hits > 0 and us_hits == 0
    mixed = eu_hits > 0 and us_hits > 0
    out, invalid, examples = [], [], []
    notes: list[str] = []
    converted_text = 0
    for v in series:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            out.append(float("nan")), invalid.append(False)
            continue
        if isinstance(v, bool):
            out.append(float("nan")), invalid.append(True), examples.append(str(v))
            continue
        if isinstance(v, (int, float)):
            f = float(v)
            ok = math.isfinite(f)
            out.append(f if ok else float("nan")), invalid.append(not ok)
            if not ok:
                examples.append(str(v))
            continue
        s, neg = _strip_number(str(v))
        val = None
        try:
            if not s.isascii():                                            # float() would accept digits from other scripts; those are not guessed at
                raise ValueError
            if _INDIAN_RE.match(s) or (_US_RE.match(s) and not european):
                val = float(s.replace(",", ""))
            elif european and _EU_RE.match(s):
                val = float(s.replace(".", "").replace(",", "."))
            elif not mixed and re.fullmatch(r"-?\d+(\.\d+)?([eE][-+]?\d+)?", s):
                val = float(s)
        except ValueError:
            val = None
        if val is None or not math.isfinite(val):
            out.append(float("nan")), invalid.append(True)
            if len(examples) < 5:
                examples.append(str(v)[:40])
            continue
        out.append(-val if neg else val), invalid.append(False)
        if s != str(v).strip():
            converted_text += 1
    if converted_text:
        notes.append(f"{converted_text} value(s) written as text with symbols or separators (for example ₹1,200.50) were read as numbers.")
    if european:
        notes.append("Numbers in this column use a decimal comma (1.234,56) and were read that way.")
    if mixed:
        notes.append("This column mixes decimal-comma and decimal-point numbers, so ambiguous values were not converted.")
    return NumericResult(pd.Series(out, index=series.index, dtype=float), pd.Series(invalid, index=series.index, dtype=bool), notes, examples[:5])


_ISO_RE = re.compile(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?:[ T].*)?$")
_DMY_RE = re.compile(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2}|\d{4})$")
_TEXT_FORMATS = ("%d %b %Y", "%d %B %Y", "%d-%b-%Y", "%d-%B-%Y", "%b %d, %Y", "%B %d, %Y", "%d %b, %Y", "%b %d %Y")


@dataclass
class DateResult:
    values: pd.Series                       # python date or None
    invalid: pd.Series
    question: DateQuestion | None           # set when the order of day and month cannot be known
    notes: list[str]
    examples: list[str]


def _valid_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def date_order_needed(series: pd.Series) -> tuple[str | None, list[str]]:
    """'day_first', 'month_first', 'mixed' (the same column uses both), 'ask' (all values fit both readings), or None when no slash-style date
    needs an order at all. Returns the examples that decided it."""
    day_only, month_only, both, examples = 0, 0, 0, []
    for v in series:
        if not isinstance(v, str):
            continue
        m = _DMY_RE.match(v.strip())
        if not m:
            continue
        a, b = int(m.group(1)), int(m.group(2))
        d_ok, m_ok = a <= 31 and b <= 12, a <= 12 and b <= 31
        if d_ok and m_ok and a != b:
            both += 1
            if len(examples) < 3:
                examples.append(v.strip())
        elif d_ok and not m_ok:
            day_only += 1
        elif m_ok and not d_ok:
            month_only += 1
    if day_only and month_only:
        return "mixed", examples
    if day_only:
        return "day_first", examples
    if month_only:
        return "month_first", examples
    if both:
        return "ask", examples
    return None, examples


def coerce_dates(series: pd.Series, order: str | None = None, column: str = "date") -> DateResult:
    """Dates to ``datetime.date``. ISO dates and written-out month names are unambiguous; a numeric day/month order is decided by the data when
    the data decides it, by the person's answer (``order``) when it does not, and is otherwise reported as a question, never assumed."""
    decided, examples = date_order_needed(series)
    notes: list[str] = []
    question = None
    use = order if order in ("day_first", "month_first") else (decided if decided in ("day_first", "month_first") else None)
    if decided in ("ask", "mixed") and use is None:
        question = DateQuestion(column=column, examples=examples)
    if decided == "day_first" and order is None:
        notes.append("Dates like 13/01/2026 were read as day/month/year because some values can only be read that way.")
    if decided == "month_first" and order is None:
        notes.append("Dates like 01/13/2026 were read as month/day/year because some values can only be read that way.")
    if decided in ("ask", "mixed") and order in ("day_first", "month_first"):
        notes.append("Dates like 03/04/2026 were read " + ("day first (3 April)" if order == "day_first" else "month first (4 March)") + ", as you chose.")
    out, invalid, bad = [], [], []
    two_digit = 0
    for v in series:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            out.append(None), invalid.append(False)
            continue
        d = None
        if isinstance(v, datetime):
            d = v.date()
        elif isinstance(v, date):
            d = v
        elif isinstance(v, str):
            s = v.strip()
            m = _ISO_RE.match(s)
            if m:
                d = _valid_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            else:
                m = _DMY_RE.match(s)
                if m and not use and int(m.group(1)) == int(m.group(2)):          # 05/05/2026: the same either way, so not a question
                    y = m.group(3)
                    d = _valid_date(int(y) + 2000 if len(y) == 2 else int(y), int(m.group(2)), int(m.group(1)))
                elif m and use:
                    a, b, y = int(m.group(1)), int(m.group(2)), m.group(3)
                    yy = int(y) + 2000 if len(y) == 2 else int(y)
                    two_digit += 1 if len(y) == 2 else 0
                    d = _valid_date(yy, b, a) if use == "day_first" else _valid_date(yy, a, b)
                elif not m:
                    for fmt in _TEXT_FORMATS:
                        try:
                            d = datetime.strptime(s, fmt).date()
                            break
                        except ValueError:
                            continue
        if d is None and not (question is not None and isinstance(v, str) and _DMY_RE.match(v.strip())):
            invalid.append(True)
            if len(bad) < 5:
                bad.append(str(v)[:40])
        else:
            invalid.append(False)
        out.append(d)
    if two_digit:
        notes.append(f"{two_digit} date(s) had a two-digit year and were read as 20YY.")
    return DateResult(pd.Series(out, index=series.index, dtype=object), pd.Series(invalid, index=series.index, dtype=bool), question, notes, bad)


# ------------------------------------------------------------------------------------------------ helpers shared by the service and tests
def sha256_hex(content: bytes) -> str:
    import hashlib

    return hashlib.sha256(content).hexdigest()


def safe_display_name(filename: str) -> str:
    """The file's name for display only: no path, no control characters, bounded. It is never used to build a path or a command."""
    base = (filename or "upload").replace("\\", "/").split("/")[-1]
    base = re.sub(r"[\x00-\x1f\x7f]", "", base).strip() or "upload"
    return base[:200]


def spreadsheet_safe(value: Any) -> Any:
    """For any CSV/Excel EXPORT: a text value that a spreadsheet would run as a formula (=, +, -, @, tab, carriage return) is prefixed with an
    apostrophe so it opens as text. Numbers, dates and None are returned unchanged."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        if value[:1] == "-" and re.fullmatch(r"-?\d+(\.\d+)?", value.strip()):
            return value                                                    # a plain negative number is data, not a formula
        return "'" + value
    return value
