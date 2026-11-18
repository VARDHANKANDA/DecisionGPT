"""Files handed back for spreadsheets are protected against formula injection, and the stored data is left exactly as it was."""
import csv
import io

from app.services import export_safety, research_export_service


def test_the_csv_stream_neutralises_formula_cells_and_keeps_everything_else(tmp_path):
    src = tmp_path / "processed.csv"
    src.write_text('name,note,amount\n=SUM(A1:A9),+1,10\n"@cmd",-5,-12.5\nKurta,hello,3\n', encoding="utf-8")
    out = b"".join(export_safety.safe_csv_stream(src)).decode("utf-8")
    rows = list(csv.reader(io.StringIO(out)))
    assert rows[0] == ["name", "note", "amount"]
    assert rows[1] == ["'=SUM(A1:A9)", "'+1", "10"]
    assert rows[2] == ["'@cmd", "-5", "-12.5"]                    # a plain negative number is data, not a formula
    assert rows[3] == ["Kurta", "hello", "3"]
    assert src.read_text(encoding="utf-8").startswith("name,note,amount\n=SUM(A1:A9)")      # the stored file is untouched


def test_a_large_file_is_streamed_in_chunks(tmp_path):
    src = tmp_path / "big.csv"
    src.write_text("a,b\n" + "".join(f"{i},=x{i}\n" for i in range(1500)), encoding="utf-8")
    chunks = list(export_safety.safe_csv_stream(src))
    assert len(chunks) >= 3 and b"'=x1499" in b"".join(chunks)


def test_the_research_csv_export_neutralises_text_cells():
    text = research_export_service._rows_to_csv(["model", "note"], [["=cmd|' /C calc'!A0", "ok"], ["xgb", "+2"]])
    rows = list(csv.reader(io.StringIO(text)))
    assert rows[1][0].startswith("'=") and rows[2] == ["xgb", "'+2"]
