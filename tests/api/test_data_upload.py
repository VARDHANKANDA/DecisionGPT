import io

import pandas as pd


def _create_business(client, name="Test D2C Co") -> str:
    response = client.post(
        "/api/v1/businesses",
        json={
            "name": name,
            "industry": "apparel",
            "business_type": "D2C",
            "business_size": "small",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _build_workbook() -> bytes:
    products = pd.DataFrame(
        [
            {"Product ID": "P001", "Product Name": "Cotton Kurta", "Category": "Apparel", "Cost Price": 400, "Selling Price": 999, "Stock Quantity": 120},
            {"Product ID": "P002", "Product Name": "Linen Shirt", "Category": "Apparel", "Cost Price": 500, "Selling Price": 1299, "Stock Quantity": 80},
        ]
    )
    customers = pd.DataFrame(
        [
            {"Customer ID": "C001", "Segment": "Loyal", "First Purchase Date": "2024-01-10", "Last Purchase Date": "2024-06-01", "Purchase Frequency": 4, "Monetary Value": 5200},
            {"Customer ID": "C002", "Segment": "New", "First Purchase Date": "2024-05-01", "Last Purchase Date": "2024-05-01", "Purchase Frequency": 1, "Monetary Value": 999},
        ]
    )
    sales = pd.DataFrame(
        [
            {"Order Date": "2024-06-01", "Customer ID": "C001", "Product ID": "P001", "Quantity": 2, "Unit Price": 999, "Discount": 0, "Total Amount": 1998},
            {"Order Date": "2024-06-02", "Customer ID": "C002", "Product ID": "P002", "Quantity": 1, "Unit Price": 1299, "Discount": 100, "Total Amount": 1199},
        ]
    )
    marketing = pd.DataFrame(
        [
            {"Date": "2024-06-01", "Channel": "Instagram", "Campaign": "Summer Sale", "Spend": 5000, "Impressions": 20000, "Clicks": 800, "Conversions": 40, "Revenue": 25000},
        ]
    )
    inventory = pd.DataFrame(
        [
            {"Product ID": "P001", "Date": "2024-06-01", "Stock Level": 118, "Reorder Level": 20},
            {"Product ID": "P002", "Date": "2024-06-01", "Stock Level": 79, "Reorder Level": 15},
        ]
    )

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        products.to_excel(writer, sheet_name="Products", index=False)
        customers.to_excel(writer, sheet_name="Customers", index=False)
        sales.to_excel(writer, sheet_name="Sales", index=False)
        marketing.to_excel(writer, sheet_name="Marketing", index=False)
        inventory.to_excel(writer, sheet_name="Inventory", index=False)
    buffer.seek(0)
    return buffer.read()


def test_full_workbook_upload_ingests_all_sheets(client):
    business_id = _create_business(client)
    workbook_bytes = _build_workbook()

    response = client.post(
        f"/api/v1/businesses/{business_id}/data/upload",
        files={"file": ("demo_business.xlsx", workbook_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert response.status_code == 200, response.text
    job = response.json()
    assert job["status"] == "completed", job
    assert job["summary_json"]["rows_ingested"] == {
        "products": 2,
        "customers": 2,
        "sales": 2,
        "marketing_campaigns": 1,
        "inventory": 2,
    }

    summary = client.get(f"/api/v1/businesses/{business_id}/data/summary").json()
    assert summary == {
        "products": 2,
        "customers": 2,
        "sales": 2,
        "marketing_campaigns": 1,
        "inventory_records": 2,
        "finance_records": 0,
        "business_profile_set": False,
    }


def test_csv_upload_with_explicit_data_type(client):
    business_id = _create_business(client)
    csv_bytes = (
        b"Order Date,Customer ID,Product ID,Quantity,Unit Price,Discount,Total Amount\n"
        b"2024-06-01,C001,P001,2,999,0,1998\n"
    )

    response = client.post(
        f"/api/v1/businesses/{business_id}/data/upload?data_type=sales",
        files={"file": ("sales_export.csv", csv_bytes, "text/csv")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "completed"
    assert response.json()["summary_json"]["rows_ingested"]["sales"] == 1


def test_unknown_data_type_fails_gracefully_not_500(client):
    """An unrecognised ?data_type=... must not crash (was a KeyError → HTTP 500);
    it now yields a failed job with a clear message."""
    business_id = _create_business(client)
    r = client.post(
        f"/api/v1/businesses/{business_id}/data/upload?data_type=aliens",
        files={"file": ("x.csv", b"a,b\n1,2\n", "text/csv")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "failed"
    assert "Unknown data type 'aliens'" in r.json()["error_message"]
    assert "sales" in r.json()["error_message"]  # lists the supported types


def test_ambiguous_mapping_requires_confirmation_then_ingests(client):
    business_id = _create_business(client)
    # None of these headers match any alias for the three required product
    # fields (external_product_id, name, selling_price) — should be flagged.
    csv_bytes = b"Item Code,Item Label,Item Price\nP001,Kurta,999\n"

    upload = client.post(
        f"/api/v1/businesses/{business_id}/data/upload?data_type=products",
        files={"file": ("products.csv", csv_bytes, "text/csv")},
    )
    assert upload.status_code == 200
    job = upload.json()
    assert job["status"] == "needs_mapping_confirmation"
    unmapped = set(job["mapping_json"]["products"]["unmapped_required_fields"])
    assert unmapped == {"external_product_id", "name", "selling_price"}

    incomplete = client.post(
        f"/api/v1/businesses/{business_id}/data/mapping?job_id={job['id']}",
        json={"mappings": {"products": {"Item Code": "external_product_id"}}},
    )
    # name/selling_price still unmapped -> should fail clearly, not crash
    assert incomplete.status_code == 422

    confirm_ok = client.post(
        f"/api/v1/businesses/{business_id}/data/mapping?job_id={job['id']}",
        json={
            "mappings": {
                "products": {
                    "Item Code": "external_product_id",
                    "Item Label": "name",
                    "Item Price": "selling_price",
                },
            }
        },
    )
    assert confirm_ok.status_code == 200, confirm_ok.text
    assert confirm_ok.json()["status"] == "completed"
    assert confirm_ok.json()["summary_json"]["rows_ingested"]["products"] == 1


def test_business_data_isolation(client):
    business_a = _create_business(client, "Business A")
    business_b = _create_business(client, "Business B")

    workbook_bytes = _build_workbook()
    client.post(
        f"/api/v1/businesses/{business_a}/data/upload",
        files={"file": ("a.xlsx", workbook_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )

    summary_a = client.get(f"/api/v1/businesses/{business_a}/data/summary").json()
    summary_b = client.get(f"/api/v1/businesses/{business_b}/data/summary").json()

    assert summary_a["products"] == 2
    assert summary_b["products"] == 0
    assert summary_b["sales"] == 0
