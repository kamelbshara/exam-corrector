"""
Renders question/option strings (plain text with inline LaTeX math wrapped
in $...$, matplotlib "mathtext" syntax -- the same subset MathJax renders
on the web side) to tightly-cropped PNGs, for embedding into the printed
PDF via reportlab. Text and math share one renderer call since matplotlib
mathtext already handles mixed plain-text/math within a single string.
"""
import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from PIL import Image  # noqa: E402

DPI = 250
_cache = {}


def render_to_png(text, fontsize=9, bold=False, color="black"):
    """Returns (png_bytes, width_pt, height_pt). Cached by (text, fontsize,
    bold, color) since the same option/question strings recur often within
    one PDF (e.g. re-rendered for both teacher and student flavors)."""
    key = (text, fontsize, bold, color)
    if key in _cache:
        return _cache[key]

    fig = plt.figure(figsize=(0.1, 0.1))
    fig.text(0, 0, text, fontsize=fontsize, color=color, fontweight="bold" if bold else "normal")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=DPI, bbox_inches="tight", pad_inches=0.02, transparent=True)
    plt.close(fig)
    buf.seek(0)
    png_bytes = buf.getvalue()

    img = Image.open(io.BytesIO(png_bytes))
    w_px, h_px = img.size
    w_pt = w_px / DPI * 72
    h_pt = h_px / DPI * 72

    result = (png_bytes, w_pt, h_pt)
    _cache[key] = result
    return result


def clear_cache():
    _cache.clear()
