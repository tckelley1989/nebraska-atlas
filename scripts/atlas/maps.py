"""Choropleth map pages, drawn at build time.

Every map uses exactly one registry ramp and always shows its legend (methods spec 8).
Paths carry a class per bin; switching indicators swaps classes, so geometry ships once.
"""
import json
import math
import re

from . import fmt
from .pages import tone

CATEGORY_CLASSES = {"equalized": ["state", "none"]}


def simplify(path: str, tol: float = 1.2, min_area: float = 3.0) -> str:
    out, best = [], None
    for sp in re.findall(r"M[^M]*", path):
        pts = [tuple(map(float, p.split(","))) for p in re.findall(r"-?\d+\.?\d*,-?\d+\.?\d*", sp)]
        if len(pts) < 3:
            continue
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        area = (max(xs) - min(xs)) * (max(ys) - min(ys))
        keep = [pts[0]]
        for p in pts[1:]:
            if math.hypot(p[0] - keep[-1][0], p[1] - keep[-1][1]) >= tol:
                keep.append(p)
        d = _rel(keep)
        if best is None or area > best[0]:
            best = (area, d)
        if area >= min_area and len(keep) >= 3:
            out.append(d)
    return "".join(out) or (best[1] if best else "")


def _rel(pts: list) -> str:
    """A closed ring as one absolute move and relative steps, in tenths of a unit. Steps are taken between the rounded
    points, so rounding never accumulates: every vertex lands where the absolute path put it."""
    r = [(round(x * 10), round(y * 10)) for x, y in pts]
    def num(v: int) -> str:
        t = f"{abs(v) / 10:.1f}".rstrip("0").rstrip(".")
        t = t[1:] if t.startswith("0.") else t  # 0.5 -> .5
        return ("-" if v < 0 else "") + t if v else "0"
    out = [f"M{r[0][0] / 10:.1f},{r[0][1] / 10:.1f}l"]
    for (x0, y0), (x1, y1) in zip(r, r[1:]):
        a, b = num(x1 - x0), num(y1 - y0)
        out.append(a + ("" if b.startswith("-") else ",") + b + " ")
    return "".join(out).rstrip() + "z"


def bin_index(v, breaks: list) -> int:
    return sum(1 for b in breaks if v >= b)


def classes_for(a, level: str, row: dict, ids: list) -> list:
    k = row["key"]
    if row["format"] == "category":
        names = CATEGORY_CLASSES.get(k)
        out = []
        for i in ids:
            b = a.places(level)[i].get("b", {}).get(k)
            out.append(names[b] if names and isinstance(b, int) and b < len(names) else "na")
        return out
    breaks = [float(x) for x in row["breaks"].split("|")]
    out = []
    for i in ids:
        v = a.value(level, i, k)
        out.append(f"{row['ramp']}-{bin_index(v, breaks) + 1}" if isinstance(v, (int, float)) else "na")
    return out


def names_for(a, level: str) -> dict:
    return {i: (a.systems_xw[i]["display_name"] if level == "system" else a.counties_xw[i]["name"] + " County") for i in a.places(level)}


def geo_ids(a, level: str) -> list:
    geo = a.geo_system if level == "system" else a.geo_county
    return [i for i in geo["paths"] if i in a.places(level)]


def geo_js(a, level: str) -> str:
    """Map geometry for one level, shared by every measure page and cached by the browser once. Each page sends only its
    own bin classes, aligned with these ids."""
    geo = a.geo_system if level == "system" else a.geo_county
    ids, names = geo_ids(a, level), names_for(a, level)
    body = {"vb": geo["viewBox"], "ids": ids, "d": [simplify(geo["paths"][i]) for i in ids], "n": [names[i] for i in ids],
            "href": ("system" if level == "system" else "county") + "/"}
    return "window.LEDGER_GEO=" + json.dumps(body, ensure_ascii=False, separators=(",", ":")) + ";"


def section(level: str) -> str:
    return "schools" if level == "system" else "counties"


def measure_href(level: str, key: str) -> str:
    """Where a measure lives: one page per measure, holding its map, table and relationships."""
    return f"{section(level)}/{key}.html"


def has_page(row: dict) -> bool:
    """A category measure gets a page only when it has map classes (equalized); others stay on the profiles."""
    return row["format"] != "category" or row["key"] in CATEGORY_CLASSES


def index(a, level: str) -> dict:
    """Every measure at one level, in registry group order, with the key eight first: the switcher on every measure page."""
    from .pages import GROUP_ORDER
    groups = []
    for g in GROUP_ORDER[level]:
        rows = [r for r in a.registry if r["level"] == level and r["group"] == g and has_page(r)]
        rows.sort(key=lambda r: (r["key_indicator"] != "yes", int(r["key_order"] or 99)))
        if rows:
            groups.append({"name": g, "items": [{"key": r["key"], "short": r["short"], "key_ind": r["key_indicator"] == "yes"} for r in rows]})
    key8 = [{"key": r["key"], "short": r["short"]} for r in a.key_eight(level)]
    return {"groups": groups, "key8": key8, "n": sum(len(g["items"]) for g in groups)}


def measure_map(a, level: str, row: dict) -> dict:
    """One measure across every place: map bin classes, legend, table values, highest and lowest five."""
    ids, names = geo_ids(a, level), names_for(a, level)
    href = "system" if level == "system" else "county"
    c = classes_for(a, level, row, ids)
    labels = row["legend"].split("|")
    if row["format"] == "category":
        names_c = CATEGORY_CLASSES[row["key"]]
        legend = [{"cls": n, "label": lab, "count": c.count(n)} for n, lab in zip(names_c, labels)]
        tab = [[None, labels[names_c.index(x)], ""] if x in names_c else None for x in c]
    else:
        legend = [{"cls": f"{row['ramp']}-{j + 1}", "label": lab, "count": c.count(f"{row['ramp']}-{j + 1}")} for j, lab in enumerate(labels)]
        tab = []
        for i in ids:
            v = a.value(level, i, row["key"])
            tab.append([round(v, 6), fmt.value(v, row), tone(row, v)] if isinstance(v, (int, float)) else None)
    vals = [(a.value(level, i, row["key"]), i) for i in ids]
    ranked = sorted((v, i) for v, i in vals if isinstance(v, (int, float)))
    item = lambda v, i: {"name": names[i], "href": f"{href}/{i}.html", "value": fmt.value(v, row), "tone": tone(row, v)}
    st = a.stats(level, row["key"])
    cat = row["format"] == "category"
    return {
        "legend": legend, "missing": c.count("na"), "missing_label": row["missing_label"],
        "median_v": fmt.value(st["median"], row) if st["median"] is not None and not cat else None,
        "top": [item(v, i) for v, i in reversed(ranked[-5:])] if not cat else [],
        "bottom": [item(v, i) for v, i in ranked[:5]] if not cat else [],
        "count": len(ids),
        "classes_json": json.dumps(c, separators=(",", ":")),
        "table_json": json.dumps(tab, ensure_ascii=False, separators=(",", ":")),
    }
