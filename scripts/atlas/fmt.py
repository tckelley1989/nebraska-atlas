"""Number formatting, driven by the registry's format column."""
MINUS = "−"


def signed(x: float, digits: int = 1, suffix: str = "") -> str:
    s = f"{abs(x):,.{digits}f}{suffix}"
    if round(x, digits) == 0:
        return s
    return ("+" if x > 0 else MINUS) + s


def pct_change(x: float, digits: int = 1) -> str:
    """A percent change. At three times the base or more (+200%), the multiple: a percent that large misleads
    from a small base (methods spec 8.5)."""
    if x >= 200:
        return f"{1 + x / 100:,.1f} times"
    return signed(x, digits, "%")


def money(x: float, digits: int = 0) -> str:
    s = f"${abs(x):,.{digits}f}"
    return (MINUS + s) if x < 0 else s


def big_money(x: float) -> str:
    if abs(x) >= 1e9:
        return f"${x / 1e9:,.2f} billion"
    if abs(x) >= 1e6:
        return f"${x / 1e6:,.1f} million"
    return money(x)


def value(v, row: dict, fallback: str | None = None) -> str:
    """Format one measure for display. Change measures always carry a sign (methods spec 8.3)."""
    f = row["format"]
    if f == "category" or not isinstance(v, (int, float)):
        return fallback or row.get("missing_label") or "Not available"
    diverging = row["scale"] == "diverging"
    if f == "pct_change":
        return pct_change(v)
    if f in ("pct", "rate"):
        return signed(v, 1, "%") if diverging else f"{v:,.1f}%"
    if f == "dollars":
        return money(v)
    if f == "cents":
        return money(v, 2)
    if f == "per1000":
        return signed(v, 1) if diverging or "gap" in row["key"] else f"{v:,.1f}"
    if f in ("years", "rate_plain"):
        return f"{v:,.1f}"
    return f"{v:,.2f}"


def ordinal(n: int) -> str:
    suf = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n:,}{suf}"
