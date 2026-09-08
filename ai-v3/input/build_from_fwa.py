"""Assemble vancouver.json: BC Freshwater Atlas geography (geo_fwa.py),
OpenStreetMap station positions, municipal boundaries and labels.

Frame and water come from geo_fwa (the approved shape); stations from
osm_station_latlon.json (OSM nodes + hand entries for the stations under
construction); municipalities from the province's ABMS layer (cached in
osm/ABMS_MUNICIPALITIES_SP.json). Board = BOARD mm per canvas unit, so a
100-unit canvas is a 200 mm-wide board.

Copper furniture: municipal boundaries as thin exposed-copper hairlines on
land (they run mid-channel through water, where copper on copper would
show nothing), city names as small copper text placed at the spot in each
municipality farthest from track, water and other labels, and the
VANCOUVER wordmark bottom-centre.

Run:  python build_from_fwa.py   (then ../tools/auto_label.py)
"""
import json
import math
import random

from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union

import geo_fwa as G

BOARD = 2.0                              # board mm per canvas unit
CANVAS_W = 100.0
SCALE = CANVAS_W / G.W_KM                # canvas units per km
CANVAS_H = round(G.H_KM * SCALE, 2)
MM_PER_KM = SCALE * BOARD
MIN_PITCH = 3.3 / BOARD                  # canvas units (see build_from_osm)
PAD_CLEAR_MM = 2.2
CITY_TEXT_MM = 1.5
TITLE_MM = 8.0


def c(x_km, y_km):
    return (round(x_km * SCALE, 2), round(y_km * SCALE, 2))


def c_inv(cx, cy):
    return (cx / SCALE, cy / SCALE)


d = json.load(open("vancouver.json", encoding="utf-8"))
water = G.water()
land = G.FRAME.difference(water)

# --- stations ------------------------------------------------------------
LL = json.load(open("osm_station_latlon.json", encoding="utf-8"))
missing = set(d["stations"]) - set(LL)
assert not missing, f"no position for {missing}"
KM = {sid: G.km(*ll) for sid, ll in LL.items()}
for sid, p in KM.items():                # bank stations onto land
    q = Point(p)
    if water.contains(q):
        b = land.boundary.interpolate(land.boundary.project(q))
        vx, vy = b.x - q.x, b.y - q.y
        L = math.hypot(vx, vy) or 1
        KM[sid] = (b.x + vx / L * 0.08, b.y + vy / L * 0.08)
CANVAS = {sid: c(*p) for sid, p in KM.items()}


def push(a, b, min_d):
    dd = math.hypot(b[0] - a[0], b[1] - a[1])
    if dd >= min_d:
        return b
    ux, uy = (b[0] - a[0]) / dd, (b[1] - a[1]) / dd
    return (round(a[0] + ux * min_d, 2), round(a[1] + uy * min_d, 2))


for chain in [["waterfront", "burrard", "granville", "stadium"],
              ["waterfront", "vancouver-city-centre", "yaletown"],
              ["bridgeport", "capstan", "aberdeen", "lansdowne", "richmond-brighouse"],
              ["bridgeport", "templeton", "sea-island-centre", "yvr"],
              ["lafarge", "lincoln", "coquitlam-central"]]:
    for a, b in zip(chain, chain[1:]):
        CANVAS[b] = push(CANVAS[a], CANVAS[b], MIN_PITCH)
ids = list(CANVAS)
for _ in range(60):
    moved = False
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            (ax, ay), (bx, by) = CANVAS[a], CANVAS[b]
            dd = math.hypot(bx - ax, by - ay)
            if dd >= MIN_PITCH - 1e-6:
                continue
            ux, uy = ((bx - ax) / dd, (by - ay) / dd) if dd > 1e-6 else (1.0, 0.0)
            h = (MIN_PITCH - dd) / 2 + 0.01
            CANVAS[a] = (round(ax - ux * h, 2), round(ay - uy * h, 2))
            CANVAS[b] = (round(bx + ux * h, 2), round(by + uy * h, 2))
            moved = True
    if not moved:
        break

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

routes_km = unary_union([LineString([c_inv(*CANVAS[a]), c_inv(*CANVAS[b])])
                         for line in d["lines"] for path in line["paths"]
                         for a, b in zip(path, path[1:])])
station_pts = unary_union([Point(c_inv(*p)) for p in CANVAS.values()])

# --- water with LED clearance ----------------------------------------------
for cx, cy in CANVAS.values():
    water = water.difference(Point(c_inv(cx, cy)).buffer(PAD_CLEAR_MM / MM_PER_KM, 12))


def ring_with_holes(poly):
    pts = list(poly.exterior.coords)[:-1]
    for ring in poly.interiors:
        hole = list(ring.coords)[:-1]
        if Polygon(hole).area < 0.02:
            continue
        i = min(range(len(pts)), key=lambda k: (pts[k][0] - hole[0][0]) ** 2 +
                (pts[k][1] - hole[0][1]) ** 2)
        pts = pts[:i + 1] + hole + [hole[0]] + [pts[i]] + pts[i + 1:]
    return [list(c(*p)) for p in pts]


geo = [{"name": f"water-{i}", "type": "water", "points": ring_with_holes(g)}
       for i, g in enumerate(sorted(getattr(water, "geoms", [water]), key=lambda p: -p.area))
       if g.area >= 0.02]

# --- municipal boundaries (copper hairlines on land) -----------------------
munis = {}
for f in json.load(open("osm/ABMS_MUNICIPALITIES_SP.json", encoding="utf-8"))["features"]:
    name = f["properties"]["ADMIN_AREA_ABBREVIATION"]
    munis[name] = G._project(f["geometry"]).intersection(G.FRAME)
# Only one boundary is drawn: UBC / the University Endowment Lands. That
# isn't a municipality (it's unincorporated Electoral Area A), but the
# City of Vancouver's western limit *is* that line - so keep the part of
# Vancouver's boundary shared with no other municipality, on land.
others = unary_union([m.boundary for k, m in munis.items() if k != "Vancouver"])
bounds = munis["Vancouver"].boundary.difference(others.buffer(0.05))
bounds = bounds.difference(G.FRAME.boundary.buffer(0.02))   # not the frame itself
bounds = bounds.difference(water.buffer(0.06))               # land parts only
bounds = bounds.simplify(0.04, preserve_topology=True)
n_lines = 0
for g in getattr(bounds, "geoms", [bounds]):
    if g.geom_type != "LineString" or g.length < 0.8:
        continue
    geo.append({"name": f"boundary-{n_lines}", "type": "line", "copper": True,
                "width": 0.25, "points": [list(c(*p)) for p in g.coords]})
    n_lines += 1
print(f"UBC boundary: {n_lines} copper hairline(s)")

# The UBC peninsula itself: the unincorporated land west of Vancouver.
unincorporated = land.difference(unary_union(list(munis.values())))
van_minx = munis["Vancouver"].bounds[0]
ubc = max((g for g in getattr(unincorporated, "geoms", [unincorporated])
           if g.bounds[0] < van_minx + 1.0), key=lambda g: g.area)
munis["UBC"] = ubc

# --- city labels: farthest spot from track, water and each other -----------
LABEL = {"UBC": "UBC",
         "Vancouver": "Vancouver", "Burnaby": "Burnaby", "Richmond": "Richmond",
         "Delta": "Delta", "Surrey": "Surrey", "Langley - District": "Langley",
         "New Westminster": "New Westminster", "Coquitlam": "Coquitlam",
         "Port Coquitlam": "Port Coquitlam", "Port Moody": "Port Moody",
         "North Vancouver - District": "North Vancouver",
         "West Vancouver": "West Vancouver", "Pitt Meadows": "Pitt Meadows",
         "Maple Ridge": "Maple Ridge"}
random.seed(4)
annotations = []
placed = []   # shapely boxes of placed text, km

# Station labels already in vancouver.json (hand-placed or annealed) are
# obstacles for the city labels, so a rebuild never drops a city name on
# top of one; leaders count too.
import sys
sys.path.insert(0, "../tools")
import citymap
_tmp = dict(d)
_tmp["canvas_h_mm"], _tmp["board_scale"] = CANVAS_H, BOARD
json.dump(_tmp, open("_tmp_city.json", "w", encoding="utf-8"))
_city = citymap.load("_tmp_city.json")
import os
os.remove("_tmp_city.json")
for st in list(_city.stations.values()) + _city.extras:
    bx = citymap.label_box(st, citymap.TEXT_H, BOARD)
    placed.append(Polygon([(x / MM_PER_KM, y / MM_PER_KM) for x, y in bx]).buffer(0.25))
    seg = citymap.leader_segment(st, BOARD)
    if seg:
        placed.append(LineString([(p[0] / MM_PER_KM, p[1] / MM_PER_KM) for p in seg]).buffer(0.2))
avoid = unary_union([routes_km.buffer(0.35), water.buffer(0.12), station_pts.buffer(0.6)])


def text_box(x, y, text, size_mm):
    w = len(text) * 0.85 * size_mm / MM_PER_KM
    h = 1.3 * size_mm / MM_PER_KM
    return box(x - w / 2, y - h / 2, x + w / 2, y + h / 2)


# --- wordmark bottom-centre, placed first so the city labels avoid it ----
tx, ty = CANVAS_W / 2, CANVAS_H - 1.3 * TITLE_MM / BOARD / 2 - 2.0
title_box = text_box(*c_inv(tx, ty), "VANCOUVER", TITLE_MM)
if not land.contains(title_box):
    print("  warning: wordmark box is not entirely on land")
placed.append(title_box.buffer(0.4))
annotations.append({"text": "VANCOUVER", "x": round(tx, 2), "y": round(ty, 2),
                    "size": TITLE_MM, "angle": 0, "anchor": "center",
                    "copper": True, "bold": True})


for key, text in LABEL.items():
    poly = munis.get(key)
    if poly is None or poly.is_empty:
        continue
    region = poly.difference(water)
    if region.area < 4.0 and key != "UBC":
        continue
    minx, miny, maxx, maxy = region.bounds
    best = None
    for _ in range(600):
        x, y = random.uniform(minx, maxx), random.uniform(miny, maxy)
        tb = text_box(x, y, text, CITY_TEXT_MM)
        if (not region.contains(tb) or any(tb.intersects(p) for p in placed)
                or tb.distance(G.FRAME.boundary) < 0.5):
            continue
        score = min(tb.distance(avoid), 1.5) + 0.3 * min(tb.distance(G.FRAME.boundary), 1.0)
        if best is None or score > best[0]:
            best = (score, x, y, tb)
    if best is None:
        print(f"  no spot for {text}")
        continue
    placed.append(best[3].buffer(0.3))
    x, y = c(best[1], best[2])
    annotations.append({"text": text, "x": x, "y": y, "size": CITY_TEXT_MM,
                        "angle": 0, "anchor": "center", "copper": True})
print(f"city labels: {len(annotations)}")

wf, sb = CANVAS["waterfront"], CANVAS["seabus"]
geo.append({"name": "seabus-route", "type": "line", "dash": "dot", "width": 0.5,
            "points": [list(wf), list(sb)]})
d["geo"] = geo
d["annotations"] = annotations
d["canvas_mm"] = CANVAS_W
d["canvas_h_mm"] = CANVAS_H
d["board_scale"] = BOARD
json.dump(d, open("vancouver.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print(f"wrote vancouver.json: board {CANVAS_W * BOARD:.0f} x {CANVAS_H * BOARD:.1f} mm, "
      f"{MM_PER_KM:.2f} mm/km, {len(geo)} geo, {len(annotations)} annotations")
