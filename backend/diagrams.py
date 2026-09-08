"""
Generates small illustrative diagrams for questions where a picture makes
the problem clearer (geometry shapes, coordinate points, function graphs,
data bar charts). Returns base64-encoded PNG so it can be embedded
directly in the question bank JSON and later decoded once for both the
PDF (reportlab drawImage) and the web preview (<img src="data:...">).
"""
import base64
import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import Polygon, Rectangle, Circle, FancyArrowPatch, Wedge  # noqa: E402

DPI = 150
LINE_COLOR = "#1a1d29"
ACCENT = "#1f3a8a"
FILL = "#eef1fb"


def _finish(fig, ax):
    ax.set_aspect("equal")
    ax.axis("off")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=DPI, bbox_inches="tight", pad_inches=0.12, transparent=True)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def triangle_with_angles(angle1, angle2, unknown_label="?"):
    """A triangle with two known angles labeled and the third marked unknown."""
    fig, ax = plt.subplots(figsize=(2.6, 2.2))
    pts = np.array([[0, 0], [4, 0], [1.3, 2.6]])
    ax.add_patch(Polygon(pts, closed=True, fill=True, facecolor=FILL, edgecolor=LINE_COLOR, linewidth=1.6))
    ax.text(pts[0][0] - 0.15, pts[0][1] - 0.28, f"{angle1}°", fontsize=12, ha="center")
    ax.text(pts[1][0] + 0.15, pts[1][1] - 0.28, f"{angle2}°", fontsize=12, ha="center")
    ax.text(pts[2][0], pts[2][1] + 0.22, unknown_label, fontsize=12, ha="center", color=ACCENT, fontweight="bold")
    ax.set_xlim(-0.8, 4.8)
    ax.set_ylim(-0.7, 3.2)
    return _finish(fig, ax)


def triangle_base_height(base, height):
    """A triangle with base and (dashed) height labeled, for area questions."""
    fig, ax = plt.subplots(figsize=(2.8, 2.2))
    apex_x = base * 0.35
    pts = np.array([[0, 0], [base, 0], [apex_x, height]])
    ax.add_patch(Polygon(pts, closed=True, fill=True, facecolor=FILL, edgecolor=LINE_COLOR, linewidth=1.6))
    ax.plot([apex_x, apex_x], [0, height], linestyle="--", color=ACCENT, linewidth=1.3)
    ax.plot([apex_x - 0.12, apex_x + 0.12], [0, 0], color=ACCENT, linewidth=1.3)
    ax.text(base / 2, -height * 0.16 - 0.15, f"base = {base}", fontsize=11, ha="center")
    ax.text(apex_x + 0.15, height / 2, f"h = {height}", fontsize=11, va="center", color=ACCENT)
    ax.set_xlim(-0.6, base + 0.6)
    ax.set_ylim(-height * 0.35 - 0.4, height + 0.5)
    return _finish(fig, ax)


def rectangle_diagram(length, width):
    fig, ax = plt.subplots(figsize=(2.8, 2.0))
    ax.add_patch(Rectangle((0, 0), length, width, facecolor=FILL, edgecolor=LINE_COLOR, linewidth=1.6))
    ax.text(length / 2, -width * 0.18 - 0.1, f"{length}", fontsize=12, ha="center")
    ax.text(length + 0.18, width / 2, f"{width}", fontsize=12, va="center")
    ax.set_xlim(-0.4, length + 0.9)
    ax.set_ylim(-width * 0.4 - 0.3, width + 0.4)
    return _finish(fig, ax)


def right_triangle_diagram(opp, adj, hyp):
    """A right triangle labeled with opposite, adjacent, and hypotenuse
    sides, and the reference angle marked, for trig-ratio questions."""
    fig, ax = plt.subplots(figsize=(2.8, 2.4))
    pts = np.array([[0, 0], [adj, 0], [0, opp]])
    ax.add_patch(Polygon(pts, closed=True, fill=True, facecolor=FILL, edgecolor=LINE_COLOR, linewidth=1.6))
    # right-angle marker
    s = min(adj, opp) * 0.12
    ax.add_patch(Rectangle((0, 0), s, s, facecolor="none", edgecolor=LINE_COLOR, linewidth=1.0))
    # reference angle arc at bottom-right vertex
    ax.add_patch(Wedge((adj, 0), min(adj, opp) * 0.28, 90, 180, facecolor="none", edgecolor=ACCENT, linewidth=1.2))
    ax.text(adj * 0.42, -opp * 0.12 - 0.1, f"adj = {adj}", fontsize=10, ha="center")
    ax.text(-0.18, opp * 0.5, f"opp = {opp}", fontsize=10, va="center", ha="right")
    ax.text(adj * 0.42, opp * 0.5, f"hyp = {hyp}", fontsize=10, ha="center", color=ACCENT)
    ax.text(adj - min(adj, opp) * 0.42, min(adj, opp) * 0.12, "θ", fontsize=12, color=ACCENT)
    ax.set_xlim(-1.4, adj + 0.6)
    ax.set_ylim(-opp * 0.3 - 0.4, opp + 0.4)
    return _finish(fig, ax)


def similar_triangles_diagram(small_side, large_side):
    fig, ax = plt.subplots(figsize=(3.2, 2.0))
    small = np.array([[0, 0], [1.6, 0], [0.5, 1.4]])
    scale = large_side / small_side if small_side else 1.5
    scale = min(max(scale, 1.15), 2.0)
    large = small * scale + np.array([2.6, 0])
    ax.add_patch(Polygon(small, closed=True, fill=True, facecolor=FILL, edgecolor=LINE_COLOR, linewidth=1.5))
    ax.add_patch(Polygon(large, closed=True, fill=True, facecolor=FILL, edgecolor=LINE_COLOR, linewidth=1.5))
    ax.text(0.8, -0.28, f"{small_side}", fontsize=11, ha="center")
    ax.text(2.6 + 0.8 * scale, -0.28, f"{large_side}", fontsize=11, ha="center", color=ACCENT)
    ax.set_xlim(-0.4, 2.6 + 1.7 * scale)
    ax.set_ylim(-0.6, 1.4 * scale + 0.4)
    return _finish(fig, ax)


def cylinder_diagram(radius, height):
    fig, ax = plt.subplots(figsize=(2.4, 2.6))
    ellipse_h = radius * 0.5
    top_cy = height
    ax.add_patch(Rectangle((-radius, 0), 2 * radius, height, facecolor=FILL, edgecolor=LINE_COLOR, linewidth=1.5))
    top = plt.matplotlib.patches.Ellipse((0, top_cy), 2 * radius, ellipse_h, facecolor=FILL, edgecolor=LINE_COLOR, linewidth=1.5)
    bottom = plt.matplotlib.patches.Ellipse((0, 0), 2 * radius, ellipse_h, facecolor=FILL, edgecolor=LINE_COLOR, linewidth=1.5)
    ax.add_patch(bottom)
    ax.add_patch(top)
    ax.plot([0, radius], [top_cy, top_cy], color=ACCENT, linewidth=1.2)
    ax.text(radius * 0.5, top_cy + ellipse_h * 0.35, f"r={radius}", fontsize=10, color=ACCENT, ha="center")
    ax.text(radius + 0.25, height / 2, f"h={height}", fontsize=10, va="center")
    ax.set_xlim(-radius - 0.6, radius + 1.3)
    ax.set_ylim(-ellipse_h * 0.7, top_cy + ellipse_h * 0.7 + 0.3)
    return _finish(fig, ax)


def coordinate_points_diagram(p1, p2):
    """Two points on a coordinate grid with a connecting segment, for
    distance/slope questions."""
    fig, ax = plt.subplots(figsize=(2.8, 2.8))
    xs = [p1[0], p2[0]]
    ys = [p1[1], p2[1]]
    pad = max(2, (max(xs) - min(xs) + max(ys) - min(ys)) * 0.25)
    lo_x, hi_x = min(xs) - pad, max(xs) + pad
    lo_y, hi_y = min(ys) - pad, max(ys) + pad
    ax.axhline(0, color="#c0c5d6", linewidth=1)
    ax.axvline(0, color="#c0c5d6", linewidth=1)
    ax.plot(xs, ys, color=ACCENT, linewidth=1.6, marker="o", markersize=5, markerfacecolor=ACCENT, markeredgecolor=ACCENT)
    ax.text(p1[0], p1[1] + pad * 0.12, f"({p1[0]}, {p1[1]})", fontsize=9, ha="center")
    ax.text(p2[0], p2[1] + pad * 0.12, f"({p2[0]}, {p2[1]})", fontsize=9, ha="center")
    ax.set_xlim(lo_x, hi_x)
    ax.set_ylim(lo_y, hi_y)
    ax.grid(True, color="#e2e5ee", linewidth=0.6)
    ax.set_xticks(range(int(lo_x), int(hi_x) + 1))
    ax.set_yticks(range(int(lo_y), int(hi_y) + 1))
    ax.tick_params(labelsize=6, length=2)
    ax.axis("on")
    for spine in ax.spines.values():
        spine.set_visible(False)
    buf = io.BytesIO()
    ax.set_aspect("equal")
    fig.savefig(buf, format="png", dpi=DPI, bbox_inches="tight", pad_inches=0.12, transparent=True)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def function_graph(a, b, mark_x=None, c=0, quadratic=False):
    """Plots f(x) = a*x + b (or a*x^2 + b*x + c if quadratic), optionally
    marking the point being evaluated."""
    fig, ax = plt.subplots(figsize=(3.0, 2.4))
    span = 6
    xs = np.linspace(-span, span, 200)
    ys = a * xs ** 2 + b * xs + c if quadratic else a * xs + b
    ax.axhline(0, color="#c0c5d6", linewidth=1)
    ax.axvline(0, color="#c0c5d6", linewidth=1)
    ax.plot(xs, ys, color=ACCENT, linewidth=1.8)
    if mark_x is not None:
        my = a * mark_x ** 2 + b * mark_x + c if quadratic else a * mark_x + b
        ax.plot([mark_x], [my], marker="o", markersize=6, color="#ef4444", zorder=5)
        ax.annotate(f"({mark_x}, {my:g})", (mark_x, my), textcoords="offset points", xytext=(6, 6), fontsize=9)
    y_all = list(ys)
    if mark_x is not None:
        y_all.append(my)
    y_lo, y_hi = min(y_all), max(y_all)
    pad = max(1, (y_hi - y_lo) * 0.15)
    ax.set_xlim(-span, span)
    ax.set_ylim(y_lo - pad, y_hi + pad)
    ax.grid(True, color="#e2e5ee", linewidth=0.6)
    ax.tick_params(labelsize=6, length=2)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_aspect("auto")
    ax.axis("on")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=DPI, bbox_inches="tight", pad_inches=0.12, transparent=True)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def bar_chart(values, highlight_idx=None):
    fig, ax = plt.subplots(figsize=(3.0, 2.0))
    colors = [ACCENT] * len(values)
    if highlight_idx is not None:
        colors[highlight_idx] = "#ef4444"
    ax.bar(range(len(values)), values, color=colors, width=0.6)
    ax.set_xticks(range(len(values)))
    ax.set_xticklabels([str(v) for v in values], fontsize=8)
    ax.tick_params(left=False, labelleft=False, bottom=False)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_aspect("auto")
    ax.axis("on")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=DPI, bbox_inches="tight", pad_inches=0.12, transparent=True)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def probability_pie(favorable, total):
    fig, ax = plt.subplots(figsize=(2.0, 2.0))
    unfavorable = total - favorable
    ax.pie(
        [favorable, unfavorable],
        colors=[ACCENT, FILL],
        wedgeprops={"edgecolor": LINE_COLOR, "linewidth": 1.2},
        labels=[f"{favorable}", f"{unfavorable}"],
        textprops={"fontsize": 10},
    )
    return _finish(fig, ax)
