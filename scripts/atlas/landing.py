"""How it works page (from the approved mockup "Landing"): the background every measure page assumes. Every figure is computed
here from the bundle; the worked examples are generated from certification fields and tested against the certified total."""
import csv
import statistics as st

from . import fmt
from .about import terms
from .data import BUNDLE
from .dive import Ptax, formula_parts, short_name, esc, INK, SUB, RULE, LOCAL, TAN, SLATE

EXAMPLES = [("24-0001", "receives equalization aid"), ("01-0090", "no equalization aid")]
START = [("system", "aid_ps"), ("county", "ptax_net_real_change"), ("system", "lc2_limit_levy")]


def big(x: float) -> str:
    return f"${x / 1e9:,.2f} billion" if abs(x) >= 1e9 else f"${x / 1e6:,.0f} million"


def _csv(p):
    with open(p, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def need_bars(f: dict) -> str:
    """Need against resources for one system; the gap, where there is one, is equalization aid."""
    need, res, eq, le = f["need"], f["res"], f["eq"], f["le"]
    top = max(need, res); W = 330; X = lambda v: v / top * W
    s = [f'<svg class="dchart nb" viewBox="0 0 {W + 330} 96" role="img" aria-label="Formula need against formula resources">',
         f'<text x="0" y="22" font-size="12.5" font-weight="700" fill="{INK}">Need</text><rect x="80" y="10" width="{X(need):.1f}" height="18" fill="{INK}"/>'
         f'<text x="{80 + X(need) + 6:.0f}" y="24" font-size="12" fill="{INK}">{big(need)}</text>',
         f'<text x="0" y="56" font-size="12.5" font-weight="700" fill="{INK}">Resources</text>'
         f'<rect x="80" y="44" width="{X(le):.1f}" height="18" fill="{LOCAL}"/><rect x="{80 + X(le):.1f}" y="44" width="{X(res - le):.1f}" height="18" fill="{TAN}"/>']
    if eq > 0:
        s.append(f'<rect x="{80 + X(res):.1f}" y="44" width="{X(eq):.1f}" height="18" fill="{SLATE}"/>'
                 f'<text x="{80 + X(need) + 6:.0f}" y="58" font-size="12" fill="{INK}">gap: {big(eq)} equalization aid</text>')
    else:
        s.append(f'<text x="{80 + X(res) + 6:.0f}" y="58" font-size="12" fill="{INK}">{big(res)}, more than need</text>')
    s.append(f'<rect x="80" y="76" width="10" height="10" fill="{LOCAL}"/><text x="94" y="85" font-size="11.5" fill="{SUB}">Local effort</text>'
             f'<rect x="170" y="76" width="10" height="10" fill="{TAN}"/><text x="184" y="85" font-size="11.5" fill="{SUB}">Other resources</text>'
             + (f'<rect x="290" y="76" width="10" height="10" fill="{SLATE}"/><text x="304" y="85" font-size="11.5" fill="{SUB}">Equalization aid</text>' if eq > 0 else ""))
    return "".join(s) + "</svg>"


def example(a, code: str, status: str) -> dict:
    f = formula_parts(a, code)
    xw = a.systems_xw[code]
    lep = {c: a.value("system", c, "lep_ps") for c in a.formula}
    lep_rank = 1 + sum(1 for v in lep.values() if isinstance(v, (int, float)) and v > (lep[code] or 0))
    aid_ps = a.value("system", code, "aid_ps"); med = a.stats("system", "aid_ps")["median"]
    paid_twice = {"Allocated income tax", "Option funding", "CAP aid", "Foundation aid, 60% counted"}
    return {"code": code, "name": xw["display_name"], "short": short_name_from(xw["display_name"]), "where": f'{xw["counties"]} · {status}',
            "stu": f'{f["stu"]:,.0f}', "bars": need_bars(f),
            "need_parts": [(n, fmt.money(v)) for n, v in f["need_parts"]], "need": fmt.money(f["need"]),
            "res_parts": [(n, fmt.money(v), n in paid_twice) for n, v in f["res_parts"]], "res": fmt.money(f["res"]),
            "eq": fmt.money(f["eq"]), "aid_parts": [(n, fmt.money(v)) for n, v in f["aid_parts"]], "aid": fmt.money(f["aid"]),
            "cert": f["cert"], "aid_raw": f["aid"], "f": f, "cover": f["res"] / f["need"] if f["need"] else 0,
            "lep_ps": fmt.money(lep[code] or 0), "lep_rank": lep_rank, "aid_ps": fmt.money(aid_ps), "median": fmt.money(med)}


def short_name_from(n: str) -> str:
    for suf in (" Public Schools", " Community Schools", " Community School", " Public School"):
        n = n.replace(suf, "")
    return n


def build(a) -> dict:
    F = a.formula
    T = {k: sum((r[k] or 0) for r in F.values()) for k in ("formula_need", "total_resources", "equalization_aid", "foundation_aid", "foundation_out", "calculated_aid")}
    n_eq = sum(1 for r in F.values() if (r["equalization_aid"] or 0) > 0)
    cert = [c[a.aid_year] for c in a.cert.values() if a.aid_year in c]
    sav = sum(c["teeosa_adjusted_valuation"] or 0 for c in cert); tv = sum(c["taxable_value_prior_october"] or 0 for c in cert)
    lex = EXAMPLES[0][0]
    ex = [example(a, c, s) for c, s in EXAMPLES]
    # property taxes, all counties, 2019 dollars
    p = Ptax(a)
    agg = {k: sum(x[k] for x in p.f.values()) for k in ("v0", "v1", "t0", "t1", "c0", "c1")}
    real = lambda v, y1: v * (p.d1 if y1 else p.d0)
    v0, v1 = real(agg["v0"], 0), real(agg["v1"], 1); l0, l1 = real(agg["t0"], 0), real(agg["t1"], 1)
    n0, n1 = l0 - real(agg["c0"], 0), l1 - real(agg["c1"], 1)
    r0, r1 = l0 / v0 * 100, l1 / v1 * 100; k0, k1 = n0 / l0, n1 / l1
    chg = lambda x0, x1: x1 / x0 - 1
    meth = lambda y: set().union(*[m for (yy, _), m in p.methods.items() if yy == y])
    credit_note = " ".join(
        f"County credits for tax year {y} are {'estimates, split to counties from statewide totals' if 'estimated' in meth(y) else 'Revenue certifications'}."
        for y in (p.y0, p.y1))
    ptax_rows = [("Taxable valuation", big(v0), big(v1), chg(v0, v1), False), ("× Tax rate, per $100 of taxable valuation", f"${r0:.2f}", f"${r1:.2f}", chg(r0, r1), False),
                 ("= Taxes levied", big(l0), big(l1), chg(l0, l1), True), ("× Share left after credits", f"{100 * k0:.1f}%", f"{100 * k1:.1f}%", chg(k0, k1), False),
                 ("= Taxes after credits", big(n0), big(n1), chg(n0, n1), True)]
    ptax_rows = [(lab, x0, x1, fmt.signed(100 * c, 1, "%"), "down" if c < 0 else "up", b) for lab, x0, x1, c, b in ptax_rows]
    # budgets and credits
    L = _csv(BUNDLE / "lc2_budgets.csv"); by = max(r["budget_year"] for r in L); cur = [r for r in L if r["budget_year"] == by]
    votes = sum(1 for r in cur if float(r["board_vote_added_D140"] or 0) > 0); unused = sum(float(r["unused_D240"] or 0) for r in cur)
    credit_share = (a.county_js["tiers"]["state"]["d"] or {}).get("ptax_credit_share", "")
    # pick a measure
    listing = {}
    for lvl in ("system", "county"):
        groups = []
        from .pages import GROUP_ORDER
        for g in GROUP_ORDER[lvl]:
            rows = [r for r in a.registry if r["level"] == lvl and r["group"] == g and r["format"] != "category"]
            rows.sort(key=lambda r: (r["key_indicator"] != "yes", int(r["key_order"] or 99)))
            groups.append({"name": g, "items": [{"key": r["key"], "short": r["short"], "key_ind": r["key_indicator"] == "yes"} for r in rows]})
        listing[lvl] = {"groups": groups, "n": sum(len(g["items"]) for g in groups)}
    aid_vals = a.stats("system", "aid_ps")["vals"]
    starts = []
    for lvl, k in START:
        row = a.ind[(k, lvl)]
        desc = {"aid_ps": f"Why aid runs from about {fmt.money(round(aid_vals[0], -2))} to {fmt.money(round(aid_vals[-1], -2))} per student across {len(aid_vals)} systems",
                "ptax_net_real_change": "How taxable valuation, rates and credits moved each county's taxes since 2019",
                "lc2_limit_levy": "How levies under the $1.05 limit compare, and why they go with aid"}[k]
        starts.append({"href": f"{lvl}/{k}.html", "title": row["label"], "desc": desc})
    lx, ac = ex
    f_lx = lx["f"]
    return {
        "aid_year": f"{a.aid_year}-{str(a.aid_year + 1)[2:]}", "aid_total": big(T["calculated_aid"]), "need_total": big(T["formula_need"]),
        "res_total": big(T["total_resources"]), "eq_total": big(T["equalization_aid"]), "found_total": big(T["foundation_aid"] + T["foundation_out"]),
        "n_eq": n_eq, "n_sys": len(F), "sav_total": big(sav), "tv_total": big(tv),
        "lex_tv": fmt.money(a.value("system", lex, "tv_ps")), "lex_sav": fmt.money(a.value("system", lex, "val_ps")),
        "examples": ex, "lx": lx, "ac": ac,
        "lx_found": (fmt.money(f_lx["found_in"] + f_lx["found_out"]), fmt.money(f_lx["found_in"]), fmt.money(f_lx["found_out"])),
        "ac_found": fmt.money(ac["f"]["found_in"] + ac["f"]["found_out"]),
        "ptax_rows": ptax_rows, "y0": p.y0, "y1": p.y1, "credit_note": credit_note,
        "budget_year": by, "votes": votes, "n_budgets": len(cur), "unused": big(unused), "credit_share": credit_share,
        "terms": terms(), "listing": listing, "starts": starts,
    }
