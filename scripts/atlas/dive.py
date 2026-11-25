"""Deeper dive: one page per measure, five steps (design doc "Deeper Dive: Design").

1 What's normal: every place by group (size band or tier), median and middle half.
2 Kind of place: the group table.
3 Why, by design: the mechanism from the measure's families (registry/mechanisms.csv), with a chart where the
  arithmetic has one: the TEEOSA formula (s01) or the property tax identity (c07).
4 What else goes with it: Spearman against every other measure, families set aside, Holm at 5%, at least half the
  places, within-group check, holding results first (methods section 5).
5 Up close: a scatter against the strongest result that holds.

Charts are drawn here, at build, in a desktop and a phone width. The selected place (?sel=) is marked by
assets/dive.js from data embedded in the page."""
import csv
import hashlib
import json
import math
import statistics as st

from . import fmt
from .data import BUNDLE, REG

INK, SUB, RULE, CARD, GROUND = "#2c2c2c", "#5e5a54", "#ddd5c8", "#fbf8f3", "#f3eee6"
RUST, SLATE, TAN, LOCAL = "#c1432e", "#4b6777", "#ce9e62", "#8a847b"
DOT = "#a87638"
SIZE_BANDS = [(0, 200, "Under 200"), (200, 500, "200 to 499"), (500, 1000, "500 to 999"), (1000, 5000, "1,000 to 4,999"), (5000, 1e12, "5,000 or more")]
TIERS = [("metro", "Metropolitan"), ("micro", "Micropolitan"), ("rural", "Rural")]
LEVERS = {"lc2_limit_levy": "board", "lc2_gf_levy": "board", "lc2_unused_share": "board"}  # set by a school board each budget year
PHONE = 350
DESK = 1040
NOUN = {"system": ("system", "systems"), "county": ("county", "counties")}


# ------------------------------------------------------------------------------------------------ helpers
def esc(s) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def sg(r: float) -> str:
    return ("+" if r > 0 else fmt.MINUS) + f"{abs(r):.2f}"


PROPER = ("General Fund", "English", "Special Building", "TEEOSA", "NSCAS", "ACT", "AQuESTT", "ELPA", "LEP", "CAP")


def lc(s: str) -> str:
    """Lowercase a label for use mid-sentence, keeping acronyms and proper names (TEEOSA, General Fund, English)."""
    if s.startswith(PROPER) or (len(s) > 1 and s[1].isupper()):
        return s
    return s[:1].lower() + s[1:]


def word(r: float) -> str:
    a = abs(r)
    return "negligible" if a < .1 else "weak" if a < .3 else "moderate" if a < .5 else "strong"


def q(a: list, p: float) -> float:
    a = sorted(a); k = (len(a) - 1) * p; i = int(k)
    return a[i] + (a[min(i + 1, len(a) - 1)] - a[i]) * (k - i)


def tw(s, fs) -> float:  # text width estimate (Archivo)
    return len(str(s)) * fs * 0.55


def jit(code: str, span: float) -> float:
    return (int(hashlib.md5(code.encode()).hexdigest()[:6], 16) / 0xFFFFFF - 0.5) * span


def ranks(a: list) -> list:
    o = sorted(range(len(a)), key=lambda i: a[i]); r = [0.0] * len(a); i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and a[o[j + 1]] == a[o[i]]:
            j += 1
        for k in range(i, j + 1):
            r[o[k]] = (i + j) / 2
        i = j + 1
    return r


def pear(x: list, y: list) -> float:
    n = len(x); mx = sum(x) / n; my = sum(y) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y)); sxx = sum((a - mx) ** 2 for a in x); syy = sum((b - my) ** 2 for b in y)
    return sxy / math.sqrt(sxx * syy) if sxx and syy else 0.0


def spear(pairs: list) -> float:
    return pear(ranks([a for a, _ in pairs]), ranks([b for _, b in pairs]))


def nice_step(span: float, n: int) -> float:
    raw = span / max(n, 1); mag = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag:
            return m * mag
    return 10 * mag


def tick_label(v: float, row: dict) -> str:
    f = row["format"]
    if f == "dollars":
        return f"${v / 1e6:,.1f}M" if abs(v) >= 1e6 else f"${v:,.0f}"
    if f == "cents":
        return f"${v:.2f}"
    if f in ("pct", "rate", "pct_change"):
        return (fmt.signed(v, 0, "%") if row["scale"] == "diverging" or f == "pct_change" else f"{v:,.0f}%")
    return fmt.signed(v, 0) if row["scale"] == "diverging" else f"{v:,.4g}"


class Labels:
    """Places labels without overlap: tries offsets in turn, drops a label that fits nowhere."""
    def __init__(self, W, H):
        self.boxes, self.W, self.H = [], W, H

    def block(self, box):
        self.boxes.append(box)

    def place(self, x, y, text, fs, tries):
        w, h = tw(text, fs), fs * 1.15
        for dx, dy, anchor in tries:
            x0 = x + dx - (w if anchor == "end" else 0); y0 = y + dy - h * 0.85
            box = (x0, y0, x0 + w, y0 + h)
            if box[0] < 0 or box[2] > self.W or box[1] < 0 or box[3] > self.H:
                continue
            if any(not (box[2] < b[0] or box[0] > b[2] or box[3] < b[1] or box[1] > b[3]) for b in self.boxes):
                continue
            self.boxes.append(box)
            return x + dx, y + dy, anchor
        return None


def svg_open(W, H, label, cls=""):
    return [f'<svg class="dchart {cls}" viewBox="0 0 {W} {H:.0f}" role="img" aria-label="{esc(label)}">']


def halo(text_el: str) -> str:
    return text_el.replace("<text ", f'<text stroke="{CARD}" stroke-width="4" paint-order="stroke" ', 1)


# ------------------------------------------------------------------------------------------------ data
def _csv(p):
    with open(p, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def mechanisms():
    return {r["family"]: r for r in _csv(REG / "mechanisms.csv")}


class Dive:
    """Everything one dive page needs, for one measure at one level."""

    def __init__(self, a, level: str, key: str):
        self.a, self.level, self.key = a, level, key
        self.row = a.ind[(key, level)]
        self.noun, self.nouns = NOUN[level]
        self.places = a.places(level)
        self.codes = [c for c in self.places if (level == "county" or c in a.formula)]
        self.group_of = {c: self._group(c) for c in self.codes}
        self.group_names = [g for _, _, g in SIZE_BANDS] if level == "system" else [n for _, n in TIERS]
        vals = {c: a.value(level, c, key) for c in self.codes}
        self.v = {c: v for c, v in vals.items() if isinstance(v, (int, float))}
        self.n = len(self.v)
        self.median = st.median(self.v.values()) if self.v else None
        # families.csv is the source of truth for which measures share arithmetic
        self.fam = [x["family"] for x in a.families if x["level"] == level and key in x["members"].split("|")]
        self.mech = mechanisms()
        self._axis()

    # groups
    def _group(self, c):
        if self.level == "system":
            n = self.a.formula[c]["formula_students"] or 0
            return next(g for lo, hi, g in SIZE_BANDS if lo <= n < hi)
        return dict(TIERS)[self.a.counties_xw[c]["tier"]]

    def groups(self):
        out = []
        for g in self.group_names:
            vs = [v for c, v in self.v.items() if self.group_of[c] == g]
            if not vs:
                continue
            gg = {"name": g, "n": len(vs), "median": st.median(vs), "q1": q(vs, .25), "q3": q(vs, .75)}
            if self.level == "county":  # the tier's own figure, summed then divided (methods 1.1)
                tier = next(k for k, n in TIERS if n == g)
                gg["together"] = (self.a.county_js["tiers"].get(tier) or {}).get("d", {}).get(self.key) or ""
            out.append(gg)
        return out

    def state_figure(self):
        if self.level == "county":
            return (self.a.county_js["tiers"].get("state") or {}).get("d", {}).get(self.key) or ""
        st_ = (self.a.system_js["indicators"].get(self.key) or {}).get("state")
        return self.fv(st_) if isinstance(st_, (int, float)) else ""

    # axis: clipped at the 99th percentile when a long tail would squash the rest; a floor with a break mark when
    # every value sits far above zero (design decision 3, applied by rule)
    def _axis(self):
        if not self.v:
            self.lo = self.hi = 0; self.clip = None; self.floor = False; return
        vs = sorted(self.v.values()); mn, mx = vs[0], vs[-1]; p99 = q(vs, .99)
        diverging = self.row["scale"] == "diverging"
        self.clip = p99 if (mx - p99) > 0.25 * (p99 - mn) and p99 > mn else None
        hi = self.clip if self.clip else mx
        if diverging:
            lo = min(mn, 0); hi = max(hi, 0)
        elif mn > 0 and mn > 0.25 * hi:
            step = nice_step(hi - mn, 5)
            lo = math.floor(mn / step) * step
        else:
            lo = min(0, mn)
        self.floor = (not diverging) and lo > 0
        span = hi - lo or 1
        if not self.clip:
            hi = hi + span * 0.02
        if diverging or lo < 0:
            lo = lo - span * 0.02
        self.lo, self.hi = lo, hi

    def ticks(self, n):
        step = nice_step(self.hi - self.lo, n)
        t = math.ceil(self.lo / step) * step; out = []
        while t <= self.hi + 1e-9:
            out.append(round(t, 10)); t += step
        if self.floor and (not out or out[0] > self.lo + 1e-9):
            out = [self.lo] + out
        return out

    def fv(self, v):
        return fmt.value(v, self.row)

    # ------------------------------------------------------------------ relationships (methods section 5)
    def relationships(self):
        a, L = self.a, self.level
        fams = {x["family"]: set(x["members"].split("|")) for x in a.families if x["level"] == L}
        infam = lambda k: any(self.key in m and k in m for m in fams.values())
        min_n = math.ceil(len(self.codes) / 2)
        res, setaside = [], []
        for r in a.registry:
            k = r["key"]
            if r["level"] != L or k == self.key or r["format"] == "category":
                continue
            pr = [(self.v[c], a.value(L, c, k), c) for c in self.v if isinstance(a.value(L, c, k), (int, float))]
            if len(pr) < 5:
                continue
            rho = spear([(x, y) for x, y, _ in pr])
            if infam(k):
                setaside.append({"key": k, "name": r["short"], "rho": rho, "n": len(pr)}); continue
            n = len(pr)
            z = math.atanh(max(min(rho, .999999), -.999999)) * math.sqrt((n - 3) / 1.06)
            p = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
            rx = ranks([x for x, _, _ in pr]); ry = ranks([y for _, y, _ in pr]); g = {}
            for i, (_, _, c) in enumerate(pr):
                t = g.setdefault(self.group_of[c], [0, 0, 0]); t[0] += rx[i]; t[1] += ry[i]; t[2] += 1
            wx = [rx[i] - g[self.group_of[c]][0] / g[self.group_of[c]][2] for i, (_, _, c) in enumerate(pr)]
            wy = [ry[i] - g[self.group_of[c]][1] / g[self.group_of[c]][2] for i, (_, _, c) in enumerate(pr)]
            res.append({"key": k, "name": r["short"], "label": r["label"], "rho": rho, "n": n, "p": p, "within": pear(wx, wy),
                        "lever": k in LEVERS})
        tested = sorted([r for r in res if r["n"] >= min_n], key=lambda r: r["p"])
        few = sorted([r for r in res if r["n"] < min_n], key=lambda r: -abs(r["rho"]))
        m = len(tested); run = 0.0
        for i, r in enumerate(tested):
            run = max(run, min(1.0, (m - i) * r["p"])); r["padj"] = run; r["holds"] = run < .05
            r["between"] = abs(r["within"]) < abs(r["rho"]) / 2
        tested.sort(key=lambda r: (not r["holds"], -abs(r["rho"])))  # holding results first (rule 5)
        return {"tested": tested, "few": few, "setaside": sorted(setaside, key=lambda r: -abs(r["rho"])), "m": m, "min_n": min_n,
                "holds": [r for r in tested if r["holds"]]}

    def driver_rho(self, k, drv):
        cs = [c for c in self.codes if isinstance(self.a.value(self.level, c, k), (int, float)) and isinstance(self.a.value(self.level, c, drv), (int, float))]
        return spear([(self.a.value(self.level, c, k), self.a.value(self.level, c, drv)) for c in cs]) if len(cs) > 10 else 0.0


# ------------------------------------------------------------------------------------------------ charts
def strip(d: Dive, W: int) -> str:
    """Step 1: every place, one row per group, middle half shaded, median barred. Dots carry data-c for place mode."""
    phone = W < 600
    L, R = (8, W - 8) if phone else (150, W - 40)
    gs = d.groups(); rowh = 62 if phone else 48; y0 = 40
    X = lambda v: L + (max(d.lo, min(v, d.hi)) - d.lo) / (d.hi - d.lo) * (R - L)
    H = y0 + rowh * len(gs) + 52
    s = svg_open(W, H, f"{d.row['label']}, every {d.noun}, by {'size band' if d.level == 'system' else 'tier'}", "dstrip")
    lab = Labels(W, H)
    base = y0 + rowh * len(gs)
    for t in d.ticks(4 if phone else 7):
        anchor = "start" if abs(t - d.lo) < 1e-9 else "middle"
        s.append(f'<line x1="{X(t):.1f}" x2="{X(t):.1f}" y1="{y0 - 8}" y2="{base}" stroke="{INK if t == 0 and d.lo < 0 else RULE}"/>'
                 f'<text x="{X(t):.1f}" y="{base + 18}" font-size="12" fill="{SUB}" text-anchor="{anchor}">{esc(tick_label(t, d.row))}</text>')
    if d.floor:
        s.append(f'<path class="brk" d="M{L - 5:.1f} {base + 2}l4 -4l4 8l4 -8l4 4" fill="none" stroke="{INK}" stroke-width="1.2"/>')
    s.append(f'<text x="{R}" y="{H - 4}" font-size="12" fill="{SUB}" text-anchor="end">{esc(d.row["label"])}</text>')
    if d.median is not None:
        mt = f"Median {d.noun} {d.fv(d.median)}"
        s.append(f'<line x1="{X(d.median):.1f}" x2="{X(d.median):.1f}" y1="{y0 - 14}" y2="{base}" stroke="{INK}" stroke-dasharray="3 3"/>'
                 f'<text x="{X(d.median) + 4:.1f}" y="{y0 - 18}" font-size="12" fill="{INK}">{esc(mt)}</text>')
    for i, g in enumerate(gs):
        cy = y0 + rowh * i + (rowh / 2 + 8 if phone else rowh / 2)
        if phone:
            s.append(halo(f'<text x="{L}" y="{cy - 22:.0f}" font-size="12" font-weight="600" fill="{INK}">{esc(g["name"])} '
                          f'<tspan font-weight="400" fill="{SUB}">· {g["n"]} {d.nouns if g["n"] != 1 else d.noun} · median {esc(d.fv(g["median"]))}</tspan></text>'))
        else:
            s.append(f'<text x="0" y="{cy - 2:.0f}" font-size="13" font-weight="600" fill="{INK}">{esc(g["name"])}</text>'
                     f'<text x="0" y="{cy + 14:.0f}" font-size="11.5" fill="{SUB}">{g["n"]} {d.nouns if g["n"] != 1 else d.noun}</text>')
        hh = 22 if phone else 30
        s.append(f'<rect x="{X(g["q1"]):.1f}" y="{cy - hh / 2:.1f}" width="{max(X(g["q3"]) - X(g["q1"]), 1):.1f}" height="{hh}" fill="{RULE}" opacity="0.75"/>'
                 f'<line x1="{X(g["median"]):.1f}" x2="{X(g["median"]):.1f}" y1="{cy - hh / 2:.1f}" y2="{cy + hh / 2:.1f}" stroke="{INK}" stroke-width="2.5"/>')
        for c, v in d.v.items():
            if d.group_of[c] != g["name"]:
                continue
            cx, yy = X(v), cy + jit(c, hh - 6)
            if d.clip and v > d.clip:
                s.append(f'<path class="dd" data-c="{c}" d="M{cx - 4:.1f} {yy - 5:.1f}l7 5l-7 5z" fill="{DOT}"/>')
            else:
                s.append(f'<circle class="dd" data-c="{c}" cx="{cx:.1f}" cy="{yy:.1f}" r="{2.6 if phone else 3.2}"/>')
    return "".join(s + ["</svg>"])


def scatter(d: Dive, key: str, W: int) -> str:
    """Step 5: the measure against one partner; the five places furthest from the line labeled. Dots carry data-c."""
    a, L_ = d.a, d.level
    prow = a.ind[(key, L_)]
    sc = [(c, a.value(L_, c, key), v) for c, v in d.v.items() if isinstance(a.value(L_, c, key), (int, float))]
    phone = W < 600
    xs = [x for _, x, _ in sc]; xlo, xhi = min(xs), max(xs); pad = (xhi - xlo) * 0.04 or 1; xlo -= pad; xhi += pad
    ylo, yhi = d.lo, d.hi
    L, R, T, Bt = (52 if phone else 72), W - 10, 30, (316 if phone else 400)
    SX = lambda v: L + (v - xlo) / (xhi - xlo) * (R - L)
    SY = lambda v: T + (yhi - max(ylo, min(v, yhi))) / (yhi - ylo) * (Bt - T)
    n = len(sc); mx = sum(xs) / n; my = sum(y for _, _, y in sc) / n
    sxx = sum((x - mx) ** 2 for x in xs) or 1
    b = sum((x - mx) * (y - my) for _, x, y in sc) / sxx; a0 = my - b * mx
    s = svg_open(W, Bt + 46, f"{d.row['short']} against {prow['short']}, every {d.noun}", "scatter")
    lab = Labels(W, Bt)
    s.append(f'<text x="0" y="13" font-size="12" fill="{SUB}">{esc(d.row["short"])}</text>'); lab.block((0, 0, tw(d.row["short"], 12) + 8, 18))
    for t in d.ticks(4 if phone else 6):
        s.append(f'<line x1="{L}" x2="{R}" y1="{SY(t):.1f}" y2="{SY(t):.1f}" stroke="{INK if t == 0 and d.lo < 0 else RULE}"/>'
                 f'<text x="{L - 6}" y="{SY(t) + 4:.1f}" font-size="11.5" fill="{SUB}" text-anchor="end">{esc(tick_label(t, d.row))}</text>')
    if d.floor:
        s.append(f'<path d="M{L - 2} {Bt + 6}l4 -4l-8 -4l8 -4l-4 -4" fill="none" stroke="{INK}" stroke-width="1.2"/>')
    step = nice_step(xhi - xlo, 4 if phone else 7); t = math.ceil(xlo / step) * step
    while t <= xhi:
        s.append(f'<line x1="{SX(t):.1f}" x2="{SX(t):.1f}" y1="{T}" y2="{Bt}" stroke="{RULE}"/>'
                 f'<text x="{SX(t):.1f}" y="{Bt + 17}" font-size="11.5" fill="{SUB}" text-anchor="middle">{esc(tick_label(t, prow))}</text>')
        t += step
    s.append(f'<text x="{R}" y="{Bt + 36}" font-size="11.5" fill="{SUB}" text-anchor="end">{esc(prow["short"])}, {esc(prow["period"])}</text>')
    xa, xb = xlo, xhi
    if d.floor and b:
        bound = (ylo - a0) / b
        xa, xb = (max(xlo, bound), xhi) if b > 0 else (xlo, min(xhi, bound))
    s.append(f'<line x1="{SX(xa):.1f}" y1="{SY(a0 + b * xa):.1f}" x2="{SX(xb):.1f}" y2="{SY(a0 + b * xb):.1f}" stroke="{INK}" stroke-dasharray="5 4" stroke-width="1.25"/>')
    for c, x, y in sc:
        if d.clip and y > d.clip:
            s.append(f'<path class="dd" data-c="{c}" d="M{SX(x) - 5:.1f} {SY(y) + 7:.1f}l5 -8l5 8z" fill="{DOT}"/>')
            lab.block((SX(x) - 6, SY(y) - 2, SX(x) + 6, SY(y) + 8))
        else:
            s.append(f'<circle class="dd" data-c="{c}" cx="{SX(x):.1f}" cy="{SY(y):.1f}" r="{2.8 if phone else 3.4}"/>')
    tries = [(9, -8, "start"), (-9, -8, "end"), (9, 15, "start"), (-9, 15, "end"), (-9, 28, "end"), (9, 28, "start"), (-9, 41, "end"), (9, 41, "start")]
    far = sorted(sc, key=lambda t: -abs(t[2] - (a0 + b * t[1])))[:5]
    names = d.a.systems_xw if L_ == "system" else d.a.counties_xw
    for c, x, y in far:
        nm = short_name(d, c) + (f" ({d.fv(y)})" if d.clip and y > d.clip else "")
        at = lab.place(SX(x), SY(y), nm, 12, tries)
        if at:
            if abs(at[1] - SY(y)) > 16:
                s.append(f'<line data-l="{c}" x1="{SX(x):.1f}" y1="{SY(y) + 4:.1f}" x2="{at[0]:.1f}" y2="{at[1] - 10:.1f}" stroke="{SUB}" stroke-width="0.8"/>')
            s.append(halo(f'<text data-l="{c}" x="{at[0]:.1f}" y="{at[1]:.1f}" font-size="12" fill="{INK}" text-anchor="{at[2]}">{esc(nm)}</text>'))
    return "".join(s + ["</svg>"])


def short_name(d: Dive, c: str) -> str:
    if d.level == "county":
        return d.a.counties_xw[c]["name"]
    n = d.a.systems_xw[c]["display_name"]
    for suf in (" Public Schools", " Community Schools", " Community School", " Public School"):
        n = n.replace(suf, "")
    return n


def corr_bar(r: float) -> str:
    w = abs(r) * 120; col = SLATE if r > 0 else RUST; x = 60 if r > 0 else 60 - w
    return (f'<svg class="cbar" viewBox="0 0 120 14" width="120" height="14" aria-hidden="true"><rect x="0" y="5" width="120" height="4" fill="{RULE}"/>'
            f'<line x1="60" x2="60" y1="1" y2="13" stroke="{SUB}"/><rect x="{x:.1f}" y="3" width="{w:.1f}" height="8" fill="{col}"/></svg>')


# ------------------------------------------------------------------------------------------------ mechanisms
NEED_NAMES = {"basic_funding": "Basic funding", "poverty": "Poverty", "lep": "Limited English proficiency", "special_receipts": "Special receipts",
              "summer_school": "Summer school", "transportation": "Transportation", "elementary_site": "Elementary site",
              "distance_education": "Distance education", "focus_school": "Focus school", "community_achievement": "Community achievement plan",
              "system_averaging": "System averaging", "student_growth": "Student growth", "new_school": "New school", "need_stabilization": "Need stabilization"}


def formula_parts(a, c: str) -> dict:
    """One system's certification, as the four formula lines. Every number is a certification field."""
    f = a.formula[c]; g = lambda k: f[k] or 0
    nd = sorted([(NEED_NAMES.get(k, k), v) for k, v in (a.need_parts.get(c) or {}).items() if v], key=lambda kv: -kv[1])
    res = [(n, g(k)) for n, k in (("Local effort", "local_effort"), ("Other receipts", "other_receipts"), ("Foundation aid, 60% counted", "foundation_aid"),
                                  ("Allocated income tax", "income_tax_rebate"), ("Option funding", "option_funding"), ("CAP aid", "cap_aid")) if g(k)]
    aid = [(n, v) for n, v in (("Equalization aid", g("equalization_aid")), ("Foundation aid, all", g("foundation_aid") + g("foundation_out")),
                               ("Allocated income tax", g("income_tax_rebate")), ("Option funding", g("option_funding")), ("CAP aid", g("cap_aid"))) if v]
    cert = (a.cert.get(c) or {}).get(a.aid_year, {})
    return {"need": g("formula_need"), "need_parts": nd, "res": g("total_resources"), "res_parts": res, "eq": g("equalization_aid"),
            "aid": g("calculated_aid"), "aid_parts": aid, "cert": cert.get("total_state_aid"), "le": g("local_effort"),
            "sav": cert.get("teeosa_adjusted_valuation"), "found_in": g("foundation_aid"), "found_out": g("foundation_out"),
            "stu": g("formula_students")}


def distance_chart(d: Dive, W: int) -> str:
    """Formula resources against need, every system sorted: below zero receives equalization aid."""
    a = d.a; phone = W < 600
    rows_ = []
    for c in d.codes:
        f = a.formula[c]
        if f["formula_need"]:
            rows_.append((c, (f["total_resources"] / f["formula_need"] - 1) * 100))
    rows_.sort(key=lambda t: t[1])
    L, R, T, Bt = (48 if phone else 56), W - 8, 30, (206 if phone else 256)
    lo, hi = -60, 200
    Y = lambda v: T + (hi - max(lo, min(v, hi))) / (hi - lo) * (Bt - T)
    bw = (R - L) / len(rows_)
    s = svg_open(W, Bt + 34, "Formula resources against need, every system, sorted", "dist")
    s.append(f'<text x="{L - 6}" y="12" font-size="12" fill="{SUB}">Resources above (+) or below ({fmt.MINUS}) formula need</text>')
    for t in (-50, 0, 50, 100, 150, 200):
        s.append(f'<line x1="{L}" x2="{R}" y1="{Y(t):.1f}" y2="{Y(t):.1f}" stroke="{INK if t == 0 else RULE}" stroke-width="{1.25 if t == 0 else 1}"/>'
                 f'<text x="{L - 6}" y="{Y(t) + 4:.1f}" font-size="11.5" fill="{SUB}" text-anchor="end">{fmt.signed(t, 0, "%") if t else "0%"}</text>')
    for i, (c, v) in enumerate(rows_):
        col = SLATE if v < 0 else (TAN if v < 10 else "#cfc8bc")
        s.append(f'<rect class="db" data-c="{c}" x="{L + i * bw:.2f}" y="{min(Y(v), Y(0)):.1f}" width="{max(bw * 0.86, 0.6):.2f}" height="{abs(Y(0) - Y(v)):.1f}" fill="{col}"/>')
    s.append(f'<text x="{R}" y="{Bt + 26}" font-size="11.5" fill="{SUB}" text-anchor="end">Each bar is one system · bars past +200% are cut</text>')
    return "".join(s + ["</svg>"])


class Ptax:
    """The property tax identity by county: taxes after credits = taxable valuation x average rate x share left after credits."""
    FACTORS = [("g_val", "Taxable valuation, after inflation"), ("g_rate", "Average tax rate"), ("g_left", "Share left after state credits")]
    PROGRAMS = {"rptc": "real property tax credit", "lb1107": "LB 1107 income tax credit", "sdptrc": "school district credit on the statement"}

    def __init__(self, a):
        pt = {(r["tax_year"], r["fips"]): (float(r["taxable_value"]), float(r["taxes_levied"])) for r in _csv(BUNDLE / "property_taxes.csv") if r["authority"] == "total"}
        self.y0, self.y1 = "2019", max(y for y, _ in pt)
        cr, self.programs, self.methods = {}, {}, {}
        for r in _csv(BUNDLE / "credits.csv"):
            if r["amount"]:
                k = (r["tax_year"], r["fips"]); cr[k] = cr.get(k, 0) + float(r["amount"])
                self.programs.setdefault(k, {})[r["program"]] = float(r["amount"]); self.methods.setdefault(k, set()).add(r["method"])
        self.d0, self.d1 = a.calendar_deflator(int(self.y0)), a.calendar_deflator(int(self.y1))
        self.f = {}
        for fips in a.counties_xw:
            if (self.y0, fips) not in pt or (self.y1, fips) not in pt:
                continue
            (v0, t0), (v1, t1) = pt[(self.y0, fips)], pt[(self.y1, fips)]
            c0, c1 = cr.get((self.y0, fips), 0), cr.get((self.y1, fips), 0)
            x = dict(v0=v0, v1=v1, t0=t0, t1=t1, c0=c0, c1=c1, n0=t0 - c0, n1=t1 - c1)
            x["g_val"] = v1 * self.d1 / (v0 * self.d0) - 1
            x["g_rate"] = (t1 / v1) / (t0 / v0) - 1
            x["g_left"] = ((t1 - c1) / t1) / ((t0 - c0) / t0) - 1
            x["g_net"] = x["n1"] * self.d1 / (x["n0"] * self.d0) - 1
            x["g_nom"] = x["n1"] / x["n0"] - 1
            self.f[fips] = x

    def strips(self, d: Dive, W: int) -> str:
        phone = W < 600
        L, R = (8, W - 8) if phone else (250, W - 30)
        lo, hi = -45, 45
        X = lambda v: L + (max(lo, min(hi, v)) - lo) / (hi - lo) * (R - L)
        rowh = 58 if phone else 46; y0 = 30
        rows_ = self.FACTORS + [("g_net", "Taxes after credits")]
        H = y0 + rowh * len(rows_) + 42
        s = svg_open(W, H, "Every county: the three factors and the result, percent change since 2019", "factors")
        for t in range(lo, hi + 1, 30 if phone else 15):
            anchor = "start" if t == lo else "end" if t == hi else "middle"
            s.append(f'<line x1="{X(t):.1f}" x2="{X(t):.1f}" y1="{y0 - 8}" y2="{y0 + rowh * len(rows_)}" stroke="{INK if t == 0 else RULE}"/>'
                     f'<text x="{X(t):.1f}" y="{y0 + rowh * len(rows_) + 18}" font-size="12" fill="{SUB}" text-anchor="{anchor}">{fmt.signed(t, 0, "%") if t else "0%"}</text>')
        for i, (k, label) in enumerate(rows_):
            cy = y0 + rowh * i + (rowh / 2 + 8 if phone else rowh / 2)
            if phone:
                s.append(halo(f'<text x="{L}" y="{cy - 18:.0f}" font-size="12" font-weight="600" fill="{INK}">{esc(label)}</text>'))
            else:
                s.append(f'<text x="0" y="{cy + 4:.0f}" font-size="13" font-weight="600" fill="{INK}">{esc(label)}</text>')
            for c, x in self.f.items():
                s.append(f'<circle class="dd" data-c="{c}" cx="{X(100 * x[k]):.1f}" cy="{cy + jit(c + k, 16):.1f}" r="{2.6 if phone else 3}"/>')
        s.append(f'<text x="{R}" y="{H - 2}" font-size="11.5" fill="{SUB}" text-anchor="end">Change since {self.y0}, each county · past ±45% at the edge</text>')
        return "".join(s + ["</svg>"])

    def factor_rho(self, d: Dive, key: str) -> dict:
        cs = [c for c in self.f if isinstance(d.a.value("county", c, key), (int, float))]
        return {k: spear([(d.a.value("county", c, key), self.f[c][k]) for c in cs]) for k, _ in self.FACTORS}

    def place(self, a, c: str) -> dict:
        x = self.f[c]
        k0, k1 = (self.y0, c), (self.y1, c)
        return {"v0": x["v0"], "v1": x["v1"], "t0": x["t0"], "t1": x["t1"], "c0": x["c0"], "c1": x["c1"],
                "f": [round(100 * x[k], 3) for k, _ in self.FACTORS] + [round(100 * x["g_net"], 3)], "nom": round(100 * x["g_nom"], 3),
                "p0": {self.PROGRAMS[p]: v for p, v in self.programs.get(k0, {}).items()}, "p1": {self.PROGRAMS[p]: v for p, v in self.programs.get(k1, {}).items()},
                "est0": "estimated" in self.methods.get(k0, set()), "school": a.value("county", c, "ptax_school_share")}


# ------------------------------------------------------------------------------------------------ why lines (design rule:
# every relationship that holds gets its mechanism, or a plain statement that none is known)
FARM = {"proprietor_share", "livestock_share", "farm_share", "ptax_ag_share", "ptax_value_ag_share", "irrigated_share", "land_value_acre"}
FNAME = {"g_val": "taxable valuation", "g_rate": "the rate", "g_left": "the share left after credits"}


def whys(d: Dive, rel: dict, ptax) -> list:
    """Groups of (title, text) covering every result that holds (methods 5.9). A mechanism is stated only where there is
    arithmetic behind it: the TEEOSA formula, the levy (the request divided by taxable valuation) and the three
    property tax factors. Everything else is called an association, with its own correlation."""
    out, none, by_factor, base_link, base_none, levies = [], [], {}, [], [], []
    lst = lambda rs: ", ".join(f'{lc(r["name"])} ({sg(r["rho"])})' for r in rs)
    cap = lambda s: s[:1].upper() + s[1:]
    y = lc(d.row["short"])
    tv = lambda k: d.driver_rho(k, "tv_ps")
    w = lambda v: "with" if v > 0 else "against"
    VAL = {"tv_ps", "val_ps"}
    LEVY = {"lc2_limit_levy", "lc2_gf_levy"}
    for r in rel["holds"]:
        k = r["key"]
        # aid against taxable valuation per student: the formula's own arithmetic (local effort), only in the direction it predicts
        pair = {d.key, k}
        if "aid_ps" in pair and pair & VAL and r["rho"] < 0:
            vname = lc(d.a.ind[((pair & VAL).pop(), "system")]["short"])
            out.append(("Through the formula", f'TEEOSA aid per student goes against {vname} ({sg(r["rho"])}) because the '
                        "formula's school adjusted valuation measures the same property: more of it means more local effort and less equalization aid."))
            continue
        # a levy on the other side: collected below so the two levies read as one entry
        if d.level == "system" and k in LEVY and d.key not in LEVERS:
            levies.append(r)
            continue
        if d.level == "system" and k == "lc2_unused_share" and d.key not in LEVERS:
            out.append(("Unused authority", f'Unused authority ({sg(r["rho"])}) is what a board chose not to request. No formula ties it to {y}; treat it as an association.'))
            continue
        # this page is a levy: report whether each partner shares its denominator
        if d.level == "system" and d.key in LEVY:
            (base_link if abs(tv(k)) >= .3 else base_none).append(r)
            continue
        # the property tax identity: the partner's strongest factor
        if d.level == "county" and ptax is not None and "c07" in d.fam:
            fr = ptax.factor_rho(d, k); top = max(fr, key=lambda x: abs(fr[x]))
            by_factor.setdefault(top, []).append((r, fr[top]))
            continue
        none.append(r)
    if levies:
        names = " and ".join(f'{r["name"] if n == 0 else lc(r["name"])} ({sg(r["rho"])})' for n, r in enumerate(levies))
        lv = " and ".join(sg(tv(r["key"])) for r in levies)
        head = (f"{names}. The levy is the request divided by taxable valuation, so it runs low where taxable valuation per student is high "
                f"(rank correlation{'s' if len(levies) > 1 else ''} {lv}). ")
        b_ = tv(d.key)
        if d.key in VAL:
            text = head + ("That denominator is this measure" if d.key == "tv_ps" else "School adjusted valuation tracks taxable valuation (rank correlation " + sg(b_) + ")") + \
                   ": the arithmetic runs from it to the levy, not from the levy to it."
        elif abs(b_) >= .3:
            text = head + (f"{cap(y)} goes {w(b_)} taxable valuation per student ({sg(b_)}). That shared denominator is the only arithmetic between them; "
                           f"the levy does not set {y}.")
            if d.key == "aid_ps":
                text += " A board's levy does not change its aid: local effort is always figured at $1.00 per $100 of school adjusted valuation."
        else:
            text = (f"{names}. A school board sets the levy each budget year, and no formula ties it to {y}. {cap(y)} barely moves with taxable "
                    f"valuation per student ({sg(b_)}), so the levy's denominator does not link them either. Treat it as an association.")
        out.append(("A levy the board sets", text))
    if base_link:
        a_ = tv(d.key)
        parts = [f'{lc(r["name"])} ({sg(r["rho"])}) is the denominator itself' if r["key"] == "tv_ps" else
                 f'{lc(r["name"])} ({sg(r["rho"])}) goes {w(tv(r["key"]))} taxable valuation per student ({sg(tv(r["key"]))})' for r in base_link]
        out.append(("Through the levy's denominator",
                    f"The levy is the request divided by taxable valuation, so it runs low where taxable valuation per student is high (rank correlation {sg(a_)}). "
                    + cap("; ".join(parts))
                    + ". That shared denominator is the arithmetic link; it does not mean the levy moves these measures or they move the levy."))
    if base_none:
        out.append(("No formula link", f"{cap(lst(base_none))}. These do not share the levy's link through taxable valuation per student; no formula ties them to {y}."))
    for top, items in by_factor.items():
        for farm in (True, False):
            sub = [(r, v) for r, v in items if (r["key"] in FARM) == farm]
            if not sub:
                continue
            rs = [r for r, _ in sub]; vals = [v for _, v in sub]
            rng = f"rank correlation {sg(vals[0])}" if len(vals) == 1 else f"rank correlations {sg(min(vals, key=abs))} to {sg(max(vals, key=abs))}"
            text = f'{cap(lst(rs))}: {"each is" if len(rs) > 1 else "it is"} tied most closely to {FNAME[top]} ({rng}), one of the three factors in step 3.'
            if farm and top == "g_left":
                cs = [c for c in d.codes if isinstance(d.a.value("county", c, "ptax_ag_share"), (int, float))]
                rac = spear([(d.a.value("county", c, "ptax_ag_share"), d.a.value("county", c, "ptax_credit_share")) for c in cs])
                text += (f" Counties where farm property pays more of the taxes also have more of the bill paid by credits (rank correlation {sg(rac)}). "
                         "The real property tax credit is figured separately for agricultural land.")
            if not farm:
                text += " The factor is arithmetic; no formula ties these measures to it, so treat the link as an association."
            out.append(("Farm counties" if farm else f"Through {FNAME[top]}", text))
    if none:
        out.append(("No formula link", f"{cap(lst(none))}. No formula ties {'it' if len(none) == 1 else 'these'} to {y}; treat {'it as an association' if len(none) == 1 else 'them as associations'}."))
    return out


# ------------------------------------------------------------------------------------------------ page
def plain(row) -> str:
    n = row["note"].strip()
    i = n.find(". ")
    return n if i < 0 else n[:i + 1]


def mechanism_note(d: Dive) -> list:
    """The family reasons that tie this measure to others, from registry/mechanisms.csv."""
    out = []
    for f in d.fam:
        m = d.mech.get(f)
        if not m:
            continue
        fam = next(x for x in d.a.families if x["family"] == f)
        members = [d.a.ind[(k, d.level)]["short"] for k in fam["members"].split("|") if k != d.key and (k, d.level) in d.a.ind]
        out.append({"why": m["why"], "with": members, "chart": m["chart"]})
    return out


def shared_names(a, level: str) -> dict:
    xw = a.systems_xw if level == "system" else a.counties_xw
    return {c: (r["display_name"] if level == "system" else r["name"] + " County") for c, r in xw.items()}


def shared_places(a, level: str, ptax) -> dict:
    """Place facts that do not change from one dive page to the next, one file each, cached by the browser once instead of
    inlined on every page: names for every page; the formula (systems) or the property tax arithmetic (counties) only for
    the pages that draw it."""
    d0 = Dive(a, level, "aid_ps" if level == "system" else "ptax_net_real_change")
    names, extra = {}, {}
    for c, name in shared_names(a, level).items():
        names[c] = {"n": name, "s": short_name(d0, c)}
        if level == "system" and c in a.formula:
            fp = formula_parts(a, c)
            extra[c] = {"fx": {k: (round(x, 2) if isinstance(x, float) else x) for k, x in fp.items()},
                        "why": (f"because its resources cover {100 * fp['res'] / fp['need']:.0f}% of its need" if fp["need"] else "")}
        if level == "county" and c in ptax.f:
            extra[c] = {"px": ptax.place(a, c)}
    js = lambda v, o: f"window.{v}=" + json.dumps(o, ensure_ascii=False, separators=(",", ":")) + ";"
    return {f"dive-places-{level}.js": js("DIVE_PLACES", names),
            ("dive-formula.js" if level == "system" else "dive-ptax.js"): js("DIVE_EXTRA", extra)}


def page(a, level: str, key: str, ptax=None) -> dict:
    d = Dive(a, level, key)
    row = d.row
    rel = d.relationships()
    gs = d.groups()
    noun, nouns = d.noun, d.nouns
    ctx = {"level": level, "key": key, "row": row, "label": row["label"], "short": row["short"], "plain": plain(row), "noun": noun, "nouns": nouns,
           "period": row["period"], "source": row["source"], "n": d.n}
    # step 1
    vs = sorted(d.v.values())
    lo_mid = min(g["q1"] for g in gs); hi_mid = max(g["q3"] for g in gs)
    gname = "size band" if level == "system" else "tier"
    s1 = (f"The median {noun} is <b>{esc(d.fv(d.median))}</b>, and each {gname}'s middle half falls between about "
          f"{esc(d.fv(lo_mid))} and {esc(d.fv(hi_mid))}.")
    above = [c for c in d.v if d.clip and d.v[c] > d.clip]
    if above:
        s1 += f" {len(above)} {nouns if len(above) != 1 else noun} above the 99th percentile ({esc(d.fv(d.clip))}) {'are' if len(above) != 1 else 'is'} drawn at the edge."
    ctx["s1_lead"] = s1
    ctx["s1_desk"], ctx["s1_phone"] = strip(d, DESK), strip(d, PHONE)
    ctx["s1_note"] = (f"Each dot is one {noun}, placed by its {gname}. The shaded box is the {gname}'s middle half, the bar its median, the dashed line the median {noun}."
                      + (f" The axis starts at {esc(d.fv(d.lo))}, below every {noun}; the zigzag marks that it does not start at zero." if d.floor else ""))
    # step 2
    meds = [g["median"] for g in gs]; iqr = st.mean(g["q3"] - g["q1"] for g in gs)
    if max(meds) - min(meds) < iqr:
        s2 = (f"No. {gname.capitalize()} medians run from {esc(d.fv(min(meds)))} to {esc(d.fv(max(meds)))}, a smaller gap than the spread inside a typical {gname}.")
    else:
        hi_g = max(gs, key=lambda g: g["median"]); lo_g = min(gs, key=lambda g: g["median"])
        s2 = (f"Partly. {hi_g['name']} {nouns} have the highest median ({esc(d.fv(hi_g['median']))}) and {lo_g['name'].lower()} {nouns} the lowest "
              f"({esc(d.fv(lo_g['median']))}), but the {gname}s overlap.")
    ctx["s2_lead"] = s2
    ctx["groups"] = [dict(g, median_f=d.fv(g["median"]), q1_f=d.fv(g["q1"]), q3_f=d.fv(g["q3"]),
                          together_f=g.get("together", "")) for g in gs]
    ctx["state_f"] = d.state_figure()
    ctx["median_f"] = d.fv(d.median)
    ctx["gname"] = gname
    # step 3
    mn = mechanism_note(d)
    ctx["mech"] = mn
    chart = next((m["chart"] for m in mn if m["chart"]), "")
    ctx["mech_chart"] = chart
    if chart == "formula":
        n_eq = sum(1 for c in d.codes if (a.formula[c]["equalization_aid"] or 0) > 0)
        near = sum(1 for c in d.codes if a.formula[c]["formula_need"] and 0 <= (a.formula[c]["total_resources"] / a.formula[c]["formula_need"] - 1) * 100 < 10)
        ctx["s3_lead"] = ("Aid is formula need minus formula resources, plus foundation aid and a few smaller payments. A system receives equalization aid "
                          f"only when its resources fall short of its need; {n_eq} of {len(d.codes)} do.")
        ctx["s3_chart_title"] = "Every system: resources against need"
        ctx["s3_chart_note"] = (f"A bar below zero is a system whose resources fall short of need; it receives equalization aid. Slate: {n_eq} systems. "
                                f"Tan: within 10% above need, where a small change in need or resources would bring aid ({near}). Grey: the rest.")
        ctx["s3_desk"], ctx["s3_phone"] = distance_chart(d, DESK), distance_chart(d, PHONE)
    elif chart == "ptax":
        fr = {k: spear([(ptax.f[c][k], ptax.f[c]["g_net"]) for c in ptax.f]) for k, _ in Ptax.FACTORS}
        ctx["s3_lead"] = ("Taxes after credits are taxable valuation × the average rate × the share of the bill left after state credits. "
                          "County totals, not one owner's bill; new construction adds to both taxable valuation and taxes.")
        ctx["s3_chart_title"] = "Every county: which factor moved most"
        ctx["s3_chart_note"] = (f"Across counties, the change in taxes after credits follows the credit factor most closely (rank correlation {sg(fr['g_left'])}), "
                                f"then the rate ({sg(fr['g_rate'])}), then taxable valuation ({sg(fr['g_val'])}). Credits lower what owners pay; the boards that levy still receive their full levy.")
        ctx["s3_desk"], ctx["s3_phone"] = ptax.strips(d, DESK), ptax.strips(d, PHONE)
    else:
        ctx["s3_lead"] = (" ".join(f'{m["why"]}' for m in mn) if mn else
                          f"No formula connects {lc(row['short'])} to the other measures. Step 4 is exploratory: an association there is not a cause.")
    ctx["setaside"] = [dict(r, rho_f=sg(r["rho"])) for r in rel["setaside"]]
    # step 4
    holds = rel["holds"]; m = rel["m"]
    levers = [r for r in holds if r["key"] in ("lc2_limit_levy", "lc2_gf_levy")]
    s4 = f"<b>{len(holds)} of {m}</b> {'measure goes' if len(holds) == 1 else 'measures go'} with {lc(row['short'])} more strongly than chance would explain."
    if levers:
        s4 += f" {'One is a levy' if len(levers) == 1 else 'Two are levies'} a school board sets; the box below says how they line up with it."
    s4 += " The rest could be chance." if holds else " Any pattern among the rest could be chance."
    if m == 0:
        s4 = (f"Too few {nouns} have {lc(row['short'])} ({d.n}) to test it against other measures: a test needs at least {rel['min_n']}, "
              f"half of all {nouns}, so a result from a few {nouns} never sits beside one from all of them.")
    ctx["s4_lead"] = s4
    ctx["whys"] = whys(d, rel, ptax)
    ctx["tested"] = [dict(r, rho_f=sg(r["rho"]), word=word(r["rho"]), bar=corr_bar(r["rho"]), within_f=sg(r["within"])) for r in rel["tested"][:8]]
    ctx["m"] = m; ctx["min_n"] = rel["min_n"]; ctx["few"] = rel["few"]
    ctx["within_all"] = bool(holds) and not any(r["between"] for r in holds)
    ctx["holds_within"] = ", ".join(f'{r["name"]} ({sg(r["within"])})' for r in holds)
    # step 5: up to four scatters drawn at build; the first is the strongest that holds (rule 7)
    picks = (holds + [r for r in rel["tested"] if not r["holds"]])[:4]
    ctx["scatters"] = [{"key": r["key"], "name": r["name"], "rho_f": sg(r["rho"]), "holds": r["holds"], "word": word(r["rho"]),
                        "desk": scatter(d, r["key"], DESK), "phone": scatter(d, r["key"], PHONE)} for r in picks]
    ctx["no_holds"] = not holds
    # place data for dive.js: value, rank, group, peers; and the place's own step 3
    pl = {}
    eqs = {c: (a.formula[c]["equalization_aid"] or 0) > 0 for c in d.codes} if level == "system" else {}
    for c, v in d.v.items():
        grp = d.group_of[c]
        peers = [x for x in d.v if d.group_of[x] == grp and (level == "county" or eqs[x] == eqs[c])]
        pmed = st.median(d.v[x] for x in peers)
        rank = 1 + sum(1 for x in d.v.values() if x > v)
        p = {"v": d.fv(v), "r": f"{fmt.ordinal(rank)} highest of {d.n}", "g": grp,
             "pm": d.fv(pmed), "pn": len(peers), "pr": 1 + sum(1 for x in peers if d.v[x] > v),
             "pd": (f"{'equalized' if eqs[c] else 'not equalized'}, {grp.lower()} formula students" if level == "system" else grp.lower())}
        pl[c] = p
    ctx["place_json"] = json.dumps({"level": level, "key": key, "noun": noun, "nouns": nouns, "chart": chart, "places": pl,
                                    "y0": getattr(ptax, "y0", ""), "y1": getattr(ptax, "y1", ""),
                                    "d0": getattr(ptax, "d0", 0), "d1": getattr(ptax, "d1", 0), "aid_year": a.aid_year}, separators=(",", ":"))
    names = shared_names(a, level)
    ctx["options"] = sorted(((names[c], c) for c in pl))
    return ctx
