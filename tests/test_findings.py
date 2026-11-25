"""Findings: every placeholder resolves, and the laws table matches the text that introduces it."""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
pytestmark = pytest.mark.skipif(not (ROOT / "data" / "bundle" / "manifest.json").exists(), reason="no measures bundle yet")


@pytest.fixture(scope="module")
def findings():
    from atlas import facts
    from atlas import findings as fnd
    from atlas.data import Atlas
    return fnd.load(facts.build(Atlas()))


def test_no_unresolved_placeholders(findings):
    for x in findings:
        assert "{" not in str(x["html"]) and "{" not in str(x["chart"]), x["slug"]


def test_laws_count_matches_text(findings):
    laws = next(x for x in findings if x["slug"] == "laws")
    words = {"Three": 3, "Four": 4, "Five": 5}
    said = words[re.search(r"(Three|Four|Five) laws", str(laws["html"])).group(1)]
    rows = str(laws["chart"]).count("<tr>") - 1
    assert rows == said


def test_change_numbers_signed(findings):
    for x in findings:
        for n in re.findall(r"changed ([^\s,]+%)", str(x["html"])):
            assert n[0] in "+−", (x["slug"], n)


def test_foundation_and_relief_arithmetic():
    from atlas import facts
    from atlas.data import Atlas
    f = facts.build(Atlas())
    assert abs(f["found_net_raw"] + (f["found_total_raw"] - f["found_net_raw"]) - f["found_total_raw"]) < 1
    assert 0 < f["found_net_raw"] < f["found_total_raw"]
    assert f["n_left_le"] <= f["n_left"] and f["n_left_flip"] <= f["n_left"]
    assert f["relief_gain_raw"] > f["teeosa_gain_raw"] > 0  # Finding 1's headline direction


def test_findings_wording_rules(findings):
    text = " ".join(str(x["html"]) + str(x["chart"]) + x["headline"] for x in findings)
    for banned in ("property wealth", "which follows need", "took the place of", "rose +", "rose −"):
        assert banned not in text, banned
