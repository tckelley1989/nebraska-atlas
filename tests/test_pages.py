"""Build the site from the bundle and check the pages: counts, known values, no leaked blanks."""
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "_site"

pytestmark = pytest.mark.skipif(not (ROOT / "data" / "bundle" / "manifest.json").exists(), reason="no measures bundle yet")


@pytest.fixture(scope="module", autouse=True)
def built():
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build.py")], check=True, capture_output=True)


def test_page_counts():
    assert len(list((SITE / "system").glob("*.html"))) == 244
    assert len(list((SITE / "county").glob("*.html"))) == 93
    for p in ("index.html", "schools.html", "counties.html"):
        assert (SITE / p).exists(), p


def test_no_leaked_blanks():
    bad = re.compile(r">\s*(None|nan|NaN|undefined)\s*<")
    for p in SITE.rglob("*.html"):
        assert not bad.search(p.read_text(encoding="utf-8")), p.name


def test_formula_identity_on_every_system_page():
    """Equalization aid shown equals formula need minus total resources, floored at zero."""
    for p in (SITE / "system").glob("*.html"):
        t = p.read_text(encoding="utf-8")
        cells = dict(re.findall(r"<td>(Formula need|Total resources|Equalization aid: need minus resources, if positive)</td><td class=\"num\">\$([\d,]+)</td>", t))
        need, res, eq = (int(cells[k].replace(",", "")) for k in ("Formula need", "Total resources", "Equalization aid: need minus resources, if positive"))
        assert eq == max(0, need - res), p.name


def test_draft_guards_on():
    assert (SITE / "robots.txt").read_text().startswith("User-agent: *\nDisallow: /")
    assert 'name="robots" content="noindex' in (SITE / "system" / "24-0001.html").read_text()


def test_change_numbers_carry_signs():
    """Methods spec 8.3: tiles in up/down color always start with + or minus."""
    for p in list((SITE / "county").glob("*.html"))[:20]:
        for v in re.findall(r'<p class="big (?:up|down)">([^<]+)</p>', p.read_text(encoding="utf-8")):
            assert v[0] in "+−", (p.name, v)


def test_key_eight_cover_most_places():
    """A key measure that goes mostly blank (as NSCAS did with NDE's 2025-26 release) fails the build."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from atlas.data import Atlas
    a = Atlas()
    for level, n in (("system", 244), ("county", 93)):
        for r in a.key_eight(level):
            have = sum(1 for p in a.places(level) if a.value(level, p, r["key"]) is not None)
            assert have >= 0.8 * n, (level, r["key"], have)


def test_big_changes_show_the_multiple():
    """Methods spec 8.5: at three times the base or more, the multiple, never a four-digit percent."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from atlas import fmt
    assert fmt.pct_change(199.94) == "+199.9%" and fmt.pct_change(200) == "3.0 times" and fmt.pct_change(-60) == "−60.0%"
    big = re.compile(r"\+(\d[\d,]*\.\d)%")
    for p in list((SITE / "system").glob("*.html")) + list((SITE / "county").glob("*.html")) + [SITE / "index.html"]:
        for m in big.findall(p.read_text(encoding="utf-8")):
            assert float(m.replace(",", "")) < 200, (p.name, m)


def test_tier_changes_sum_counts_first():
    """Methods spec 1.1: a tier's change is its counties' summed levels, never an average of county rates."""
    import csv
    sys.path.insert(0, str(ROOT / "scripts"))
    from atlas.data import Atlas
    a = Atlas()
    lv = {}
    for r in csv.DictReader(open(ROOT / "data" / "bundle" / "county_levels.csv", encoding="utf-8")):
        if r["base_year"] == "2019" and r["id"].isdigit() and r["id"] != "31000":
            lv.setdefault(r["indicator"], {})[r["id"]] = (float(r["base_level"]), float(r["current_level"]))
    tier = {f: c["tier"] for f, c in a.counties_xw.items()}
    for ind in ("pop_change", "jobs_change", "ptax_real_change", "ptax_net_real_change", "sales_real_change"):
        for t in ("metro", "micro", "rural", "state"):
            fs = [f for f in lv[ind] if t == "state" or tier[f] == t]
            want = 100 * (sum(lv[ind][f][1] for f in fs) / sum(lv[ind][f][0] for f in fs) - 1)
            shown = a.county_js["tiers"][t]["d"][ind]
            assert shown == fmt_change(want), (ind, t, shown, want)


def fmt_change(x):
    sys.path.insert(0, str(ROOT / "scripts"))
    from atlas import fmt
    return fmt.signed(x, 1, "%")
