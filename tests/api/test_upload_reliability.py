"""The upload workflow end to end through the real API: valid files import and persist, messy-but-legitimate files import with a clear report, bad
files are refused with an actionable message (never a server error), nothing is half-saved, and tenants cannot reach each other's uploads."""
import io
import logging
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.db.session import Base, get_db
from app.main import app as fastapi_app
from app.models.ingestion_job import DataIngestionJob
from app.models.sale import Sale
from app.services import data_ingestion_service as ing
from tests.api.test_platform_api import P, _owner, auth_on  # noqa: F401  (auth_on is a fixture)

PW = "orange-river-4271"
HEAD = "Date,Product ID,Quantity,Unit Price\n"


def make_business(client, name="Shop"):
    r = client.post("/api/v1/businesses", json={"name": name, "industry": "retail", "business_type": "D2C", "business_size": "small"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def upload(client, bid, content, name="sales.csv", kind="sales", **params):
    q = "&".join([f"data_type={kind}"] if kind and name.lower().endswith(".csv") else []) + ("&" if params else "") + "&".join(f"{k}={v}" for k, v in params.items())
    return client.post(f"{P}/{bid}/data/upload" + (f"?{q}" if q else ""), files={"file": (name, content)})


def job(r):
    assert r.status_code == 200, r.text
    return r.json()


def table(client, bid, kind="sales"):
    """The stored rows of one table as plain dicts of values."""
    return [r["values"] for r in client.get(f"{P}/{bid}/data/tables/{kind}?limit=200").json()["rows"]]


def sales_rows(client, bid):
    return client.get(f"{P}/{bid}/data/summary").json()["sales"]


def xlsx(sheets):
    wb = Workbook()
    wb.remove(wb.active)
    for t, rows in sheets.items():
        ws = wb.create_sheet(t)
        for r in rows:
            ws.append(r)
    b = io.BytesIO()
    wb.save(b)
    return b.getvalue()


# ------------------------------------------------------------------ success paths
def test_a_valid_csv_is_imported_persisted_and_visible_to_the_dashboard(client):
    bid = make_business(client)
    j = job(upload(client, bid, (HEAD + "2026-01-01,A1,2,100\n2026-01-02,A2,1,250\n").encode()))
    assert j["status"] == "completed" and j["summary_json"]["rows_ingested"] == {"sales": 2}
    assert sales_rows(client, bid) == 2
    assert sorted(float(r["unit_price"]) for r in table(client, bid)) == [100.0, 250.0]
    assert client.get(f"{P}/{bid}/data/jobs/{j['id']}").json()["status"] == "completed"          # the job can be read back later
    assert j["id"] in [u["id"] for u in client.get(f"{P}/{bid}/data/uploads").json()]


def test_the_import_report_says_what_was_read_used_skipped_and_cleaned(client):
    bid = make_business(client)
    text = " Order Date ,Item,Qty , Price ,Notes,Empty\n2026-01-01,A1,2,\"₹1,200.50\",gift,\n2026-01-01,A1,2,\"₹1,200.50\",gift,\n,,,,,\n2026-01-02,A2,,250,,\n2026-01-03,A3,1,abc,,\n"
    j = job(upload(client, bid, text.encode("utf-8")))
    d = j["summary_json"]["datasets"][0]
    assert j["status"] == "completed" and d["rows_read"] == 5 and d["rows_imported"] == 2 and d["rows_skipped"] == 2
    assert {s["row"]: s["reason"].split(" (")[0] for s in d["skipped_examples"]} == {3: "missing 'quantity'", 4: "unreadable number in 'unit_price'"}
    assert {u["as"] for u in d["columns_used"]} == {"sale_date", "external_product_id", "quantity", "unit_price"}
    assert d["columns_not_used"] == ["Notes"] and d["columns_removed_empty"] == ["Empty"]                # "not used" is not "deleted"
    assert d["duplicate_rows"] == 1 and any("kept" in w for w in d["warnings"])
    assert {a["code"] for a in d["actions"]} >= {"blank_rows_removed", "empty_columns_removed"} and any("₹" in a["message"] for a in d["actions"])
    assert j["summary_json"]["original_kept"] is True
    assert float(table(client, bid)[0]["unit_price"]) == 1200.5                                              # ₹1,200.50 became 1200.5


def test_extra_columns_are_not_imported_but_are_kept_in_the_original_file(client):
    bid = make_business(client)
    raw = (HEAD.strip() + ",Notes,Region\n2026-01-01,A1,2,100,gift,North\n").encode()
    j = job(upload(client, bid, raw))
    assert j["status"] == "completed" and j["summary_json"]["datasets"][0]["columns_not_used"] == ["Notes", "Region"]
    kept = list(Path(get_settings().business_upload_path).rglob("original.csv"))
    assert len(kept) == 1 and kept[0].read_bytes() == raw                                                 # the original, byte for byte


@pytest.mark.parametrize("encoding,text", [("utf-8", "café"), ("cp1252", "café"), ("utf-8-sig", "café"), ("utf-16", "café")])
def test_common_encodings_import(client, encoding, text):
    bid = make_business(client)
    content = (HEAD + f"2026-01-01,{text},2,100\n").encode(encoding)
    j = job(upload(client, bid, content))
    assert j["status"] == "completed" and sales_rows(client, bid) == 1


@pytest.mark.parametrize("delim", [";", "\t", "|"])
def test_other_delimiters_import(client, delim):
    bid = make_business(client)
    j = job(upload(client, bid, ("Date" + delim + "Product ID" + delim + "Quantity" + delim + "Unit Price\n2026-01-01" + delim + "A" + delim + "2" + delim + "100\n").encode()))
    assert j["status"] == "completed"


def test_an_xlsx_with_one_arbitrary_sheet_name_is_recognised_by_its_columns(client):
    bid = make_business(client)
    j = job(upload(client, bid, xlsx({"Sheet1": [["Date", "Product ID", "Quantity", "Unit Price"], ["2026-01-01", "A1", 2, 100]]}), "export.xlsx", kind=None))
    assert j["status"] == "completed" and j["summary_json"]["rows_ingested"] == {"sales": 1}


def test_a_workbook_with_several_named_sheets_imports_each_and_lists_unused_sheets(client):
    bid = make_business(client)
    book = xlsx({
        "Sales": [["Date", "Product ID", "Quantity", "Unit Price"], ["2026-01-01", "P1", 2, 100]],
        "Products": [["Product ID", "Product Name", "Selling Price"], ["P1", "Kurta", 100]],
        "README": [["Notes about this file"], ["written by hand"]],
    })
    j = job(upload(client, bid, book, "all.xlsx", kind=None))
    assert j["status"] == "completed" and j["summary_json"]["rows_ingested"] == {"sales": 1, "products": 1}
    assert [s["sheet"] for s in j["summary_json"]["sheets_not_used"]] == ["README"]


def test_excel_numbers_for_ids_stay_whole_text_not_1001_point_0(client):
    bid = make_business(client)
    j = job(upload(client, bid, xlsx({"Sales": [["Date", "Product ID", "Quantity", "Unit Price"], ["2026-01-01", 1001.0, 2, 100]]}), "s.xlsx", kind=None))
    assert j["status"] == "completed"
    assert [r["product"] for r in table(client, bid)] == ["1001"]


def test_dates_written_day_first_are_read_day_first_when_the_data_proves_it(client):
    bid = make_business(client)
    j = job(upload(client, bid, (HEAD + "13/01/2026,A,1,10\n05/02/2026,A,1,10\n").encode()))
    assert j["status"] == "completed"
    assert sorted(r["sale_date"] for r in table(client, bid)) == ["2026-01-13", "2026-02-05"]


# ------------------------------------------------------------------ duplicates are reported, never deleted
def test_identical_rows_are_imported_as_separate_transactions_and_reported(client):
    bid = make_business(client)
    j = job(upload(client, bid, (HEAD + "2026-01-01,A1,1,100\n" * 3 + "2026-01-02,A2,1,250\n").encode()))
    assert j["status"] == "completed" and sales_rows(client, bid) == 4                                   # none deleted
    assert j["summary_json"]["datasets"][0]["duplicate_rows"] == 2


def test_the_same_file_twice_needs_an_explicit_confirmation(client):
    bid = make_business(client)
    content = (HEAD + "2026-01-01,A1,1,100\n").encode()
    first = job(upload(client, bid, content))
    again = job(upload(client, bid, content))
    assert first["status"] == "completed" and again["status"] == "failed" and "already imported" in again["error_message"]
    assert again["summary_json"]["duplicate_of"]["job_id"] == first["id"] and sales_rows(client, bid) == 1
    forced = job(upload(client, bid, content, allow_duplicate_file="true"))
    assert forced["status"] == "completed" and sales_rows(client, bid) == 2


# ------------------------------------------------------------------ refusals: clear messages, nothing saved
@pytest.mark.parametrize("name,content,needle", [
    ("sales.csv", b"", "empty"),
    ("sales.csv", b"Date,Product ID,Quantity,Unit Price\n", "no data rows"),
    ("report.pdf", b"%PDF-1.4", "Unsupported"),
    ("tool.exe", b"MZ\x90\x00", "Unsupported"),
    ("old.xls", b"\xd0\xcf\x11\xe0xxxx", ".xlsx"),
    ("sales.csv", b"PK\x03\x04binary-excel-with-a-csv-name", "Excel file"),
    ("sales.csv", b"Date,Quantity\n1,2\x00\x00\n", "binary"),
    ("fake.xlsx", b"this is plain text pretending to be Excel", "not a zip"),
    ("sales.csv", b"Date,Product ID,Quantity,Unit Price\n2026-01-01,A,1,2,3,4\n", "more values than the header"),
])
def test_unreadable_or_unsupported_files_are_refused_with_a_reason_and_save_nothing(client, name, content, needle):
    bid = make_business(client)
    j = job(upload(client, bid, content, name))
    assert j["status"] == "failed" and needle.lower() in j["error_message"].lower(), j["error_message"]
    assert sales_rows(client, bid) == 0 and j["mapping_json"] == {}


def test_an_oversized_file_is_refused(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_upload_bytes", 200)
    bid = make_business(client)
    j = job(upload(client, bid, (HEAD + "2026-01-01,A,1,1\n" * 100).encode()))
    assert j["status"] == "failed" and "limit" in j["error_message"] and sales_rows(client, bid) == 0


def test_a_file_with_too_many_rows_or_columns_is_refused(client, monkeypatch):
    bid = make_business(client)
    monkeypatch.setattr(get_settings(), "max_upload_rows", 3)
    j = job(upload(client, bid, (HEAD + "2026-01-01,A,1,1\n" * 10).encode()))
    assert j["status"] == "failed" and "rows" in j["error_message"] and sales_rows(client, bid) == 0
    wide = ",".join(f"c{i}" for i in range(250)) + "\n" + ",".join("1" for _ in range(250)) + "\n"
    j = job(upload(client, bid, wide.encode(), kind="sales"))
    assert j["status"] == "failed" and "columns" in j["error_message"]


def test_decimals_in_a_whole_number_field_are_refused_not_rounded(client):
    bid = make_business(client)
    j = job(upload(client, bid, (HEAD + "2026-01-01,A1,2.5,100\n").encode()))
    assert j["status"] == "failed" and "decimals" in j["error_message"] and "NOT imported" in j["error_message"] and sales_rows(client, bid) == 0


def test_a_file_where_most_rows_cannot_be_read_is_refused_as_a_whole(client):
    bid = make_business(client)
    rows = "".join(f"not-a-date-{i},A,1,10\n" for i in range(8)) + "2026-01-01,A,1,10\n"
    j = job(upload(client, bid, (HEAD + rows).encode()))
    assert j["status"] == "failed" and "most rows" in j["error_message"] and "unreadable date" in j["error_message"] and sales_rows(client, bid) == 0


def test_a_file_whose_kind_cannot_be_told_asks_the_person_instead_of_guessing(client):
    bid = make_business(client)
    j = job(upload(client, bid, xlsx({"Sheet1": [["Foo", "Bar"], [1, 2]]}), "x.xlsx", kind=None))
    assert j["status"] == "failed" and "What is in this file" in j["error_message"]


# ------------------------------------------------------------------ mapping and date questions
def test_missing_required_columns_ask_for_a_mapping_and_the_original_is_kept(client):
    bid = make_business(client)
    j = job(upload(client, bid, b"Day,Item,Units,Amount\n2026-01-01,A,2,200\n"))
    assert j["status"] == "needs_mapping_confirmation" and len(list(Path(get_settings().business_upload_path).rglob("original.csv"))) == 1
    p = j["mapping_json"]["sales"]
    assert set(p["unmapped_required_fields"]) == {"sale_date", "unit_price"} and p["available_columns"] == ["Day", "Item", "Units", "Amount"]
    done = job(client.post(f"{P}/{bid}/data/mapping?job_id={j['id']}", json={"mappings": {"sales": {"Day": "sale_date", "Item": "external_product_id", "Units": "quantity", "Amount": "unit_price"}}}))
    assert done["status"] == "completed" and sales_rows(client, bid) == 1


def test_an_incomplete_mapping_is_a_422_not_a_crash(client):
    bid = make_business(client)
    j = job(upload(client, bid, b"Day,Item,Units,Amount\n2026-01-01,A,2,200\n"))
    r = client.post(f"{P}/{bid}/data/mapping?job_id={j['id']}", json={"mappings": {"sales": {"Day": "sale_date"}}})
    assert r.status_code == 422 and sales_rows(client, bid) == 0


def test_ambiguous_dates_ask_a_question_and_the_answer_decides(client):
    bid = make_business(client)
    j = job(upload(client, bid, (HEAD + "03/04/2026,A,1,10\n05/06/2026,A,1,10\n").encode()))
    assert j["status"] == "needs_mapping_confirmation" and sales_rows(client, bid) == 0
    q = j["mapping_json"]["sales"]["date_questions"][0]
    assert q["field"] == "sale_date" and q["examples"]
    no_answer = client.post(f"{P}/{bid}/data/mapping?job_id={j['id']}", json={"mappings": {}})
    assert no_answer.status_code == 422 and "day/month/year" in no_answer.text
    done = job(client.post(f"{P}/{bid}/data/mapping?job_id={j['id']}", json={"mappings": {}, "date_orders": {"sales": {"sale_date": "month_first"}}}))
    assert done["status"] == "completed"
    assert sorted(r["sale_date"] for r in table(client, bid)) == ["2026-03-04", "2026-05-06"]


def test_confirming_twice_cannot_import_twice(client):
    bid = make_business(client)
    j = job(upload(client, bid, b"Day,Item,Units,Amount\n2026-01-01,A,2,200\n"))
    body = {"mappings": {"sales": {"Day": "sale_date", "Item": "external_product_id", "Units": "quantity", "Amount": "unit_price"}}}
    assert client.post(f"{P}/{bid}/data/mapping?job_id={j['id']}", json=body).status_code == 200
    assert client.post(f"{P}/{bid}/data/mapping?job_id={j['id']}", json=body).status_code == 422
    assert sales_rows(client, bid) == 1


# ------------------------------------------------------------------ rollback, retry, persistence
def test_a_failure_while_saving_leaves_nothing_behind_and_a_retry_works(client, db_session, monkeypatch):
    bid = make_business(client)
    real = ing._INGESTORS["sales"]

    def explode(db, business_id, df):
        real(db, business_id, df)                                  # the rows ARE added to the session ...
        raise RuntimeError("disk on fire: secret-detail")           # ... and then the save fails

    monkeypatch.setitem(ing._INGESTORS, "sales", explode)
    j = job(upload(client, bid, (HEAD + "2026-01-01,A1,1,100\n2026-01-02,A2,1,250\n").encode()))
    assert j["status"] == "failed" and "nothing was imported" in j["error_message"] and "secret-detail" not in json_text(j)
    assert db_session.query(Sale).count() == 0 and not list(Path(get_settings().business_upload_path).rglob("original*"))
    monkeypatch.setitem(ing._INGESTORS, "sales", real)
    retry = job(upload(client, bid, (HEAD + "2026-01-01,A1,1,100\n2026-01-02,A2,1,250\n").encode()))      # the SAME file is not treated as already imported
    assert retry["status"] == "completed" and db_session.query(Sale).count() == 2


def json_text(j):
    import json

    return json.dumps(j)


def test_a_failed_import_leaves_no_original_file_but_a_completed_one_does(client, db_session, tmp_path):
    bid = make_business(client)
    root = Path(get_settings().business_upload_path)
    bad = job(upload(client, bid, b""))
    assert bad["status"] == "failed" and not (root.exists() and list(root.rglob("original*")))
    good = job(upload(client, bid, (HEAD + "2026-01-01,A1,1,100\n").encode()))
    files = list(root.rglob("original.csv"))
    assert good["status"] == "completed" and len(files) == 1 and files[0].read_bytes().startswith(b"Date,Product ID")


def test_uploaded_data_survives_a_restart(tmp_path):
    """A file-backed database re-opened by a NEW engine (a restart) still holds the rows, the job and the original file."""
    url = f"sqlite:///{(tmp_path / 'restart.db').as_posix()}"
    e1 = create_engine(url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(e1)
    S1 = sessionmaker(bind=e1, autoflush=False)

    def over():
        s = S1()
        try:
            yield s
        finally:
            s.close()

    fastapi_app.dependency_overrides[get_db] = over
    try:
        c = TestClient(fastapi_app)
        bid = make_business(c)
        j = job(upload(c, bid, (HEAD + "2026-01-01,A1,2,100\n").encode()))
        key_file = list(Path(get_settings().business_upload_path).rglob("original.csv"))
    finally:
        fastapi_app.dependency_overrides.clear()
        e1.dispose()
    e2 = create_engine(url, connect_args={"check_same_thread": False})            # the "restarted" process
    with sessionmaker(bind=e2)() as s2:
        assert s2.query(Sale).count() == 1 and s2.get(DataIngestionJob, j["id"]).status == "completed"
    assert key_file and key_file[0].exists()
    e2.dispose()


# ------------------------------------------------------------------ security boundaries
def test_another_business_cannot_see_confirm_or_read_a_job_and_cannot_upload_into_your_business(client, auth_on):
    a, ha = _owner(client, "ua@example.com", "Alpha")
    b, hb = _owner(client, "ub@example.com", "Beta")
    j = client.post(f"{P}/{a}/data/upload?data_type=sales", files={"file": ("s.csv", b"Day,Item,Units,Amount\n2026-01-01,A,2,200\n")}, headers=ha).json()
    assert j["status"] == "needs_mapping_confirmation"
    for r in (client.get(f"{P}/{a}/data/jobs/{j['id']}", headers=hb),
              client.post(f"{P}/{a}/data/mapping?job_id={j['id']}", json={"mappings": {}}, headers=hb),
              client.post(f"{P}/{a}/data/upload?data_type=sales", files={"file": ("s.csv", (HEAD + "2026-01-01,A,1,1\n").encode())}, headers=hb),
              client.get(f"{P}/{a}/data/tables/sales", headers=hb)):
        assert r.status_code == 404 and "Alpha" not in r.text
    # your own business's job cannot be reached through someone else's path
    assert client.get(f"{P}/{b}/data/jobs/{j['id']}", headers=hb).status_code == 404
    assert client.get(f"{P}/{a}/data/jobs/{j['id']}", headers=ha).status_code == 200


def test_upload_needs_a_signed_in_owner_when_authentication_is_on(client, auth_on):
    a, ha = _owner(client, "uo@example.com", "Owner")
    assert client.post(f"{P}/{a}/data/upload", files={"file": ("s.csv", b"a\n1\n")}).status_code == 401


def test_the_file_name_cannot_steer_where_the_original_is_stored_and_content_is_never_logged(client, caplog):
    bid = make_business(client)
    secret_cell = "ZZ-CUSTOMER-SECRET-9931"
    with caplog.at_level(logging.DEBUG):
        j = job(upload(client, bid, (HEAD + f"2026-01-01,{secret_cell},1,10\n").encode(), "../../../../etc/passwd.csv"))
    assert j["filename"] == "passwd.csv" and j["status"] == "completed"
    root = Path(get_settings().business_upload_path).resolve()
    stored = list(root.rglob("*"))
    assert stored and all(root in p.resolve().parents or p.resolve() == root for p in stored)
    assert not any("passwd" in p.name for p in stored)                                    # the stored name is fixed, never the uploaded one
    assert secret_cell not in "\n".join(r.getMessage() + str(r.__dict__) for r in caplog.records)


def test_text_that_looks_like_code_or_a_formula_is_stored_as_plain_text(client):
    bid = make_business(client)
    payload = '=HYPERLINK("http://evil.example","x")'
    quoted = payload.replace('"', '""')                                                    # correct CSV: quotes inside a quoted field are doubled
    j = job(upload(client, bid, (HEAD + f'2026-01-01,"{quoted}",1,10\n2026-01-02,<script>alert(1)</script>,1,10\n').encode()))
    assert j["status"] == "completed"
    names = sorted(r["product"] for r in table(client, bid))
    assert set(names) == {payload, "<script>alert(1)</script>"}                                # kept verbatim: data, not instructions


def test_a_zip_bomb_xlsx_is_refused_without_being_opened(client, monkeypatch):
    from app.services import upload_preprocessing as prep

    monkeypatch.setattr(prep, "MAX_ARCHIVE_EXPANSION_BYTES", 500)
    bid = make_business(client)
    j = job(upload(client, bid, xlsx({"Sales": [["Date", "Product ID", "Quantity", "Unit Price"], ["2026-01-01", "A", 1, 1]]}), "bomb.xlsx", kind=None))
    assert j["status"] == "failed" and "expands" in j["error_message"]


def test_no_server_error_for_any_of_a_set_of_hostile_inputs(client):
    bid = make_business(client)
    hostile = [b"\xff\xfe\xfd" * 100, b"a,b\n" + b"\x00" * 50, b'a,"b\n1,2', b"=1+1\n=2+2\n", ("a," * 5000 + "\n1\n").encode(), b"\n\n\n", b"a,b\n" + b"x," * 100000]
    for blob in hostile:
        r = upload(client, bid, blob)
        assert r.status_code == 200 and r.json()["status"] in ("failed", "completed", "needs_mapping_confirmation"), (blob[:20], r.status_code)
