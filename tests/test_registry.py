"""Registry and token checks. A failure here stops the build before anything publishes."""
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BINS = {"howmuch6": 6, "howmuch7": 7, "change7": 7}


def rows():
    with open(ROOT / "registry" / "indicators.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_keys_unique_per_level():
    seen = [(r["key"], r["level"]) for r in rows()]
    assert len(seen) == len(set(seen))


def test_key_eight_per_level():
    for level in ("county", "system"):
        orders = sorted(int(r["key_order"]) for r in rows() if r["level"] == level and r["key_indicator"] == "yes")
        assert orders == list(range(1, 9)), level


def test_bins_match_ramp():
    for r in rows():
        if r["ramp"] in BINS:
            n = len(r["breaks"].split("|")) + 1
            assert n == BINS[r["ramp"]], f'{r["key"]}: {n} bins on {r["ramp"]}'
            assert len(r["legend"].split("|")) == n, f'{r["key"]}: legend count'


def test_every_row_has_label_and_source():
    for r in rows():
        assert r["label"].strip() and r["source"].strip(), r["key"]


def test_tokens_define_every_ramp_step():
    css = (ROOT / "design" / "tokens.css").read_text()
    for ramp, n in BINS.items():
        for i in range(1, n + 1):
            assert re.search(rf"--{ramp.replace('change7', 'change')}-{i}:", css), f"{ramp} step {i}"


def test_crosswalk_counts():
    with open(ROOT / "registry" / "crosswalk_systems.csv", encoding="utf-8") as f:
        assert sum(1 for _ in f) - 1 == 244
    with open(ROOT / "registry" / "crosswalk_counties.csv", encoding="utf-8") as f:
        assert sum(1 for _ in f) - 1 == 93
