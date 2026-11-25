"""Render the v2 site into _site/.

Reads the measures bundle (data/bundle), the registry, crosswalks and design tokens,
and renders one template per page type with Jinja.
"""
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

sys.path.insert(0, str(Path(__file__).resolve().parent))
import json
from atlas import pages, maps, facts, findings, about, dive  # noqa: E402
from atlas.data import Atlas  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "_site"
DRAFT = os.environ.get("ATLAS_DRAFT", "1") == "1"  # stays on until launch day

QUILT = ('<svg width="28" height="28" viewBox="0 0 30 30" aria-hidden="true">'
         '<path d="M0 0H15V15Z" fill="#c1432e"/><path d="M0 0V15H15Z" fill="#ce9e62"/>'
         '<path d="M15 0H30V15Z" fill="#4b6777"/><path d="M15 0L15 15H30Z" fill="#f3eee6"/>'
         '<path d="M0 15H15V30Z" fill="#f3eee6"/><path d="M0 15V30H15Z" fill="#4b6777"/>'
         '<path d="M15 15H30V30Z" fill="#ce9e62"/><path d="M15 15V30H30Z" fill="#c1432e"/></svg>')
NAV = [("Findings", "index.html", "findings"), ("Schools", "schools.html", "schools"),
       ("Counties", "counties.html", "counties"), ("About", "about.html", "about")]  # Schools and Counties make up the Atlas section


def main():
    a = Atlas()
    if OUT.exists():
        shutil.rmtree(OUT)
    for d in ("assets", "system", "county", "dive/system", "dive/county"):
        (OUT / d).mkdir(parents=True)
    shutil.copy(ROOT / "design" / "tokens.css", OUT / "assets" / "tokens.css")
    shutil.copy(ROOT / "templates" / "site.css", OUT / "assets" / "site.css")
    shutil.copy(ROOT / "templates" / "search.js", OUT / "assets" / "search.js")
    shutil.copy(ROOT / "templates" / "dive.js", OUT / "assets" / "dive.js")

    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=select_autoescape(["html"]),
                      trim_blocks=True, lstrip_blocks=True)
    built = datetime.fromisoformat(a.manifest["built_utc"]).strftime("%B %-d, %Y")
    common = dict(draft=DRAFT, quilt=QUILT, nav=NAV, built=built)

    def write(path, template, **ctx):
        depth = path.count("/")
        html = env.get_template(template).render(root="../" * depth, **common, **ctx)
        (OUT / path).write_text(html, encoding="utf-8")

    f = facts.build(a)
    fl = findings.load(f)
    synth = next(x for x in fl if x["synthesis"])
    synth["headline_hero"] = "Since 2019, Nebraska has lowered property tax bills mainly by paying part of them"
    hero_lead = (f"Credits now cover {f['credit_share_state']} of all property taxes. Certified formula aid "
                 f"grew {f['aid_change_dollars']} from 2019-20 to {f['aid_year']}.")
    state = a.county_js["tiers"]["state"]
    state_tiles = []
    for r in a.key_eight("county"):
        v = state["v"].get(r["key"]) if "v" in state else None
        state_tiles.append({"short": r["short"], "value": state["d"].get(r["key"]) or "", "tone": pages.tone(r, v) if v is not None else
                            ("up" if (state["d"].get(r["key"]) or "").startswith("+") else "down" if (state["d"].get(r["key"]) or "").startswith("\u2212") else ""),
                            "pos": None, "tier": "", "state": "", "rank": r["period"], "median": None, "cat_note": ""})
    write("index.html", "index.html", title="Findings", section="findings", f=f, findings=fl, synthesis=synth,
          hero_lead=hero_lead, state_tiles=state_tiles)

    for code in a.formula:
        ctx = pages.system_page(a, code)
        write(f"system/{code}.html", "system.html", title=ctx["name"], section="schools",
              description=ctx["desc"][:300], **ctx)
        (OUT / "system" / f"{code}.csv").write_text(about.profile_csv(a, "system", code, ctx["name"]), encoding="utf-8")
    for fips in a.counties_xw:
        ctx = pages.county_page(a, fips)
        write(f"county/{fips}.html", "county.html", title=ctx["name"], section="counties",
              description=ctx["desc"][:300], **ctx)
        (OUT / "county" / f"{fips}.csv").write_text(about.profile_csv(a, "county", fips, ctx["name"]), encoding="utf-8")
    for level, page, section in (("system", "schools.html", "schools"), ("county", "counties.html", "counties")):
        ctx = maps.map_page(a, level)
        write(page, "map.html", section=section, **ctx)

    # Deeper dive: one page per measure (design doc "Deeper Dive: Design")
    ptax = dive.Ptax(a)
    listing = {"system": [], "county": []}
    for r in a.registry:
        if r["format"] == "category":
            continue
        ctx = dive.page(a, r["level"], r["key"], ptax)
        write(f"dive/{r['level']}/{r['key']}.html", "dive.html", title=f"Deeper dive: {r['label']}",
              section="schools" if r["level"] == "system" else "counties", description=ctx["plain"], **ctx)
        listing[r["level"]].append({"key": r["key"], "label": r["label"], "group": r["group"], "key_indicator": r["key_indicator"] == "yes"})
    write("dive/index.html", "dive_index.html", title="Deeper dive", section="", listing=listing,
          group_order=pages.GROUP_ORDER)

    files = about.downloads(OUT)
    shutil.copy(ROOT / "data" / "bundle" / "manifest.json", OUT / "data" / "manifest.json")
    write("about.html", "about.html", title="About", section="about", glossary=about.glossary(a), terms=about.terms(),
          methods=about.methods_html(), files=files, sources=about.sources(a), commit=a.manifest["source_commit"])
    (OUT / "assets" / "search-index.js").write_text(
        "window.LEDGER_SEARCH=" + json.dumps(about.search_index(a), ensure_ascii=False, separators=(",", ":")) + ";", encoding="utf-8")

    (OUT / "robots.txt").write_text("User-agent: *\nDisallow: /\n" if DRAFT else "User-agent: *\nAllow: /\n")
    (OUT / ".nojekyll").write_text("")
    n = sum(1 for _ in OUT.rglob("*.html"))
    print(f"Built {OUT}: {n} pages (draft={DRAFT})")


if __name__ == "__main__":
    main()
