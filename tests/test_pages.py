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
