"""Column suggestions: the field's own name and earlier aliases beat later ones, a column is never mapped to two fields, and a sales file that only
has a product NAME still links its rows to a product."""
from app.services.canonical_schema import CANONICAL_TYPES
from app.services.column_mapping import suggest_mapping

SALES = CANONICAL_TYPES["sales"]


def test_a_product_id_beats_a_product_name_whatever_the_column_order():
    m = suggest_mapping(["Order Date", "Product Name", "Product ID", "Quantity", "Unit Price"], SALES)
    assert m.column_to_field["Product ID"] == "external_product_id" and "Product Name" not in m.column_to_field
    m = suggest_mapping(["Product ID", "Product Name", "Order Date", "Quantity", "Unit Price"], SALES)
    assert m.column_to_field["Product ID"] == "external_product_id" and "Product Name" not in m.column_to_field


def test_a_product_name_alone_is_used_for_the_sales_product_link():
    m = suggest_mapping(["Order Date", "Product Name", "Quantity", "Unit Price"], SALES)
    assert m.column_to_field["Product Name"] == "external_product_id" and not m.unmapped_required_fields


def test_one_column_is_never_mapped_to_two_fields():
    m = suggest_mapping(["Date", "Qty", "Price", "Product"], SALES)
    assert len(set(m.column_to_field)) == len(m.column_to_field)
    assert sorted(m.column_to_field.values()) == sorted(set(m.column_to_field.values()))


def test_a_product_file_still_maps_its_name_column_to_name():
    m = suggest_mapping(["Product ID", "Product Name", "Category", "Unit Cost", "Selling Price"], CANONICAL_TYPES["products"])
    assert m.column_to_field["Product Name"] == "name" and m.column_to_field["Product ID"] == "external_product_id"
