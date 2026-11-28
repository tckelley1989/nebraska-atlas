"""Measure pages (methods 5): identities on every place, the statistical rules, phone charts and links (design doc rules)."""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "_site"
sys.path.insert(0, str(ROOT / "scripts"))

pytestmark = pytest.mark.skipif(not (ROOT / "data" / "bundle" / "manifest.json").exists(), reason="no measures bundle yet")


@pytest.fixture(scope="module", autouse=True)
def built():
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build.py")], check=True, capture_output=True)


@pytest.fixture(scope="module")
def atlas():
    from atlas.data import Atlas
    return Atlas()


def mpage(level, key):
    return SITE / ("schools" if level == "system" else "counties") / f"{key}.html"


def measure_pages():
    """Every measure page that carries the relationship engine (number measures)."""
    for d in ("schools", "counties"):
        for p in (SITE / d).glob("*.html"):
            if 'id="dive-data"' in p.read_text(encoding="utf-8"):
                yield p


def page_data(level, key):
    """The page's own data merged with the shared files it loads, as dive.js does."""
    t = mpage(level, key).read_text(encoding="utf-8")
    d = json.loads(re.search(r'<script id="dive-data" type="application/json">(.*?)</script>', t, re.S).group(1))
    for src in re.findall(r'<script src="\.\./assets/(dive-(?:places|formula|ptax)[a-z-]*\.js)"', t):
        body = (SITE / "assets" / src).read_text(encoding="utf-8")
        shared = json.loads(body[body.index("=") + 1:-1])
        for c, p in d["places"].items():
            p.update(shared.get(c, {}))
    return t, d


def test_pages_load_only_the_shared_data_they_draw():
    for p in measure_pages():
        t = p.read_text(encoding="utf-8")
        chart = json.loads(re.search(r'<script id="dive-data" type="application/json">(.*?)</script>', t, re.S).group(1))["chart"]
        assert ("dive-formula.js" in t) == (chart == "formula"), p.name
        assert ("dive-ptax.js" in t) == (chart == "ptax"), p.name
        assert '"fx"' not in t and '"px"' not in t, p.name


def test_a_page_for_every_measure_and_old_addresses_redirect(atlas):
    from atlas.maps import has_page
    for r in atlas.registry:
        assert mpage(r["level"], r["key"]).exists() == has_page(r), r["key"]
        old = SITE / "dive" / r["level"] / f"{r['key']}.html"
        assert old.exists() == (r["format"] != "category"), r["key"]
        if old.exists():
            t = old.read_text(encoding="utf-8")
            target = re.search(r'location\.replace\("([^"]+)" \+ location\.search \+ location\.hash\)', t).group(1)
            assert (old.parent / target).resolve() == mpage(r["level"], r["key"]).resolve(), r["key"]
    assert "../how.html" in (SITE / "dive" / "index.html").read_text(encoding="utf-8")


def test_formula_lines_add_to_the_certified_total_for_every_system():
    """Step 3 place mode: need parts = need, resource parts = resources, equalization = max(0, need - resources),
    aid parts = total aid = certified total (review 1 rule: every formula line generated and tested)."""
    _, d = page_data("system", "aid_ps")
    assert d["chart"] == "formula" and len(d["places"]) == 244
    for code, p in d["places"].items():
        f = p["fx"]
        assert abs(sum(v for _, v in f["need_parts"]) - f["need"]) <= 1, code
        assert abs(sum(v for _, v in f["res_parts"]) - f["res"]) <= 1, code
        assert abs(max(0, f["need"] - f["res"]) - f["eq"]) <= 1, code
        assert abs(sum(v for _, v in f["aid_parts"]) - f["aid"]) <= 1, code
        assert abs(f["aid"] - f["cert"]) <= 1, code


def test_property_tax_identity_for_every_county(atlas):
    """Taxes after credits = taxable valuation x average rate x share left, and it reproduces the published measure."""
    _, d = page_data("county", "ptax_net_real_change")
    assert d["chart"] == "ptax"
    n = 0
    for fips, p in d["places"].items():
        x = p["px"]; g_val, g_rate, g_left, g_net = (v / 100 for v in x["f"])
        assert abs((1 + g_val) * (1 + g_rate) * (1 + g_left) - 1 - g_net) < 1e-4, fips  # factors stored to 0.001 points
        assert abs(100 * g_net - atlas.value("county", fips, "ptax_net_real_change")) < 0.01, fips
        n += 1
    assert n == 93


def test_relationship_rules(atlas):
    """Holding results first, never below one that does not hold (rule 5); at least half the places (rule 6);
    pairs in the same family are set aside, never tested (rule 4)."""
    from atlas import dive
    for r in atlas.registry:
        if r["format"] == "category":
            continue
        d = dive.Dive(atlas, r["level"], r["key"])
        rel = d.relationships()
        flags = [x["holds"] for x in rel["tested"]]
        assert flags == sorted(flags, reverse=True), r["key"]
        assert all(x["n"] >= rel["min_n"] for x in rel["tested"]), r["key"]
        tested = {x["key"] for x in rel["tested"]} | {x["key"] for x in rel["few"]}
        assert not tested & {x["key"] for x in rel["setaside"]}, r["key"]
        for f in d.fam:
            members = next(x for x in atlas.families if x["family"] == f)["members"].split("|")
            assert not tested & set(members), (r["key"], f)


def test_every_chart_has_a_phone_version_and_axis_title(atlas):
    for p in measure_pages():
        t = p.read_text(encoding="utf-8")
        desk, phone = t.count('<div class="w-desk">'), t.count('<div class="w-phone">')
        assert desk == phone and desk >= 1, p.name
        for svg in re.findall(r'<svg class="dchart[^"]*".*?</svg>', t, re.S):
            texts = re.findall(r"<text[^>]*>([^<]+)", svg)
            assert len(texts) >= 3, p.name  # an axis title plus tick labels


def test_every_place_can_be_followed_and_profile_links_resolve(atlas):
    for level in ("system", "county"):
        t, d = page_data(level, "aid_ps" if level == "system" else "ptax_net_real_change")
        pick = re.search(r'<select id="pick">(.*?)</select>', t, re.S).group(1)
        opts = set(re.findall(r'<option value="([0-9-]+)">', pick))
        assert opts and opts <= set(d["places"]), level
    prof = (SITE / "system" / "24-0001.html").read_text(encoding="utf-8")
    links = re.findall(r'href="\.\./(schools|counties)/([a-z0-9_]+)\.html\?sel=24-0001"', prof)
    assert links and all(d == "schools" for d, _ in links)
    for d, key in links:
        assert (SITE / d / f"{key}.html").exists(), key
    data = (SITE / "schools" / "aid_ps.html").read_text(encoding="utf-8")
    assert 'data-base="../system/"' in data  # the profile link the page writes for a followed place


def test_levy_relationships_lead_with_their_explanation():
    """A relationship with a measure a board controls carries its explanation (review 1 rule)."""
    t, _ = page_data("system", "aid_ps")
    assert "Board sets" in t
    assert "A board&#39;s levy does not change its aid" in t or "A board's levy does not change its aid" in t


def test_why_lines_cover_every_holding_result_and_claim_no_mechanism_without_arithmetic(atlas):
    """Methods 5.9: every result that holds is explained; a direction word agrees with the sign beside it; a mechanism is
    stated only where arithmetic links the pair (the TEEOSA formula, the levy's denominator, the property tax factors)."""
    from atlas import dive
    ptax = dive.Ptax(atlas)
    VAL, LEVY = {"tv_ps", "val_ps"}, {"lc2_limit_levy", "lc2_gf_levy"}
    for r in atlas.registry:
        if r["format"] == "category":
            continue
        d = dive.Dive(atlas, r["level"], r["key"])
        rel = d.relationships()
        text = " ".join(t for _, t in dive.whys(d, rel, ptax))
        low = text.lower()
        holds = {x["key"] for x in rel["holds"]}
        for x in rel["holds"]:
            assert x["name"].lower() in low, (r["key"], x["name"])
        for word, sign in re.findall(r"goes (with|against) [^()]*?\(([+−])", text):
            assert (word == "with") == (sign == "+"), (r["key"], word, sign)
        assert "runs through it, not between them" not in text, r["key"]
        if "because the formula" in text:
            assert ("aid_ps" in holds | {r["key"]}) and (VAL & (holds | {r["key"]})), r["key"]
        if "divided by taxable valuation" in text:
            assert r["key"] in LEVY or holds & LEVY, r["key"]
        if "factors charted above" in text:
            assert r["level"] == "county" and "c07" in d.fam, r["key"]
        if "does not change its aid" in text:
            assert r["key"] == "aid_ps", r["key"]


def test_no_empty_test_counts():
    for p in measure_pages():
        assert "0 of 0" not in p.read_text(encoding="utf-8"), p.name


def test_how_it_works_page(atlas):
    """The How it works page's worked examples add to the certified total, its links resolve, and its figures come
    from the bundle (spot checks against the data)."""
    from atlas import landing
    ctx = landing.build(atlas)
    for e in ctx["examples"]:
        assert abs(e["aid_raw"] - e["cert"]) <= 1, e["code"]
    t = (SITE / "how.html").read_text(encoding="utf-8")
    links = set(re.findall(r'href="((?:schools|counties)/[a-z0-9_]+\.html)', t))
    assert links
    for href in links:
        assert (SITE / href).exists(), href
    assert ctx["aid_total"] in t and ctx["unused"] in t and str(ctx["votes"]) in t
    nav = (SITE / "index.html").read_text(encoding="utf-8")
    assert 'href="how.html"' in nav and "Deeper dive" not in nav


def test_every_tested_measure_is_listed_and_plottable(atlas):
    """Step 4 lists all tested measures; step 5 offers every tested measure and every one too thin to test."""
    from atlas import dive
    for r in atlas.registry:
        if r["format"] == "category":
            continue
        rel = dive.Dive(atlas, r["level"], r["key"]).relationships()
        t = mpage(r["level"], r["key"]).read_text(encoding="utf-8")
        assert len(re.findall(r'<tr data-x="', t)) == len(rel["tested"]), r["key"]
        offered = set(re.findall(r'<option value="\d+" data-k="([^"]+)"', t)) | set(re.findall(r'<option value="k:([^"]+)"', t))
        assert offered == {x["key"] for x in rel["tested"]} | {x["key"] for x in rel["few"]}, r["key"]


def test_shared_values_match_the_bundle(atlas):
    body = (SITE / "assets" / "dive-values-system.js").read_text(encoding="utf-8")
    V = json.loads(body[body.index("=") + 1:-1])
    for k in ("aid_ps", "nscas_scale_rel", "lc2_limit_levy"):
        for i, c in enumerate(V["codes"]):
            a, b = V["v"][k][i], atlas.value("system", c, k)
            assert (a is None) == (not isinstance(b, (int, float))), (k, c)
            if a is not None:
                assert abs(a - b) <= 1e-5 * max(1, abs(b)), (k, c)


def test_measure_switcher_and_index_list_every_page(atlas):
    """Every measure page can reach every other: the switcher lists them all, and the section front indexes them."""
    from atlas import maps
    for level, sect in (("system", "schools"), ("county", "counties")):
        keys = {k for g in maps.index(atlas, level)["groups"] for k in (it["key"] for it in g["items"])}
        assert keys == {p.stem for p in (SITE / sect).glob("*.html")}, level
        t = (SITE / f"{sect}.html").read_text(encoding="utf-8")
        assert set(re.findall(r'href="' + sect + r'/([a-z0-9_]+)\.html"', t[t.index('id="all"'):])) == keys, level
        page = (SITE / sect / f"{atlas.key_eight(level)[1]['key']}.html").read_text(encoding="utf-8")
        assert set(re.findall(r'<option value="([a-z0-9_]+)"', page[page.index('id="msel"'):page.index("</select>", page.index('id="msel"'))])) == keys
