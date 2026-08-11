from datetime import date, timedelta

import pandas as pd

from app.services import model_registry_service
from tests.integration.test_analytics import _create_business, _seed_rich_business, _upload_csv


def test_build_requires_sufficient_history(client):
    business_id = _create_business(client)
    response = client.post(f"/api/v1/businesses/{business_id}/causal-graph/build")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INSUFFICIENT_DATA"


def test_get_before_build_is_insufficient_data(client):
    business_id = _create_business(client)
    response = client.get(f"/api/v1/businesses/{business_id}/causal-graph")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INSUFFICIENT_DATA"


def test_build_produces_all_hypothesis_edges_honestly_labeled(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    business_id = _create_business(client)
    _seed_rich_business(client, business_id)

    response = client.post(f"/api/v1/businesses/{business_id}/causal-graph/build")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["version"] == "v1"
    assert "granger" in body["method"]
    assert len(body["edges"]) == 13

    valid_evidence_types = {"assumed", "observational", "data_supported", "causally_validated"}
    for edge in body["edges"]:
        assert edge["evidence_type"] in valid_evidence_types
        # Never fabricated: CAUSALLY_VALIDATED must never be auto-assigned.
        assert edge["evidence_type"] != "causally_validated"
        if edge["evidence_type"] == "assumed":
            assert edge["strength"] is None or edge["confidence"] is None

    # Nodes that are never collected anywhere in our schema must always stay assumed.
    untested_nodes = {"website_traffic", "conversion_rate", "customer_experience", "retention", "repeat_purchases"}
    for edge in body["edges"]:
        if edge["source_node"] in untested_nodes or edge["target_node"] in untested_nodes:
            assert edge["evidence_type"] == "assumed"

    # demand -> sales is the same measured quantity in our schema; must stay untested.
    demand_sales = next(e for e in body["edges"] if e["source_node"] == "demand" and e["target_node"] == "sales")
    assert demand_sales["evidence_type"] == "assumed"

    # _seed_rich_business puts exactly 2 sales/day, every day — "orders" has
    # zero variance, so it's honestly untestable (not a bug: you can't
    # correlate a constant with anything).
    orders_revenue = next(e for e in body["edges"] if e["source_node"] == "orders" and e["target_node"] == "revenue")
    assert orders_revenue["evidence_type"] == "assumed"
    assert "variation" in orders_revenue["note"] or "overlapping" in orders_revenue["note"]


def test_orders_revenue_edge_detects_real_relationship_when_orders_vary(client, db_session):
    """_seed_rich_business fixes orders at exactly 2/day, so that edge is
    always untestable there. Seed varying daily order counts here and check
    the graph actually recovers the relationship from real variation."""
    model_registry_service.sync_from_file_registry(db_session)
    business_id = _create_business(client)

    products = pd.DataFrame([{"Product ID": "P000", "Product Name": "Item", "Selling Price": 500}])
    _upload_csv(client, business_id, "products", products)

    today = date.today()
    start = today - timedelta(days=90)
    sales_rows = []
    for day_offset in range(90):
        sale_date = start + timedelta(days=day_offset)
        orders_today = 1 + (day_offset % 5)  # varies 1..5 orders/day
        for order_idx in range(orders_today):
            sales_rows.append(
                {
                    "Order Date": sale_date.isoformat(),
                    "Customer ID": f"C{(day_offset * 5 + order_idx) % 40:03d}",
                    "Product ID": "P000",
                    "Quantity": 1,
                    "Unit Price": 500,
                    "Discount": 0,
                }
            )
    _upload_csv(client, business_id, "sales", pd.DataFrame(sales_rows))

    response = client.post(f"/api/v1/businesses/{business_id}/causal-graph/build")
    assert response.status_code == 200, response.text
    edges = response.json()["edges"]
    orders_revenue = next(e for e in edges if e["source_node"] == "orders" and e["target_node"] == "revenue")
    assert orders_revenue["evidence_type"] in {"observational", "data_supported"}
    assert orders_revenue["relationship"] == "positive"


def test_build_increments_version_and_get_returns_latest(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    business_id = _create_business(client)
    _seed_rich_business(client, business_id)

    first = client.post(f"/api/v1/businesses/{business_id}/causal-graph/build").json()
    assert first["version"] == "v1"

    second = client.post(f"/api/v1/businesses/{business_id}/causal-graph/build").json()
    assert second["version"] == "v2"

    latest = client.get(f"/api/v1/businesses/{business_id}/causal-graph").json()
    assert latest["id"] == second["id"]
    assert latest["version"] == "v2"
    assert len(latest["edges"]) == 13


def test_price_demand_edge_detects_real_negative_elasticity(client, db_session):
    """Seed a business where higher price genuinely coincides with lower
    units sold, and check the graph actually recovers that direction from
    the data rather than just asserting the hypothesis."""
    model_registry_service.sync_from_file_registry(db_session)
    business_id = _create_business(client)

    products = pd.DataFrame([{"Product ID": "P000", "Product Name": "Item", "Selling Price": 500}])
    _upload_csv(client, business_id, "products", products)

    today = date.today()
    start = today - timedelta(days=90)
    sales_rows = []
    for day_offset in range(90):
        sale_date = start + timedelta(days=day_offset)
        # Price oscillates; quantity moves opposite to price plus small noise pattern.
        high_price_day = day_offset % 4 == 0
        price = 800 if high_price_day else 400
        quantity = 1 if high_price_day else 5
        sales_rows.append(
            {
                "Order Date": sale_date.isoformat(),
                "Customer ID": f"C{day_offset % 20:03d}",
                "Product ID": "P000",
                "Quantity": quantity,
                "Unit Price": price,
                "Discount": 0,
            }
        )
    _upload_csv(client, business_id, "sales", pd.DataFrame(sales_rows))

    response = client.post(f"/api/v1/businesses/{business_id}/causal-graph/build")
    assert response.status_code == 200, response.text
    edges = response.json()["edges"]
    price_demand = next(e for e in edges if e["source_node"] == "price" and e["target_node"] == "demand")
    assert price_demand["evidence_type"] in {"observational", "data_supported"}
    assert price_demand["relationship"] == "negative"


def test_causal_graph_is_isolated_per_business(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    business_a = _create_business(client)
    _seed_rich_business(client, business_a)
    client.post(f"/api/v1/businesses/{business_a}/causal-graph/build")

    business_b = _create_business(client)
    response = client.get(f"/api/v1/businesses/{business_b}/causal-graph")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INSUFFICIENT_DATA"
