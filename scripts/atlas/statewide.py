"""Statewide picture on the school systems page: spending per student, who pays, what moved formula need and the
property tax request cap. Every figure is read from the bundle's statewide.csv, deflators.csv and
school_need_components.csv; every sentence is computed."""
import csv
from collections import defaultdict
from html import escape

from markupsafe import Markup

from .data import BUNDLE

DESK, PHONE = 720, 360
INK, SUB, RULE, STATE = "var(--ink)", "var(--sub)", "var(--rule)", "var(--state)"
NEED = {"basic_funding": "Basic funding", "special_receipts": "Special receipts (incl. special education)",
        "transportation": "Transportation", "poverty": "Poverty", "lep": "Limited English proficiency",
        "system_averaging": "System averaging", "distance_education": "Distance education",
        "elementary_site": "Elementary site", "summer_school": "Summer school", "focus_school": "Focus school",
        "student_growth": "Student growth", "new_school": "New school", "community_achievement": "Community achievement",
        "need_stabilization": "Need stabilization"}


def _csv(name):
    with open(BUNDLE / name, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def sy(y: int) -> str:
    return f"{y}-{(y + 1) % 100:02d}"


def money(v, d=0):
    return f"${v:,.{d}f}"


def mil(v):
    return f"${v / 1e6:,.0f}M" if abs(v) < 1e9 else f"${v / 1e9:,.2f}B"


def pct(v, d=1):
    return f"{v:.{d}f}%"


def moved(v, d=1):
    return f"{'rose' if v >= 0 else 'fell'} {abs(v):.{d}f}%"


def chg(v, d=1):
    return ("+" if v >= 0 else "−") + f"{abs(v):.{d}f}%"


def line_chart(years: list, series: list, W: int, fmt_tick, title: str) -> str:
    """series: [(label, values, dashed)]. Direct labels at the right end; solid and dashed lines tell the two apart
    without color."""
    phone = W < 500
    H = 250 if phone else 280
    L, R, T, B = (48 if phone else 64), (128 if phone else 190), 16, 34
    vals = [v for _, vs, _ in series for v in vs if v is not None]
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.12 or abs(hi) * 0.1
    lo, hi = lo - pad, hi + pad
    import math
    step = 10 ** math.floor(math.log10((hi - lo) / 4))
    step *= next(m for m in (1, 2, 2.5, 5, 10) if (hi - lo) / (step * m) <= 5)
    ticks = [step * k for k in range(math.ceil(lo / step), math.floor(hi / step) + 1)]
    X = lambda i: L + (W - L - R) * (i / (len(years) - 1) if len(years) > 1 else 0.5)
    Y = lambda v: T + (H - T - B) * (1 - (v - lo) / (hi - lo))
    fs = 12.5 if phone else 12.5
    s = [f'<svg class="dchart" viewBox="0 0 {W} {H}" role="img" aria-label="{escape(title)}">']
    for t in ticks:
        s.append(f'<line x1="{L}" x2="{W - R}" y1="{Y(t):.1f}" y2="{Y(t):.1f}" stroke="{RULE}"/>'
                 f'<text x="{L - 6}" y="{Y(t) + 4:.1f}" text-anchor="end" font-size="{fs}" fill="{SUB}">{fmt_tick(t)}</text>')
    every = 2 if phone and len(years) > 5 else 1
    for i, y in enumerate(years):
        if i % every == 0 or i == len(years) - 1:
            s.append(f'<text x="{X(i):.1f}" y="{H - 12}" text-anchor="middle" font-size="{fs}" fill="{SUB}">{escape(y)}</text>')
    ends = []
    for k, (label, vs, dashed) in enumerate(series):
        col = INK if k == 0 else STATE
        pts = [(X(i), Y(v)) for i, v in enumerate(vs) if v is not None]
        d = "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        s.append(f'<path d="{d}" fill="none" stroke="{col}" stroke-width="2.5"{" stroke-dasharray=\"7 5\"" if dashed else ""}/>')
        for x, y in pts:
            s.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{col}"/>')
        ends.append([pts[-1][1], label, fmt_tick(vs[-1]), col])
    ends.sort()
    for i in range(1, len(ends)):  # keep end labels from overlapping
        ends[i][0] = max(ends[i][0], ends[i - 1][0] + (30 if phone else 34))
    for y, label, v, col in ends:
        s.append(f'<text x="{W - R + 8}" y="{y - 2:.1f}" font-size="{fs}" font-weight="700" fill="{col}">{escape(v)}</text>'
                 f'<text x="{W - R + 8}" y="{y + fs:.1f}" font-size="{fs - 1}" fill="{SUB}">{escape(label)}</text>')
    s.append("</svg>")
    return "".join(s)


def change_bars(rows: list, W: int, title: str) -> str:
    """rows: [(label, change)] per formula student. Bars run right for a rise and left for a fall from a zero line;
    every bar carries its signed value, so direction never rests on color."""
    phone = W < 500
    lab = 0 if phone else 260
    rowh = 50 if phone else 34
    H = 10 + rowh * len(rows)
    mx = max(abs(v) for _, v in rows)
    lo = min(0, min(v for _, v in rows))
    span = W - lab - (64 if phone else 80) - (46 if lo < 0 else 0)
    zero = lab + (46 if lo < 0 else 0) + span * (-lo) / (max(v for _, v in rows) - lo if max(v for _, v in rows) > lo else 1)
    unit = span / (max(0, max(v for _, v in rows)) - lo or 1)
    H += 10
    s = [f'<svg class="dchart" viewBox="0 0 {W} {H}" role="img" aria-label="{escape(title)}">']
    for i, (label, v) in enumerate(rows):
        total = i == len(rows) - 1
        y = 10 + i * rowh + (16 if phone else 0) + (10 if total else 0)
        if total:
            s.append(f'<line x1="0" x2="{W}" y1="{y - (22 if phone else 9)}" y2="{y - (22 if phone else 9)}" stroke="{RULE}"/>')
        s.append(f'<line x1="{zero:.1f}" x2="{zero:.1f}" y1="{y - 4}" y2="{y + 22}" stroke="{INK}" stroke-width="1.2"/>')
        fw = ' font-weight="700"' if total else ""
        if phone:
            s.append(f'<text x="0" y="{y - 6}" font-size="13"{fw} fill="{INK}">{escape(label)}</text>')
        else:
            s.append(f'<text x="{lab - 12}" y="{y + 13}" text-anchor="end" font-size="13"{fw} fill="{INK}">{escape(label)}</text>')
        w = max(1.5, abs(v) * unit)
        x = zero if v >= 0 else zero - w
        txt = ("+" if v >= 0 else "−") + money(abs(v))
        tx, anchor = (x + w + 6, "start") if v >= 0 else (x - 6, "end")
        s.append(f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="18" fill="{INK if total else STATE}"/>'
                 f'<text x="{tx:.1f}" y="{y + 14}" text-anchor="{anchor}" font-size="12.5" font-weight="700" fill="{INK}">{txt}</text>')
    s.append("</svg>")
    return "".join(s)


def build(a) -> dict:
    S = defaultdict(dict)
    for r in _csv("statewide.csv"):
        if r["value"] not in ("", None):
            S[(r["topic"], r["measure"])][int(r["school_year"][:4])] = float(r["value"])
    D = {int(r["school_year"][:4]): float(r["school_year_deflator"]) for r in _csv("deflators.csv") if r["school_year_deflator"]}
    secs = []

    # 1. spending per student (NDE per pupil cost, ADM)
    tot, sl, fed = S[("per_pupil_cost", "total")], S[("per_pupil_cost", "state_local")], S[("per_pupil_cost", "federal")]
    ys = sorted(tot)
    real = lambda d, y: d[y] * D[y]
    y0, y1 = (2019 if 2019 in ys else ys[0]), ys[-1]
    lead = (f"Schools spent {money(tot[y1])} per student in {sy(y1)}, NDE's per pupil cost including federal money. After inflation "
            f"that {moved(100 * (real(tot, y1) / real(tot, y0) - 1))} from {sy(y0)}. The state and local part, "
            f"{money(sl[y1])}, {moved(100 * (real(sl, y1) / real(sl, y0) - 1))} after inflation; federal money per student "
            f"fell from {money(fed[ys[-2]])} to {money(fed[y1])} in {sy(y1)} as pandemic relief ended.")
    series = [("Total", [real(tot, y) for y in ys], False), ("State and local", [real(sl, y) for y in ys], True)]
    tick = lambda v: f"${v / 1000:.1f}K" if v < 1e5 else money(v)
    rows = [[sy(y), money(sl[y]), money(fed[y]), money(tot[y]), money(real(sl, y)), money(real(tot, y))] for y in ys]
    secs.append({"id": "spending", "title": "What schools spend per student", "lead": lead,
                 "desk": Markup(line_chart([sy(y) for y in ys], series, DESK, tick, "Per pupil cost, 2019 dollars")),
                 "phone": Markup(line_chart([sy(y) for y in ys], series, PHONE, tick, "Per pupil cost, 2019 dollars")),
                 "axis": "Per student (average daily membership), 2019 dollars",
                 "head": ["School year", "State and local", "Federal", "Total", "State and local, 2019 $", "Total, 2019 $"], "rows": rows,
                 "note": "NDE's per pupil cost as published: adjusted current expense plus 3% of the value of buildings and contents, "
                         "divided by average daily membership. Capital outlay, debt service, pre-school, community services and adult "
                         "education are left out. Federal spending is in it from 2018-19. 2019 dollars use the Midwest CPI averaged over "
                         "each school year, September to August. Source: Nebraska Department of Education per pupil cost reports."})

    # 2. who pays: General Fund receipts by source
    m = lambda k: S[("school_money", k)]
    ys = sorted(m("state_share"))
    y0, y1 = (2019 if 2019 in ys else ys[0]), ys[-1]
    lead = (f"State sources were {pct(m('state_share')[y1])} of districts' General Fund receipts in {sy(y1)}, up from "
            f"{pct(m('state_share')[y0])} in {sy(y0)}. Counting property tax credits as local money, since they pay part of a tax "
            f"the school board levies, the state share was {pct(m('state_share_xc')[y1])}, against {pct(m('state_share_xc')[y0])}. "
            f"So {(m('state_share')[y1] - m('state_share')[y0]) - (m('state_share_xc')[y1] - m('state_share_xc')[y0]):.1f} of the "
            f"{m('state_share')[y1] - m('state_share')[y0]:.1f}-point rise is credits, which LB 34 moved onto tax statements in {sy(y1)}. TEEOSA aid was "
            f"{pct(m('teeosa_share')[y1])} of receipts, against {pct(m('teeosa_share')[y0])}.")
    series = [("State, as reported", [m("state_share")[y] for y in ys], False),
              ("State, credits as local", [m("state_share_xc")[y] for y in ys], True)]
    rows = [[sy(y), pct(m("local_share")[y] + m("county_esu_share")[y]), pct(m("federal_share")[y]), pct(m("teeosa_share")[y]),
             pct(m("state_share_xc")[y]), pct(m("state_share")[y]), mil(m("gf_total")[y]), mil(m("gf_credits")[y])] for y in ys]
    secs.append({"id": "who-pays", "title": "Who pays for schools", "lead": lead,
                 "desk": Markup(line_chart([sy(y) for y in ys], series, DESK, lambda v: f"{v:.0f}%", "State share of General Fund receipts")),
                 "phone": Markup(line_chart([sy(y) for y in ys], series, PHONE, lambda v: f"{v:.0f}%", "State share of General Fund receipts")),
                 "axis": "State share of districts' General Fund receipts",
                 "head": ["School year", "Local, county and ESU", "Federal", "TEEOSA aid", "State, credits as local", "State",
                          "General Fund receipts", "of which credits"], "rows": rows,
                 "note": "General Fund receipts as districts report them in NDE's Annual Financial Reports: local sources (01000), county "
                         "and ESU (02000), state sources (03000) and federal sources (04000), each over their sum. Credits are account "
                         "03131. The LB 1107 income tax credit went to taxpayers, so districts booked it as local taxes, and it stays local "
                         "here. Source: Nebraska Department of Education, Annual Financial Reports."})

    # 3. what moved formula need, per formula student, 2019 dollars
    amt, stu = defaultdict(lambda: defaultdict(float)), defaultdict(dict)
    for r in _csv("school_need_components.csv"):
        y = int(r["aid_year"])
        amt[y][r["component"]] += float(r["amount"] or 0)
        stu[y][r["system"]] = float(r["formula_students"] or 0)
    ys = sorted(amt)
    y0, y1 = ys[0], ys[-1]
    st = {y: sum(stu[y].values()) for y in ys}
    per = lambda y, c: amt[y][c] / st[y] * D[y]
    need = lambda y: sum(amt[y].values()) / st[y] * D[y]
    comp = sorted(NEED, key=lambda c: -(per(y1, c)))
    big = [c for c in comp if per(y1, c) >= 100 or per(y0, c) >= 100]
    rest = [c for c in comp if c not in big]
    moves = sorted(NEED, key=lambda c: -abs(per(y1, c) - per(y0, c)))
    top = moves[0]
    lead = (f"Formula need was {money(need(y1))} per formula student in the {sy(y1)} aid year, in 2019 dollars, against "
            f"{money(need(y0))} in {sy(y0)} ({chg(100 * (need(y1) / need(y0) - 1))}). "
            f"{NEED[top]} moved most: {money(per(y0, top))} to {money(per(y1, top))}, up {money(per(y1, top) - per(y0, top))}, "
            f"while need as a whole rose {money(need(y1) - need(y0))}. The other components together "
            f"{'fell ' + money(abs(other)) if (other := (need(y1) - need(y0)) - (per(y1, top) - per(y0, top))) < 0 else 'rose ' + money(other)}.")
    bars = [(NEED[c], per(y1, c) - per(y0, c)) for c in big]
    if rest:
        bars.append(("Everything else", sum(per(y1, c) - per(y0, c) for c in rest)))
    bars.sort(key=lambda r: -r[1])
    bars.append(("Formula need", need(y1) - need(y0)))
    rows = [[NEED[c], money(per(y0, c)), money(per(y1, c)), money(per(y1, c) - per(y0, c), 0).replace("$-", "−$")] for c in comp]
    rows.append(["Formula need", money(need(y0)), money(need(y1)), money(need(y1) - need(y0)).replace("$-", "−$")])
    secs.append({"id": "need", "title": "What moved formula need", "lead": lead,
                 "desk": Markup(change_bars(bars, DESK, "Change in formula need per formula student by component")),
                 "phone": Markup(change_bars(bars, PHONE, "Change in formula need per formula student by component")),
                 "axis": f"Change per formula student, {sy(y0)} to {sy(y1)} aid year, 2019 dollars",
                 "head": ["Component", f"{sy(y0)} aid", f"{sy(y1)} aid", "Change"], "rows": rows, "total_last": True,
                 "note": f"TEEOSA formula need from NDE's certification workbooks, summed over every system and divided by formula "
                         f"students statewide ({st[y0]:,.0f} in {sy(y0)}, {st[y1]:,.0f} in {sy(y1)}), in 2019 dollars with the Midwest CPI. "
                         f"Corrections are folded into the allowance they correct; the components add exactly to formula need. Source: "
                         f"Nebraska Department of Education, TEEOSA state aid certification."})

    # 4. the property tax request cap (LC-2)
    p = lambda k: S[("property_tax_request", k)]
    ys = sorted(p("request"))
    y0, y1 = ys[0], ys[-1]
    lead = (f"For {sy(y1)}, districts requested {mil(p('request')[y1])} in property taxes against {mil(p('authority')[y1])} of "
            f"authority, leaving {mil(p('unused')[y1])} unused. Requests {moved(100 * (p('request')[y1] / p('request')[y0] - 1))} "
            f"from {sy(y0)}, the cap's first budget year, while authority {moved(100 * (p('authority')[y1] / p('authority')[y0] - 1))}. "
            f"{p('board_votes')[y1]:.0f} of {p('districts')[y1]:.0f} boards used a 70% vote to add authority, and {p('at_cap')[y1]:.0f} "
            f"requested within 1% of their limit, down from {p('at_cap')[y0]:.0f}.")
    series = [("Authority", [p("authority")[y] for y in ys], False), ("Requested", [p("request")[y] for y in ys], True)]
    rows = [[sy(y), mil(p("authority_base")[y]), mil(p("board_added")[y]), mil(p("voter_added")[y] + p("override_added")[y]),
             mil(p("authority")[y]), mil(p("request")[y]), mil(p("unused")[y]), f"{p('board_votes')[y]:.0f}", f"{p('at_cap')[y]:.0f}"] for y in ys]
    secs.append({"id": "request-cap", "title": "The property tax request cap", "lead": lead,
                 "desk": Markup(line_chart([sy(y) for y in ys], series, DESK, lambda v: f"${v / 1e9:.1f}B", "Authority and request")),
                 "phone": Markup(line_chart([sy(y) for y in ys], series, PHONE, lambda v: f"${v / 1e9:.1f}B", "Authority and request")),
                 "axis": "All districts, current dollars, budget year",
                 "head": ["Budget year", "Base authority", "Board vote", "Voters or override", "Total authority", "Requested", "Unused",
                          "Board votes", "Within 1% of limit"], "rows": rows,
                 "note": "From NDE's LC-2 budget forms under LB 243 (2023). The request covers the general fund and special building "
                         "fund; bond levies are outside it. Authority a board adds by a 70% vote counts whether or not the district then "
                         "requests it, so part of what is unused is authority a board added and left unrequested. Source: Nebraska "
                         "Department of Education, LC-2 property tax request forms."})
    return {"statewide": secs}
