"""About page content, downloads and per-profile CSVs.

Everything here is read from the registry, the methods spec and the bundle, so the
About page cannot drift from what the build actually does.
"""
import csv
import io
import re
import shutil

import markdown

from .data import BUNDLE
from .pages import GROUP_ORDER

ROOT = BUNDLE.parents[1]

# One line per published file. A bundle file missing from this list fails the test gate.
FILES = {
    "counties.csv": "One row per county, tier and the state: every county measure on the site, as plain numbers.",
    "school_systems.csv": "TEEOSA certification by system and aid year: formula students, need, equalization aid, total aid, school adjusted valuation.",
    "school_formula.csv": "The latest certification, step by step for every system: need, each resource, equalization and foundation aid.",
    "school_need_components.csv": "Formula need split into its components, by system and aid year.",
    "school_revenue.csv": "Money received by system and school year from Annual Financial Reports, with credits shown separately.",
    "school_property_taxes.csv": "Property taxes each system received (01100) plus the state's credits on them, split into what the state and local taxpayers paid, by school year.",
    "school_tax_base.csv": "Each system's taxable valuation by October since 2019, with the latest October's shares by class of property (percent).",
    "school_outcomes.csv": "NSCAS results, graduation rates and teacher pay and experience by system.",
    "lc2_budgets.csv": "LC-2 budget forms: property tax authority, board votes and requests by system and budget year.",
    "property_taxes.csv": "Taxable valuation and taxes levied by county, tax year and taxing authority.",
    "property_taxes_by_class.csv": "Taxable valuation and taxes levied by county, tax year and property class.",
    "credits.csv": "State property tax credits by county, tax year and program, with how each amount was found.",
    "lb1107_claims.csv": "LB 1107 income tax credit claims and the school share used to split them.",
    "county_industry_jobs.csv": "Payroll jobs by county and industry sector, 2019 against the latest four quarters.",
    "county_levels.csv": "Base-period and current levels behind every county change measure.",
    "district_county_weights.csv": "Each system's split across counties by where its Census children ages 5 to 17 live.",
    "deflators.csv": "Midwest CPI-U deflators (2019 = 1) by calendar and school year, with the BEA check deflator.",
    "statewide.csv": "Statewide totals behind the Findings, by topic, measure and year.",
    "revisions.csv": "Every published value that changed since the previous build, with both values and both build dates.",
}



def term_id(level, key):
    return f"m-{level}-{key}"


TERM_GROUPS = ["Students", "Need", "Resources and aid", "Aid and certification", "Property value and taxes", "Reading the dives"]


def term_anchor(term: str) -> str:
    return "t-" + re.sub(r"[^a-z0-9]+", "-", term.lower()).strip("-")


def terms():
    """School finance terms from registry/terms.csv. Only approved definitions are published; drafts wait for review."""
    with open(ROOT / "registry" / "terms.csv", newline="", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["status"] == "approved"]
    groups = [{"name": g, "rows": [dict(r, anchor=term_anchor(r["term"])) for r in rows if r["group"] == g]} for g in TERM_GROUPS]
    return [g for g in groups if g["rows"]]


def glossary(a):
    out = []
    for level, title in (("county", "County measures"), ("system", "School system measures")):
        groups = []
        for g in GROUP_ORDER[level]:
            rows = [r for r in a.registry if r["level"] == level and r["group"] == g]
            if rows:
                groups.append({"name": g, "rows": [dict(r, anchor=term_id(level, r["key"])) for r in rows]})
        out.append({"title": title, "groups": groups, "n": sum(len(g["rows"]) for g in groups)})
    return out


def sources(a):
    seen = {}
    for r in a.registry:
        seen.setdefault(r["source"], set()).add(r["level"])
    return [{"name": s, "levels": " and ".join(sorted("counties" if l == "county" else "school systems" for l in lv))}
            for s, lv in sorted(seen.items())]


def methods_html():
    text = (ROOT / "methods" / "spec.md").read_text(encoding="utf-8")
    body = text.split("\n## ", 1)[1]
    body = "## " + body.split("\n## Open items")[0]
    body = re.sub(r"```latex\n.*?\n```", "<p class=\"formula\">reliability = τ² ÷ (τ² + k ÷ n)</p>", body, flags=re.S)
    html = markdown.markdown(body, extensions=["tables"])
    html = html.replace("<table>", '<div class="scroll"><table class="data">').replace("</table>", "</table></div>")
    return html.replace("<h2>", '<h3 class="mh">').replace("</h2>", "</h3>")


def downloads(out_dir):
    """Copy the bundle CSVs to _site/data and describe them."""
    dest = out_dir / "data"
    dest.mkdir(exist_ok=True)
    items = []
    for name, desc in FILES.items():
        src = BUNDLE / name
        shutil.copy(src, dest / name)
        with open(src, newline="", encoding="utf-8") as fh:
            rows = sum(1 for _ in fh) - 1
        kb = src.stat().st_size / 1024
        items.append({"name": name, "desc": desc, "rows": f"{rows:,}", "size": f"{kb:,.0f} KB" if kb < 1024 else f"{kb / 1024:,.1f} MB"})
    return items


def profile_csv(a, level, place, name):
    """Every measure for one place as plain numbers, for Excel."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(["place", "measure", "label", "value", "unit", "median", "rank_from_highest", "of", "period", "source"])
    for r in a.registry:
        if r["level"] != level:
            continue
        v = a.value(level, place, r["key"])
        st = a.stats(level, r["key"])
        rk = a.rank(level, place, r["key"])
        num = isinstance(v, (int, float))
        w.writerow([name, r["key"], r["label"], ("" if v is None else (round(v, 6) if num else v)), r["unit"],
                    "" if st["median"] is None or r["format"] == "category" else round(st["median"], 6),
                    rk[0] if rk else "", rk[1] if rk else "", r["period"], r["source"]])
    return "﻿" + buf.getvalue()  # BOM so Excel reads the minus signs and accents as UTF-8


def search_index(a):
    idx = []
    for code, xw in a.systems_xw.items():
        if code in a.formula:
            idx.append({"n": xw["display_name"], "k": "School system", "x": xw["counties"], "u": f"system/{code}.html"})
    for fips, c in a.counties_xw.items():
        idx.append({"n": f"{c['name']} County", "k": "County", "x": a.tier_name(fips), "u": f"county/{fips}.html"})
    for t in a.towns:
        if t["system_code"] in a.formula:
            idx.append({"n": t["town"], "k": "Town", "x": a.systems_xw[t["system_code"]]["display_name"], "u": f"system/{t['system_code']}.html"})
    for g in terms():
        for r in g["rows"]:
            idx.append({"n": r["term"], "k": "Term", "x": g["name"], "u": f"about.html#{r['anchor']}"})
    return idx
