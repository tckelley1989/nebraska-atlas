"""The detail sections of a county profile, restored from v1: economy (changes, industry jobs, levels, unemployment,
wages and income by year), people, farms (Census of Agriculture, what farms sell, finances, rents, crop insurance,
crop estimates), schools (students living here, money by source, systems serving the county), property taxes and
opportunity (ACS). Ported from nebraska-economy's atlas.py, layout.py, atlas_school.py and atlas_tax.py, reading
the bundle's county_detail.json; tools/parity.py holds every v1 number to the v2 page."""
import csv
import json
from decimal import Decimal, ROUND_HALF_UP

from .data import BUNDLE

MINUS = "−"
TIER = {"metro": "Metropolitan", "micro": "Micropolitan", "rural": "Rural"}
TIER_SHORT = {"metro": "Metro", "micro": "Micro", "rural": "Rural"}
# change rows with a raw change beside them: (units, label after the number); from nebraska-economy config/atlas.yaml
RAW = {"jobs_change": ("count", "jobs"), "all_jobs_change": ("count", "jobs"), "aww_real_change": ("dollars", "a week"),
       "pop_change": ("count", "people"), "pcpi_real_change": ("dollars", "per person"), "sales_real_change": ("dollars", None),
       "cattle_change": ("count", "head"), "insured_corn_change": ("count", "acres"), "farm_sales_real_change": ("dollars", None)}
ANIMALS = ["Cattle", "Hogs", "Poultry and eggs", "Milk", "Sheep and goats"]
CROPS = ["Corn", "Soybeans", "Wheat", "Sorghum", "Hay and other field crops", "Vegetables", "Fruit and nuts"]
CLASSES = {"ag": "Agricultural land and buildings", "residential": "Residential, including farm homes",
           "commercial": "Commercial and industrial", "other": "Railroad, utilities and personal property"}
AUTH = {"schools": "School districts", "county": "County", "cities": "Cities and villages", "community_college": "Community colleges",
        "nrd": "Natural resources districts", "esu": "Educational service units", "fire": "Fire districts", "townships": "Townships",
        "misc": "Other districts"}


def r_up(v, d=0):
    return float(Decimal(repr(float(v))).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP))


def fmt(v, kind: str) -> str:
    """v1's formats, rounding half up."""
    if v is None or isinstance(v, (dict, list)):
        return "n/a"
    if kind == "pct_change":
        if v >= 200:  # methods 8.5: three times the base or more reads as the multiple
            return f"{1 + v / 100:.1f} times"
        r = r_up(v, 1)
        return ("+" if r > 0 else MINUS if r < 0 else "") + f"{abs(r):.1f}%"
    if kind == "per1000":
        r = r_up(v, 1)
        return ("+" if r > 0 else MINUS if r < 0 else "") + f"{abs(r):.1f}"
    if kind == "dollars":
        r = r_up(v)
        return (MINUS if r < 0 else "") + f"${abs(r):,.0f}"
    if kind == "cents":
        return f"${r_up(v, 2):,.2f}"
    if kind in ("rate", "pct"):
        return f"{r_up(v, 1):.1f}%"
    if kind in ("years", "rate_plain"):
        return f"{r_up(v, 1):.1f}"
    if kind == "count":
        r = r_up(v)
        return (MINUS if r < 0 else "") + f"{abs(r):,.0f}"
    if kind == "count_signed":
        r = r_up(v)
        return ("+" if r > 0 else MINUS if r < 0 else "") + f"{abs(r):,.0f}"
    raise ValueError(kind)


def fmt_raw(v, kind, unit):
    if v is None:
        return None
    a = abs(v)
    sign = "+" if round(v) > 0 else MINUS if round(v) < 0 else ""
    if kind == "dollars":
        t = f"${a / 1e9:.2f} billion" if a >= 1e9 else f"${a / 1e6:.1f} million" if a >= 1e6 else f"${a:,.0f}"
    else:
        t = f"{a:,.0f}"
    return sign + t + (f" {unit}" if unit else "")


def month_label(iso: str) -> str:
    y, m = iso[:4], int(iso[5:7])
    return ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November",
            "December"][m - 1] + " " + y


def quarter_label(iso: str) -> str:
    return f"{iso[:4]} Q{(int(iso[5:7]) - 1) // 3 + 1}"


def _ints(d):
    """JSON keys back to ints where they are years."""
    if isinstance(d, dict):
        return {(int(k) if k.isdigit() and len(k) == 4 else k): _ints(v) for k, v in d.items()}
    if isinstance(d, list):
        return [_ints(v) for v in d]
    return d


class Detail:
    def __init__(self, a):
        self.a = a
        p = BUNDLE / "county_detail.json"
        self.ok = p.exists()
        if not self.ok:
            return
        J = _ints(json.loads(p.read_text(encoding="utf-8")))
        self.st, self.ch, self.p, self.ind, self.pre, self.dnames = (J["stats"], J["charts"], J["periods"], J["industry"],
                                                                     J["preliminary"], J["districts"])
        self.lv = {}
        with open(BUNDLE / "county_levels.csv", newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if r["base_year"] == "2019":
                    self.lv[(r["indicator"], r["id"])] = (float(r["base_level"]), float(r["current_level"]))

    # --------------------------------------------------------------------------------- helpers
    def raw(self, ind, area):
        if ind not in RAW:
            return None
        kind, unit = RAW[ind]
        if ind == "farm_sales_real_change":
            coa = self.st.get(area, {}).get("coa") or {}
            if coa.get(2017) and coa.get(2022) and coa[2017].get("sales_real") is not None and coa[2022].get("sales_real") is not None:
                return fmt_raw(coa[2022]["sales_real"] - coa[2017]["sales_real"], kind, unit)
            return None
        x = self.lv.get((ind, area))
        return fmt_raw(x[1] - x[0], kind, unit) if x else None

    def cols(self, fips):
        g = self.a.counties_xw[fips]
        tier, dist = self.tier_of(fips), self.dist_of(fips)
        return [(g["name"], fips), (TIER_SHORT[tier], tier), (self.dnames.get(dist, dist).replace(" district", ""), dist), ("State", "state")]

    def tier_of(self, fips):
        return self.a.counties_xw[fips]["tier"]

    def dist_of(self, fips):
        return self.a.counties_xw[fips]["crop_district"]

    def cmp(self, head, rows, cols, change=False):
        """v1's comparison table: rows (label, period, stat key, format, base indicator or None)."""
        out = []
        for label, per, key, kind, base in rows:
            cells = []
            for _, area in cols:
                v = self.st.get(area, {}).get(key)
                text = fmt(v, kind)
                rw = self.raw(base, area) if (base and change and v is not None and not isinstance(v, (dict, list))) else None
                cells.append({"v": text, "raw": rw})
            out.append({"label": label, "per": per, "cells": cells})
        return {"head": head, "cols": [c[0] for c in cols], "rows": out}

    # --------------------------------------------------------------------------------- sections
    def county(self, fips: str) -> dict:
        if not self.ok or fips not in self.st:
            return {}
        s, p = self.st[fips], self.p
        g = self.a.counties_xw[fips]
        tier, dist = self.tier_of(fips), self.dist_of(fips)
        tier_s, dist_s, st = self.st[tier], self.st[dist], self.st["state"]
        name = g["name"] + " County"
        tier_label = f"{TIER[tier]} counties"
        tier_word = f"{tier} counties"
        dist_label = self.dnames.get(dist, dist)
        cols = self.cols(fips)
        pt = self.period_text()
        since = "Change since 2019"
        secs = []

        # ---- economy
        econ_rows = [
            ("Payroll jobs", pt["qcew_window"] + (f"; {fmt(s.get('jobs_base'), 'count')} jobs in 2019, {fmt(s.get('jobs'), 'count')} now"
                                                  if (s.get("jobs_base") or 0) < 1000 else ""), "jobs_change", "pct_change", "jobs_change"),
            ("All jobs including the self-employed", f"to {p['emp_year']}, BEA", "all_jobs_change", "pct_change", "all_jobs_change"),
            ("Real weekly wage", pt["qcew_window"], "aww_real_change", "pct_change", "aww_real_change"),
            ("Real income per person", f"to {p['bea_year']}", "pcpi_real_change", "pct_change", "pcpi_real_change"),
            ("Real taxable sales", f"to {p['sales_year']}", "sales_real_change", "pct_change", "sales_real_change")]
        now_rows = [
            ("Unemployment rate", pt["laus_window"], "unemp_rate", "rate", None),
            ("Real weekly wage (2019 $)", pt["qcew_window"], "aww_real", "dollars", None),
            ("Real income per person (2019 $)", str(p["bea_year"]), "pcpi_real", "dollars", None),
            ("Self-employed share of jobs", f"{p['emp_year']}, BEA", "proprietor_share", "pct", None),
            ("Farm share of jobs", f"{p['emp_year']}, BEA", "farm_job_share", "pct", None),
            ("Farm income share of personal income", f"{p['bea_year'] - 2} to {p['bea_year']}", "farm_share", "pct", None),
            ("Transfer receipts share of income", str(p["bea_year"]), "transfers_share", "pct", None),
            ("Housing units authorized per 1,000 residents", f"{p['permit_years'][0]} to {p['permit_years'][-1]}", "permits_rate", "rate_plain", None)]
        ch, tch, sch = self.ch[fips], self.ch[tier], self.ch["state"]
        jobs_t = {"head": ["Quarter", name, tier_label, "All counties"],
                  "rows": [[quarter_label(a), f"{b:.1f}", f"{c:.1f}", f"{d:.1f}"]
                           for (a, b), (_, c), (_, d) in zip(ch["jobs_index"], tch["jobs_index"], sch["jobs_index"])]}
        st_u = dict((a, b) for a, b in sch["unemp_12m"])
        u_t = {"head": ["12 months ending", name, "All counties"],
               "rows": [[month_label(a), fmt(b, "rate"), fmt(st_u.get(a), "rate")] for a, b in ch["unemp_12m"]]}
        aww_t = {"head": ["Year", name, tier_label, "All counties"],
                 "rows": [[str(a), fmt(b, "dollars"), fmt(c, "dollars"), fmt(d, "dollars")]
                          for (a, b), (_, c), (_, d) in zip(ch["aww_real_annual"], tch["aww_real_annual"], sch["aww_real_annual"])]}
        pc_t = {"head": ["Year", name, tier_label, "All counties"],
                "rows": [[str(a), fmt(b, "dollars"), fmt(c, "dollars"), fmt(d, "dollars")]
                         for (a, b), (_, c), (_, d) in zip(ch["pcpi_real"], tch["pcpi_real"], sch["pcpi_real"])]}
        prelim = p.get("laus_preliminary_month")
        small = (s.get("jobs_base") or 0) < 1000
        econ = {"cmp": [self.cmp(since, econ_rows, cols, change=True), self.cmp("Now", now_rows, cols)],
                "industry": self.industry(s),
                "figs": [("Payroll jobs, 2019 = 100", jobs_t, "Quarterly covered employment, not seasonally adjusted, so each point carries "
                          "its season. The change compares four-quarter averages and can differ from the last point. Source: BLS QCEW."),
                         ("Unemployment rate, 12-month", u_t, "Unemployed divided by labor force, 12 months ending each month. Source: BLS LAUS."
                          + (f" {month_label(prelim)} is preliminary." if prelim else "")),
                         ("Real average weekly wage, 2019 dollars", aww_t, "Calendar-year wages divided by average employment and 52, so the "
                          "latest point is the last full year; the change table uses the latest four quarters. Source: BLS QCEW."),
                         ("Real income per person, 2019 dollars", pc_t, "Personal income divided by midyear population. Source: BEA.")],
                "small": small}
        secs.append({"id": "economy", "title": "Economy", "body": econ, "kind": "economy",
                     "sum": f"Payroll jobs {fmt(s.get('jobs_change'), 'pct_change')} since 2019 ({tier_word} "
                            f"{fmt(tier_s.get('jobs_change'), 'pct_change')}); real weekly wage {fmt(s.get('aww_real_change'), 'pct_change')}."})

        # ---- people
        people_rows = [("Population", f"July 2019 to {pt['pop_year']}", "pop_change", "pct_change", "pop_change")]
        age_rows = [("Share under 18", pt["pop_year"], "share_under18", "pct", None),
                    ("Share 18 to 64", pt["pop_year"], "share_18_64", "pct", None),
                    ("Share 65 and over", pt["pop_year"], "share_65plus", "pct", None),
                    ("Median age", pt["pop_year"], "median_age", "years", None),
                    ("Natural change per 1,000", f"July 2020 to {pt['pop_year']}", "natural_change_rate", "per1000", None),
                    ("Net migration per 1,000", f"July 2020 to {pt['pop_year']}", "net_mig_rate", "per1000", None)]
        yrs = sorted(ch["components"]["net_mig"])
        comp_t = {"head": ["Year to July 1", "Natural change", "Net migration"],
                  "rows": [[str(y), fmt(ch["components"]["natural_change"].get(y), "count_signed"), fmt(ch["components"]["net_mig"].get(y), "count_signed")]
                           for y in yrs]}
        secs.append({"id": "people", "title": "People", "kind": "people",
                     "body": {"cmp": [self.cmp(since, people_rows, cols, change=True), self.cmp("Now", age_rows, cols)],
                              "figs": [("Where population change came from", comp_t, "Births minus deaths, and net migration, years to July 1. Source: Census Bureau population estimates.")]},
                     "sum": f"Population {fmt(s.get('pop_change'), 'pct_change')} since July 2019. From July 2020 to {p['pop_year']} alone, "
                            f"net migration was {fmt(s.get('net_mig'), 'count_signed')} and natural change {fmt(s.get('natural_change'), 'count_signed')}; "
                            f"the 2019 to 2020 step joins the 2010-2020 Census series to the current one, so these parts need not add to the total."})

        # ---- farms
        secs.append({"id": "farms", "title": "Farms", "kind": "farms", "body": self.farms(fips, cols, since, dist_label),
                     "sum": f"Real farm product sales {fmt(s.get('farm_sales_real_change'), 'pct_change')} from 2017 to 2022; "
                            f"cattle {fmt(s.get('cattle_change'), 'pct_change')} since 2019."})

        # ---- schools
        sc = self.schools(fips, tier_label, dist_label)
        if sc:
            secs.append({"id": "schools", "title": "Schools", "kind": "schools", "body": sc,
                         "sum": f"About {fmt(s.get('sch_students'), 'count')} formula students live here; TEEOSA aid "
                                f"{fmt(s.get('sch_aid_ps'), 'dollars')} per formula student, {fmt(s.get('sch_eq_student_share'), 'pct')} "
                                f"in districts receiving equalization aid (estimates)."})

        # ---- property taxes
        tx = self.taxes(fips, tier_label)
        if tx:
            y = p.get("ptax_year")
            secs.append({"id": "taxes", "title": "Property taxes", "kind": "taxes", "body": tx,
                         "sum": f"Real taxes levied {fmt(s.get('ptax_real_change'), 'pct_change')} since 2019; after state credits "
                                f"{fmt(s.get('ptax_net_real_change'), 'pct_change')}. Credits paid {fmt(s.get('ptax_credit_share'), 'pct')} of {y} taxes."})

        # ---- opportunity
        an, ab = p["acs_now"], p["acs_base"]
        acs = []
        for label, k, kind in (("Median household income (2024 $)", "median_hh_income", "dollars"), ("Poverty rate", "poverty_rate", "pct"),
                               ("Bachelor's degree or higher, age 25+", "ba_plus", "pct"), ("Households with broadband", "broadband", "pct")):
            sig = s.get(k + "_change_sig")
            moe = s.get(k + "_moe")
            acs.append([label, fmt(s.get(k), kind) + ("" if s.get(k + "_reliable") else " (unreliable)"),
                        "± " + (fmt(moe, kind).lstrip("+") if moe is not None else "n/a"), fmt(s.get(k + "_base"), kind),
                        "Yes" if sig else ("No" if sig is not None else "n/a")])
        secs.append({"id": "opportunity", "title": "Opportunity", "kind": "table",
                     "body": {"tables": [{"head": ["", f"{an - 4} to {an}", "Margin (90%)", f"{ab - 4} to {ab}", "Change significant?"], "rows": acs}],
                              "note": "American Community Survey 5-year estimates. The two windows do not overlap, so they can be compared; "
                                      "\"significant\" means the difference passes the Census Bureau's test at 90% confidence. Earlier income is "
                                      f"converted to {an} dollars with the Midwest CPI-U. Estimates with a coefficient of variation over 30% are marked unreliable."},
                     "sum": f"American Community Survey {an - 4} to {an}: median household income {fmt(s.get('median_hh_income'), 'dollars')}, "
                            f"poverty rate {fmt(s.get('poverty_rate'), 'pct')}."})
        return {"csecs": secs}

    def period_text(self):
        p = self.p
        (q0, q1), (m0, m1) = p["qcew_window"], p["laus_window"]
        return {"qcew_window": f"{quarter_label(q0)} to {quarter_label(q1)}", "laus_window": f"{month_label(m0)} to {month_label(m1)}",
                "pop_year": f"July 1, {p['pop_year']}"}

    def industry(self, s):
        ind, I = s.get("ind"), self.ind
        if not ind:
            return None
        names = I.get("names", {})
        priv = ind["private"]

        def row(label, v, denom=None, total=False):
            a_, b_ = v
            return {"label": label, "v": [fmt(a_, "count"), fmt(b_, "count"), ("+" if b_ - a_ >= 0.5 else "") + fmt(b_ - a_, "count"),
                                          fmt(100 * a_ / denom[0], "pct") if denom else "", fmt(100 * b_ / denom[1], "pct") if denom else ""],
                    "total": total}
        rows = [r for _, r in sorted(((v[1] - v[0], row(names.get(k, k), v, priv)) for k, v in ind["sectors"].items()
                                      if v is not None and (v[0] or v[1])), key=lambda x: -x[0])]
        withheld = [names.get(k, k) for k, v in ind["sectors"].items() if v is None]
        if not rows and not priv:
            return {"none": "BLS withholds every private industry figure for this county; withheld values are never estimated. Source: BLS QCEW."}
        rest = ind["rest"]
        if rest is not None and withheld and (abs(rest[0]) >= 0.5 or abs(rest[1]) >= 0.5):
            rows.append(row("Not disclosed: " + ", ".join(withheld), rest, priv))
        if priv:
            rows.append(row("All private jobs", priv, priv, True))
        if ind["gov"]:
            rows.append(row(names.get("gov", "Government"), ind["gov"]))
        rows.append(row("All payroll jobs", ind["total"], total=True))
        if ind["full"]:
            lead = (f"{fmt(ind['dissim'], 'pct')} of this county's private jobs would have to change sector to restore its 2019 mix. "
                    f"The median of the {I.get('full_n')} counties BLS publishes in full is {fmt(I.get('median'), 'pct')}. An ordinary year shifts "
                    f"about {fmt(I.get('one_year_median'), 'pct')}, and those shifts mostly persist rather than reverse, so they add up over the years; "
                    f"the index cannot tell real change from BLS recoding an employer.")
        else:
            why = (f"BLS withholds {', '.join(withheld)} here" if withheld else
                   "BLS withholds this county's private total in some months" if not priv else "it had under 1,000 private jobs in 2019")
            lead = f"The share of private jobs that changed sector is not computed because {why}; the published sectors are below."
        return {"lead": lead, "rows": rows}

    def farms(self, fips, cols, since, dist_label):
        s, p = self.st[fips], self.p
        dist_s, st = self.st[self.dist_of(fips)], self.st["state"]
        c17, c22 = s["coa"][2017], s["coa"][2022]
        d22, a22 = dist_s["coa"][2022], st["coa"][2022]
        pc = lambda a_, b_: 100 * (b_ / a_ - 1) if a_ and b_ else None
        coa = []
        for label, kind, k in (("Farms", "count", "farms"), ("Land in farms, acres", "count", "acres_operated"),
                               ("Irrigated share of farmland", "pct", "irrigated_share"), ("Farm product sales (2019 $)", "dollars", "sales_real"),
                               ("Livestock share of sales", "pct", "livestock_share"), ("Corn yield, bu/acre", "years", "corn_yield"),
                               ("Soybean yield, bu/acre", "years", "soy_yield"), ("Cattle and calves, December 31", "count", "cattle")):
            chg = "" if kind == "pct" else fmt(pc(c17.get(k), c22.get(k)), "pct_change")
            if kind == "pct" and c17.get(k) is not None and c22.get(k) is not None:
                chg = fmt(c22[k] - c17[k], "per1000") + " pts"
            coa.append([label, fmt(c17.get(k), kind), fmt(c22.get(k), kind), chg, fmt(d22.get(k), kind), fmt(a22.get(k), kind)])
        wh = d22.get("withheld_counties") or 0
        tables = [{"head": ["", "2017", "2022", "Change", f"{dist_label}, 2022", "All counties, 2022"], "rows": coa,
                   "note": "USDA Census of Agriculture, taken every five years; the 2027 Census is published in 2029. 2022 was a drought year in much "
                           "of Nebraska. Sales are in 2019 dollars (Midwest CPI-U)."
                           + (f" The district total leaves out {wh} county value{'s' if wh > 1 else ''} NASS withheld to protect individual farms." if wh else "")}]
        cattle_rows = [("Cattle and calves, January 1", f"to {p['cattle_year']}", "cattle_change", "pct_change", "cattle_change"),
                       ("Insured corn acres", f"to {p['rma_latest']}", "insured_corn_change", "pct_change", "insured_corn_change")]
        more = []
        # what farms sell
        defl17 = (c17["sales_real"] / c17["sales_total"]) if c17.get("sales_total") else None
        defl22 = (c22["sales_real"] / c22["sales_total"]) if c22.get("sales_total") else None
        small = lambda x: "—" if x is None else ("under 0.1%" if 0 < x < 0.05 else fmt(x, "pct"))
        mix = []
        for label in ANIMALS + CROPS:
            v17, v22 = c17["mix"].get(label), c22["mix"].get(label)
            dv = d22["mix"].get(label)
            share = 100 * v22 / c22["sales_total"] if v22 is not None and c22.get("sales_total") else None
            dshare = 100 * dv / d22["sales_total"] if dv is not None and d22.get("sales_total") else None
            if v17 in (None, 0) and v22 in (None, 0) and (c17["mix"].get(label) is not None or c22["mix"].get(label) is not None):
                continue
            cell = lambda v, dfl: "Withheld" if v is None else fmt(v * dfl, "dollars") if dfl else "n/a"
            mix.append([label, cell(v17, defl17), cell(v22, defl22), small(share), small(dshare) if dshare is not None else "Withheld in part"])
        lead = s.get("leading")
        more.append({"title": "What farms sell",
                     "lead": (f"Leading commodity in 2022: {lead}, {fmt(s.get('leading_share'), 'pct')} of farm sales." if lead else
                              "The leading commodity can't be determined because some figures are withheld."),
                     "tables": [{"head": ["Sales (2019 $)", "2017", "2022", "Share of 2022 sales", f"{dist_label} share"], "rows": mix}],
                     "note": "\"Withheld\" means NASS suppressed the figure so individual farms cannot be identified. Withheld values are never "
                             "estimated here; a district share is shown only when every county in it is published."})
        fin = [[label, fmt(c17.get(k), kind), fmt(c22.get(k), kind), fmt(d22.get(k), kind), fmt(a22.get(k), kind)]
               for label, kind, k in (("Net cash farm income per farm (2019 $)", "dollars", "net_income_per_farm_real"),
                                      ("Production expenses, % of sales", "pct", "expense_ratio"),
                                      ("Federal program payments, % of sales", "pct", "govt_share"),
                                      ("Land and buildings value per acre", "dollars", "land_value_acre"),
                                      ("Average producer age", "years", "producer_age"), ("Producers under 35, % of producers", "pct", "young_share"))]
        more.append({"title": "Farm finances and farmers", "tables": [{"head": ["", "2017", "2022", f"{dist_label}, 2022", "All counties, 2022"], "rows": fin}],
                     "note": "Census of Agriculture. Net cash farm income is cash receipts minus cash expenses; it leaves out depreciation and inventory "
                             "changes. Land value is as reported by producers, in current dollars. Producer figures start in 2022, when the Census's "
                             "current definition of a producer is first available here."})
        rh, srh = s.get("rents") or {}, self.st.get("state_rents") or {}
        ryears = sorted(set().union(*[set(v) for v in rh.values()])) if rh else []
        if ryears:
            rows = [[str(y)] + [fmt(rh[k].get(y), "dollars") if y in rh.get(k, {}) else "—" for k in ("dryland", "irrigated", "pasture")]
                    + [fmt(srh.get(k, {}).get(y), "dollars") if y in srh.get(k, {}) else "—" for k in ("dryland", "irrigated", "pasture")] for y in ryears]
            rt = [{"head": ["Year", "Dryland cropland", "Irrigated cropland", "Pasture", "State dryland", "State irrigated", "State pasture"], "rows": rows}]
        else:
            rt = []
        more.append({"title": "Cash rents by year", "tables": rt,
                     "note": ("" if ryears else "NASS has not published cash rents for this county. ")
                     + "Average cash rent per acre, NASS county cash rents survey. A dash means NASS did not publish that county and land type that "
                       "year; the survey was not run in 2018."})
        dist_s_ = dist_s
        rma = []
        for y in sorted(s["rma"]):
            rr, dd = s["rma"][y], dist_s_["rma"][y]
            rma.append([f"{y}{' (preliminary)' if rr['preliminary'] else ''}", fmt(rr["acres_corn"], "count"), fmt(rr["acres_soy"], "count"),
                        fmt(rr["premium"], "dollars"), fmt(rr["indemnity"], "dollars"), fmt(rr["loss_ratio"], "rate_plain"),
                        fmt(dd["loss_ratio"], "rate_plain"), fmt(rr["prf_indemnity"], "dollars") if rr["prf_premium"] else "—"])
        ly = p["rma_latest"]

        def acres(d, k):
            if k != "acres_crops":
                return d.get(k)
            return d.get("acres_all") - (d.get("acres_prf") or 0) if d.get("acres_all") is not None else None
        ins = [[lbl, fmt(acres(s["rma"].get(2019, {}), k), "count"), fmt(acres(s["rma"].get(ly, {}), k), "count"),
                fmt(pc(acres(s["rma"].get(2019, {}), k), acres(s["rma"].get(ly, {}), k)), "pct_change"),
                fmt(pc(acres(dist_s_["rma"].get(2019, {}), k), acres(dist_s_["rma"].get(ly, {}), k)), "pct_change")]
               for lbl, k in (("Corn", "acres_corn"), ("Soybeans", "acres_soy"), ("Wheat", "acres_wheat"), ("Grain sorghum", "acres_sorghum"),
                              ("All insured crops except pasture and rangeland", "acres_crops"),
                              ("Pasture, rangeland, forage (index insurance)", "acres_prf"))]
        more.append({"title": "Crop insurance by year and insured acres",
                     "tables": [{"head": ["Crop year", "Insured corn acres", "Insured soybean acres", "Premium", "Indemnities", "Paid per $100",
                                          f"{dist_label}, paid per $100", "Rangeland indemnities"], "rows": rma},
                                {"head": ["Insured acres", "2019", str(ly), "Change", f"{dist_label} change"], "rows": ins}],
                     "note": "USDA Risk Management Agency Summary of Business, all insured crops. \"Paid per $100\" is indemnities per $100 of total premium; "
                             "above 100 means claims exceeded premium. Rangeland is the Pasture, Rangeland and Forage rainfall-index policy. Acres are net "
                             "reported acres times the insured share. The current crop year is preliminary while claims are paid."})
        corn_c, soy_c = s.get("corn_bu") or {}, s.get("soy_bu") or {}
        years_c = sorted(set(corn_c) | set(soy_c))
        more.append({"title": "Annual crop estimates",
                     "tables": [{"head": ["Year", "Corn for grain, bu", "Soybeans, bu"],
                                 "rows": [[str(y), fmt(corn_c.get(y), "count") if y in corn_c else "—", fmt(soy_c.get(y), "count") if y in soy_c else "—"]
                                          for y in years_c]}] if years_c else [],
                     "note": ("" if years_c else "NASS has not published crop production for this county since 2018. ")
                     + "USDA NASS publishes county crop estimates only where survey response allows. Since 2020 the remaining counties are combined into "
                       "one statewide figure, so neither every county nor every crop district can be shown. A dash means not published that year."})
        return {"tables": tables, "cmp": [self.cmp(since, cattle_rows, cols, change=True)], "more": more}

    def schools(self, fips, tier_label, dist_label):
        s = self.st[fips]
        if "sch_students" not in s:
            return None
        tier_s, dist_s, st = self.st[self.tier_of(fips)], self.st[self.dist_of(fips)], self.st["state"]
        ay = self.a.aid_year
        aid = f"{ay}-{(ay + 1) % 100:02d} aid year"
        rows = [[f"{lbl}", fmt(s.get(k), kind), fmt(tier_s.get(k), kind), fmt(dist_s.get(k), kind), fmt(st.get(k), kind)]
                for lbl, k, kind in (("Formula students living here (estimate)", "sch_students", "count"),
                                     ("TEEOSA aid per formula student (estimate)", "sch_aid_ps", "dollars"),
                                     ("Formula need per student (estimate)", "sch_need_ps", "dollars"),
                                     ("Students in equalized districts (estimate)", "sch_eq_student_share", "pct"))]
        tables = [{"head": [aid, "County", tier_label, dist_label, "All counties"], "rows": rows}]
        # money by source, students living here
        mt = self.county_money(fips, tier_label)
        # systems serving the county
        vals = s.get("sch_val_by_district") or {}
        total = sum(vals.values()) or None
        kids = {}
        for code in s.get("sch_districts", []):
            f = self.a.formula.get(code)
            share = next((float(w["share_of_children_5_17"]) for w in self._weights(code) if w["county_fips"] == fips), 0.0)
            kids[code] = (f["formula_students"] if f else 0) * share
        kt = sum(kids.values()) or None
        drows = []
        for code in sorted(set(vals) | set(kids), key=lambda c: -(vals.get(c) or 0)):
            if code not in self.a.systems_xw:
                continue
            vs = 100 * vals[code] / total if total and vals.get(code) else None
            ks = 100 * kids[code] / kt if kt and code in kids else None
            if (vs or 0) < 0.05 and (ks or 0) < 0.05:
                continue
            aps = self.a.value("system", code, "aid_ps")
            eq = (self.a.formula.get(code) or {}).get("equalization_aid") or 0
            drows.append({"code": code, "name": self.a.systems_xw[code]["display_name"], "v": [fmt(vs, "pct"), fmt(ks, "pct") if ks is not None else "—",
                                                                                               fmt(aps, "dollars"), "Yes" if eq > 0 else "No"]})
        return {"tables": tables, "money": mt, "systems": drows,
                "note": f"Taxable valuation is Revenue's certified taxable valuation for the part of each district in this county. Students and aid are "
                        f"TEEOSA's {aid} certification; a district that crosses county lines is split by where its 2020 Census children ages 5-17 "
                        f"live, so those county figures are estimates. School money by source is from each district's Annual Financial Report, "
                        f"split the same way; state money includes property tax credits and the LB 1107 credit claimed against school taxes."}

    _wcache = None

    def _weights(self, code):
        if self._wcache is None:
            self._wcache = {}
            with open(BUNDLE / "district_county_weights.csv", newline="", encoding="utf-8") as fh:
                for r in csv.DictReader(fh):
                    self._wcache.setdefault(r["system"], []).append(r)
        return self._wcache.get(code, [])

    def county_money(self, fips, tier_label):
        yrs = sorted(k for k in (self.st["state"].get("sch_afr") or {}))
        s = self.st[fips]
        if not yrs or not s.get("sch_afr"):
            return None
        last = yrs[-1]
        tier = self.tier_of(fips)
        get = lambda k: self.st[k].get("sch_afr") or {}
        lab = lambda y: f"{y}-{(y + 1) % 100:02d}"
        cols = [(f"County, {lab(2019)}", get(fips).get(2019)), (f"County, {lab(last)}", get(fips).get(last)),
                (tier_label, get(tier).get(last)), ("All counties, current systems", get("state").get(last))]
        rows = []
        for label, key in (("TEEOSA aid", "teeosa"), ("Special education", "sped"), ("Property tax credits paid by the state", "credits_all"),
                           ("Homestead exemption and other state programs", "other_all"), ("State", "state"),
                           ("Local property and motor vehicle taxes", "local_taxes_net"), ("Other local", "other_local"), ("Local", "local"),
                           ("Federal (not in the share)", "federal")):
            rows.append({"label": label, "total": key in ("state", "local"),
                         "v": [fmt(self.money_ps(x, key), "dollars") if x else "n/a" for _, x in cols]})
        rows.append({"label": "State share of General Fund receipts", "total": True,
                     "v": [fmt(x.get("state_share"), "pct") if x else "n/a" for _, x in cols]})
        return {"head": ["Per student (ADM), 2019 dollars"] + [c[0] for c in cols], "rows": rows,
                "note": f"County columns cover the systems certified today, so \"All counties\" leaves out districts that have since merged or closed "
                        f"and differs slightly from the statewide figures on system pages, which count every district that filed. Students are counted "
                        f"where they live, not where they attend."}

    @staticmethod
    def money_ps(x, key):
        adm, d = x.get("students"), x.get("defl")
        if not adm or not d:
            return None
        g = lambda k: x.get(k) or 0.0
        v = {"teeosa": g("teeosa"), "sped": g("sped"), "credits_all": g("credits") + g("lb1107"), "other_all": g("homestead") + g("other_state"),
             "state": g("state"), "local_taxes_net": g("local_taxes") - g("lb1107"), "other_local": g("other_local"), "local": g("local"),
             "federal": g("federal")}[key]
        return v * d / adm

    def taxes(self, fips, tier_label):
        s = self.st[fips]
        if "ptax" not in s:
            return None
        tier_s, st = self.st[self.tier_of(fips)], self.st["state"]
        y = self.p["ptax_year"]
        now, base = s["ptax"][y], s["ptax"][2019]
        d_now = (1 + s["ptax_real_change"] / 100) * base["total"] / now["total"] if now["total"] and s.get("ptax_real_change") is not None else None
        ch = lambda a_, b_: 100 * (b_ * d_now / a_ - 1) if a_ and b_ and d_now else None

        def dch(a_, b_):
            if a_ is None or b_ is None or not d_now:
                return "n/a"
            v = b_ * d_now - a_
            return ("+" if v >= 0.5 else "") + fmt(v, "dollars")
        rows = []
        for k, lbl in AUTH.items():
            if not base.get(k) and not now.get(k):
                continue
            rows.append({"label": lbl, "v": [fmt(base[k], "dollars"), fmt(now[k], "dollars"), fmt(ch(base[k], now[k]), "pct_change"), dch(base[k], now[k]),
                                             fmt(100 * now[k] / now["total"] if now["total"] else None, "pct"),
                                             fmt(100 * st["ptax"][y][k] / st["ptax"][y]["total"], "pct")]})
        rows.append({"label": "All taxes levied", "total": True, "v": [fmt(base["total"], "dollars"), fmt(now["total"], "dollars"),
                                                                        fmt(s["ptax_real_change"], "pct_change"), dch(base["total"], now["total"]), "100.0%", "100.0%"]})
        if now.get("credits") is not None:
            rows.append({"label": "State credits on these taxes", "v": [fmt(-base["credits"], "dollars"), fmt(-now["credits"], "dollars"),
                                                                         fmt(ch(base["credits"], now["credits"]), "pct_change"), dch(-base["credits"], -now["credits"]),
                                                                         fmt(100 * now["credits"] / now["total"], "pct"),
                                                                         fmt(100 * st["ptax"][y]["credits"] / st["ptax"][y]["total"], "pct")]})
            rows.append({"label": "Net taxes after credits", "total": True, "v": [fmt(base["net"], "dollars"), fmt(now["net"], "dollars"),
                                                                                  fmt(s["ptax_net_real_change"], "pct_change"), dch(base["net"], now["net"]),
                                                                                  fmt(100 * now["net"] / now["total"], "pct"),
                                                                                  fmt(100 * st["ptax"][y]["net"] / st["ptax"][y]["total"], "pct")]})
            rows.append({"label": "School taxes after school credits", "v": [fmt(base["schools_net"], "dollars"), fmt(now["schools_net"], "dollars"),
                                                                              fmt(s["ptax_school_net_real_change"], "pct_change"),
                                                                              dch(base["schools_net"], now["schools_net"]), "", ""]})
        auth = {"head": ["Taxes levied", "2019", str(y), "Real change", "Real change, 2019 $", f"Share, {y}", "All counties share"], "rows": rows}
        crow = [[lbl, fmt(100 * base[k] / base["total"], "pct"), fmt(100 * now[k] / now["total"], "pct"),
                 fmt(100 * st["ptax"][y][k] / st["ptax"][y]["total"], "pct")] for k, lbl in CLASSES.items()]
        if now.get("ag_net") is not None:
            crow += [["Agricultural, after credits (estimate)", fmt(100 * base["ag_net"] / base["net"], "pct"), fmt(100 * now["ag_net"] / now["net"], "pct"),
                      fmt(100 * st["ptax"][y]["ag_net"] / st["ptax"][y]["net"], "pct")],
                     ["Residential, after credits (estimate)", fmt(100 * base["res_net"] / base["net"], "pct"), fmt(100 * now["res_net"] / now["net"], "pct"),
                      fmt(100 * st["ptax"][y]["res_net"] / st["ptax"][y]["net"], "pct")]]
        lines = [[lbl, fmt(s.get(kb), kind) if kb else "—", fmt(s.get(k), kind), fmt(tier_s.get(k), kind), fmt(st.get(k), kind)]
                 for lbl, k, kb, kind in (("Average tax rate per $100 of taxable valuation", "ptax_rate", "ptax_rate_base", "cents"),
                                          ("Taxes levied per resident (2019 $)", "ptax_per_resident_real", None, "dollars"),
                                          ("Net taxes after credits per resident (2019 $)", "ptax_net_per_resident_real", None, "dollars"),
                                          ("Why taxes after credits changed: real taxable valuation since 2019", "ptax_dec_value", None, "pct_change"),
                                          ("Why: average tax rate since 2019", "ptax_dec_rate", None, "pct_change"),
                                          ("Why: share of taxes left after credits since 2019", "ptax_dec_credits", None, "pct_change"))]
        # worked arithmetic: why taxes after credits changed, the county's three factors multiplied out
        dv, dr, dc, net = (s.get(k) for k in ("ptax_dec_value", "ptax_dec_rate", "ptax_dec_credits", "ptax_net_real_change"))
        steps = None
        if None not in (dv, dr, dc, net):
            levied = 100 * ((1 + dv / 100) * (1 + dr / 100) - 1)
            w = lambda v, up, down: up if v >= 0 else down
            why = (f"Real taxes after credits {w(net, 'rose', 'fell')} {fmt(abs(net), 'pct')} since 2019. Real taxable valuation "
                   f"{w(dv, 'rose', 'fell')} {fmt(abs(dv), 'pct')} and the average tax rate {w(dr, 'rose', 'fell')} {fmt(abs(dr), 'pct')}, "
                   f"so real taxes levied {w(levied, 'rose', 'fell')} {fmt(abs(levied), 'pct')}. State credits then "
                   + (f"left {fmt(abs(dc), 'pct')} less of the bill to pay" if dc < 0 else f"left {fmt(dc, 'pct')} more of the bill to pay")
                   + " than in 2019. The largest of the three factors was "
                   + max([(abs(dv), "the change in taxable valuation"), (abs(dr), "the change in the tax rate"), (abs(dc), "credits")])[1] + ".")
            rows = [("Real taxable valuation", "since 2019", dv, f"1 + taxable valuation = {1 + dv / 100:.4f}"),
                    ("Average tax rate", "taxes levied ÷ taxable valuation", dr, f"1 + rate = {1 + dr / 100:.4f}"),
                    ("Real taxes levied", "(1 + taxable valuation) × (1 + rate) − 1", levied, f"{1 + dv / 100:.4f} × {1 + dr / 100:.4f} = {1 + levied / 100:.4f}"),
                    ("Share of the bill left after credits", "1 − credits ÷ taxes levied", dc, f"1 + share left = {1 + dc / 100:.4f}"),
                    ("Real taxes after credits", "(1 + levied) × (1 + share left) − 1", net, f"{1 + levied / 100:.4f} × {1 + dc / 100:.4f} = {1 + net / 100:.4f}")]
            steps = {"why": why, "table": {"head": ["Step, since 2019, real", "Change", "Arithmetic"],
                                           "rows": [{"label": f"{i + 1}. {a_} ({b_})", "total": i in (2, 4), "v": [fmt(v, "pct_change"), m]}
                                                    for i, (a_, b_, v, m) in enumerate(rows)]}}
        return {"steps": steps, "auth": auth, "classes": {"head": ["Share of taxes, by property", "2019", str(y), f"All counties, {y}"], "rows": crow},
                "lines": {"head": ["", "2019", str(y), tier_label, "All counties"], "rows": lines},
                "note": f"Taxes levied by every taxing authority in the county, then the state credits that pay part of those bills: the Property Tax "
                        f"Credit Act credit, the LB 1107 income tax credit and the School District Property Tax Relief Credit (from tax year 2024). County "
                        f"credits are Revenue's certifications from 2022 on; earlier real property credits and all LB 1107 credits are estimated and split "
                        f"to counties from statewide totals, and splits of credits by property class are estimates (see About). Tax year {y} is levied in "
                        f"fall {y} and paid in two halves by late summer {y + 1}. Dollar columns are as levied; the real change uses the Midwest CPI-U. "
                        f"School district taxes include bonds. Per-resident taxes overstate what residents pay where land is owned from outside the county. "
                        f"The three \"why\" rows multiply to the real change in taxes after credits: (1 + taxable valuation) × (1 + rate) × (1 + share left) − 1."}
