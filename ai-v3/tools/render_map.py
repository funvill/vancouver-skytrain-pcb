"""Render a city data file to an SVG preview of the LED PCB.

Usage:
    python render_map.py ../input/vancouver.json out.svg [--scale 1.0]
        [--text 1.2] [--short] [--collisions]

Board look: black soldermask, white silkscreen. Coordinates scale with
--scale (board size = canvas_mm * scale); text height stays constant,
which is exactly the experiment the fit test needs.
"""
import argparse

import citymap
from check_fit import find_collisions

LED_W, LED_H = 1.6, 1.5   # XL-1615RGBC body
LINE_W = 1.2              # route line width, mm
XIAO_W, XIAO_H = 17.8, 21.0


def _fmt(pts):
    return " ".join(f"{x:.2f},{y:.2f}" for x, y in pts)


def render(city, scale=1.0, text_h=1.2, use_short=False, collisions=None):
    size = city.canvas_mm * scale
    s = []
    s.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}mm" '
             f'height="{size}mm" viewBox="0 0 {size} {size}" '
             f'font-family="sans-serif">')
    # board (black soldermask)
    s.append(f'<rect x="0" y="0" width="{size}" height="{size}" rx="4" '
             f'fill="#161616"/>')
    # geography (repelled from LED pads + inset from the board edge - the
    # same adjusted shapes that go on copper, so preview == physical board)
    avoid_pts = [(st.x * scale, st.y * scale)
                for st in list(city.stations.values()) + city.extras]
    for g in citymap.prepared_geo(city, scale, avoid_pts):
        pts = g["points"]
        if g["type"] in ("water", "lake"):
            s.append(f'<polygon points="{_fmt(pts)}" fill="#0a2333" '
                     f'stroke="#3d5a6e" stroke-width="0.15"/>')
        elif g["type"] == "river":
            s.append(f'<polyline points="{_fmt(pts)}" fill="none" '
                     f'stroke="#0a2333" stroke-width="{g.get("width", 2.5)}" '
                     f'stroke-linejoin="round"/>')
        elif g["type"] == "park":
            s.append(f'<polygon points="{_fmt(pts)}" fill="#12331c" '
                     f'stroke="#3f6647" stroke-width="0.15"/>')
        elif g["type"] == "line":
            dash = {"dash": "2.2,1.4", "dot": "0.5,0.9",
                    "dashdot": "3,1,0.4,1"}.get(g.get("dash"))
            da = f' stroke-dasharray="{dash}"' if dash else ""
            s.append(f'<polyline points="{_fmt(pts)}" fill="none" '
                     f'stroke="#eee" stroke-width="{g.get("width", 0.3)}"{da}/>')
        else:  # island / land outline: white silk outline
            s.append(f'<polygon points="{_fmt(pts)}" fill="none" '
                     f'stroke="#666" stroke-width="0.2"/>')
    # route lines
    for line in city.lines:
        for path in line.paths:
            pts = [(city.stations[i].x * scale, city.stations[i].y * scale)
                   for i in path]
            s.append(f'<polyline points="{_fmt(pts)}" fill="none" '
                     f'stroke="{line.color}" stroke-width="{LINE_W}" '
                     f'stroke-linejoin="round" stroke-linecap="round"/>')
    # XIAO ghost (back side, centered, USB-C down)
    cx = cy = size / 2
    s.append(f'<rect x="{cx - XIAO_W/2:.2f}" y="{cy - XIAO_H/2:.2f}" '
             f'width="{XIAO_W}" height="{XIAO_H}" fill="none" stroke="#444" '
             f'stroke-width="0.25" stroke-dasharray="1,1"/>')
    s.append(f'<rect x="{cx - 4.6:.2f}" y="{cy + XIAO_H/2 - 3:.2f}" '
             f'width="9.2" height="3.2" fill="none" stroke="#444" '
             f'stroke-width="0.25" stroke-dasharray="1,1"/>')
    # stations: LED body + dot
    for st in list(city.stations.values()) + city.extras:
        x, y = st.x * scale, st.y * scale
        s.append(f'<rect x="{x - LED_W/2:.2f}" y="{y - LED_H/2:.2f}" '
                 f'width="{LED_W}" height="{LED_H}" fill="#222" '
                 f'stroke="#777" stroke-width="0.1"/>')
        r = 1.05 if st.interchange else 0.75
        ring = '#fff' if not st.future else '#999'
        dash = ' stroke-dasharray="0.6,0.45"' if st.future else ''
        s.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{r}" fill="none" '
                 f'stroke="{ring}" stroke-width="0.35"{dash}/>')
    # labels (white silk) - block vertically centred on the anchor, as KiCad
    for st in list(city.stations.values()) + city.extras:
        lines = citymap.display_lines(st, use_short)
        lx, ly = citymap.label_anchor(st, scale)
        anchor = st.label["anchor"]
        pitch = text_h * citymap.LINE_PITCH
        y0 = -(len(lines) - 1) * pitch / 2
        spans = "".join(
            f'<tspan x="0" y="{y0 + i * pitch:.2f}">{t}</tspan>'
            for i, t in enumerate(lines))
        s.append(f'<text transform="translate({lx:.2f},{ly:.2f}) '
                 f'rotate({st.label["angle"]})" text-anchor="{anchor}" '
                 f'dominant-baseline="middle" '
                 f'font-size="{text_h * 1.35:.2f}" fill="#eee">{spans}</text>')
        seg = citymap.leader_segment(st, scale)
        if seg:
            s.append(f'<line x1="{seg[0][0]:.2f}" y1="{seg[0][1]:.2f}" '
                     f'x2="{seg[1][0]:.2f}" y2="{seg[1][1]:.2f}" '
                     f'stroke="#eee" stroke-width="0.15"/>')
    for a in city.annotations:
        fill = "#c9a227" if a.get("copper") else "#eee"
        anchor = {"center": "middle", "end": "end"}.get(a.get("anchor"), "start")
        s.append(f'<text x="{a["x"] * scale:.2f}" y="{a["y"] * scale:.2f}" '
                 f'text-anchor="{anchor}" dominant-baseline="middle" '
                 f'font-size="{a.get("size", 1.4) * 1.35:.2f}" fill="{fill}" '
                 f'{"font-weight=bold" if a.get("bold") else ""}>{a["text"]}</text>')
    # collision overlay
    for c in collisions or []:
        s.append(f'<polygon points="{_fmt(c.poly)}" fill="rgba(255,40,40,0.45)" '
                 f'stroke="#ff2828" stroke-width="0.15"/>')
    # caption
    s.append(f'<text x="2.5" y="{size - 2}" font-size="2.2" fill="#555">'
             f'{city.name} v3 preview — board {size:.0f} mm, text '
             f'{text_h} mm{" (short names)" if use_short else ""}</text>')
    s.append('</svg>')
    return "\n".join(s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("out")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--text", type=float, default=1.2)
    ap.add_argument("--short", action="store_true")
    ap.add_argument("--collisions", action="store_true")
    args = ap.parse_args()
    city = citymap.load(args.data)
    cols = None
    if args.collisions:
        cols = find_collisions(city, args.scale, args.text, args.short)
    svg = render(city, args.scale, args.text, args.short, cols)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"wrote {args.out}" + (f" ({len(cols)} collisions)" if cols is not None else ""))


if __name__ == "__main__":
    main()
