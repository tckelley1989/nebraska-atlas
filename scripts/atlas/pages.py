"""Page contexts: everything a template needs, computed once from the Atlas object."""
from . import fmt

GROUP_ORDER = {
    "system": ["Aid and formula", "Spending and receipts", "Taxes and levy", "Students and outcomes", "Teachers"],
    "county": ["Work and pay", "People", "Farms", "Local economy", "Schools and taxes"],
}


def tone(row: dict, v) -> str:
    """Text color class for a value: change measures get up/down, levels stay ink (methods spec 8)."""
    if row["scale"] != "diverging" or not isinstance(v, (int, float)) or round(v, 1) == 0:
        return ""
    return "up" if v > 0 else "down"


def tile(a, level: str, place: str, row: dict) -> dict:
    k = row["key"]
    v = a.value(level, place, k)
    rk = a.rank(level, place, k)
    st = a.stats(level, k)
    med = fmt.value(st["median"], row) if st["median"] is not None and row["format"] != "category" else None
    if row["format"] == "category" and level == "system" and k == "equalized":
        n_eq = sum(1 for f in a.formula.values() if (f["equalization_aid"] or 0) > 0)
        rk, med = None, None
        cat_note = f"{n_eq} of {len(a.formula)} systems receive it"
        v = "Yes" if (a.formula[place]["equalization_aid"] or 0) > 0 else "No"
    else:
        cat_note = ""
    return {
        "cat_note": cat_note, "key": k, "label": row["label"], "short": row["short"], "value": v if isinstance(v, str) else fmt.value(v, row, a.text(level, place, k)),
        "tone": tone(row, v), "rank": f"{fmt.ordinal(rk[0])} highest of {rk[1]}" if rk else "",
        "pos": rk[2] if rk else None, "median": med, "categorical": row["format"] == "category",
        "source": row["source"], "period": row["period"], "note": row["note"],
    }


def grouped(a, level: str, place: str, extra=None) -> list:
    out = []
    for g in GROUP_ORDER[level]:
        rows = [r for r in a.registry if r["level"] == level and r["group"] == g]
        items = []
        for r in rows:
            t = tile(a, level, place, r)
            if extra:
                t.update(extra(r))
            items.append(t)
        out.append({"name": g, "items": items})
    return out


def system_page(a, code: str) -> dict:
    xw = a.systems_xw[code]
    rec = a.system_js["districts"][code]
    f = a.formula[code]
    stu = f["formula_students"]
    tot = {k: sum((a.formula[c][k] or 0) for c in a.formula) for k in ("formula_students", "formula_need", "equalization_aid", "calculated_aid")}
    allps = lambda k: fmt.money(tot[k] / tot["formula_students"])
    ps = lambda x: fmt.money(x / stu) if stu else "n/a"
    steps = [
        ("Formula need", "formula_need", allps("formula_need"), "need"),
        ("Local effort, $1.00 per $100 of adjusted valuation", "local_effort", "", "res"),
        ("Other receipts", "other_receipts", "", "res"),
        ("Allocated income tax", "income_tax_rebate", "", "res"),
        ("Net option enrollment funding", "option_funding", "", "res"),
        ("Community achievement plan aid", "cap_aid", "", "res"),
        ("Foundation aid counted as a resource", "foundation_aid", "", "res"),
        ("Total resources", "total_resources", "", "total"),
        ("Equalization aid: need minus resources, if positive", "equalization_aid", allps("equalization_aid"), "total"),
        ("Foundation aid outside resources", "foundation_out", "", "aid"),
        ("Total TEEOSA aid", "calculated_aid", allps("calculated_aid"), "total"),
    ]
    table = []
    n = 0
    for label, k, allv, kind in steps:
        x = f.get(k) or 0
        if kind == "res" and x == 0 and k in ("option_funding", "cap_aid"):
            continue
        n += 1
        table.append({"n": n, "label": label, "dollars": fmt.money(x), "ps": ps(x), "all": allv, "bold": kind in ("need", "total")})
    need = f["formula_need"] or 0
    segs = []
    if need > 0:
        for label, k, cls in (("Local effort", "local_effort", "s1"), ("Other resources", None, "s2"), ("Equalization aid", "equalization_aid", "eq")):
            x = (f["total_resources"] - f["local_effort"]) if k is None else (f[k] or 0)
            if x > 0:
                segs.append({"label": label, "amount": fmt.big_money(x), "pct": round(100 * min(x, need) / max(need, f["total_resources"]), 1), "cls": cls})
    base = a.cert.get(code, {}).get(2019)
    now = a.cert.get(code, {}).get(a.aid_year)
    since = []
    if base and now:
        d0, d1 = a.school_year_deflator(2019), a.school_year_deflator(a.aid_year)
        v0, v1 = a.calendar_deflator(2018), a.calendar_deflator(a.aid_year - 1)
        pairs = [
            ("Formula students", base["formula_students"], now["formula_students"], lambda x: f"{x:,.0f}"),
            ("Adjusted valuation, 2019 dollars", base["teeosa_adjusted_valuation"] * v0, now["teeosa_adjusted_valuation"] * v1, fmt.money),
            ("Formula need per student, 2019 dollars", base["formula_need"] / base["formula_students"] * d0, now["formula_need"] / now["formula_students"] * d1, fmt.money),
            ("TEEOSA aid per formula student, 2019 dollars", base["total_state_aid"] / base["formula_students"] * d0, now["total_state_aid"] / now["formula_students"] * d1, fmt.money),
        ]
        for label, x0, x1, f_ in pairs:
            ch = (x1 / x0 - 1) * 100 if x0 else None
            since.append({"label": label, "base": f_(x0), "now": f_(x1), "change": fmt.pct_change(ch) if ch is not None else "n/a",
                          "tone": "" if ch is None or round(ch, 1) == 0 else ("up" if ch > 0 else "down")})
    return {
        "code": code, "name": xw["display_name"], "counties": xw["counties"], "towns": xw["towns"].split("|") if xw["towns"] else [],
        "students": f"{stu:,.0f}", "equalized": (f["equalization_aid"] or 0) > 0, "desc": rec.get("desc", ""),
        "tiles": [tile(a, "system", code, r) for r in a.key_eight("system")], "steps": table, "segs": segs,
        "need": fmt.big_money(need), "resources": fmt.big_money(f["total_resources"] or 0), "eq": fmt.big_money(f["equalization_aid"] or 0),
        "aid_year": f"{a.aid_year}-{str(a.aid_year + 1)[2:]}", "since": since, "groups": grouped(a, "system", code),
    }


def county_page(a, fips: str) -> dict:
    xw = a.counties_xw[fips]
    rec = a.county_js["counties"][fips]
    tier = a.county_js["tiers"][xw["tier"]]
    state = a.county_js["tiers"]["state"]
    extra = lambda r: {"tier": tier["d"].get(r["key"]) or "", "state": state["d"].get(r["key"]) or ""}
    tiles = []
    for r in a.key_eight("county"):
        t = tile(a, "county", fips, r)
        t.update(extra(r))
        tiles.append(t)
    systems = sorted((c for c, x in a.systems_xw.items() if xw["name"] in x["counties"].split(", ")), key=lambda c: a.systems_xw[c]["display_name"])
    return {
        "fips": fips, "name": xw["name"] + " County", "tier": a.tier_name(fips), "crop": xw["crop_district_name"],
        "desc": rec.get("desc", ""), "tiles": tiles, "groups": grouped(a, "county", fips, extra),
        "systems": [{"code": c, "name": a.systems_xw[c]["display_name"]} for c in systems],
    }
