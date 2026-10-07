import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from generate_data import generate  # noqa: E402
from pipeline import etl  # noqa: E402


@pytest.fixture(scope="session")
def pipeline_run(tmp_path_factory):
    """Generate raw data and run the ETL once for the whole test session."""
    base = tmp_path_factory.mktemp("pipeline")
    raw_dir, db_path = base / "raw", base / "warehouse.db"
    generate(raw_dir, seed=42)
    stats = etl.run(raw_dir, db_path)
    return {"raw_dir": raw_dir, "db_path": db_path, "stats": stats}


@pytest.fixture(scope="session")
def conn(pipeline_run):
    connection = sqlite3.connect(pipeline_run["db_path"])
    yield connection
    connection.close()


@pytest.fixture
def broken_conn(pipeline_run, tmp_path):
    """A disposable copy of the warehouse that a test can corrupt on purpose."""
    copy = tmp_path / "broken.db"
    shutil.copy(pipeline_run["db_path"], copy)
    connection = sqlite3.connect(copy)
    yield connection
    connection.close()
