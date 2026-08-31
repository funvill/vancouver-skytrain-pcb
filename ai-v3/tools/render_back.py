"""Back-side placement check: XIAO (DNP, centered, USB-C down), buttons (DNP),
level shifter, bulk caps. Rendered as seen from the BACK of the board
(front-side LEDs shown mirrored as faint ghosts to prove nothing conflicts —
the board is all-SMD, so the only true conflicts would be vias/holes).

Usage: python render_back.py ../input/vancouver.json out.svg --scale 1.35
"""
import argparse

import citymap

XIAO_W, XIAO_H = 17.8, 21.0     # module body
XIAO_COURT = 1.0                 # courtyard margin
BTN = 5.1                        # C318884 button body
SHIFTER_W, SHIFTER_H = 3.0, 3.0  # SOT-23-5 + room


def render(city, scale):
    size = city.canvas_mm * scale
    cx = cy = size / 2
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}mm" '
         f'height="{size}mm" viewBox="0 0 {size} {size}" '
         f'font-family="sans-serif">',
         f'<rect width="{size}" height="{size}" rx="4" fill="#161616"/>']
    # front LEDs mirrored (back view: x flips)
    for st in list(city.stations.values()) + city.extras:
        x, y = size - st.x * scale, st.y * scale
        s.append(f'<rect x="{x-0.8:.2f}" y="{y-0.75:.2f}" width="1.6" '
                 f'height="1.5" fill="none" stroke="#333" stroke-width="0.1"/>')
    # XIAO courtyard, centered, USB-C toward bottom edge
    w, h = XIAO_W + 2 * XIAO_COURT, XIAO_H + 2 * XIAO_COURT
    s.append(f'<rect x="{cx-w/2:.2f}" y="{cy-h/2:.2f}" width="{w:.1f}" '
             f'height="{h:.1f}" fill="none" stroke="#e8b339" '
             f'stroke-width="0.3" stroke-dasharray="1.5,1"/>')
    s.append(f'<rect x="{cx-XIAO_W/2:.2f}" y="{cy-XIAO_H/2:.2f}" '
             f'width="{XIAO_W}" height="{XIAO_H}" fill="#242424" '
             f'stroke="#888" stroke-width="0.25"/>')
    s.append(f'<rect x="{cx-4.6:.2f}" y="{cy+XIAO_H/2-3.2:.2f}" width="9.2" '
             f'height="3.2" fill="#333" stroke="#aaa" stroke-width="0.2"/>')
    s.append(f'<text x="{cx:.1f}" y="{cy-2:.1f}" font-size="2.2" fill="#ccc" '
             f'text-anchor="middle">XIAO (DNP)</text>')
    s.append(f'<text x="{cx:.1f}" y="{cy+2:.1f}" font-size="1.6" fill="#888" '
             f'text-anchor="middle">USB-C ↓</text>')
    # 4 buttons flanking the XIAO (DNP), reachable from board edge-ish
    bx = 18
    for i, (dx, name) in enumerate([(-bx, "SW1 MODE"), (-bx, "SW2 BRIGHT"),
                                    (bx, "SW3 SPEED"), (bx, "SW4 LINE")]):
        by = cy - 12 if i % 2 == 0 else cy + 12
        x = cx + dx
        s.append(f'<rect x="{x-BTN/2:.2f}" y="{by-BTN/2:.2f}" width="{BTN}" '
                 f'height="{BTN}" fill="#242424" stroke="#888" '
                 f'stroke-width="0.25"/>')
        s.append(f'<text x="{x:.1f}" y="{by+BTN/2+2.4:.1f}" font-size="1.5" '
                 f'fill="#999" text-anchor="middle">{name} (DNP)</text>')
    # level shifter + bulk caps near XIAO data/5V pins (above USB side)
    s.append(f'<rect x="{cx+XIAO_W/2+3:.2f}" y="{cy+4:.2f}" '
             f'width="{SHIFTER_W}" height="{SHIFTER_H}" fill="#242424" '
             f'stroke="#8c8" stroke-width="0.25"/>')
    s.append(f'<text x="{cx+XIAO_W/2+4.5:.2f}" y="{cy+10:.2f}" '
             f'font-size="1.5" fill="#8c8" text-anchor="middle">74AHC1G125</text>')
    for i in range(2):
        s.append(f'<rect x="{cx-XIAO_W/2-5:.2f}" y="{cy+3+i*3:.2f}" '
                 f'width="2" height="1.6" fill="#242424" stroke="#88c" '
                 f'stroke-width="0.25"/>')
    s.append(f'<text x="{cx-XIAO_W/2-4:.2f}" y="{cy+11:.2f}" font-size="1.5" '
             f'fill="#88c" text-anchor="middle">2×22µF</text>')
    s.append(f'<text x="2.5" y="{size-2}" font-size="2.2" fill="#555">'
             f'{city.name} v3 BACK side (mirrored) — board {size:.0f} mm</text>')
    s.append('</svg>')
    return "\n".join(s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("out")
    ap.add_argument("--scale", type=float, default=1.35)
    args = ap.parse_args()
    city = citymap.load(args.data)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(render(city, args.scale))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
