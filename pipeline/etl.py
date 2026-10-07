"""ETL: raw CSV/JSONL files -> SQLite warehouse.

Extract  : read customers.csv, orders.csv and events.jsonl
Transform: normalize formats, remove duplicates, validate against rules
Load     : write clean tables plus a `rejected_records` quarantine table

Every input row ends up in exactly one place (loaded, removed as duplicate,
or rejected with a reason), so the tests can reconcile source and target.
"""
import json
import sqlite3
from pathlib import Path

import pandas as pd
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
TRACKING_PLAN = ROOT / "contracts" / "tracking_plan.json"
VALID_STATUSES = {"completed", "shipped", "cancelled", "returned"}


def extract(raw_dir: Path) -> dict:
    events = [json.loads(line) for line in open(raw_dir / "events.jsonl")]
    return {
        "customers": pd.read_csv(raw_dir / "customers.csv"),
        "orders": pd.read_csv(raw_dir / "orders.csv", dtype={"unit_price": str, "total_amount": str}),
        "events": events,
    }


def _parse_dates(series: pd.Series) -> pd.Series:
    iso = pd.to_datetime(series, format="%Y-%m-%d %H:%M", errors="coerce")
    latam = pd.to_datetime(series, format="%d/%m/%Y %H:%M", errors="coerce")
    return iso.fillna(latam)


def transform_customers(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["email"] = df["email"].str.strip().str.lower()
    df["created_at"] = pd.to_datetime(df["created_at"]).dt.strftime("%Y-%m-%d")
    return df.drop_duplicates(subset="customer_id")


def transform_orders(df: pd.DataFrame, customer_ids: set) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    """Return (clean_orders, rejected_orders, duplicates_removed)."""
    before = len(df)
    df = df.drop_duplicates()
    duplicates_removed = before - len(df)

    df = df.copy()
    df["status"] = df["status"].str.strip().str.lower()
    df["order_date"] = _parse_dates(df["order_date"])
    df["unit_price"] = df["unit_price"].astype(float)
    df["total_amount"] = df["total_amount"].astype(float)

    reasons = pd.Series("", index=df.index)
    reasons[~df["customer_id"].isin(customer_ids)] = "orphan_customer"
    reasons[(reasons == "") & (df["quantity"] <= 0)] = "invalid_quantity"
    reasons[(reasons == "") & df["order_date"].isna()] = "unparseable_date"
    reasons[(reasons == "") & ~df["status"].isin(VALID_STATUSES)] = "unknown_status"

    rejected = df[reasons != ""].assign(reason=reasons[reasons != ""])
    clean = df[reasons == ""].copy()
    clean["order_date"] = clean["order_date"].dt.strftime("%Y-%m-%d %H:%M:%S")
    return clean, rejected, duplicates_removed


def event_validators(plan_path: Path = TRACKING_PLAN):
    plan = json.loads(plan_path.read_text())
    envelope = Draft202012Validator(plan["envelope"])
    per_event = {name: Draft202012Validator(schema) for name, schema in plan["events"].items()}
    return envelope, per_event


def validate_event(event: dict, envelope, per_event) -> list[str]:
    """Return a list of contract violations (empty list = valid event)."""
    errors = [e.message for e in envelope.iter_errors(event)]
    if not errors:
        errors += [e.message for e in per_event[event["event_name"]].iter_errors(event["properties"])]
    return errors


def transform_events(events: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    envelope, per_event = event_validators()
    valid, rejected = [], []
    for e in events:
        errors = validate_event(e, envelope, per_event)
        row = {**{k: e.get(k) for k in ("event_id", "event_name", "user_id", "timestamp")},
               "properties": json.dumps(e.get("properties", {}))}
        if errors:
            rejected.append({**row, "reason": "; ".join(errors)})
        else:
            valid.append(row)
    return pd.DataFrame(valid), pd.DataFrame(rejected)


def load(conn: sqlite3.Connection, customers, orders, events, rejected_orders, rejected_events, stats: dict):
    customers.to_sql("dim_customers", conn, index=False, if_exists="replace")
    orders.to_sql("fct_orders", conn, index=False, if_exists="replace")
    events.to_sql("fct_events", conn, index=False, if_exists="replace")

    quarantine = pd.concat([
        pd.DataFrame({"source": "orders", "record_id": rejected_orders["order_id"].astype(str),
                      "reason": rejected_orders["reason"]}),
        pd.DataFrame({"source": "events", "record_id": rejected_events.get("event_id", pd.Series(dtype=str)),
                      "reason": rejected_events.get("reason", pd.Series(dtype=str))}),
    ], ignore_index=True)
    quarantine.to_sql("rejected_records", conn, index=False, if_exists="replace")

    pd.DataFrame([stats]).to_sql("etl_run_stats", conn, index=False, if_exists="replace")
    conn.commit()


def run(raw_dir: Path, db_path: Path) -> dict:
    raw = extract(raw_dir)
    customers = transform_customers(raw["customers"])
    orders, rejected_orders, dupes = transform_orders(raw["orders"], set(customers["customer_id"]))
    events, rejected_events = transform_events(raw["events"])

    stats = {
        "raw_orders": len(raw["orders"]),
        "duplicates_removed": dupes,
        "orders_loaded": len(orders),
        "orders_rejected": len(rejected_orders),
        "raw_events": len(raw["events"]),
        "events_loaded": len(events),
        "events_rejected": len(rejected_events),
        "raw_total_amount": round(float(raw["orders"].drop_duplicates()["total_amount"].astype(float).sum()), 2),
        "rejected_total_amount": round(float(rejected_orders["total_amount"].sum()), 2),
    }
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        load(conn, customers, orders, events, rejected_orders, rejected_events, stats)
    return stats


if __name__ == "__main__":
    import sys
    raw = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "raw"
    db = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "data" / "warehouse.db"
    print(json.dumps(run(raw, db), indent=2))
