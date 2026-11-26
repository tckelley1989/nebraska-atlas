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


def test_formula_notes():
    """Foundation aid net effect on every profile; stabilization and averaging notes only where they apply."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from atlas.data import Atlas
    from atlas import pages
    a = Atlas()
    lex = pages.formula_notes(a, "24-0001")
    assert "added $1,798,517" in lex[0]
    stab = sum(1 for c in a.formula if (a.need_parts.get(c, {}).get("need_stabilization") or 0) != 0)
    assert sum(1 for p in (SITE / "system").glob("*.html") if "needs stabilization" in p.read_text(encoding="utf-8")) == stab
    assert all("Foundation aid paid" in p.read_text(encoding="utf-8") for p in (SITE / "system").glob("*.html"))


NAMING = re.compile(r"(?i)(?<!taxable )(?<!school adjusted )\bvaluations?\b|\btaxable values?\b|\bproperty wealth\b"
                    r"|\bassessed values?\b|(?-i:(?<!School ))\b(?i:adjusted values?)\b|\bof value\b")


def test_valuation_naming_rule():
    """Taxable valuation (assessed; levy, taxes, credits) or school adjusted valuation (the formula only):
    never bare "valuation", "taxable value", "of value", "assessed value" or "property wealth".
    Revenue's report title, School Adjusted Value, is allowed. Data keys and CSV headers are skipped."""
    hits = []
    for p in SITE.rglob("*"):
        if p.suffix not in (".html", ".js", ".csv"):
            continue
        t = p.read_text(encoding="utf-8", errors="ignore")
        t = re.sub(r'"[a-z0-9_]*valuation[a-z0-9_]*"\s*:', '"k":', t)  # data keys
        t = re.sub(r'(?<=,)valuation(?=,)', "k", t)  # bare CSV fields
        # the glossary entry that defines taxable valuation as assessed value
        t = re.sub(r'<tr id="t-taxable-valuation">.*?</tr>', "", t, flags=re.S)
        t = re.sub(r"<dt>Taxable valuation</dt><dd>.*?</dd>", "", t, flags=re.S)  # the same definition on the dive landing page
        t = re.sub(r"(?<![A-Za-z])#?t-[a-z0-9-]+", "anchor", t)  # term anchors such as t-school-adjusted-valuation
        hits += [f"{p.name}: …{t[max(0, m.start() - 40):m.end() + 10]}…" for m in NAMING.finditer(t)]
    assert not hits, f"{len(hits)} hits, e.g. " + " | ".join(sorted(set(hits))[:5])


def test_periods_follow_the_bundle():
    """A measure's period comes from the bundle when the bundle labels it, so labels move with the data."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from atlas.data import Atlas
    a = Atlas()
    for (key, level), r in a.ind.items():
        js = a.county_js if level == "county" else a.system_js
        p = ((js.get("indicators") or {}).get(key) or {}).get("period")
        if p:
            assert r["period"] == p, (level, key, r["period"], p)
    t = (SITE / "system" / "28-0001.html").read_text(encoding="utf-8")
    lc2 = a.system_js["indicators"]["lc2_limit_levy"]["period"]
    assert lc2 in t


def test_map_table_has_every_place_and_matches_the_map():
    """Table view (map pages): one row per mapped place, a value wherever the map has a color, blank where it shows
    the not-available class, and the top value equals the page's highest-five list."""
    import json
    for page, n in (("schools.html", 244), ("counties.html", 93)):
        t = (SITE / page).read_text(encoding="utf-8")
        tab = json.loads(re.search(r"var T = (\{.*?\}), cur =", t, re.S).group(1))
        cls = json.loads(re.search(r"var C = (\{.*?\}), ids", t, re.S).group(1))
        assert len(tab["ids"]) == len(tab["names"]) == n, page
        for k, vals in tab["vals"].items():
            assert len(vals) == n, (page, k)
            assert all((v is None) == (c == "na") for v, c in zip(vals, cls[k])), (page, k)
            nums = [v for v in vals if v and v[0] is not None]
            if nums:
                top = max(nums, key=lambda v: v[0])[1]
                sect = re.search(rf'<div class="ranks" data-k="{k}".*?Highest five</h3><ol><li><a[^>]*>[^<]*</a> <b[^>]*>([^<]*)</b>', t, re.S)
                assert sect and sect.group(1) == top, (page, k)


def test_map_pages_offer_png_and_svg_with_source_lines():
    """Downloads draw the title, legend, period and source into the file, so every indicator needs a period line."""
    import json
    for page in ("schools.html", "counties.html"):
        t = (SITE / page).read_text(encoding="utf-8")
        assert 'class="dlbtn" data-f="png"' in t and 'class="dlbtn" data-f="svg"' in t, page
        periods = json.loads("{" + re.search(r"periods = \{(.*?)\};", t, re.S).group(1) + "}")
        keys = re.findall(r'<section class="ind" data-k="([^"]+)"', t)
        assert set(periods) == set(keys) and all("Source: " in v and len(v) > 12 for v in periods.values()), page
