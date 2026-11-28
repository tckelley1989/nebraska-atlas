"""The detail sections of a system profile, restored from v1: since 2019-20, money by source, property taxes, what makes
up formula need, the property tax base, student outcomes and teachers, and the year-by-year history. Each is computed
from the bundle by v1's definitions; the parity check (tests/test_parity.py) holds every v1 number to the v2 page."""
import csv
from collections import defaultdict

from . import fmt
from .data import BUNDLE

MINUS = fmt.MINUS


def _csv(name):
    with open(BUNDLE / name, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _f(v):
    return float(v) if v not in ("", None) else None


def sy(y: int) -> str:
    return f"{y}-{(y + 1) % 100:02d}"


def dollars(v) -> str:
    return "n/a" if v is None else fmt.money(v)


def r1(v: float, d: int = 1) -> str:
    """Half up from the CSV's decimal text: the bundle keeps six decimals, so 7.3500001 arrives as 7.35 and must read 7.4,
    as the pipeline (which formats at full precision) and the tiles show it."""
    from decimal import Decimal, ROUND_HALF_UP
    return str(Decimal(repr(v)).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP))


def pct(v, d=1) -> str:
    return "n/a" if v is None else f"{r1(v, d)}%"


def signed_money(v) -> str:
    if v is None:
        return "n/a"
    return ("+" if round(v) > 0 else "") + fmt.money(v)


def raw(v, kind: str, unit: str | None = None) -> str:
    """A change in its own units, as v1 wrote it: +149 students, +$120.3 million, −$757."""
    a = abs(v)
    sign = "+" if round(v) > 0 else MINUS if round(v) < 0 else ""
    if kind == "dollars":
        t = f"${a / 1e9:.2f} billion" if a >= 1e9 else f"${a / 1e6:.1f} million" if a >= 1e6 else f"${a:,.0f}"
    else:
        t = f"{a:,.0f}"
    return sign + t + (f" {unit}" if unit else "")


def outcome(v, kind: str) -> str:
    if v is None:
        return "Withheld"
    if kind == "pct":
        return f"{r1(v)}%"
    if kind == "per1000":
        s = r1(abs(v))
        return s if float(s) == 0 else ("+" if v > 0 else MINUS) + s
    if kind == "dollars":
        return fmt.money(v)
    return r1(v)


OUTCOMES = [("NSCAS English language arts, on track or advanced", "nscas_ela_pct_on_track_or_advanced", "pct"),
            ("NSCAS mathematics, on track or advanced", "nscas_math_pct_on_track_or_advanced", "pct"),
            ("NSCAS science, on track or advanced (grades 5 and 8)", "nscas_science_pct_on_track_or_advanced", "pct"),
            ("Four-year graduation rate", "graduation_rate_4yr", "pct"),
            ("NSCAS scale score against the state, grade-mix adjusted (points)", "nscas_scale_points_vs_state", "per1000"),
            ("NSCAS matched-cohort growth against the state (points per grade)", "nscas_cohort_growth_points_vs_state", "per1000"),
            ("Gap, not eligible less eligible for free or reduced-price lunch (points)", "lunch_status_gap_points", "per1000"),
            ("Gap, students not in special education less students in special education (points)", "sped_gap_points", "per1000"),
            ("Gap, all other students less English learners (points)", "english_learner_gap_points", "per1000"),
            ("Five-year graduation rate (class a year earlier)", "graduation_rate_5yr_prior_class", "pct"),
            ("Four-year graduation rate, students in special education", "graduation_rate_4yr_sped", "pct"),
            ("Four-year graduation rate, English learners", "graduation_rate_4yr_english_learners", "pct"),
            ("Grade 11 ACT, meeting the benchmark (ELA and math averaged)", "act_pct_meeting_benchmark_ela_math", "pct"),
            ("Grade 11 ACT, average composite score", "act_average_composite", "plain"),
            ("Grade 11 ACT science, meeting the benchmark", "act_science_pct_meeting_benchmark", "pct"),
            ("College-going rate, class two years earlier", "college_going_rate_class_two_years_earlier", "pct"),
            ("College-going rate, students eligible for free or reduced-price lunch", "college_going_rate_frl", "pct"),
            ("Dropout rate, grades 7 to 12", "dropout_rate_grades_7_12", "pct"),
            ("English learners scoring proficient on the ELPA", "elpa_pct_proficient", "pct"),
            ("AQuESTT school ratings that are Great or Excellent", "aquestt_pct_great_or_excellent", "pct"),
            ("Chronic absenteeism", "pct_chronically_absent", "pct"),
            ("Child poverty, ages 5 to 17 (Census SAIPE)", "child_poverty_pct_saipe", "pct"),
            ("Average teacher salary", "average_teacher_salary", "dollars"),
            ("Average years of teaching experience", "average_years_experience", "plain"),
            ("Teachers with a master's degree", "pct_teachers_masters", "pct"),
            ("Inexperienced teachers, share of teacher FTE", "pct_inexperienced", "pct"),
            ("Teachers on provisional credentials", "pct_provisional", "pct"),
            ("Teachers teaching out of field", "pct_out_of_field", "pct")]

MONEY = [("TEEOSA aid", "teeosa", False), ("Special education", "sped", False),
         ("Property tax credits paid by the state", "credits_all", False),
         ("Homestead exemption and other state programs", "other_all", False), ("State", "state", True),
         ("Local property and motor vehicle taxes", "local_taxes_net", False), ("Other local", "other_local", False),
         ("Local", "local", True), ("Federal (not in the share)", "federal", False)]

NEED = {"basic_funding": "Basic funding", "special_receipts": "Special receipts (incl. special education)",
        "transportation": "Transportation", "poverty": "Poverty", "lep": "Limited English proficiency",
        "system_averaging": "System averaging", "distance_education": "Distance education",
        "elementary_site": "Elementary site", "summer_school": "Summer school", "focus_school": "Focus school",
        "student_growth": "Student growth", "new_school": "New school", "community_achievement": "Community achievement",
        "need_stabilization": "Need stabilization"}


class Detail:
    """Loads the bundle files once; .system(code) returns the sections for one profile."""

    def __init__(self, a):
        self.a = a
        self.cert = defaultdict(dict)
        for r in _csv("school_systems.csv"):
            self.cert[r["system"]][int(r["aid_year"])] = {k: _f(v) for k, v in r.items() if k not in ("system", "name")}
        self.rev = defaultdict(dict)
        for r in _csv("school_revenue.csv"):
            self.rev[r["system"]][int(r["school_year"][:4])] = r
        self.ptax = defaultdict(dict)
        for r in _csv("school_property_taxes.csv"):
            self.ptax[r["system"]][int(r["school_year"][:4])] = {k: _f(v) for k, v in r.items() if k not in ("system", "name", "school_year")}
        self.lc2 = defaultdict(dict)
        for r in _csv("lc2_budgets.csv"):
            self.lc2[r["system"]][int(r["budget_year"][:4])] = {k: _f(v) for k, v in r.items() if k not in ("system", "name", "budget_year")}
        self.base = defaultdict(dict)
        for r in _csv("school_tax_base.csv"):
            self.base[r["system"]][int(r["october"])] = {k: _f(v) for k, v in r.items() if k not in ("system", "name", "october")}
        self.weights = defaultdict(list)
        for r in _csv("district_county_weights.csv"):
            self.weights[r["system"]].append(r)
        self.outcomes = {r["system"]: r for r in _csv("school_outcomes.csv")}
        self.need = defaultdict(lambda: defaultdict(dict))
        for r in _csv("school_need_components.csv"):
            self.need[r["system"]][int(r["aid_year"])][r["component"]] = _f(r["amount"]) or 0.0
        self.sw = defaultdict(dict)
        for r in _csv("statewide.csv"):
            if r["value"] not in ("", None):
                self.sw[(r["topic"], r["measure"])][int(r["school_year"][:4])] = float(r["value"])

    # ------------------------------------------------------------------------------------------ helpers
    def sd(self, y):  # school-year deflator to 2019 dollars
        return self.a.school_year_deflator(y)

    def cd(self, y):  # calendar-year deflator
        return self.a.calendar_deflator(y)

    def state_hist(self, y):
        t = lambda m: self.sw[("teeosa_statewide", m)].get(y)
        return {"students": t("students"), "need": t("need"), "aid": t("aid")}

    def money_ps(self, x: dict, adm: float, defl: float) -> dict:
        if not adm or not defl:
            return {}
        k = defl / adm
        v = {"teeosa": x["teeosa"], "sped": x["sped"], "credits_all": x["credits"] + x["lb1107"],
             "other_all": x["homestead"] + x["other_state"], "state": x["state"], "local_taxes_net": x["local_taxes"] - x["lb1107"],
             "other_local": x["other_local"], "local": x["local"], "federal": x["federal"]}
        return {key: val * k for key, val in v.items()}

    def rev_row(self, r: dict) -> dict:
        g = lambda k: _f(r[k]) or 0.0
        return {"teeosa": g("teeosa_aid"), "sped": g("special_education"), "credits": g("property_tax_credits"),
                "lb1107": g("lb1107_credit_estimate"), "homestead": g("homestead_exemption"), "other_state": g("other_state"),
                "state": g("state_total"), "local_taxes": g("local_taxes_as_reported"), "other_local": g("other_local"),
                "local": g("local_total_less_lb1107"), "federal": g("federal")}

    def state_rev(self, y: int) -> dict | None:
        m = lambda k: self.sw[("school_money", k)].get(y)
        if m("adm") is None:
            return None
        return {"teeosa": m("teeosa"), "sped": m("sped"), "credits": m("credits"), "lb1107": m("lb1107") or 0.0,
                "homestead": m("homestead"), "other_state": m("other_state"), "state": m("state"), "local_taxes": m("local_taxes"),
                "other_local": m("other_local"), "local": m("local"), "federal": m("federal"), "adm": m("adm"),
                "state_share": m("state_share"), "state_share_xc": m("state_share_xc")}

    # ------------------------------------------------------------------------------------------ sections
    def since(self, code: str) -> dict | None:
        h = self.cert.get(code, {})
        y0, y1 = 2019, self.a.aid_year
        if y0 not in h or y1 not in h:
            return {"none": f"This system was formed by reorganization after {sy(y0)}, so it has no {sy(y0)} certification to compare with."}
        b, n = h[y0], h[y1]
        s0, s1 = self.state_hist(y0), self.state_hist(y1)
        st_ch = lambda a_, b_: 100 * (b_ / a_ - 1) if a_ and b_ else None
        rows = []
        items = [
            ("Formula students", "count", b["formula_students"], n["formula_students"],
             st_ch(s0["students"], s1["students"]), "students"),
            ("School adjusted valuation, 2019 dollars", "dollars", b["teeosa_adjusted_valuation"] * self.cd(y0 - 1),
             n["teeosa_adjusted_valuation"] * self.cd(y1 - 1), None, None),
            ("Formula need per student, 2019 dollars", "dollars", b["formula_need"] / b["formula_students"] * self.sd(y0),
             n["formula_need"] / n["formula_students"] * self.sd(y1),
             st_ch(s0["need"] / s0["students"] * self.sd(y0), s1["need"] / s1["students"] * self.sd(y1)), None),
            ("TEEOSA aid per formula student, 2019 dollars", "dollars", b["total_state_aid"] / b["formula_students"] * self.sd(y0),
             n["total_state_aid"] / n["formula_students"] * self.sd(y1),
             st_ch(s0["aid"] / s0["students"] * self.sd(y0), s1["aid"] / s1["students"] * self.sd(y1)), None),
        ]
        for label, kind, v0, v1, sc, unit in items:
            ch = 100 * (v1 / v0 - 1) if v0 else None
            rows.append({"label": label, "base": f"{v0:,.0f}" if kind == "count" else dollars(v0),
                         "now": f"{v1:,.0f}" if kind == "count" else dollars(v1),
                         "change": fmt.pct_change(ch) if ch is not None else "n/a", "raw": raw(v1 - v0, kind, unit),
                         "all": fmt.pct_change(sc) if sc is not None else "n/a",
                         "tone": "" if ch is None or round(ch, 1) == 0 else ("up" if ch > 0 else "down")})
        return {"rows": rows, "y0": sy(y0), "y1": sy(y1)}

    def money(self, code: str) -> dict | None:
        rv = self.rev.get(code)
        if not rv:
            return None
        last = max(rv)
        x1 = rv[last]
        x0 = rv.get(2019)
        ps = lambda r: self.money_ps(self.rev_row(r), _f(r["adm"]), _f(r["deflator_to_2019_dollars"]))
        p0, p1 = (ps(x0) if x0 else {}), ps(x1)
        st = self.state_rev(last)
        pst = self.money_ps(st, st["adm"], self.sd(last)) if st else {}
        rows = []
        for label, key, total in MONEY:
            a_, b_ = p0.get(key), p1.get(key)
            rows.append({"label": label, "total": total, "v0": dollars(a_) if x0 else None, "v1": dollars(b_),
                         "ch": signed_money(b_ - a_) if a_ is not None and b_ is not None else "n/a", "all": dollars(pst.get(key))})
        sh0, sh1 = (_f(x0["state_share_pct"]) if x0 else None), _f(x1["state_share_pct"])
        xc0, xc1 = (_f(x0["state_share_credits_as_local_pct"]) if x0 else None), _f(x1["state_share_credits_as_local_pct"])
        d = (sh1 - sh0) if sh0 is not None and sh1 is not None else None
        rows.append({"label": "State share of General Fund receipts", "total": True, "v0": pct(sh0) if x0 else None, "v1": pct(sh1),
                     "ch": ((("+" if d > 0 else MINUS if d < 0 else "") + f"{abs(d):.1f} pts") if d is not None else "n/a"),
                     "all": pct(st["state_share"]) if st else ""})
        lead = (f"State sources were {pct(sh1)} of the system's General Fund receipts in {sy(last)}"
                + (f", against {pct(sh0)} in {sy(2019)}" if sh0 is not None else "")
                + f"; counting property tax credits and homestead reimbursement as local, {pct(xc1)}"
                + (f" against {pct(xc0)}." if xc0 is not None else "."))
        ppc = self.a.value("system", code, "ppc_adm")
        stp = self.sw[("per_pupil_cost", "total")]
        py = max(stp) if stp else None
        if isinstance(ppc, (int, float)) and py:
            lead += f" NDE's per pupil cost, what the system spent per student, was {fmt.money(ppc)} (current dollars) in {sy(py)}, against {fmt.money(stp[py])} statewide."
        return {"rows": rows, "y0": sy(2019) if x0 else None, "y1": sy(last), "lead": lead,
                "flag": x1.get("credit_booking_flag") == "True"}

    def taxes(self, code: str) -> dict | None:
        pa, lc = self.ptax.get(code, {}), self.lc2.get(code, {})
        if not pa and not lc:
            return None
        out = {"per": [], "lc2": [], "years": [], "lc2_years": []}
        last = max(pa) if pa else None
        ps = lambda y, k: pa[y][k] / pa[y]["adm"] * pa[y]["deflator_to_2019_dollars"] if y in pa and pa[y]["adm"] else None
        if pa:
            yrs = [y for y in (2019, last) if y in pa]
            out["years"] = [sy(y) for y in yrs]
            for label, k in (("Property taxes received, with state credits", "taxes_billed_with_credits"),
                             ("Paid by the state as credits", "paid_by_state_credits"), ("Paid by local taxpayers", "paid_by_local_taxpayers")):
                vals = [ps(y, k) for y in yrs]
                ch = signed_money(vals[1] - vals[0]) if len(vals) == 2 and None not in vals else None
                out["per"].append({"label": label, "vals": [dollars(v) for v in vals], "ch": ch, "total": k == "paid_by_local_taxpayers"})
        if lc:
            ys = sorted(lc)
            out["lc2_years"] = [sy(y) for y in ys]
            g = lambda y, k: lc[y].get(k)
            lines = [("Certified taxable valuation", lambda y: g(y, "certified_value_B490"), dollars),
                     ("Property tax request authority, base", lambda y: g(y, "authority_base_D110"), dollars),
                     ("Added by a 70% school board vote", lambda y: g(y, "board_vote_added_D140"), dollars),
                     ("Added by voters or a levy override", lambda y: (g(y, "voter_added_D160") or 0) + (g(y, "override_added_D170") or 0), dollars),
                     ("Total authority", lambda y: g(y, "total_authority_D180"), dollars),
                     ("Property tax request, general fund", lambda y: g(y, "request_general_fund_D210"), dollars),
                     ("Property tax request, special building fund", lambda y: g(y, "request_special_building_D220"), dollars),
                     ("Total request", lambda y: g(y, "request_total_D230"), dollars),
                     ("Unused authority", lambda y: g(y, "unused_D240"), dollars),
                     ("Unused, share of authority", lambda y: 100 * g(y, "unused_D240") / g(y, "total_authority_D180")
                      if g(y, "total_authority_D180") and g(y, "unused_D240") is not None else None, pct),
                     ("General fund levy per $100 of taxable valuation", lambda y: 100 * g(y, "request_general_fund_D210") / g(y, "certified_value_B490")
                      if g(y, "certified_value_B490") and g(y, "request_general_fund_D210") is not None else None,
                      lambda v: "n/a" if v is None else f"${v:.2f}")]
            for label, fn, f_ in lines:
                vals = [fn(y) for y in ys]
                if label.startswith("Added by voters") and not any(vals):
                    continue
                out["lc2"].append({"label": label, "vals": [f_(v) for v in vals], "total": label in ("Total authority", "Total request")})
        lead = ""
        k1, k0 = (ps(last, "paid_by_local_taxpayers") if last else None), ps(2019, "paid_by_local_taxpayers")
        if k1 and k0:
            lead = (f"Local taxpayers paid {fmt.money(k1)} per student in {sy(last)} (2019 dollars), "
                    f"{fmt.pct_change(100 * (k1 / k0 - 1))} since {sy(2019)}.")
        if lc:
            y = max(lc)
            z = lc[y]
            share = 100 * z["unused_D240"] / z["total_authority_D180"] if z.get("total_authority_D180") and z.get("unused_D240") is not None else None
            lead += (f" For {sy(y)} it requested {dollars(z['request_total_D230'])}"
                     + (f", leaving {pct(share)} of its authority unused. Unused authority is room under the LB 243 cap, part of it "
                        f"added by board vote; it is not money held back." if share is not None else "."))
        out["lead"] = lead.strip()
        return out

    def need_parts(self, code: str) -> dict | None:
        n = self.need.get(code)
        h = self.cert.get(code, {})
        y1 = self.a.aid_year
        y0 = 2019 if 2019 in (n or {}) and 2019 in h else None
        if not n or y1 not in n or y1 not in h:
            return None
        per = lambda y, c: n[y].get(c, 0.0) / h[y]["formula_students"] * self.sd(y) if h[y]["formula_students"] else None
        comps = sorted(NEED, key=lambda c: -(per(y1, c) or 0))
        rows = []
        for c in comps:
            a_, b_ = (per(y0, c) if y0 else None), per(y1, c)
            if not a_ and not b_:
                continue
            rows.append({"label": NEED[c], "v0": dollars(a_) if y0 else None, "v1": dollars(b_),
                         "ch": signed_money(b_ - a_) if y0 and a_ is not None and b_ is not None else None})
        t0 = sum(per(y0, c) or 0 for c in NEED) if y0 else None
        t1 = sum(per(y1, c) or 0 for c in NEED)
        rows.append({"label": "All components", "v0": dollars(t0) if y0 else None, "v1": dollars(t1),
                     "ch": signed_money(t1 - t0) if y0 else None, "total": True})
        return {"rows": rows, "y0": sy(y0) if y0 else None, "y1": sy(y1)}

    def taxbase(self, code: str) -> dict | None:
        b = self.base.get(code)
        if not b:
            return None
        last = max(b)
        x = b[last]
        shares = [(lbl, x.get(k)) for lbl, k in (("Residential", "residential_pct"), ("Commercial, industrial and mineral", "commercial_industrial_mineral_pct"),
                                                   ("Agricultural land and buildings", "agricultural_pct")) if x.get(k) is not None]
        change = None
        real = self.a.value("system", code, "val_real_change")  # the published measure: it deflates an unfinished year by the latest 12 months
        if 2019 in b and b[2019]["taxable_value"] and x["taxable_value"] and isinstance(real, (int, float)):
            change = f"{dollars(b[2019]['taxable_value'])} to {dollars(x['taxable_value'])}, real {fmt.pct_change(real)}"
        counties = []
        for w in sorted(self.weights.get(code, []), key=lambda w: -(_f(w["taxable_value_latest_october"]) or 0)):
            fips = w["county_fips"]
            nm = self.a.counties_xw.get(fips, {}).get("name")
            if not nm:
                continue
            counties.append({"fips": fips, "name": nm, "value": dollars(_f(w["taxable_value_latest_october"])) if _f(w["taxable_value_latest_october"]) else "—",
                             "kids": pct(100 * (_f(w["share_of_children_5_17"]) or 0)), "land": pct(100 * (_f(w["share_of_land"]) or 0))})
        return {"october": last, "shares": [(lbl, pct(v)) for lbl, v in shares], "change": change, "counties": counties}

    def outcomes_rows(self, code: str) -> dict | None:
        r, st = self.outcomes.get(code), self.outcomes.get("state")
        if not r:
            return None
        rows = [{"label": lbl, "v": outcome(_f(r.get(k)), kind), "state": outcome(_f(st.get(k)), kind) if st else ""} for lbl, k, kind in OUTCOMES]
        ela, math_ = _f(r.get("nscas_ela_pct_on_track_or_advanced")), _f(r.get("nscas_math_pct_on_track_or_advanced"))
        if ela is not None and math_ is not None and st:
            lead = (f"{pct(ela)} of students tested were on track or advanced in English language arts and {pct(math_)} in mathematics, "
                    f"against {pct(_f(st['nscas_ela_pct_on_track_or_advanced']))} and {pct(_f(st['nscas_math_pct_on_track_or_advanced']))} statewide.")
        else:
            lead = "NDE withholds some of this system's results because the groups are small."
        return {"rows": rows, "year": r["school_year"], "lead": lead}

    def history(self, code: str) -> dict | None:
        h = self.cert.get(code)
        if not h:
            return None
        rows = []
        for y in sorted(h):
            x = h[y]
            s = self.state_hist(y)
            n = x["formula_students"]
            rows.append([sy(y), f"{n:,.0f}" if n else "n/a",
                         dollars(x["teeosa_adjusted_valuation"] * self.cd(y - 1)) if x["teeosa_adjusted_valuation"] else "n/a",
                         dollars(x["formula_need"] / n * self.sd(y)) if n else "n/a", dollars(x["equalization_aid"]),
                         dollars(x["total_state_aid"] / n * self.sd(y)) if n else "n/a",
                         dollars(s["aid"] / s["students"] * self.sd(y)) if s["students"] else "n/a"])
        return {"rows": rows}

    def system(self, code: str) -> dict:
        return {"since2": self.since(code), "money": self.money(code), "taxes": self.taxes(code), "need_parts": self.need_parts(code),
                "taxbase": self.taxbase(code), "outcomes": self.outcomes_rows(code), "history": self.history(code)}
