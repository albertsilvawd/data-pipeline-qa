"""Generate a synthetic e-commerce dataset with realistic data problems.

The raw files intentionally contain issues a real source system produces:
duplicate rows, inconsistent formats, orphan records and malformed events.
The ETL must clean or quarantine them, and the tests prove it did.

Usage: python scripts/generate_data.py [output_dir] [--seed 42]
"""
import argparse
import csv
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

COUNTRIES = ["AR", "BR", "CL", "UY", "PY", "EC", "US"]
STATUSES = ["completed", "shipped", "cancelled", "returned"]


def generate(out_dir: Path, seed: int = 42, n_customers: int = 200, n_orders: int = 1000) -> dict:
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    start = datetime(2026, 1, 1)

    # --- customers -------------------------------------------------------
    customers = []
    for i in range(1, n_customers + 1):
        email = f"customer{i}@example.com"
        if rng.random() < 0.05:
            email = email.upper()  # inconsistent casing, ETL lowercases it
        customers.append({
            "customer_id": i,
            "email": email,
            "country": rng.choice(COUNTRIES),
            "created_at": (start - timedelta(days=rng.randint(1, 365))).strftime("%Y-%m-%d"),
        })

    # --- orders ----------------------------------------------------------
    orders = []
    for i in range(1, n_orders + 1):
        customer_id = rng.randint(1, n_customers)
        if rng.random() < 0.02:
            customer_id = n_customers + rng.randint(1, 50)  # orphan: customer does not exist
        quantity = rng.randint(1, 5)
        if rng.random() < 0.01:
            quantity = 0  # invalid quantity
        unit_price = round(rng.uniform(5, 300), 2)
        order_date = start + timedelta(days=rng.randint(0, 270), minutes=rng.randint(0, 1439))
        # two date formats coming from two source systems
        date_str = order_date.strftime("%Y-%m-%d %H:%M") if rng.random() < 0.8 else order_date.strftime("%d/%m/%Y %H:%M")
        status = rng.choices(STATUSES, weights=[60, 25, 10, 5])[0]
        if rng.random() < 0.1:
            status = f"  {status.upper()} "  # messy casing and whitespace
        orders.append({
            "order_id": i,
            "customer_id": customer_id,
            "order_date": date_str,
            "status": status,
            "quantity": quantity,
            "unit_price": f"{unit_price:.2f}",
            "total_amount": f"{quantity * unit_price:.2f}",
        })
    # exact duplicate rows, as produced by a source that re-sends records
    duplicates = rng.sample(orders, k=int(n_orders * 0.02))
    raw_orders = orders + duplicates
    rng.shuffle(raw_orders)

    # --- analytics events --------------------------------------------------
    events = []
    event_seq = 0

    def add_event(name, user_id, ts, props):
        nonlocal event_seq
        event_seq += 1
        events.append({
            "event_id": f"evt_{event_seq:06d}",
            "event_name": name,
            "user_id": user_id,
            "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "properties": props,
        })

    for o in orders:
        if o["customer_id"] > n_customers or o["quantity"] == 0:
            continue  # invalid orders never reached checkout
        clean_status = o["status"].strip().lower()
        ts = datetime.strptime(o["order_date"], "%Y-%m-%d %H:%M") if "-" in o["order_date"] \
            else datetime.strptime(o["order_date"], "%d/%m/%Y %H:%M")
        add_event("page_view", o["customer_id"], ts - timedelta(minutes=5), {"page": "/product"})
        cart = {"product_id": f"P{rng.randint(1, 80):03d}", "quantity": o["quantity"]}
        if rng.random() < 0.01:
            cart["quantity"] = str(o["quantity"])  # wrong type: tracking bug
        add_event("add_to_cart", o["customer_id"], ts - timedelta(minutes=2), cart)
        if clean_status != "cancelled":
            purchase = {"order_id": o["order_id"], "value": float(o["total_amount"]), "currency": "USD"}
            if rng.random() < 0.01:
                del purchase["value"]  # missing required property
            add_event("purchase", o["customer_id"], ts, purchase)

    # --- write files ---------------------------------------------------------
    with open(out_dir / "customers.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=customers[0].keys())
        w.writeheader()
        w.writerows(customers)
    with open(out_dir / "orders.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=raw_orders[0].keys())
        w.writeheader()
        w.writerows(raw_orders)
    with open(out_dir / "events.jsonl", "w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")

    return {"customers": len(customers), "orders": len(raw_orders), "events": len(events)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir", nargs="?", default="data/raw")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    counts = generate(Path(args.output_dir), seed=args.seed)
    print(f"Generated raw data in {args.output_dir}: {counts}")
