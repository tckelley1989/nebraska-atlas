"""When a measures bundle is present, every registry key must exist in it, and the manifest must match the files."""
import csv
import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "data" / "bundle"
FILES = {"county": "counties.csv", "system": ("school_systems.csv", "school_outcomes.csv", "school_revenue.csv", "lc2_budgets.csv")}

pytestmark = pytest.mark.skipif(not (BUNDLE / "manifest.json").exists(), reason="no measures bundle yet")


def test_manifest_matches_files():
    m = json.loads((BUNDLE / "manifest.json").read_text())
    for name, meta in m["files"].items():
        data = (BUNDLE / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == meta["sha256"], name


def test_county_keys_in_bundle():
    with open(BUNDLE / FILES["county"], newline="", encoding="utf-8") as f:
        header = next(csv.reader(f))
    with open(ROOT / "registry" / "indicators.csv", newline="", encoding="utf-8") as f:
        keys = [r["key"] for r in csv.DictReader(f) if r["level"] == "county"]
    missing = [k for k in keys if k not in header]
    assert not missing, f"county keys not in {FILES['county']}: {missing}"
