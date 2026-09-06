"""Parse the v1 natural map's coastline (v1/input/natrual/map.svg, F.Mask
layer path `rect3973`) into subpath polygons in svg mm -> coast_mm.json
next to the svg, which build_from_v1.py assembles (even-odd) into water.

The path uses m/l/h/v/c/z with relative coords and a scale(0.26458333)
transform (px -> mm); cubic curves are flattened to their end points,
which at this map's detail is well under the copper's 0.25 mm simplify.

Run once (or after editing map.svg):  python parse_v1_coast.py
"""
import json
import re

SVG = "../../v1/input/natrual/map.svg"
OUT = "../../v1/input/natrual/coast_mm.json"
S = 0.26458333  # the path's transform="scale(...)": px -> mm

t = open(SVG, encoding="utf-8").read()
i = t.index('id="rect3973"')
seg = t[t.rfind("<path", 0, i):t.index("/>", i)]
d = re.search(r'\bd="([^"]*)"', seg, re.S).group(1)
toks = re.findall(r"[A-Za-z]|-?[\d.]+(?:e-?\d+)?", d)

subs, cur = [], []
x = y = sx = sy = 0.0
cmd = None
k = 0


def num():
    global k
    v = float(toks[k])
    k += 1
    return v


while k < len(toks):
    if toks[k].isalpha():
        cmd = toks[k]
        k += 1
    if cmd in "mM":
        nx, ny = num(), num()
        x, y = (x + nx, y + ny) if cmd == "m" else (nx, ny)
        if cur:
            subs.append(cur)
        cur = [(x, y)]
        sx, sy = x, y
        cmd = "l" if cmd == "m" else "L"
    elif cmd in "lL":
        nx, ny = num(), num()
        x, y = (x + nx, y + ny) if cmd == "l" else (nx, ny)
        cur.append((x, y))
    elif cmd in "hH":
        v = num()
        x = x + v if cmd == "h" else v
        cur.append((x, y))
    elif cmd in "vV":
        v = num()
        y = y + v if cmd == "v" else v
        cur.append((x, y))
    elif cmd in "cC":
        vals = [num() for _ in range(6)]
        x, y = (x + vals[4], y + vals[5]) if cmd == "c" else (vals[4], vals[5])
        cur.append((x, y))
    elif cmd in "zZ":
        x, y = sx, sy
        subs.append(cur)
        cur = []
        cmd = None
    else:
        raise SystemExit(f"unhandled path command {cmd!r} at token {k}")
if cur:
    subs.append(cur)

polys = [[(round(px * S, 2), round(py * S, 2)) for px, py in s] for s in subs]
json.dump(polys, open(OUT, "w"))
print(f"{len(polys)} subpaths -> {OUT}")
