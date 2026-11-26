"""v1 vs v2 parity: every number v1 shows on a profile, by section and row, looked up on the v2 profile.

Run with v1 built by nebraska-economy's `python -m pipeline.atlas` (into its site/) from the same pipeline commit as v2's
bundle, and v2 built by scripts/build.py:  python tools/parity.py system|county [V1_SITE] [V2_SITE]
Known exceptions, each a v2 rule: ranks read "highest" (v1 sometimes "lowest"), and a change of +200% or more reads
as a multiple (methods 8.5)."""
import re, html, json, collections, sys
from pathlib import Path
V1 = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parents[2] / "nebraska-economy" / "site"
V2 = Path(sys.argv[3]) if len(sys.argv) > 3 else Path(__file__).resolve().parents[1] / "_site"
NUM = re.compile(r"[+−-]?\$?\d[\d,]*(?:\.\d+)?%?(?: (?:million|billion|times))?")
def clean(s): return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()
def body(s):
    s = re.sub(r"<script.*?</script>|<style.*?</style>", "", s, flags=re.S)
    return s
def val(tok):
    t = tok.replace("−", "-").replace("$", "").replace(",", "").replace("%", "")
    mult = 1e6 if t.endswith(" million") else 1e9 if t.endswith(" billion") else 1
    t = t.replace(" million", "").replace(" billion", "").replace(" times", "")
    try: return float(t) * mult
    except ValueError: return None
class Nums(set):
    """Exact tokens, plus numeric match within half a part in 100,000 or one unit (deflators are rounded in the bundle)."""
    def __init__(self, toks):
        super().__init__(toks)
        import bisect
        self.vals = sorted(v for v in (val(x) for x in toks) if v is not None); self.bis = bisect
    def __contains__(self, tok):
        if set.__contains__(self, tok): return True
        v = val(tok)
        if v is None: return False
        tol = max(abs(v) * 5e-6, 1.0 if (abs(v) >= 1000 or "$" in tok) and float(v).is_integer() else 0.0)
        i = self.bis.bisect_left(self.vals, v - tol)
        return i < len(self.vals) and self.vals[i] <= v + tol
def v2nums(p):
    s = body(p.read_text(encoding="utf-8"))
    t = clean(s)
    return Nums(NUM.findall(t)), t
def norm(n): return n.replace("−", "-").replace("-", "−") if n.startswith(("-", "−")) else n
def v1rows(p):
    s = body(p.read_text(encoding="utf-8"))
    out = []
    # tiles
    for m in re.finditer(r'<div class="tile"><span class="lbl">(.*?)</span>(.*?)</div>', s, re.S):
        out.append(("tiles", clean(m.group(1)), clean(m.group(2))))
    # sections: rows of tables
    for sec in re.finditer(r'<section class="card sec" id="([^"]+)">(.*?)</section>', s, re.S):
        sid, inner = sec.group(1), sec.group(2)
        for tr in re.finditer(r"<tr[^>]*>(.*?)</tr>", inner, re.S):
            cells = [clean(c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr.group(1), re.S)]
            if cells and any(NUM.search(c) for c in cells[1:]):
                out.append((sid, cells[0], " | ".join(cells[1:])))
    return out
level = sys.argv[1] if len(sys.argv) > 1 else "system"
d1, d2 = ("district", "system") if level == "system" else ("county", "county")
miss = collections.Counter(); seen = collections.Counter(); ex = {}
pages = sorted((V1 / d1).glob("*.html"))
for p in pages:
    q = V2 / d2 / p.name
    if not q.exists(): miss[("PAGE", "missing")] += 1; continue
    nums, t2 = v2nums(q)
    for sec, lab, vals in v1rows(p):
        key = (sec, re.sub(r"\d{4}-\d{2}|\d{4}", "Y", lab)[:70])
        seen[key] += 1
        vs = [norm(n) for n in NUM.findall(vals)]
        lost = [n for n in vs if n not in nums and n.replace("−", "-") not in nums and n.lstrip("+") not in nums]
        if lost:
            miss[key] += 1; ex.setdefault(key, (p.stem, vals[:120], lost[:4]))
print(len(pages), "pages")
rows = sorted(seen, key=lambda k: (k[0], -seen[k]))
for k in rows:
    if miss[k]:
        print(f"{miss[k]:4d}/{seen[k]:<4d} {k[0]:10s} {k[1][:60]:60s} e.g. {ex[k][0]}: {ex[k][1][:70]} -> missing {ex[k][2]}")
full = sum(1 for k in rows if not miss[k]); print("rows fully present:", full, "of", len(rows))
