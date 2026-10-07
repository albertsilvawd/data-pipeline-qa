"""Run every SQL data quality check against the warehouse built by the ETL."""
import pytest

from pipeline.quality import CHECKS, run_check


@pytest.mark.parametrize("check", CHECKS, ids=[c.name for c in CHECKS])
def test_quality_check_passes(conn, check):
    violations = run_check(conn, check)
    assert violations == [], f"{check.name}: {len(violations)} violating rows, e.g. {violations[:3]}"
