"""About page, downloads, search index, definitions and the PDF step."""
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "_site"
BUNDLE = ROOT / "data" / "bundle"
sys.path.insert(0, str(ROOT / "scripts"))

pytestmark = pytest.mark.skipif(not (BUNDLE / "manifest.json").exists(), reason="no measures bundle yet")


@pytest.fixture(scope="module", autouse=True)
def built():
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build.py")], check=True, capture_output=True)


def registry():
    return list(csv.DictReader(open(ROOT / "registry" / "indicators.csv", encoding="utf-8")))


def test_every_bundle_csv_is_described_and_published():
    from atlas import about
    assert set(about.FILES) == {p.name for p in BUNDLE.glob("*.csv")}
    html = (SITE / "about.html").read_text(encoding="utf-8")
    for name in about.FILES:
        assert (SITE / "data" / name).read_bytes() == (BUNDLE / name).read_bytes(), name
        assert f'data/{name}"' in html, name
    assert (SITE / "data" / "manifest.json").exists()


def test_about_lists_every_measure_once():
    html = (SITE / "about.html").read_text(encoding="utf-8")
    for r in registry():
        assert html.count(f'id="m-{r["level"]}-{r["key"]}"') == 1, r["key"]


def test_methods_render_without_internal_notes():
    html = (SITE / "about.html").read_text(encoding="utf-8")
    assert "Open items" not in html and "```" not in html and "Write the rule here" not in html
    for n in range(1, 10):
        assert re.search(rf'<h3 class="mh">{n}\. ', html), n


def test_profile_csvs_cover_the_registry():
    reg = registry()
    for level, code, name in (("system", "24-0001", "Lexington"), ("county", "31047", "Dawson")):
        rows = list(csv.DictReader(open(SITE / level / f"{code}.csv", encoding="utf-8-sig")))
        assert len(rows) == sum(1 for r in reg if r["level"] == level)
        assert all(name in r["place"] for r in rows)
    lex = {r["measure"]: r for r in csv.DictReader(open(SITE / "system" / "24-0001.csv", encoding="utf-8-sig"))}
    assert round(float(lex["aid_ps"]["value"])) == 9229
    assert len(list((SITE / "system").glob("*.csv"))) == 244
    assert len(list((SITE / "county").glob("*.csv"))) == 93


def test_search_index_covers_every_place():
    js = (SITE / "assets" / "search-index.js").read_text(encoding="utf-8")
    idx = json.loads(js[len("window.LEDGER_SEARCH="):-1])
    kinds = {}
    for e in idx:
        kinds[e["k"]] = kinds.get(e["k"], 0) + 1
        assert (SITE / e["u"].split("#")[0]).exists(), e
    assert kinds["School system"] == 244 and kinds["County"] == 93 and kinds["Town"] > 400


def test_definition_ids_are_unique_and_complete():
    for p in (SITE / "system" / "24-0001.html", SITE / "county" / "31047.html"):
        html = p.read_text(encoding="utf-8")
        ids = re.findall(r'id="(d-[^"]+)"', html)
        assert ids and len(ids) == len(set(ids)), p.name
        for ref in re.findall(r'aria-describedby="([^"]+)"', html):
            assert ref in ids, ref


def test_profiles_link_csv_and_pdf():
    html = (SITE / "system" / "24-0001.html").read_text(encoding="utf-8")
    assert 'href="24-0001.csv"' in html and 'href="24-0001.pdf"' in html


def test_pdf_step_runs_in_ci():
    wf = (ROOT / ".github" / "workflows" / "pages.yml").read_text()
    assert "scripts/pdfs.py" in wf and wf.index("scripts/build.py") < wf.index("scripts/pdfs.py") < wf.index("upload-pages-artifact")


def test_key_terms():
    """Approved terms are on the About page once each, with an anchor and a search entry; drafts are not."""
    rows = list(csv.DictReader(open(ROOT / "registry" / "terms.csv", encoding="utf-8")))
    assert {r["status"] for r in rows} <= {"approved", "draft"}
    assert len({r["term"].lower() for r in rows}) == len(rows)
    from atlas import about
    assert {r["group"] for r in rows} <= set(about.TERM_GROUPS)
    t = (SITE / "about.html").read_text(encoding="utf-8")
    search = (SITE / "assets" / "search-index.js").read_text(encoding="utf-8")
    for r in rows:
        a = about.term_anchor(r["term"])
        if r["status"] == "approved":
            assert t.count(f'id="{a}"') == 1, r["term"]
            assert f"about.html#{a}" in search, r["term"]
        else:
            assert f'id="{a}"' not in t, r["term"]
    for r in rows:
        assert "—" not in r["definition"], r["term"]
