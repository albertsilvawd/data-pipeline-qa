"""Testing the tests: corrupt a copy of the warehouse on purpose and make sure
the matching quality check fails. A check that can never fail proves nothing."""
import pytest

from pipeline.quality import CHECKS, run_check

BY_NAME = {c.name: c for c in CHECKS}

DEFECTS = {
    "orders_primary_key_unique":
        "INSERT INTO fct_orders SELECT * FROM fct_orders LIMIT 1",
    "orders_customer_exists":
        "UPDATE fct_orders SET customer_id = 99999 WHERE rowid = 1",
    "orders_status_accepted_values":
        "UPDATE fct_orders SET status = 'COMPLETED ' WHERE rowid = 1",
    "orders_total_equals_qty_x_price":
        "UPDATE fct_orders SET total_amount = total_amount + 10 WHERE rowid = 1",
    "orders_date_in_expected_range":
        "UPDATE fct_orders SET order_date = '1970-01-01 00:00:00' WHERE rowid = 1",
    "orders_required_fields_not_null":
        "UPDATE fct_orders SET status = NULL WHERE rowid = 1",
    "customers_email_lowercase_and_valid":
        "UPDATE dim_customers SET email = 'NOT-AN-EMAIL' WHERE rowid = 1",
    "row_count_reconciliation":
        "DELETE FROM fct_orders WHERE rowid = 1",  # silent data loss
    "amount_reconciliation":
        "UPDATE fct_orders SET unit_price = unit_price * 2, total_amount = total_amount * 2 WHERE rowid = 1",
    "purchase_event_matches_order":
        "UPDATE fct_events SET properties = json_set(properties, '$.value', 0.01) "
        "WHERE event_name = 'purchase' AND rowid = (SELECT MIN(rowid) FROM fct_events WHERE event_name = 'purchase')",
    "purchase_tracking_coverage_above_95pct":
        "DELETE FROM fct_events WHERE event_name = 'purchase' AND rowid % 5 = 0",
}


@pytest.mark.parametrize("check_name,defect_sql", DEFECTS.items(), ids=DEFECTS.keys())
def test_check_catches_injected_defect(broken_conn, check_name, defect_sql):
    check = BY_NAME[check_name]
    assert run_check(broken_conn, check) == [], "warehouse must be clean before the defect"
    broken_conn.execute(defect_sql)
    assert run_check(broken_conn, check) != [], f"{check_name} did not detect the defect"
