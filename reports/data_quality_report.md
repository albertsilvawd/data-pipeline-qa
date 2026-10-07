# Data Quality Report

**17/17 checks passed**

## ETL run

| Metric | Value |
|---|---|
| raw_orders | 1020 |
| duplicates_removed | 20 |
| orders_loaded | 974 |
| orders_rejected | 26 |
| raw_events | 2834 |
| events_loaded | 2814 |
| events_rejected | 20 |
| raw_total_amount | 457417.12 |
| rejected_total_amount | 9491.94 |

## Checks

| Category | Check | Result | Violations |
|---|---|---|---|
| completeness | orders_required_fields_not_null | PASS | 0 |
| completeness | customers_email_not_null | PASS | 0 |
| uniqueness | orders_primary_key_unique | PASS | 0 |
| uniqueness | customers_primary_key_unique | PASS | 0 |
| uniqueness | events_id_unique | PASS | 0 |
| integrity | orders_customer_exists | PASS | 0 |
| validity | orders_status_accepted_values | PASS | 0 |
| validity | orders_quantity_positive | PASS | 0 |
| validity | orders_total_equals_qty_x_price | PASS | 0 |
| validity | orders_date_in_expected_range | PASS | 0 |
| validity | customers_email_lowercase_and_valid | PASS | 0 |
| reconciliation | row_count_reconciliation | PASS | 0 |
| reconciliation | amount_reconciliation | PASS | 0 |
| reconciliation | events_count_reconciliation | PASS | 0 |
| events | purchase_event_matches_order | PASS | 0 |
| events | purchase_event_user_matches_order_customer | PASS | 0 |
| events | purchase_tracking_coverage_above_95pct | PASS | 0 |
