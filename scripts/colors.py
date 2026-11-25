"""Color checks for the design tokens: contrast and color-blind separation.

Separation is the distance between two colors in OKLab, times 100, after simulating
deuteranopia and protanopia (Machado, Oliveira and Fernandes 2009, severity 1.0).
About 10 reads as clearly different; under 5 most readers with color blindness see one color.
"""
import re
from pathlib import Path

import numpy as np

TOKENS = Path(__file__).resolve().parents[1] / "design" / "tokens.css"

DEUTAN = np.array([[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]])
PROTAN = np.array([[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]])
_M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566], [0.0883024619, 0.2817188376, 0.6299787005]])
_M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468], [1.9779984951, -2.4285922050, 0.4505937099], [0.0259040371, 0.7827717662, -0.8086757660]])


def tokens() -> dict:
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", TOKENS.read_text()))


def _lin(hexcolor: str) -> np.ndarray:
    c = np.array([int(hexcolor[i:i + 2], 16) for i in (1, 3, 5)]) / 255
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _oklab(lin: np.ndarray) -> np.ndarray:
    return _M2 @ np.cbrt(_M1 @ lin)


def separation(a: str, b: str) -> float:
    """Smallest OKLab distance x 100 across normal vision, deuteranopia and protanopia."""
    la, lb = _lin(a), _lin(b)
    out = [np.linalg.norm(_oklab(la) - _oklab(lb))]
    for m in (DEUTAN, PROTAN):
        out.append(np.linalg.norm(_oklab(np.clip(m @ la, 0, 1)) - _oklab(np.clip(m @ lb, 0, 1))))
    return float(min(out) * 100)


def contrast(a: str, b: str) -> float:
    """WCAG 2 contrast ratio."""
    def lum(h):
        r, g, b_ = _lin(h)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b_
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def ramp(name: str, n: int) -> list:
    t = tokens()
    prefix = "change" if name == "change7" else name
    return [t[f"{prefix}-{i}"] for i in range(1, n + 1)]
