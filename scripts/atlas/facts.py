"""Every number the Findings text uses, computed from the bundle at build time.

The findings/*.md files reference these by name ({{ f.credits_gain }}), so no number
in Findings is ever typed by hand (rebuild plan: narrative separated from data).
"""
import csv
import math
from collections import defaultdict

from . import fmt


def _spearman(xs, ys):
    def rank(x):
        o = sorted(range(len(x)), key=lambda i: x[i])
        r = [0.0] * len(x)
        i = 0
        while i < len(o):
            j = i
            while j + 1 < len(o) and x[o[j + 1]] == x[o[i]]:
                j += 1
            for k in range(i, j + 1):
                r[o[k]] = (i + j) / 2 + 1
            i = j + 1
        return r
    rx, ry = rank(xs), rank(ys)
    n = len(rx)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((u - mx) * (v - my) for u, v in zip(rx, ry))
    return cov / math.sqrt(sum((u - mx) ** 2 for u in rx) * sum((v - my) ** 2 for v in ry))


def _corr(a, ykey, xkey):
    pairs = [(d["v"].get(ykey), d["v"].get(xkey)) for d in a.system_js["districts"].values()]
    pairs = [(y, x) for y, x in pairs if isinstance(y, (int, float)) and isinstance(x, (int, float))]
    ys, xs = zip(*pairs)
    return _spearman(list(ys), list(xs)), len(pairs)


def money_m(x):
    return f"${x / 1e6:,.0f} million"


def build(a) -> dict:
    S = defaultdict(dict)
    with open(a_bundle(a, "statewide.csv"), newline="") as fh:
        for r in csv.DictReader(fh):
            S[(r["topic"], r["measure"])][r["school_year"]] = float(r["value"]) if r["value"] else None
    sm = lambda m, y: S[("school_money", m)][y]
    ts = lambda m, y: S[("teeosa_statewide", m)][y]
    ptr = lambda m, y: S[("property_tax_request", m)][y]
    defl = {r["school_year"]: float(r["school_year_deflator"]) for r in a.deflators.values() if r["school_year_deflator"]}
    y0, y1 = "2019-20", max(y for y in S[("school_money", "gf_total")])
    a0 = "2019-20"
    a1 = max(y for y in S[("teeosa_statewide", "aid")])
    b_years = sorted(S[("property_tax_request", "board_votes")])
    b0, b1 = b_years[0], b_years[-1]
    adm = lambda y: sm("adm", y)
    ps19 = lambda m, y: sm(m, y) / adm(y) * defl[y]
    tiers = a.county_js["tiers"]
    tv = lambda t, k: tiers[t]["d"].get(k)
    counties = a.county_js["counties"].values()
    f = {
        "money_year": y1, "aid_year": a1, "budget_year": b1, "budget_first": b0,
        "credits_gain": money_m(sm("gf_credits", y1) - sm("gf_credits", y0)),
        "aid_gain": money_m(sm("gf_teeosa", y1) - sm("gf_teeosa", y0)),
        "credits_gain_raw": sm("gf_credits", y1) - sm("gf_credits", y0),
        "aid_gain_raw": sm("gf_teeosa", y1) - sm("gf_teeosa", y0),
        "share0": f"{sm('state_share', y0):.1f}%", "share1": f"{sm('state_share', y1):.1f}%",
        "share_xc0": f"{sm('state_share_xc', y0):.1f}%", "share_xc1": f"{sm('state_share_xc', y1):.1f}%",
        "share_raw": (sm("state_share", y0), sm("state_share", y1), sm("state_share_xc", y0), sm("state_share_xc", y1)),
        "net_fell": sum(1 for c in counties if (c["v"].get("ptax_net_real_change") or 0) < 0),
        "n_counties": len(a.county_js["counties"]),
        "net_rural": tv("rural", "ptax_net_real_change"), "net_metro": tv("metro", "ptax_net_real_change"),
        "net_state": tv("state", "ptax_net_real_change"),
        "levied_rural": tv("rural", "ptax_real_change"), "levied_metro": tv("metro", "ptax_real_change"),
        "levied_state": tv("state", "ptax_real_change"), "credit_share_state": tv("state", "ptax_credit_share"),
        "credit_share_rural": tv("rural", "ptax_credit_share"), "credit_share_metro": tv("metro", "ptax_credit_share"),
        "aid_change_dollars": money_m(ts("aid", a1) - ts("aid", a0)),
        "eq0": money_m(ts("eq", a0)), "eq1": money_m(ts("eq", a1)), "foundation1": money_m(ts("foundation", a1)),
        "equalized0": f"{ts('equalized', a0):.0f}", "equalized1": f"{ts('equalized', a1):.0f}",
        "votes0": f"{ptr('board_votes', b0):.0f}", "votes1": f"{ptr('board_votes', b1):.0f}",
        "atcap0": f"{ptr('at_cap', b0):.0f}", "atcap1": f"{ptr('at_cap', b1):.0f}",
        "districts1": f"{ptr('districts', b1):.0f}", "unused1": money_m(ptr("unused", b1)),
        "request0": f"${ptr('request', b0) / 1e9:,.2f} billion", "request1": f"${ptr('request', b1) / 1e9:,.2f} billion",
        "request_growth": fmt.signed((ptr("request", b1) / ptr("request", b0) - 1) * 100, 1, "%"),
        "requests_by_year": [{"year": y, "votes": ptr("board_votes", y), "atcap": ptr("at_cap", y)} for y in b_years],
        "ppc_change": fmt.signed((S[("per_pupil_cost", "state_local")][y1] * defl[y1] / (S[("per_pupil_cost", "state_local")][y0] * defl[y0]) - 1) * 100, 1, "%"),
        "credits_ps0": fmt.money(((sm("credits", y0) or 0) + (sm("lb1107", y0) or 0)) / adm(y0) * defl[y0]),
        "credits_ps1": fmt.money(((sm("credits", y1) or 0) + (sm("lb1107", y1) or 0)) / adm(y1) * defl[y1]),
        "local_ps0": fmt.money(ps19("local", y0)), "local_ps1": fmt.money(ps19("local", y1)),
        "pop_metro": tv("metro", "pop_change"), "pop_micro": tv("micro", "pop_change"), "pop_rural": tv("rural", "pop_change"),
        "pop_state": tv("state", "pop_change"),
        "pop_lost": sum(1 for c in counties if (c["v"].get("pop_change") or 0) < 0),
        "wage_rural": tv("rural", "aww_real_change"), "wage_metro": tv("metro", "aww_real_change"),
        "inc_rural": tv("rural", "pcpi_real_change"), "inc_metro": tv("metro", "pcpi_real_change"),
    }
    cc = {}
    with open(a_bundle(a, "property_taxes.csv"), newline="") as fh:
        for r in csv.DictReader(fh):
            if r["fips"] == "31000" and r["authority"] == "community_college":
                cc[int(r["tax_year"])] = float(r["taxes_levied"])
    cc_last = max(cc)
    f["cc_tax0"], f["cc_tax1"], f["cc_year1"] = money_m(cc[2019]), money_m(cc[cc_last]), cc_last
    for key, subj in (("ela", "nscas_ela"), ("math", "nscas_math")):
        for x in ("poverty_ps", "ppc_adm", "aid_ps"):
            r, n = _corr(a, subj, x)
            f[f"r_{key}_{x}"] = fmt.signed(r, 2) if round(r, 2) != 0 else "0.00"
            f[f"n_{key}"] = n
    return f


def a_bundle(a, name):
    from .data import BUNDLE
    return BUNDLE / name
