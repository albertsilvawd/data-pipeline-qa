"""Analytics event validation against the tracking plan (contracts/tracking_plan.json)."""
import pytest

from pipeline.etl import event_validators, validate_event

ENVELOPE, PER_EVENT = event_validators()


def event(name, props, **overrides):
    base = {"event_id": "evt_000001", "event_name": name, "user_id": 7,
            "timestamp": "2026-03-01T10:00:00Z", "properties": props}
    return {**base, **overrides}


VALID = [
    event("page_view", {"page": "/product"}),
    event("add_to_cart", {"product_id": "P001", "quantity": 2}),
    event("purchase", {"order_id": 15, "value": 49.9, "currency": "USD"}),
]

INVALID = {
    "purchase without value": event("purchase", {"order_id": 15, "currency": "USD"}),
    "quantity sent as string": event("add_to_cart", {"product_id": "P001", "quantity": "2"}),
    "negative purchase value": event("purchase", {"order_id": 15, "value": -1, "currency": "USD"}),
    "unexpected currency": event("purchase", {"order_id": 15, "value": 10, "currency": "BRL"}),
    "event not in tracking plan": event("checkout_started", {}),
    "malformed timestamp": event("page_view", {"page": "/"}, timestamp="01/03/2026"),
    "missing user_id": {k: v for k, v in event("page_view", {"page": "/"}).items() if k != "user_id"},
}


@pytest.mark.parametrize("evt", VALID, ids=[e["event_name"] for e in VALID])
def test_valid_events_pass_the_contract(evt):
    assert validate_event(evt, ENVELOPE, PER_EVENT) == []


@pytest.mark.parametrize("evt", INVALID.values(), ids=INVALID.keys())
def test_invalid_events_are_caught(evt):
    assert validate_event(evt, ENVELOPE, PER_EVENT) != []


def test_bad_events_in_source_were_quarantined(conn):
    rejected = conn.execute("SELECT COUNT(*) FROM rejected_records WHERE source = 'events'").fetchone()[0]
    assert rejected > 0, "the source contains tracking bugs, so some events must be rejected"
