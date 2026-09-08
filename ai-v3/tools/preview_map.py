"""Board-accurate PNG preview of vancouver.json without KiCad.

Draws exactly what export_art.py will put on the board - water and
copper furniture in gold, routes / rings / labels / leaders in white silk
- using the same geometry helpers (citymap.prepared_geo, label_anchor,
display_lines, leader_segment), so the label layout can be iterated here
and only committed to the .kicad_pcb once it reads well.

Usage:
    python preview_map.py ../input/vancouver.json ../test-results/preview.png [--scale 2.0] [--collisions]
"""
import argparse
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, PathPatch
from matplotlib.path import Path

import citymap
import check_fit
import export_art

GOLD, SILK, MASK = "#e8c93a", "#f4f4f4", "#2f5442"
PT_PER_MM = 72 / 25.4
FONT = "DejaVu Sans Mono"   # closest stock match to KiCad's stroke font width


def font_pt(size_mm):
    # KiCad's "size" is roughly the cap height; matplotlib's is the em box
    return size_mm * PT_PER_MM * 1.35


def draw_poly(ax, pts, color, z):
    ax.add_patch(PathPatch(Path(pts + [pts[0]], closed=True), facecolor=color,
                           edgecolor="none", zorder=z))


def render(city, scale, out, collisions=False, dpi=300):
    W, H = city.canvas_mm * scale, city.height * scale
    fig = plt.figure(figsize=(W / 25.4, H / 25.4), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)
    ax.set_facecolor(MASK)
    ax.set_axis_off()
    avoid = export_art.avoid_points(city, scale)
    geo = citymap.prepared_geo(city, scale, avoid)
    for g in geo:
        pts = [tuple(p) for p in g["points"]]
        if g["type"] in ("water", "lake"):
            draw_poly(ax, pts, GOLD, 1)
        elif g["type"] == "line":
            col = GOLD if g.get("copper") else SILK
            w = g.get("width", 0.3)
            xs, ys = zip(*pts)
            dash = g.get("dash")
            ls = {"dot": (0, (1.0, 1.8)), "dash": (0, (4.4, 2.8)),
                  "dashdot": (0, (7, 2.5, 1, 2.5))}.get(dash, "solid")
            ax.plot(xs, ys, color=col, lw=w * PT_PER_MM, ls=ls, zorder=2,
                    solid_capstyle="butt")
        elif g["type"] == "park":
            xs, ys = zip(*(pts + [pts[0]]))
            ax.plot(xs, ys, color=SILK, lw=0.15 * PT_PER_MM, zorder=2)
    # routes
    for _, p1, p2, a, b in citymap.segments(city):
        ax.plot([p1[0] * scale, p2[0] * scale], [p1[1] * scale, p2[1] * scale],
                color=SILK, lw=export_art.ROUTE_W * PT_PER_MM, zorder=3,
                solid_capstyle="round")
    # stations: ring + pad
    for st in list(city.stations.values()) + city.extras:
        x, y = st.x * scale, st.y * scale
        r, w = ((export_art.RING_R_INT, export_art.RING_W_INT) if st.interchange
                else (export_art.RING_R, export_art.RING_W))
        ax.add_patch(Circle((x, y), r, fill=False, ec=SILK, lw=w * PT_PER_MM, zorder=4))
        ax.add_patch(plt.Rectangle((x - 0.8, y - 0.75), 1.6, 1.5, fc=GOLD, ec="none", zorder=4))
    # labels + leaders
    for st in list(city.stations.values()) + city.extras:
        lx, ly = citymap.label_anchor(st, scale)
        text = "\n".join(citymap.display_lines(st))
        ha = "left" if st.label["anchor"] == "start" else "right"
        ax.text(lx, ly, text, fontsize=font_pt(citymap.TEXT_H), color=SILK,
                rotation=-st.label["angle"], rotation_mode="anchor", ha=ha,
                va="center", family=FONT, linespacing=1.15, zorder=5)
        seg = citymap.leader_segment(st, scale)
        if seg:
            ax.plot([seg[0][0], seg[1][0]], [seg[0][1], seg[1][1]], color=SILK,
                    lw=0.15 * PT_PER_MM, zorder=5)
    for a in city.annotations:
        col = GOLD if a.get("copper") else SILK
        ha = {"center": "center", "end": "right"}.get(a.get("anchor"), "left")
        ax.text(a["x"] * scale, a["y"] * scale, a["text"], fontsize=font_pt(a.get("size", 1.4)),
                color=col, ha=ha, va="center", family=FONT, zorder=5,
                fontweight="bold" if a.get("bold") else "normal",
                rotation=-a.get("angle", 0))
    if collisions:
        for col_ in check_fit.find_collisions(city, scale):
            if col_.kind == "label-geo":
                continue
            pts = [tuple(p) for p in col_.poly]
            ax.add_patch(PathPatch(Path(pts + [pts[0]], closed=True), facecolor="#ff3030",
                                   alpha=0.45, edgecolor="#ff3030", lw=0.5, zorder=6))
    fig.savefig(out, dpi=dpi, facecolor=MASK)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("out")
    ap.add_argument("--scale", type=float, default=2.0)
    ap.add_argument("--collisions", action="store_true")
    ap.add_argument("--dpi", type=int, default=300)
    args = ap.parse_args()
    city = citymap.load(args.data)
    render(city, args.scale, args.out, args.collisions, args.dpi)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
