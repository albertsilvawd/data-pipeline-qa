"""Reusable data quality checks, written in SQL.

Each check is a query that returns the rows that BREAK the rule.
Zero rows = check passed. The same pattern ports directly to BigQuery
(see sql/bigquery/), dbt tests or Great Expectations.
"""
import json
import sqlite3
from dataclasses import dataclass


@dataclass
class Check:
    name: str
    category: str
    sql: str  # returns violating rows


CHECKS = [
    # --- completeness -------------------------------------------------------
    Check("orders_required_fields_not_null", "completeness", """
        SELECT order_id FROM fct_orders
        WHERE order_id IS NULL OR customer_id IS NULL OR order_date IS NULL
           OR status IS NULL OR total_amount IS NULL"""),
    Check("customers_email_not_null", "completeness",
          "SELECT customer_id FROM dim_customers WHERE email IS NULL OR email = ''"),

    # --- uniqueness ---------------------------------------------------------
    Check("orders_primary_key_unique", "uniqueness",
          "SELECT order_id, COUNT(*) FROM fct_orders GROUP BY order_id HAVING COUNT(*) > 1"),
    Check("customers_primary_key_unique", "uniqueness",
          "SELECT customer_id, COUNT(*) FROM dim_customers GROUP BY customer_id HAVING COUNT(*) > 1"),
    Check("events_id_unique", "uniqueness",
          "SELECT event_id, COUNT(*) FROM fct_events GROUP BY event_id HAVING COUNT(*) > 1"),

    # --- referential integrity ---------------------------------------------
    Check("orders_customer_exists", "integrity", """
        SELECT o.order_id FROM fct_orders o
        LEFT JOIN dim_customers c ON c.customer_id = o.customer_id
        WHERE c.customer_id IS NULL"""),

    # --- validity / business rules -----------------------------------------
    Check("orders_status_accepted_values", "validity", """
        SELECT order_id, status FROM fct_orders
        WHERE status NOT IN ('completed', 'shipped', 'cancelled', 'returned')"""),
    Check("orders_quantity_positive", "validity",
          "SELECT order_id FROM fct_orders WHERE quantity <= 0"),
    Check("orders_total_equals_qty_x_price", "validity", """
        SELECT order_id, quantity, unit_price, total_amount FROM fct_orders
        WHERE ABS(total_amount - ROUND(quantity * unit_price, 2)) > 0.01"""),
    Check("orders_date_in_expected_range", "validity", """
        SELECT order_id, order_date FROM fct_orders
        WHERE order_date < '2026-01-01' OR order_date >= '2027-01-01'"""),
    Check("customers_email_lowercase_and_valid", "validity", """
        SELECT customer_id, email FROM dim_customers
        WHERE email <> LOWER(email) OR email NOT LIKE '%_@_%._%'"""),

    # --- reconciliation (source vs target) ---------------------------------
    Check("row_count_reconciliation", "reconciliation", """
        SELECT s.raw_orders, s.duplicates_removed, s.orders_loaded, s.orders_rejected
        FROM etl_run_stats s
        WHERE s.raw_orders <> s.duplicates_removed + s.orders_loaded + s.orders_rejected
           OR s.orders_loaded <> (SELECT COUNT(*) FROM fct_orders)"""),
    Check("amount_reconciliation", "reconciliation", """
        SELECT s.raw_total_amount, s.rejected_total_amount,
               (SELECT ROUND(SUM(total_amount), 2) FROM fct_orders) AS loaded_total
        FROM etl_run_stats s
        WHERE ABS(s.raw_total_amount - s.rejected_total_amount
                  - (SELECT SUM(total_amount) FROM fct_orders)) > 0.01"""),
    Check("events_count_reconciliation", "reconciliation", """
        SELECT s.raw_events, s.events_loaded, s.events_rejected FROM etl_run_stats s
        WHERE s.raw_events <> s.events_loaded + s.events_rejected
           OR s.events_loaded <> (SELECT COUNT(*) FROM fct_events)"""),

    # --- analytics / event validation --------------------------------------
    Check("purchase_event_matches_order", "events", """
        SELECT e.event_id, json_extract(e.properties, '$.order_id') AS order_id
        FROM fct_events e
        LEFT JOIN fct_orders o ON o.order_id = json_extract(e.properties, '$.order_id')
        WHERE e.event_name = 'purchase'
          AND (o.order_id IS NULL
               OR ABS(o.total_amount - json_extract(e.properties, '$.value')) > 0.01
               OR o.status = 'cancelled')"""),
    Check("purchase_event_user_matches_order_customer", "events", """
        SELECT e.event_id FROM fct_events e
        JOIN fct_orders o ON o.order_id = json_extract(e.properties, '$.order_id')
        WHERE e.event_name = 'purchase' AND e.user_id <> o.customer_id"""),
    Check("purchase_tracking_coverage_above_95pct", "events", """
        SELECT eligible, tracked FROM (
            SELECT (SELECT COUNT(*) FROM fct_orders WHERE status <> 'cancelled') AS eligible,
                   (SELECT COUNT(*) FROM fct_events WHERE event_name = 'purchase') AS tracked)
        WHERE tracked < 0.95 * eligible"""),
]


def run_check(conn: sqlite3.Connection, check: Check) -> list[tuple]:
    return conn.execute(check.sql).fetchall()


def run_all(conn: sqlite3.Connection) -> list[dict]:
    results = []
    for check in CHECKS:
        rows = run_check(conn, check)
        results.append({"name": check.name, "category": check.category,
                        "passed": not rows, "violations": len(rows), "sample": rows[:3]})
    return results


def write_report(results: list[dict], stats: dict, path) -> None:
    passed = sum(r["passed"] for r in results)
    lines = [
        "# Data Quality Report", "",
        f"**{passed}/{len(results)} checks passed**", "",
        "## ETL run", "", "| Metric | Value |", "|---|---|",
        *[f"| {k} | {v} |" for k, v in stats.items()], "",
        "## Checks", "", "| Category | Check | Result | Violations |", "|---|---|---|---|",
        *[f"| {r['category']} | {r['name']} | {'PASS' if r['passed'] else 'FAIL'} | {r['violations']} |"
          for r in results], "",
    ]
    path.write_text("\n".join(lines))


if __name__ == "__main__":
    import sys
    from pathlib import Path
    db = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/warehouse.db")
    with sqlite3.connect(db) as conn:
        res = run_all(conn)
        stats = dict(zip([d[0] for d in conn.execute("SELECT * FROM etl_run_stats").description],
                         conn.execute("SELECT * FROM etl_run_stats").fetchone()))
    out = Path("reports/data_quality_report.md")
    out.parent.mkdir(exist_ok=True)
    write_report(res, stats, out)
    print(json.dumps([{k: r[k] for k in ("name", "passed", "violations")} for r in res], indent=2))
    sys.exit(0 if all(r["passed"] for r in res) else 1)
