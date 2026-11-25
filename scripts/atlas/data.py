"""Load the measures bundle, the registry and the crosswalks into one object the templates read."""
import csv
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "data" / "bundle"
REG = ROOT / "registry"


def _js(name: str) -> dict:
    s = (BUNDLE / name).read_text(encoding="utf-8")
    return json.JSONDecoder().raw_decode(s[s.index("{"):])[0]


def _csv(path: Path) -> list:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


class Atlas:
    def __init__(self):
        self.registry = _csv(REG / "indicators.csv")
        self.ind = {(r["key"], r["level"]): r for r in self.registry}
        self.families = _csv(REG / "families.csv")
        self.systems_xw = {r["system_code"]: r for r in _csv(REG / "crosswalk_systems.csv")}
        self.counties_xw = {r["fips"]: r for r in _csv(REG / "crosswalk_counties.csv")}
        self.towns = _csv(REG / "crosswalk_towns.csv")
        self.manifest = json.loads((BUNDLE / "manifest.json").read_text())
        self.county_js = _js("data.js")
        self.system_js = _js("data_sd.js")
        self.geo_county = _js("geo.js")
        self.geo_system = _js("geo_sd.js")
        # Periods follow the data. The bundle labels each measure's latest period, so a new LAUS month or LC-2 year
        # moves the label with the values. The registry period is the fallback for measures the bundle leaves unlabeled.
        for (key, level), r in self.ind.items():
            js = self.county_js if level == "county" else self.system_js
            p = ((js.get("indicators") or {}).get(key) or {}).get("period")
            if p:
                r["registry_period"], r["period"] = r["period"], p
        self.deflators = {r["year"]: r for r in _csv(BUNDLE / "deflators.csv")}
        self.formula = {r["system"]: {k: _num(v) for k, v in r.items()} for r in _csv(BUNDLE / "school_formula.csv")}
        self.need_parts = {}
        for r in _csv(BUNDLE / "school_need_components.csv"):
            if r["aid_year"] and int(float(r["aid_year"])) == int(next(iter(self.formula.values()))["aid_year"]):
                self.need_parts.setdefault(r["system"], {})[r["component"]] = _num(r["amount"]) or 0
        self.cert = {}
        for r in _csv(BUNDLE / "school_systems.csv"):
            self.cert.setdefault(r["system"], {})[int(r["aid_year"])] = {k: _num(v) for k, v in r.items()}
        self.aid_year = int(next(iter(self.formula.values()))["aid_year"])
        self._rank_cache = {}

    # --- values ---------------------------------------------------------------------------
    def places(self, level: str) -> dict:
        return self.county_js["counties"] if level == "county" else self.system_js["districts"]

    def value(self, level: str, place: str, key: str):
        return self.places(level).get(place, {}).get("v", {}).get(key)

    def text(self, level: str, place: str, key: str):
        return self.places(level).get(place, {}).get("d", {}).get(key)

    def key_eight(self, level: str) -> list:
        rows = [r for r in self.registry if r["level"] == level and r["key_indicator"] == "yes"]
        return sorted(rows, key=lambda r: int(r["key_order"]))

    def stats(self, level: str, key: str) -> dict:
        """Sorted values, median and count for one measure across every place that has it."""
        ck = (level, key)
        if ck not in self._rank_cache:
            vals = [p["v"].get(key) for p in self.places(level).values()]
            vals = sorted(v for v in vals if isinstance(v, (int, float)))
            self._rank_cache[ck] = {"vals": vals, "n": len(vals), "median": statistics.median(vals) if vals else None}
        return self._rank_cache[ck]

    def rank(self, level: str, place: str, key: str):
        """(rank from the highest, count, position 0..100 from the lowest). Ties share the higher rank."""
        v = self.value(level, place, key)
        s = self.stats(level, key)
        if not isinstance(v, (int, float)) or s["n"] < 2:
            return None
        above = sum(1 for x in s["vals"] if x > v)
        below = sum(1 for x in s["vals"] if x < v)
        return above + 1, s["n"], round(100 * below / (s["n"] - 1), 1)

    # --- deflators (methods spec 2.2) -----------------------------------------------------
    def school_year_deflator(self, aid_year: int) -> float:
        return float(self.deflators[str(aid_year)]["school_year_deflator"])

    def calendar_deflator(self, year: int) -> float:
        return float(self.deflators[str(year)]["calendar_year_deflator"])

    def tier_name(self, fips: str) -> str:
        return {"metro": "Metropolitan", "micro": "Micropolitan", "rural": "Rural"}.get(self.counties_xw[fips]["tier"], "")
