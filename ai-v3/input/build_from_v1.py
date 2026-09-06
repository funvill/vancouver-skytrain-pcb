"""Assemble vancouver.json from the v1 NATURAL map (v1/input/natrual/map.svg).

That map draws Metro Vancouver as it is - Burrard Inlet with the North
Shore above it, Point Grey, the Fraser's arms winding east-west, Boundary
Bay - where TransLink's schematic (traced earlier) stretches everything
south of Broadway and turns the Fraser into a 45-degree band.

Frame: the SVG's own 200 x 100 mm page ("svg mm"). Sources:

  v1/input/natrual/map.svg     coastline (F.Mask layer path, parsed to
                               coast_mm.json by parse_v1_coast.py); station dots (green
                               squares in map.png) for snapping
  v1_station_board_xy.json     station = midpoint of its N/S LED pair on
                               the v1 board, in v1 board mm
  v1_svg_to_board.json         similarity fit  board = s*svg + t  from
                               matching those LEDs to the png's dots (the
                               v1 board rotated the map ~9 deg to level
                               the Millennium line; we keep the map's
                               orientation and map LEDs back into it)
  (Surrey-Langley Extension: v1 predates it - placed from lat/lon, see
   EXT_LATLON below)

Everything lands on the 100-unit canvas (board mm = canvas * 1.5) with ONE
uniform scale sized to the full width, Point Grey to Langley City Centre.
The region is ~2:1, so the map takes the top half of the square board and
the wordmark / legend / border the band below. Label fields are kept.

Run:  python build_from_v1.py   (needs shapely, pillow, scipy, numpy)
"""
import json
import math

import numpy as np
from PIL import Image
from scipy import ndimage
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

V1 = "../../v1/input/natrual/"
MARGIN = 4.0
SNAP_MM = 2.5   # svg mm: snap an LED-derived position to a png dot this close

fit = json.load(open("v1_svg_to_board.json"))
S = complex(*fit["s"])
T = complex(*fit["t"])


def board_to_svg(x, y):
    z = (complex(x, y) - T) / S
    return z.real, z.imag


# --- station dots from the png (green squares) -------------------------
im = np.array(Image.open(V1 + "map.png").convert("RGB")).astype(int)
H, W, _ = im.shape
r, g, b = im[..., 0], im[..., 1], im[..., 2]
lab, n = ndimage.label((g > 150) & (r < 120) & (b < 120))
dots = [(cx * 200 / W, cy * 200 / W)
        for (cy, cx), sz in zip(ndimage.center_of_mass(lab > 0, lab, range(1, n + 1)),
                                ndimage.sum(lab > 0, lab, range(1, n + 1)))
        if sz >= 4]

d = json.load(open("vancouver.json", encoding="utf-8"))
v1 = json.load(open("v1_station_board_xy.json", encoding="utf-8"))


def norm(s):
    return s.replace("–", "-").replace("—", "-").lower()


by_name = {norm(s["name"]): sid for sid, s in d["stations"].items()}
SVG = {}
snapped = 0
for name, (x, y, _n) in v1.items():
    px, py = board_to_svg(x, y)
    q = min(dots, key=lambda p: math.hypot(p[0] - px, p[1] - py))
    if math.hypot(q[0] - px, q[1] - py) <= SNAP_MM:
        px, py = q
        snapped += 1
    SVG[by_name[norm(name)]] = (px, py)

# Surrey-Langley Extension: v1 predates it. Fit lat/lon -> this map's
# frame directly (a similarity over stations at the map's corners and
# core) and place the eight stations with it, so they head ESE along
# Fraser Highway at the map's own scale and tilt.
LATLON = {
    "waterfront": (49.2856, -123.1116), "king-george": (49.1827, -122.8447),
    "lafarge": (49.2786, -122.7918), "richmond-brighouse": (49.1683, -123.1367),
    "yvr": (49.1955, -123.1817), "lougheed": (49.2486, -122.8970),
    "metrotown": (49.2258, -123.0039), "columbia": (49.2049, -122.9060),
    "commercial-broadway": (49.2625, -123.0690), "bridgeport": (49.1936, -123.1290),
}
EXT_LATLON = {
    "green-timbers": (49.1745, -122.8248), "152-street": (49.1660, -122.8010),
    "fleetwood": (49.1590, -122.7855), "bakerview": (49.1525, -122.7710),
    "hillcrest": (49.1345, -122.7330), "clayton": (49.1275, -122.7195),
    "willowbrook": (49.1180, -122.7010), "langley-city-centre": (49.1050, -122.6620),
}
KX, KY = 111.32 * math.cos(math.radians(49.2)), 111.32   # km per degree


def km(lat, lon):
    return complex((lon + 123) * KX, -(lat - 49.2) * KY)


# The v1 map is true-ish east-west but squeezes the south (Richmond to
# Boundary Bay is ~13 km drawn in 11 mm), so a true-scale extension would
# plunge off the page. Use the map's own east-west scale (Waterfront ->
# King George) for longitude and the map's southern squeeze for latitude,
# anchored on King George, so the chain runs ESE along Fraser Highway
# and Langley lands just above the page's bottom edge like everything
# else south of the Fraser.
wf_km, kg_km = km(*LATLON["waterfront"]), km(*LATLON["king-george"])
SX = (SVG["king-george"][0] - SVG["waterfront"][0]) / (kg_km.real - wf_km.real)
br_km = km(*LATLON["richmond-brighouse"])
SY = (SVG["richmond-brighouse"][1] - SVG["waterfront"][1]) / (br_km.imag - wf_km.imag)
kg = SVG["king-george"]
# ... but Langley City really is 7 km south of Brighouse, which the map
# already draws near its bottom edge: cap the southward scale so Langley
# City Centre lands just above the page edge (y=96) instead of below it.
lc_km = km(*EXT_LATLON["langley-city-centre"])
SY = min(SY, (96.0 - kg[1]) / (lc_km.imag - kg_km.imag))
print(f"extension scale: {SX:.2f} svg-mm/km east, {SY:.2f} svg-mm/km south")
for sid, ll in EXT_LATLON.items():
    dz = km(*ll) - kg_km
    SVG[sid] = (kg[0] + dz.real * SX, kg[1] + dz.imag * SY)
bp, ab = SVG["bridgeport"], SVG["aberdeen"]   # Capstan (2024) postdates v1
SVG["capstan"] = ((bp[0] + ab[0]) / 2, (bp[1] + ab[1]) / 2)
SVG["seabus"] = board_to_svg(116.75, 32.75)   # v1's SeaBus LED: Lonsdale Quay
missing = set(d["stations"]) - set(SVG)
assert not missing, f"no position for {missing}"
print(f"{snapped}/{len(v1)} v1 stations snapped to a map.png dot")

# --- frame: full width, Point Grey to Langley + label room --------------
X0, Y0 = 0.0, 0.0
FRAME_R = SVG["langley-city-centre"][0] + 9.0
SCALE = (100 - 2 * MARGIN) / (FRAME_R - X0)


def c(x, y):
    return (round(MARGIN + (x - X0) * SCALE, 2), round(MARGIN + (y - Y0) * SCALE, 2))


CANVAS = {sid: c(*xy) for sid, xy in SVG.items()}


def push(a, b, min_d):
    dd = math.hypot(b[0] - a[0], b[1] - a[1])
    if dd >= min_d:
        return b
    ux, uy = (b[0] - a[0]) / dd, (b[1] - a[1]) / dd
    return (round(a[0] + ux * min_d, 2), round(a[1] + uy * min_d, 2))


# The only deliberate bending of real proportions: runs whose stations
# are closer than a 2.8 mm LED pitch at this scale are spread outward
# along their real direction.
MIN_PITCH = 2.8 / 1.5
for chain in [["waterfront", "burrard", "granville", "stadium"],
              ["waterfront", "vancouver-city-centre", "yaletown"],
              ["bridgeport", "capstan", "aberdeen", "lansdowne",
               "richmond-brighouse"],
              ["bridgeport", "templeton", "sea-island-centre", "yvr"],
              ["lafarge", "lincoln", "coquitlam-central"]]:
    for a, b in zip(chain, chain[1:]):
        CANVAS[b] = push(CANVAS[a], CANVAS[b], MIN_PITCH)

# ... and any remaining pair closer than the pitch (Granville sits on
# Vancouver City Centre in the source, Broadway-City Hall on its
# neighbour) is separated symmetrically until nothing is too close.
ids = list(CANVAS)
for _ in range(50):
    moved = False
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            (ax, ay), (bx, by) = CANVAS[a], CANVAS[b]
            dd = math.hypot(bx - ax, by - ay)
            if dd >= MIN_PITCH - 1e-6:
                continue
            if dd < 1e-6:
                ux, uy = 1.0, 0.0
            else:
                ux, uy = (bx - ax) / dd, (by - ay) / dd
            h = (MIN_PITCH - dd) / 2 + 0.01
            CANVAS[a] = (round(ax - ux * h, 2), round(ay - uy * h, 2))
            CANVAS[b] = (round(bx + ux * h, 2), round(by + uy * h, 2))
            moved = True
    if not moved:
        break

# Tight vertical / horizontal runs at the LED pitch: two-line labels there
# stack edge to edge, so those names stay on one line.
for sid in ["king-edward", "oakridge", "langara", "marine-drive", "bridgeport",
            "capstan", "aberdeen", "lansdowne", "richmond-brighouse",
            "templeton", "sea-island-centre", "yvr", "lincoln", "lafarge",
            "coquitlam-central"]:
    d["stations"][sid]["wrap"] = False

for sid, (x, y) in CANVAS.items():
    if sid in d["stations"]:
        d["stations"][sid]["x"], d["stations"][sid]["y"] = x, y
    else:
        for e in d["extras"]:
            if e["id"] == sid:
                e["x"], e["y"] = x, y

# --- coastline: even-odd assembly of the SVG's subpaths -----------------
subpaths = json.load(open(V1 + "coast_mm.json"))
shapes = [Polygon(sp).buffer(0) for sp in subpaths if len(sp) >= 3]
water = shapes[0]
for sh in shapes[1:]:
    water = water.symmetric_difference(sh)
# The Fraser leaves the page at x=200 (east of Port Mann); carry it on to
# the frame edge at the same banks so Langley sits on the right side of it.
edge = water.intersection(box(199.0, -5, 200.0, 105))
ys = [g.bounds for g in (edge.geoms if hasattr(edge, "geoms") else [edge])]
for _, y1, _, y2 in ys:
    water = water.union(box(199.0, y1, FRAME_R + 5, y2))
water = water.simplify(0.25, preserve_topology=True)
# A real coastline puts some LEDs *inside* the water (SeaBus at Lonsdale
# Quay, the river-bank stations, Sea Island). citymap.repel only nudges
# nearby edges, so carve a clearance disk out of the copper around every
# LED here - the pad ends up on a small island, which reads as a pier.
PAD_CLEAR_MM = 2.4  # board mm from LED centre to the nearest copper
r_svg = PAD_CLEAR_MM / (SCALE * 1.5)
for sid, (cx, cy) in CANVAS.items():
    sx, sy = (cx - MARGIN) / SCALE + X0, (cy - MARGIN) / SCALE + Y0
    water = water.difference(Point(sx, sy).buffer(r_svg, 16))


def ring_with_holes(poly):
    """One point ring for gr_poly (no hole concept): bridge out to each
    island and back along the same seam."""
    pts = list(poly.exterior.coords)[:-1]
    for ring in poly.interiors:
        hole = list(ring.coords)[:-1]
        if Polygon(hole).area < 1.0:
            continue
        i = min(range(len(pts)), key=lambda k: (pts[k][0] - hole[0][0]) ** 2 +
                (pts[k][1] - hole[0][1]) ** 2)
        pts = pts[:i + 1] + hole + [hole[0]] + [pts[i]] + pts[i + 1:]
    return [list(c(*p)) for p in pts]


geo = []
pieces = water.geoms if water.geom_type == "MultiPolygon" else [water]
for i, g in enumerate(sorted(pieces, key=lambda p: -p.area)):
    if g.area < 3.0:
        continue
    geo.append({"name": f"water-{i}", "type": "water", "points": ring_with_holes(g)})
print(f"water: {len(geo)} piece(s)")

# --- map furniture (canvas units) --------------------------------------
wf, sb = CANVAS["waterfront"], CANVAS["seabus"]
geo.append({"name": "seabus-route", "type": "line", "dash": "dot",
            "width": 0.5, "points": [[wf[0], wf[1]], [sb[0], sb[1]]]})
BORDER_Y = round(max(y for _, y in CANVAS.values()) + 6.0, 1)
geo.append({"name": "us-border", "type": "line", "dash": "dashdot",
            "width": 0.3, "points": [[3.0, BORDER_Y], [97.0, BORDER_Y]]})
TITLE_Y = BORDER_Y + 11.0
LEG_X, LEG_Y = 62.0, TITLE_Y + 10.5
for i, (dash, w) in enumerate([(None, 1.5), ("dash", 1.5), ("dot", 0.5)]):
    y = LEG_Y + i * 2.7
    geo.append({"name": f"legend-{i}", "type": "line", "dash": dash,
                "width": w, "points": [[LEG_X, y], [LEG_X + 6.0, y]]})
d["geo"] = geo
d["annotations"] = [
    {"text": "VANCOUVER", "x": 50.0, "y": TITLE_Y, "size": 9.0, "angle": 0,
     "anchor": "center", "copper": True, "bold": True},
    {"text": "Existing line", "x": LEG_X + 7.5, "y": LEG_Y, "size": 1.3},
    {"text": "Future (2027-2029)", "x": LEG_X + 7.5, "y": LEG_Y + 2.7, "size": 1.3},
    {"text": "SeaBus", "x": LEG_X + 7.5, "y": LEG_Y + 5.4, "size": 1.3},
    {"text": "CANADA", "x": 88.0, "y": BORDER_Y - 1.4, "size": 1.2},
    {"text": "USA", "x": 88.0, "y": BORDER_Y + 1.4, "size": 1.2},
]

json.dump(d, open("vancouver.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print(f"wrote vancouver.json: {len(CANVAS)} stations, {len(geo)} geo shapes, "
      f"{SCALE * 1.5:.3f} board-mm per svg-mm, map bottom canvas y="
      f"{max(y for _, y in CANVAS.values()):.1f}")
