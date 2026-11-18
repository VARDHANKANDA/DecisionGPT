"""Reading and cleaning an uploaded file: every rule is tested on a small input whose correct answer is known.

The principles under test: nothing is guessed silently, nothing is deleted without being reported, nothing is invented, nothing in the file is
executed, and resource use is bounded."""
import io
import zipfile

import numpy as np
import pandas as pd
import pytest
from openpyxl import Workbook

from app.core.errors import ValidationFailedError
from app.services import upload_preprocessing as prep

MAX = 1000


def _csv(text: str, enc: str = "utf-8") -> bytes:
    return text.encode(enc)


def _read(text, name="s.csv", enc="utf-8"):
    return prep.read_upload(name, _csv(text, enc), MAX)


def _xlsx(sheets: dict[str, list[list]]) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    for title, rows in sheets.items():
        ws = wb.create_sheet(title)
        for r in rows:
            ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ------------------------------------------------------------------ decoding and delimiters
def test_utf8_bom_and_plain_utf8_read_identically():
    plain, bom = _read("a,b\n1,2\n"), prep.read_upload("s.csv", b"\xef\xbb\xbf" + b"a,b\n1,2\n", MAX)
    assert list(plain.frames["s.csv"].columns) == list(bom.frames["s.csv"].columns) == ["a", "b"]


def test_windows_1252_is_read_with_a_warning_not_rejected():
    r = prep.read_upload("s.csv", "name,price\ncaf\xe9,100\n".encode("cp1252"), MAX)
    df = r.frames["s.csv"]
    assert df.loc[0, "name"] == "café" and r.reports["s.csv"].encoding == "windows-1252"
    assert any("Windows-1252" in w for w in r.reports["s.csv"].warnings)


def test_utf16_with_bom_is_read():
    r = prep.read_upload("s.csv", "a,b\n1,2\n".encode("utf-16"), MAX)
    assert r.frames["s.csv"].shape == (1, 2) and r.reports["s.csv"].encoding == "utf-16"


@pytest.mark.parametrize("delim", [",", ";", "\t", "|"])
def test_the_delimiter_is_detected(delim):
    r = _read(delim.join(["Date", "Qty", "Price"]) + "\n" + delim.join(["2026-01-01", "2", "100"]) + "\n")
    assert list(r.frames["s.csv"].columns) == ["Date", "Qty", "Price"] and r.reports["s.csv"].delimiter == delim


def test_a_comma_inside_quotes_does_not_split_a_field():
    r = _read('name,price\n"Kurta, red",100\n')
    assert r.frames["s.csv"].loc[0, "name"] == "Kurta, red"


@pytest.mark.parametrize("content,needle", [
    (b"", "empty"), (b"   \n\n", "empty"), (b"%PDF-1.7 binary", "PDF"), (b"PK\x03\x04junk", "Excel"), (b"a,b\n1,\x00\x00\x00\n", "binary"),
    (b"a,b\n", "no data rows"),
])
def test_unreadable_or_non_csv_content_is_refused_with_a_reason(content, needle):
    with pytest.raises(ValidationFailedError, match=needle):
        prep.read_upload("s.csv", content, MAX)


def test_a_row_with_extra_filled_cells_is_refused_because_a_value_probably_contains_the_separator():
    with pytest.raises(ValidationFailedError, match="more values than the header"):
        _read("a,b\n1,2,3\n")


def test_short_rows_are_padded_and_reported_and_long_rows_with_only_empty_extras_are_trimmed():
    r = _read("a,b,c\n1,2\n4,5,6,\n")
    assert r.frames["s.csv"].loc[0, "c"] is None
    assert any(a.code == "short_rows_padded" for a in r.reports["s.csv"].actions)


def test_unsupported_extensions_are_refused_and_xls_says_how_to_convert():
    for name in ("a.pdf", "a.txt", "a.exe", "noextension", ""):
        with pytest.raises(ValidationFailedError, match="Unsupported"):
            prep.read_upload(name, b"a,b\n1,2\n", MAX)
    with pytest.raises(ValidationFailedError, match=r"\.xlsx"):
        prep.read_upload("old.xls", b"\xd0\xcf\x11\xe0", MAX)


# ------------------------------------------------------------------ headers
def test_header_names_are_trimmed_and_blank_and_duplicate_names_get_deterministic_distinct_names_without_losing_data():
    r = _read(" Date ,,Qty,qty,Qty\n2026-01-01,x,1,2,3\n")
    df, rep = r.frames["s.csv"], r.reports["s.csv"]
    assert list(df.columns) == ["Date", "Unnamed column 2", "Qty", "qty (2)", "Qty (3)"]
    assert df.iloc[0].tolist() == ["2026-01-01", "x", "1", "2", "3"]                  # every value survived, none overwritten
    assert {a.code for a in rep.actions} >= {"duplicate_headers_renamed", "blank_headers_named"}
    again = _read(" Date ,,Qty,qty,Qty\n2026-01-01,x,1,2,3\n").frames["s.csv"]
    assert list(again.columns) == list(df.columns)                                     # deterministic


# ------------------------------------------------------------------ cells, blanks, nulls
def test_spacing_inside_a_value_is_never_changed_so_distinct_names_stay_distinct():
    """A double space inside a product name is data: ``PAVITHRAM  SE`` and ``PAVITHRAM SE`` are two values to this code. Collapsing them merged two
    products in a real evaluation dataset and changed a distinct-product count (found by the 27-task trace test)."""
    raw = pd.DataFrame({"Product": ["PAVITHRAM  SE", "PAVITHRAM SE", "  PAVITHRAM SE  ", "a	b"], "Qty": [1, 2, 3, 4]})
    out = prep.clean_frame(raw, prep.FrameReport(name="t"), 1000)
    assert list(out["Product"]) == ["PAVITHRAM  SE", "PAVITHRAM SE", "PAVITHRAM SE", "a	b"]      # ends trimmed, inside untouched
    assert out["Product"].nunique() == 3


def test_whitespace_and_non_breaking_spaces_are_trimmed_and_null_spellings_become_missing():
    r = _read("a,b,c,d,e,f\n  x  ,\u00a0y\u00a0,N/A,null,-,none\nz,w,1,2,3,4\n")
    first = r.frames["s.csv"].iloc[0].tolist()
    assert first[:2] == ["x", "y"] and first[2:] == [None, None, None, None]       # spelled-out "no value" becomes missing, not the text "N/A"


def test_blank_rows_and_empty_columns_are_removed_and_counted_never_silently():
    r = _read("a,b,empty\n1,2,\n,,\n3,4,\n")
    df, rep = r.frames["s.csv"], r.reports["s.csv"]
    assert list(df.columns) == ["a", "b"] and len(df) == 2
    assert rep.blank_rows_removed == 1 and rep.empty_columns_removed == ["empty"] and rep.rows_read == 3
    assert {a.code for a in rep.actions} >= {"blank_rows_removed", "empty_columns_removed"}


def test_exact_duplicate_rows_are_counted_and_warned_about_but_never_removed():
    r = _read("d,p,q\n2026-01-01,A,1\n2026-01-01,A,1\n2026-01-01,A,1\n2026-01-02,B,1\n")
    assert len(r.frames["s.csv"]) == 4 and r.reports["s.csv"].duplicate_rows == 2
    assert any("kept" in w for w in r.reports["s.csv"].warnings)


def test_a_cell_with_a_huge_amount_of_text_is_refused():
    with pytest.raises(ValidationFailedError, match="characters"):
        _read("a,b\n" + "x" * (prep.MAX_CELL_CHARS + 1) + ",1\n")


def test_row_and_column_limits_are_enforced_with_actionable_messages():
    many_rows = "a\n" + "\n".join(str(i) for i in range(30)) + "\n"
    with pytest.raises(ValidationFailedError, match="limit"):
        prep.read_upload("s.csv", many_rows.encode(), 10)
    wide = ",".join(f"c{i}" for i in range(prep.MAX_COLUMNS + 1)) + "\n" + ",".join("1" for _ in range(prep.MAX_COLUMNS + 1)) + "\n"
    with pytest.raises(ValidationFailedError, match="columns"):
        _read(wide)


# ------------------------------------------------------------------ Excel
def test_xlsx_values_are_read_and_dates_become_iso_text():
    import datetime as dt

    r = prep.read_upload("w.xlsx", _xlsx({"Sales": [["Date", "Qty"], [dt.datetime(2026, 1, 5), 2], [dt.datetime(2026, 1, 6, 14, 30), 3]]}), MAX)
    df = r.frames["Sales"]
    assert df["Date"].tolist() == ["2026-01-05", "2026-01-06 14:30:00"] and df["Qty"].tolist() == [2, 3]


def test_formulas_are_never_evaluated_and_text_that_looks_like_a_formula_stays_text():
    wb = Workbook()
    ws = wb.active
    ws.title = "Sales"
    ws.append(["a", "b"])
    ws.append([1, "=1+1"])                                                       # a real formula, never calculated by anything: no stored value
    ws.append(["x", "y"])
    for col, text in ((1, '=HYPERLINK("http://evil.example","x")'), (2, "=cmd|' /C calc'!A0")):
        cell = ws.cell(row=4, column=col, value=text)
        cell.data_type = "s"                                                     # a plain TEXT cell whose text starts with '='
    buf = io.BytesIO()
    wb.save(buf)
    df = prep.read_upload("w.xlsx", buf.getvalue(), MAX).frames["Sales"]
    assert df.iloc[0, 1] is None                                                 # the formula was NOT evaluated to 2
    assert df.iloc[2, 0].startswith("=HYPERLINK") and df.iloc[2, 1].startswith("=cmd")   # kept verbatim as text: data, never an action


def test_hidden_and_empty_sheets_are_skipped_and_listed_not_silently_dropped():
    wb = Workbook()
    ws = wb.active
    ws.title = "Sales"
    ws.append(["a"]), ws.append([1])
    hidden = wb.create_sheet("Secret")
    hidden.append(["x"]), hidden.append([1])
    hidden.sheet_state = "hidden"
    wb.create_sheet("Blank")
    buf = io.BytesIO()
    wb.save(buf)
    r = prep.read_upload("w.xlsx", buf.getvalue(), MAX)
    assert list(r.frames) == ["Sales"]
    assert {(i["sheet"], i["reason"].split(" ")[0]) for i in r.ignored_sheets} == {("Secret", "hidden"), ("Blank", "empty")}


@pytest.mark.parametrize("content,needle", [
    (b"not a zip at all", "not a zip"), (b"PK\x03\x04garbage-not-a-real-zip", "damaged|not a real"),
])
def test_a_damaged_or_fake_xlsx_is_a_message_not_a_crash(content, needle):
    with pytest.raises(ValidationFailedError, match=needle):
        prep.read_upload("w.xlsx", content, MAX)


def test_a_zip_that_is_not_a_workbook_is_refused():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("hello.txt", "hi")
    with pytest.raises(ValidationFailedError, match="not an Excel workbook"):
        prep.read_upload("w.xlsx", buf.getvalue(), MAX)


def test_an_archive_that_expands_enormously_is_refused_before_it_is_opened(monkeypatch):
    monkeypatch.setattr(prep, "MAX_ARCHIVE_EXPANSION_BYTES", 100)
    with pytest.raises(ValidationFailedError, match="expands"):
        prep.read_upload("w.xlsx", _xlsx({"Sales": [["a"], [1]]}), MAX)


def test_too_many_sheets_are_refused(monkeypatch):
    monkeypatch.setattr(prep, "MAX_SHEETS", 2)
    with pytest.raises(ValidationFailedError, match="sheets"):
        prep.read_upload("w.xlsx", _xlsx({f"S{i}": [["a"], [1]] for i in range(3)}), MAX)


# ------------------------------------------------------------------ numbers
def _num(values):
    return prep.coerce_numeric(pd.Series(values, dtype=object))


def test_plain_and_separated_numbers_are_read_exactly():
    r = _num(["1200", "1,200", "1,200.50", "12,34,567", "  -5 ", "1e3", 7, 2.5])
    assert r.values.tolist() == [1200, 1200, 1200.5, 1234567, -5, 1000, 7, 2.5] and not r.invalid.any()


def test_currency_symbols_and_accounting_brackets_are_understood():
    r = _num(["₹1,200.50", "Rs. 500", "$3", "(1,200)", "INR 99"])
    assert r.values.tolist() == [1200.5, 500, 3, -1200, 99] and not r.invalid.any()
    assert any("symbols or separators" in n for n in r.notes)


def test_a_decimal_comma_column_is_read_as_decimal_comma_only_when_it_is_consistent():
    r = _num(["1.234,56", "12,5", "3,75"])
    assert r.values.tolist() == [1234.56, 12.5, 3.75]
    mixed = _num(["1.234,56", "1,234.56"])                              # both conventions in one column: not guessed
    assert mixed.invalid.any() and any("mixes" in n for n in mixed.notes)


@pytest.mark.parametrize("bad", ["abc", "12abc", "1.2.3", "--5", "NaN-ish", "inf", "-inf", "1,2,3,4", "٣", True])
def test_text_that_is_not_unambiguously_a_number_is_invalid_not_guessed(bad):
    r = _num([bad])
    assert bool(r.invalid.iloc[0]) and np.isnan(r.values.iloc[0])


def test_missing_stays_missing_and_is_not_invalid():
    r = _num([None, float("nan"), "5"])
    assert r.invalid.tolist() == [False, False, False] and np.isnan(r.values.iloc[0]) and r.values.iloc[2] == 5


def test_non_finite_numbers_from_excel_are_invalid():
    r = _num([float("inf"), float("-inf")])
    assert r.invalid.all()


# ------------------------------------------------------------------ dates
def _dates(values, order=None):
    return prep.coerce_dates(pd.Series(values, dtype=object), order)


def test_iso_and_written_month_dates_are_unambiguous():
    r = _dates(["2026-01-05", "2026/1/5", "5 Jan 2026", "Jan 5, 2026", "05-Jan-2026", "January 5, 2026"])
    assert {str(d) for d in r.values} == {"2026-01-05"} and r.question is None and not r.invalid.any()


def test_slash_dates_are_decided_by_the_data_when_it_can_decide():
    day_first = _dates(["13/01/2026", "05/02/2026"])
    assert day_first.question is None and [str(d) for d in day_first.values] == ["2026-01-13", "2026-02-05"]
    month_first = _dates(["01/13/2026", "02/05/2026"])
    assert month_first.question is None and [str(d) for d in month_first.values] == ["2026-01-13", "2026-02-05"]


def test_slash_dates_that_fit_both_readings_are_a_question_never_a_guess():
    r = _dates(["03/04/2026", "05/06/2026"])
    assert r.question is not None and r.question.options == ("day_first", "month_first") and r.question.examples
    assert not r.invalid.any()                                                           # unanswered is not "invalid"


def test_the_persons_answer_resolves_the_order():
    assert [str(d) for d in _dates(["03/04/2026"], "day_first").values] == ["2026-04-03"]
    assert [str(d) for d in _dates(["03/04/2026"], "month_first").values] == ["2026-03-04"]


def test_a_column_that_uses_both_orders_is_a_question():
    assert _dates(["13/01/2026", "01/13/2026"]).question is not None


def test_same_day_and_month_is_not_ambiguous():
    r = _dates(["05/05/2026"])
    assert r.question is None and [str(d) for d in r.values] == ["2026-05-05"] and not r.invalid.any()


@pytest.mark.parametrize("bad", ["2026-13-01", "2026-02-30", "31/02/2026", "yesterday", "32 Jan 2026", "abc"])
def test_impossible_or_unreadable_dates_are_invalid(bad):
    assert bool(_dates([bad], "day_first").invalid.iloc[0])


def test_python_dates_and_missing_values_pass_through():
    import datetime as dt

    r = _dates([dt.date(2026, 1, 5), dt.datetime(2026, 1, 6, 9), None])
    assert [str(d) if d else None for d in r.values] == ["2026-01-05", "2026-01-06", None] and not r.invalid.any()


def test_two_digit_years_are_read_as_20yy_and_noted():
    r = _dates(["13/01/26"])
    assert str(r.values.iloc[0]) == "2026-01-13" and any("two-digit" in n for n in r.notes)


# ------------------------------------------------------------------ names, hashes, export safety
def test_the_display_name_is_never_a_path_and_has_no_control_characters():
    assert prep.safe_display_name("../../etc/passwd") == "passwd"
    assert prep.safe_display_name("C:\\Users\\x\\sales.csv") == "sales.csv"
    assert prep.safe_display_name("a\x00b\nc.csv") == "abc.csv" and prep.safe_display_name("") == "upload"
    assert len(prep.safe_display_name("x" * 500 + ".csv")) <= 200


def test_the_hash_is_stable_and_content_specific():
    assert prep.sha256_hex(b"a") == prep.sha256_hex(b"a") != prep.sha256_hex(b"b")


@pytest.mark.parametrize("value,expected", [
    ("=SUM(A1:A9)", "'=SUM(A1:A9)"), ("+cmd|' /C calc'!A0", "'+cmd|' /C calc'!A0"), ("@SUM(1)", "'@SUM(1)"), ("-2+3", "'-2+3"),
    ("\t=x", "'\t=x"), ("\r=x", "'\r=x"), ("Kurta", "Kurta"), ("-5", "-5"), ("-12.5", "-12.5"), (42, 42), (3.5, 3.5), (None, None),
])
def test_exported_text_that_a_spreadsheet_would_run_as_a_formula_is_neutralised(value, expected):
    assert prep.spreadsheet_safe(value) == expected


def test_a_date_order_the_person_chose_is_stated_in_the_report():
    col = pd.Series(["03/04/2026", "05/06/2026", None], dtype=object)
    day = prep.coerce_dates(col, "day_first", column="d")
    assert day.question is None and [str(v) for v in day.values[:2]] == ["2026-04-03", "2026-06-05"]
    assert any("day first (3 April), as you chose" in n for n in day.notes)
    month = prep.coerce_dates(col, "month_first", column="d")
    assert [str(v) for v in month.values[:2]] == ["2026-03-04", "2026-05-06"]
    assert any("month first (4 March), as you chose" in n for n in month.notes)
    # nothing is claimed when the data itself decided the order
    decided = prep.coerce_dates(pd.Series(["13/01/2026", "02/02/2026"], dtype=object), None, column="d")
    assert not any("as you chose" in n for n in decided.notes)


def test_values_read_as_missing_because_of_their_spelling_are_counted_per_column_and_reported():
    """A product called "None" or a customer code "NA" looks like a null spelling. It is read as missing (the standard reading) but the person is told
    exactly how many cells and in which columns, so nothing is lost silently."""
    raw = pd.DataFrame({"Product": ["Tea", "None", "N/A", "Coffee"], "Customer": ["C1", "NA", "C3", "-"], "Qty": [1, 2, 3, 4]})
    rep = prep.FrameReport(name="t")
    out = prep.clean_frame(raw, rep, 1000)
    acts = [a for a in rep.actions if a.code == "null_spellings_read_as_missing"]
    assert len(acts) == 1 and acts[0].count == 4
    assert "'Product' (2)" in acts[0].message and "'Customer' (2)" in acts[0].message and "rename it in your file" in acts[0].message
    assert out["Product"].isna().sum() == 2
    # genuinely empty cells are not "spelled" nulls: nothing to report
    quiet = prep.FrameReport(name="t")
    prep.clean_frame(pd.DataFrame({"P": ["a", None, ""], "Q": [1, 2, 3]}), quiet, 1000)
    assert not [a for a in quiet.actions if a.code == "null_spellings_read_as_missing"]
