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
    # geography
    for g in city.geo:
        pts = [(x * scale, y * scale) for x, y in g["points"]]
        if g["type"] in ("water", "lake"):
            s.append(f'<polygon points="{_fmt(pts)}" fill="#0a2333"/>')
        elif g["type"] == "river":
            s.append(f'<polyline points="{_fmt(pts)}" fill="none" '
                     f'stroke="#0a2333" stroke-width="{g.get("width", 2.5)}" '
                     f'stroke-linejoin="round"/>')
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
    # labels (white silk)
    for st in list(city.stations.values()) + city.extras:
        text = st.short if use_short else st.name
        lx = st.x * scale + st.label["dx"]
        ly = st.y * scale + st.label["dy"]
        anchor = st.label["anchor"]
        s.append(f'<text transform="translate({lx:.2f},{ly:.2f}) '
                 f'rotate({st.label["angle"]})" text-anchor="{anchor}" '
                 f'font-size="{text_h * 1.35:.2f}" fill="#eee">{text}</text>')
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
