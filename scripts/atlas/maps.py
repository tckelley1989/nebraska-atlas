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


def map_page(a, level: str) -> dict:
    geo = a.geo_system if level == "system" else a.geo_county
    ids = [i for i in geo["paths"] if i in a.places(level)]
    names = {i: (a.systems_xw[i]["display_name"] if level == "system" else a.counties_xw[i]["name"] + " County") for i in ids}
    href = "system" if level == "system" else "county"
    paths = [{"id": i, "d": simplify(geo["paths"][i]), "name": names[i], "href": f"{href}/{i}.html"} for i in ids]
    indicators, cls, tab = [], {}, {}
    for row in a.key_eight(level):
        c = classes_for(a, level, row, ids)
        cls[row["key"]] = c
        if row["format"] == "category":
            labels = row["legend"].split("|")
            legend = [{"cls": n, "label": lab, "count": c.count(n)} for n, lab in zip(CATEGORY_CLASSES[row["key"]], labels)]
        else:
            labels = row["legend"].split("|")
            legend = [{"cls": f"{row['ramp']}-{j + 1}", "label": lab, "count": c.count(f"{row['ramp']}-{j + 1}")} for j, lab in enumerate(labels)]
        missing = c.count("na")
        vals = [(a.value(level, i, row["key"]), i) for i in ids]
        ranked = sorted((v, i) for v, i in vals if isinstance(v, (int, float)))
        # table view: raw value (for sorting), shown value and tone, aligned with ids; None where blank
        if row["format"] == "category":
            labels = row["legend"].split("|")
            names_c = CATEGORY_CLASSES[row["key"]]
            tab[row["key"]] = [[None, labels[names_c.index(x)], ""] if x in names_c else None for x in c]
        else:
            tab[row["key"]] = [[round(v, 6), fmt.value(v, row), tone(row, v)] if isinstance(v, (int, float)) else None for v, _ in vals]
        top = [{"name": names[i], "href": f"{href}/{i}.html", "value": fmt.value(v, row), "tone": tone(row, v)} for v, i in reversed(ranked[-5:])]
        bottom = [{"name": names[i], "href": f"{href}/{i}.html", "value": fmt.value(v, row), "tone": tone(row, v)} for v, i in ranked[:5]]
        st = a.stats(level, row["key"])
        indicators.append({
            "key": row["key"], "format": row["format"], "label": row["label"], "short": row["short"], "note": row["note"], "period": row["period"],
            "source": row["source"], "legend": legend, "missing": missing, "missing_label": row["missing_label"],
            "median": fmt.value(st["median"], row) if st["median"] is not None and row["format"] != "category" else None,
            "top": top, "bottom": bottom if row["format"] != "category" else [],
        })
    first = indicators[0]["key"]
    for p, c in zip(paths, cls[first]):
        p["cls"] = c
    return {
        "level": level, "title": "School systems" if level == "system" else "Counties",
        "heading": "School systems" if level == "system" else "Counties",
        "count": len(ids), "noun": "systems" if level == "system" else "counties",
        "view_box": geo["viewBox"], "paths": paths, "indicators": indicators,
        "classes_json": json.dumps({k: v for k, v in cls.items()}, separators=(",", ":")),
        "table_json": json.dumps({"names": [names[i] for i in ids], "href": f"{href}/", "ids": ids, "vals": tab},
                                 ensure_ascii=False, separators=(",", ":")),
    }
