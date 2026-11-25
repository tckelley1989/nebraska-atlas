"""Render the v2 site into _site/.

Reads the registry, crosswalks and design tokens; renders templates with Jinja.
Measure data arrives in data/ from nebraska-economy (see data/README.md).
"""
import csv
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "_site"
DRAFT = os.environ.get("ATLAS_DRAFT", "1") == "1"  # stays on until launch day

QUILT = ('<svg width="28" height="28" viewBox="0 0 30 30" aria-hidden="true">'
         '<path d="M0 0H15V15Z" fill="#c1432e"/><path d="M0 0V15H15Z" fill="#ce9e62"/>'
         '<path d="M15 0H30V15Z" fill="#4b6777"/><path d="M15 0L15 15H30Z" fill="#f3eee6"/>'
         '<path d="M0 15H15V30Z" fill="#f3eee6"/><path d="M0 15V30H15Z" fill="#4b6777"/>'
         '<path d="M15 15H30V30Z" fill="#ce9e62"/><path d="M15 15V30H30Z" fill="#c1432e"/></svg>')


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    ind = read_csv(ROOT / "registry" / "indicators.csv")
    systems = read_csv(ROOT / "registry" / "crosswalk_systems.csv")
    counties = read_csv(ROOT / "registry" / "crosswalk_counties.csv")
    key_eight = []
    for level, name in (("county", "counties"), ("system", "school systems")):
        rows = sorted((r for r in ind if r["level"] == level and r["key_indicator"] == "yes"),
                      key=lambda r: int(r["key_order"]))
        key_eight.append((name, rows))

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "assets").mkdir(parents=True)
    shutil.copy(ROOT / "design" / "tokens.css", OUT / "assets" / "tokens.css")
    shutil.copy(ROOT / "templates" / "site.css", OUT / "assets" / "site.css")

    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=select_autoescape(["html"]))
    common = dict(draft=DRAFT, quilt=QUILT, root="",
                  built=datetime.now(timezone.utc).strftime("%B %-d, %Y %H:%M UTC"))
    html = env.get_template("index.html").render(
        title="Version 2", key_eight=key_eight, n_indicators=len(ind),
        n_county=sum(r["level"] == "county" for r in ind), n_system=sum(r["level"] == "system" for r in ind),
        n_systems=len(systems), n_counties=len(counties), **common)
    (OUT / "index.html").write_text(html, encoding="utf-8")
    (OUT / "robots.txt").write_text("User-agent: *\nDisallow: /\n" if DRAFT else "User-agent: *\nAllow: /\n")
    (OUT / ".nojekyll").write_text("")
    print(f"Built {OUT} (draft={DRAFT})")


if __name__ == "__main__":
    main()
