"""Color rules from the design system, checked on every build.

Separation is OKLab distance x 100 under normal vision, deuteranopia and protanopia
(scripts/colors.py). Contrast is the WCAG 2 ratio.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from colors import contrast, ramp, separation, tokens  # noqa: E402

MIN_STEP = 8.0       # neighboring steps on one ramp
MIN_PAPER = 7.0      # the little-change grey against the map background
MIN_CATEGORY = 10.0  # who-pays colors against each other
MIN_TEXT = 4.5       # WCAG AA for body text


def test_ramp_neighbors_separate():
    for name, n in (("howmuch6", 6), ("howmuch7", 7), ("change7", 7)):
        r = ramp(name, n)
        for i in range(n - 1):
            s = separation(r[i], r[i + 1])
            assert s >= MIN_STEP, f"{name} steps {i + 1}-{i + 2}: {s:.1f}"


def test_ramps_get_darker():
    for name, n in (("howmuch6", 6), ("howmuch7", 7)):
        r = ramp(name, n)
        lum = [contrast(c, "#000000") for c in r]
        assert lum == sorted(lum, reverse=True), name


def test_change_ramp_is_balanced():
    r = ramp("change7", 7)
    for i in range(3):
        a, b = contrast(r[i], "#000000"), contrast(r[6 - i], "#000000")
        assert abs(a - b) / max(a, b) < 0.15, f"rust step {i + 1} and slate step {7 - i} differ in lightness"


def test_little_change_stands_off_the_paper():
    t = tokens()
    assert separation(t["change-4"], t["card"]) >= MIN_PAPER


def test_who_pays_colors_separate():
    t = tokens()
    names = ["state", "credits", "local", "federal"]
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            assert separation(t[a], t[b]) >= MIN_CATEGORY, f"{a} vs {b}"


def test_text_contrast():
    t = tokens()
    for fg in ("ink", "sub", "down-text", "up-text"):
        for bg in ("ground", "card"):
            assert contrast(t[fg], t[bg]) >= MIN_TEXT, f"{fg} on {bg}"
