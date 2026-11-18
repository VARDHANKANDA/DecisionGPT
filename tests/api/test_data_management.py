"""My Data: library, row listing, manual entry, edit, delete — all against the real
canonical tables, scoped by business."""
import pytest


def _business(client, name="Mgmt Co") -> str:
    r = client.post(
        "/api/v1/businesses",
        json={"name": name, "industry": "retail", "business_type": "D2C", "business_size": "small"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _add_product(client, bid, pid="P1", name="Kurta", price=500):
    r = client.post(
        f"/api/v1/businesses/{bid}/data/tables/products/rows",
        json={"rows": [{"external_product_id": pid, "name": name, "selling_price": price, "unit_cost": 200}]},
    )
    assert r.status_code == 201, r.text


def test_library_lists_every_kind_with_zero_rows_initially(client):
    bid = _business(client)
    lib = client.get(f"/api/v1/businesses/{bid}/data/library").json()
    kinds = {x["type"]: x for x in lib}
    assert {"sales", "customers", "products", "inventory", "marketing_campaigns", "finance"} <= set(kinds)
    assert all(x["rows"] == 0 for x in lib)


def test_manual_entry_then_view_edit_delete_sale(client):
    bid = _business(client)
    _add_product(client, bid)
    r = client.post(
        f"/api/v1/businesses/{bid}/data/tables/sales/rows",
        json={"rows": [{"sale_date": "2026-09-01", "product": "P1", "quantity": 3, "unit_price": 500}]},
    )
    assert r.status_code == 201 and r.json()["added"] == 1

    table = client.get(f"/api/v1/businesses/{bid}/data/tables/sales").json()
    assert table["total"] == 1
    row = table["rows"][0]
    assert row["values"]["product"] == "Kurta"
    assert row["values"]["revenue"] == 1500.0  # computed from quantity x price, same as uploads

    # Editing quantity recalculates the total (documented behaviour) and persists.
    e = client.patch(
        f"/api/v1/businesses/{bid}/data/tables/sales/rows/{row['id']}", json={"changes": {"quantity": 4}}
    )
    assert e.status_code == 200
    assert e.json()["values"]["quantity"] == 4 and e.json()["values"]["revenue"] == 2000.0

    # Link columns can't be edited in place.
    bad = client.patch(
        f"/api/v1/businesses/{bid}/data/tables/sales/rows/{row['id']}", json={"changes": {"product": "x"}}
    )
    assert bad.status_code == 422

    assert client.delete(f"/api/v1/businesses/{bid}/data/tables/sales/rows/{row['id']}").status_code == 204
    assert client.get(f"/api/v1/businesses/{bid}/data/tables/sales").json()["total"] == 0


def test_manual_entry_validation_message_is_plain_language(client):
    bid = _business(client)
    r = client.post(
        f"/api/v1/businesses/{bid}/data/tables/sales/rows",
        json={"rows": [{"sale_date": "not a date", "quantity": 1, "unit_price": 10}]},
    )
    assert r.status_code == 422
    assert "date" in r.json()["error"]["message"].lower()


def test_delete_product_detaches_sales_and_clear_table(client):
    bid = _business(client)
    _add_product(client, bid)
    client.post(
        f"/api/v1/businesses/{bid}/data/tables/sales/rows",
        json={"rows": [{"sale_date": "2026-09-01", "product": "P1", "quantity": 1, "unit_price": 500}]},
    )
    prod = client.get(f"/api/v1/businesses/{bid}/data/tables/products").json()["rows"][0]
    assert client.delete(f"/api/v1/businesses/{bid}/data/tables/products/rows/{prod['id']}").status_code == 204
    sale = client.get(f"/api/v1/businesses/{bid}/data/tables/sales").json()["rows"][0]
    assert sale["values"]["product"] is None  # sale is kept; its product link is cleared

    d = client.delete(f"/api/v1/businesses/{bid}/data/tables/sales").json()
    assert d["deleted"] == 1
    assert client.get(f"/api/v1/businesses/{bid}/data/tables/sales").json()["total"] == 0


def test_data_is_isolated_between_businesses(client):
    a, b = _business(client, "A"), _business(client, "B")
    _add_product(client, a)
    assert client.get(f"/api/v1/businesses/{b}/data/tables/products").json()["total"] == 0
    row = client.get(f"/api/v1/businesses/{a}/data/tables/products").json()["rows"][0]
    # business B can't touch business A's row
    assert client.delete(f"/api/v1/businesses/{b}/data/tables/products/rows/{row['id']}").status_code == 404


def test_unknown_table_type_is_404(client):
    bid = _business(client)
    assert client.get(f"/api/v1/businesses/{bid}/data/tables/nope").status_code == 404


@pytest.mark.parametrize(
    "question,intent",
    [
        ("Which products sold the most last month?", "top_products"),
        ("Which customers are likely to stop buying?", "customer_churn"),
        ("What might my sales look like next month?", "sales_forecast"),
        ("What is improving and what is getting worse?", "improving_worsening"),
        ("What should I focus on to improve my business?", "what_focus"),
        ("Which customers are most valuable?", "valuable_customers"),
    ],
)
def test_example_questions_route_to_real_intents(question, intent):
    from app.services.assistant_service import classify_intent

    assert classify_intent(question) == intent


def test_top_products_answer_uses_real_sales(client):
    bid = _business(client)
    _add_product(client, bid, "P1", "Kurta", 500)
    from datetime import date

    client.post(
        f"/api/v1/businesses/{bid}/data/tables/sales/rows",
        json={"rows": [{"sale_date": date.today().isoformat(), "product": "P1", "quantity": 2, "unit_price": 500}]},
    )
    r = client.post(f"/api/v1/businesses/{bid}/chat", json={"message": "Which products sold the most last month?"})
    body = r.json()
    assert body["intent"] == "top_products" and body["sufficient_evidence"] is True
    assert "Kurta" in body["answer"] and "₹1,000" in body["answer"]
    assert body["answer_type"] == "known"
    assert body["details"]["table"][0]["revenue"] == 1000.0


def test_my_businesses_empty_when_not_signed_in(client):
    assert client.get("/api/v1/businesses/mine").json() == []


def test_units_history_is_real_daily_units_and_empty_without_sales(client):
    bid = _business(client, "History Co")
    assert client.get(f"/api/v1/businesses/{bid}/analytics/units-history").json() == []
    _add_product(client, bid)
    rows = [
        {"sale_date": "2026-09-01", "product": "P1", "quantity": 3, "unit_price": 500},
        {"sale_date": "2026-09-03", "product": "P1", "quantity": 2, "unit_price": 500},
    ]
    assert client.post(f"/api/v1/businesses/{bid}/data/tables/sales/rows", json={"rows": rows}).status_code == 201
    hist = client.get(f"/api/v1/businesses/{bid}/analytics/units-history?days=30").json()
    assert [(h["date"], h["units_sold"]) for h in hist] == [
        ("2026-09-01", 3.0),
        ("2026-09-02", 0.0),  # a day with no sales is a real zero
        ("2026-09-03", 2.0),
    ]
