#!/usr/bin/env bash
# End-to-end run: generate data -> ETL -> tests -> quality report.
# Exits non-zero if any test or quality check fails, so it can gate a pipeline.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> 1/4 Generating raw data"
python scripts/generate_data.py data/raw --seed "${SEED:-42}"

echo "==> 2/4 Running ETL"
python -m pipeline.etl data/raw data/warehouse.db

echo "==> 3/4 Running automated tests"
python -m pytest -q

echo "==> 4/4 Writing data quality report"
python -m pipeline.quality data/warehouse.db > /dev/null
echo "Report: reports/data_quality_report.md"
