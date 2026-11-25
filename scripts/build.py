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
from atlas import pages, maps  # noqa: E402
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
       ("Counties", "counties.html", "counties"), ("About", "about.html", "about")]


def main():
    a = Atlas()
    if OUT.exists():
        shutil.rmtree(OUT)
    for d in ("assets", "system", "county"):
        (OUT / d).mkdir(parents=True)
    shutil.copy(ROOT / "design" / "tokens.css", OUT / "assets" / "tokens.css")
    shutil.copy(ROOT / "templates" / "site.css", OUT / "assets" / "site.css")

    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=select_autoescape(["html"]),
                      trim_blocks=True, lstrip_blocks=True)
    built = datetime.fromisoformat(a.manifest["built_utc"]).strftime("%B %-d, %Y")
    common = dict(draft=DRAFT, quilt=QUILT, nav=NAV, built=built)

    def write(path, template, **ctx):
        depth = path.count("/")
        html = env.get_template(template).render(root="../" * depth, **common, **ctx)
        (OUT / path).write_text(html, encoding="utf-8")

    key_eight = [("counties", a.key_eight("county")), ("school systems", a.key_eight("system"))]
    write("index.html", "index.html", title="Version 2", section="findings", key_eight=key_eight,
          n_indicators=len(a.registry), n_county=sum(r["level"] == "county" for r in a.registry),
          n_system=sum(r["level"] == "system" for r in a.registry), n_systems=len(a.systems_xw), n_counties=len(a.counties_xw))

    for code in a.formula:
        ctx = pages.system_page(a, code)
        write(f"system/{code}.html", "system.html", title=ctx["name"], section="schools",
              description=ctx["desc"][:300], **ctx)
    for fips in a.counties_xw:
        ctx = pages.county_page(a, fips)
        write(f"county/{fips}.html", "county.html", title=ctx["name"], section="counties",
              description=ctx["desc"][:300], **ctx)
    for level, page, section in (("system", "schools.html", "schools"), ("county", "counties.html", "counties")):
        ctx = maps.map_page(a, level)
        write(page, "map.html", section=section, **ctx)

    (OUT / "robots.txt").write_text("User-agent: *\nDisallow: /\n" if DRAFT else "User-agent: *\nAllow: /\n")
    (OUT / ".nojekyll").write_text("")
    n = sum(1 for _ in OUT.rglob("*.html"))
    print(f"Built {OUT}: {n} pages (draft={DRAFT})")


if __name__ == "__main__":
    main()
