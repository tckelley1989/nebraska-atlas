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
from atlas import county_detail, profile_detail, statewide, pages, maps, facts, findings, about, dive, landing  # noqa: E402
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
       ("Counties", "counties.html", "counties"), ("How it works", "how.html", "how"), ("About", "about.html", "about")]  # Schools and Counties make up the Atlas section


def main():
    a = Atlas()
    if OUT.exists():
        shutil.rmtree(OUT)
    for d in ("assets", "system", "county", "schools", "counties", "dive/system", "dive/county"):
        (OUT / d).mkdir(parents=True)
    shutil.copy(ROOT / "design" / "tokens.css", OUT / "assets" / "tokens.css")
    shutil.copy(ROOT / "templates" / "site.css", OUT / "assets" / "site.css")
    shutil.copy(ROOT / "templates" / "search.js", OUT / "assets" / "search.js")
    shutil.copy(ROOT / "templates" / "dive.js", OUT / "assets" / "dive.js")
    shutil.copy(ROOT / "templates" / "measure.js", OUT / "assets" / "measure.js")

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

    detail = profile_detail.Detail(a)
    cdetail = county_detail.Detail(a)
    for code in a.formula:
        ctx = pages.system_page(a, code)
        ctx.update(detail.system(code))
        write(f"system/{code}.html", "system.html", title=ctx["name"], section="schools",
              description=ctx["desc"][:300], **ctx)
        (OUT / "system" / f"{code}.csv").write_text(about.profile_csv(a, "system", code, ctx["name"]), encoding="utf-8")
    for fips in a.counties_xw:
        ctx = pages.county_page(a, fips)
        ctx.update(cdetail.county(fips))
        write(f"county/{fips}.html", "county.html", title=ctx["name"], section="counties",
              description=ctx["desc"][:300], **ctx)
        (OUT / "county" / f"{fips}.csv").write_text(about.profile_csv(a, "county", fips, ctx["name"]), encoding="utf-8")
    # One page per measure: map, table and relationships (methods 5). The section front is the first key measure's page,
    # with the index of every measure and, for schools, the Statewide picture.
    ptax = dive.Ptax(a)
    for lvl in ("system", "county"):
        for fn, body in dive.shared_places(a, lvl, ptax).items():
            (OUT / "assets" / fn).write_text(body, encoding="utf-8")
        (OUT / "assets" / f"dive-values-{lvl}.js").write_text(dive.shared_values(a, lvl), encoding="utf-8")
        (OUT / "assets" / f"geo-{lvl}.js").write_text(maps.geo_js(a, lvl), encoding="utf-8")
    redirect = env.get_template("redirect.html")
    for lvl in ("system", "county"):
        sect = maps.section(lvl)
        ix = maps.index(a, lvl)
        first = a.key_eight(lvl)[0]["key"]
        for r in (x for x in a.registry if x["level"] == lvl and maps.has_page(x)):
            ctx = {"level": lvl, "key": r["key"], "label": r["label"], "short": r["short"], "note": r["note"], "group": r["group"],
                   "period": r["period"], "source": r["source"], "plain": dive.plain(r), "short_lc": dive.lc(r["short"]), "sect": sect, "ix": ix, "dv": False}
            ctx.update(maps.measure_map(a, lvl, r))
            if r["format"] != "category":
                ctx.update(dive.page(a, lvl, r["key"], ptax))
                ctx["dv"] = True
            write(f"{sect}/{r['key']}.html", "measure.html", title=r["label"], section=sect, description=ctx["plain"][:300], **ctx)
            if r["key"] == first:
                front = dict(ctx, front=True, **(statewide.build(a) if lvl == "system" else {}))
                write(f"{sect}.html", "measure.html", title="School systems" if lvl == "system" else "Counties", section=sect,
                      description=ctx["plain"][:300], **front)
            if r["format"] != "category":  # the old Deeper dive address
                (OUT / "dive" / lvl / f"{r['key']}.html").write_text(
                    redirect.render(target=f"../../{sect}/{r['key']}.html", title=r["label"]), encoding="utf-8")
    write("how.html", "how.html", title="How school money and property taxes work", section="how", **landing.build(a))
    (OUT / "dive" / "index.html").write_text(redirect.render(target="../how.html", title="How it works"), encoding="utf-8")

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
