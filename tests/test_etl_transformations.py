"""Unit tests for the transformation rules, using small hand-made inputs."""
import pandas as pd

from pipeline import etl


def make_orders(rows):
    cols = ["order_id", "customer_id", "order_date", "status", "quantity", "unit_price", "total_amount"]
    return pd.DataFrame(rows, columns=cols)


def test_exact_duplicates_are_removed_and_counted():
    row = [1, 10, "2026-03-01 10:00", "completed", 2, "5.00", "10.00"]
    clean, rejected, dupes = etl.transform_orders(make_orders([row, row]), customer_ids={10})
    assert len(clean) == 1 and dupes == 1 and rejected.empty


def test_status_is_trimmed_and_lowercased():
    df = make_orders([[1, 10, "2026-03-01 10:00", "  SHIPPED ", 1, "5.00", "5.00"]])
    clean, _, _ = etl.transform_orders(df, customer_ids={10})
    assert clean.iloc[0]["status"] == "shipped"


def test_both_source_date_formats_are_parsed():
    df = make_orders([
        [1, 10, "2026-03-01 10:00", "completed", 1, "5.00", "5.00"],
        [2, 10, "01/03/2026 10:00", "completed", 1, "5.00", "5.00"],  # dd/mm/yyyy
    ])
    clean, _, _ = etl.transform_orders(df, customer_ids={10})
    assert list(clean["order_date"]) == ["2026-03-01 10:00:00", "2026-03-01 10:00:00"]


def test_invalid_rows_are_quarantined_with_a_reason():
    df = make_orders([
        [1, 99, "2026-03-01 10:00", "completed", 1, "5.00", "5.00"],   # customer 99 does not exist
        [2, 10, "2026-03-01 10:00", "completed", 0, "5.00", "0.00"],   # zero quantity
        [3, 10, "not a date", "completed", 1, "5.00", "5.00"],
        [4, 10, "2026-03-01 10:00", "lost", 1, "5.00", "5.00"],
    ])
    clean, rejected, _ = etl.transform_orders(df, customer_ids={10})
    assert clean.empty
    assert dict(zip(rejected["order_id"], rejected["reason"])) == {
        1: "orphan_customer", 2: "invalid_quantity", 3: "unparseable_date", 4: "unknown_status"}


def test_customer_emails_are_normalized():
    df = pd.DataFrame([{"customer_id": 1, "email": " Ana@Example.COM ", "country": "AR",
                        "created_at": "2025-05-01"}])
    assert etl.transform_customers(df).iloc[0]["email"] == "ana@example.com"


def test_every_raw_row_is_accounted_for(pipeline_run):
    s = pipeline_run["stats"]
    assert s["raw_orders"] == s["duplicates_removed"] + s["orders_loaded"] + s["orders_rejected"]
    assert s["orders_rejected"] > 0, "the generated data contains bad rows, so some must be rejected"
