"""Findings: markdown files with numbers filled from facts.py, plus a chart per finding where one helps."""
import re
from pathlib import Path

import markdown
from jinja2 import Environment
from markupsafe import Markup

from . import fmt

ROOT = Path(__file__).resolve().parents[2]
LAWS = [
    ("LB 1107 (2020) and LB 34 (2024): school property tax credit",
     "Relief from school property taxes. LB 34 moved the credit onto the tax statement so every taxpayer receives it, after about 45% of Nebraskans had not claimed it on their income tax returns.",
     "Credits paid {credit_share_state} of all property taxes in 2025, {credit_share_rural} in rural counties and {credit_share_metro} in metro counties. From 2019, real taxes after credits changed {net_state} statewide while real taxes levied changed {levied_state}."),
    ("LB 583 (2023): foundation aid and special education",
     "Raise the state's investment in education and reduce schools' reliance on property taxes.",
     "TEEOSA aid rose {aid_change_dollars} from 2019-20 to {aid_year}, as foundation aid ({foundation1}) took the place of equalization aid ({eq0} to {eq1})."),
    ("LB 243 (2023): school property tax request cap",
     "Hold growth in each district's property tax request to 3% a year, with allowances, so new state money turns into property tax relief.",
     "Requests rose from {request0} in {budget_first} to {request1} in {budget_year} ({request_growth}). For {budget_year}, {votes1} of {districts1} boards voted to add authority and {unused1} went unrequested."),
    ("LB 243 (2023): community colleges",
     "Replace the community college property tax levy with state aid.",
     "Community college property taxes fell from {cc_tax0} in tax year 2019 to {cc_tax1} in {cc_year1} (current dollars)."),
]


def _bar_rows(rows, maxv):
    out = []
    for label, value, text, cls in rows:
        w = max(0.5, 100 * abs(value) / maxv) if maxv else 0
        out.append(f'<div class="brow"><span class="bl">{label}</span><div class="btrack"><div class="bar {cls}" style="width:{w:.1f}%"></div></div><b class="{cls}-text">{text}</b></div>')
    return "".join(out)


def _num(s):
    return float(s.replace("−", "-").replace("%", "").replace("+", "").replace("$", "").replace(",", ""))


def chart(kind: str, f: dict) -> str:
    if kind == "credits_vs_aid":
        rows = [("Property tax credits", f["credits_gain_raw"], "+" + f["credits_gain"], "credits"),
                ("TEEOSA aid", f["aid_gain_raw"], "+" + f["aid_gain"], "state")]
        return f'<div class="bars" role="img" aria-label="Increase 2019-20 to {f["money_year"]}: credits {f["credits_gain"]}, TEEOSA aid {f["aid_gain"]}">{_bar_rows(rows, max(r[1] for r in rows))}</div>'
    if kind == "state_share":
        s0, s1, x0, x1 = f["share_raw"]
        def dots(label, a, b):
            return (f'<div class="drow"><span class="bl">{label}</span><div class="dtrack"><span class="dline" style="left:{a / 60 * 100:.1f}%;width:{(b - a) / 60 * 100:.1f}%"></span>'
                    f'<span class="d0" style="left:{a / 60 * 100:.1f}%"></span><span class="d1" style="left:{b / 60 * 100:.1f}%"></span></div><b>{a:.1f}% to {b:.1f}%</b></div>')
        return f'<div class="dots" role="img" aria-label="State share {s0:.1f}% to {s1:.1f}%; credits as local {x0:.1f}% to {x1:.1f}%">{dots("State share of receipts", s0, s1)}{dots("Credits counted as local", x0, x1)}<p class="note">Hollow: 2019-20. Filled: {f["money_year"]}. Scale 0 to 60%.</p></div>'
    if kind in ("taxes_by_tier", "population"):
        keys = (("Rural", "net_rural"), ("Metro", "net_metro"), ("All counties", "net_state")) if kind == "taxes_by_tier" else \
               (("Metro", "pop_metro"), ("Micro", "pop_micro"), ("Rural", "pop_rural"), ("All counties", "pop_state"))
        rows = [(lab, _num(f[k]), f[k], "up" if _num(f[k]) > 0 else "down") for lab, k in keys]
        return f'<div class="bars" role="img" aria-label="{kind}">{_bar_rows(rows, max(abs(r[1]) for r in rows))}</div>'
    if kind == "requests":
        rows = "".join(f'<tr><td>{r["year"]}</td><td class="num">{r["votes"]:.0f}</td><td class="num">{r["atcap"]:.0f}</td></tr>' for r in f["requests_by_year"])
        return f'<table class="data small"><thead><tr><th>Budget year</th><th class="num">Used a 70% board vote</th><th class="num">At the cap</th></tr></thead><tbody>{rows}</tbody></table>'
    if kind == "laws":
        rows = "".join(f'<tr><td><b>{law}</b></td><td>{aim}</td><td>{out.format(**f)}</td></tr>' for law, aim, out in LAWS)
        return f'<div class="scroll"><table class="data"><thead><tr><th>Law</th><th>Stated aim</th><th>What changed since</th></tr></thead><tbody>{rows}</tbody></table></div>'
    return ""


def load(f: dict) -> list:
    env = Environment()
    out = []
    for i, p in enumerate(sorted((ROOT / "findings").glob("*.md")), 1):
        text = p.read_text(encoding="utf-8")
        m = re.match(r"---\n(.*?)\n---\n(.*)", text, re.S)
        meta = dict(line.split(": ", 1) for line in m.group(1).splitlines())
        body = env.from_string(m.group(2)).render(f=f)
        out.append({"n": f"{i:02d}", "slug": p.stem[3:], "headline": meta["headline"], "synthesis": meta.get("synthesis") == "true",
                    "html": Markup(markdown.markdown(body)), "chart": Markup(chart(meta.get("chart", ""), f))})
    return out
