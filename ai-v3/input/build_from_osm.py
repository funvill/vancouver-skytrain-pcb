"""Assemble vancouver.json from OpenStreetMap: real station positions and
a real, simplified shoreline.

Sources (cached Overpass responses in ./osm/, fetched with curl - see the
queries at the bottom of this file):
  osm/stations.json    SkyTrain station nodes (railway=station +
                       station=subway; the Surrey-Langley stations under
                       construction)
  osm/coastline.json   natural=coastline ways in the box (OSM keeps land
                       on the LEFT of a coastline way's direction - that
                       is how sea/land is told apart below)
  osm/rivers_east.json waterway=river centrelines - the Fraser main stem
                       east of Port Mann and the Pitt River, which the
                       coastline doesn't cover; drawn as a buffered line
  osm/water.json       natural=water lakes; only the large named ones are
                       kept (Burnaby, Deer, Trout, Como, Lost Lagoon ...)

Frame: an equirectangular projection of a lat/lon box chosen to run from
Point Grey to just past Langley City Centre and from the North Shore to
just below Langley; the board takes the box's own aspect (150 mm wide).
Water runs to the board edge - it forms no border. Stations are real
positions except where two LEDs would be closer than the 2.8 mm pitch
(downtown, Richmond, Sea Island), which are spread apart minimally.

Run:  python build_from_osm.py   (needs shapely)
"""
import json
import math

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import polygonize, unary_union
from shapely.strtree import STRtree

# --- frame ----------------------------------------------------------------
LON0, LON1 = -123.275, -122.612      # west .. east
LAT0, LAT1 = 49.336, 49.087          # north .. south
LAT_MID = (LAT0 + LAT1) / 2
KX, KY = 111.32 * math.cos(math.radians(LAT_MID)), 111.32   # km per degree


def km(lat, lon):
    """Box-relative km: x east from the west edge, y south from the north."""
    return ((lon - LON0) * KX, (LAT0 - lat) * KY)


W_KM, H_KM = (LON1 - LON0) * KX, (LAT0 - LAT1) * KY
CANVAS_W = 100.0
SCALE = CANVAS_W / W_KM            # canvas units per km
CANVAS_H = round(H_KM * SCALE, 2)
BOARD = 1.5                        # board mm per canvas unit
FRAME = box(0, 0, W_KM, H_KM)


def c(x_km, y_km):
    return (round(x_km * SCALE, 2), round(y_km * SCALE, 2))


def load(name):
    return json.load(open(f"osm/{name}", encoding="utf-8"))


def pts(geom):
    return [km(p["lat"], p["lon"]) for p in (geom or []) if p]


# --- sea / inlet / Fraser arms from the coastline --------------------------
coast = load("coastline.json")
lines = []
for e in coast["elements"]:
    p = pts(e.get("geometry"))
    if len(p) >= 2:
        lines.append(LineString(p))
faces = list(polygonize(unary_union(lines + [FRAME.boundary])))
tree = STRtree(faces)
votes = [0] * len(faces)   # +land / -water
for ln in lines:
    xy = list(ln.coords)
    for (ax, ay), (bx, by) in zip(xy, xy[1:]):
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy)
        if L < 1e-6:
            continue
        # geographic left of travel, expressed in this y-down frame
        lx, ly = dy / L, -dx / L
        mx, my = (ax + bx) / 2, (ay + by) / 2
        for side, sgn in ((1, +1), (-1, -1)):
            q = Point(mx + lx * 0.03 * sgn, my + ly * 0.03 * sgn)
            for i in tree.query(q):
                if faces[i].contains(q):
                    votes[i] += side
                    break
sea = unary_union([f for f, v in zip(faces, votes) if v < 0])
print(f"coastline: {len(faces)} faces, {sum(1 for v in votes if v < 0)} water")

# --- rivers the coastline stops short of -----------------------------------
riv = load("rivers_east.json")
river_polys = []
for e in riv["elements"]:
    name = e.get("tags", {}).get("name", "")
    if e["type"] == "relation" and name == "Fraser River":
        for m in e["members"]:
            p = [q for q in pts(m.get("geometry")) if q[0] > (-122.90 - LON0) * KX]
            if len(p) >= 2:
                river_polys.append(LineString(p).buffer(0.32))
    elif e["type"] == "way" and name == "Pitt River":
        p = pts(e.get("geometry"))
        if len(p) >= 2:
            river_polys.append(LineString(p).buffer(0.22))

# --- the large lakes -------------------------------------------------------
KEEP_LAKES = {"Burnaby Lake", "Deer Lake", "Trout Lake", "Como Lake",
              "Lost Lagoon", "Lafarge Lake", "Sasamat Lake", "Mundy Lake"}
wat = load("water.json")
lakes = []
for e in wat["elements"]:
    name = e.get("tags", {}).get("name")
    if name not in KEEP_LAKES:
        continue
    if e["type"] == "way":
        p = pts(e.get("geometry"))
        if len(p) >= 4:
            lakes.append(Polygon(p).buffer(0))
    else:
        outer = [LineString(pts(m.get("geometry"))) for m in e["members"]
                 if m["role"] == "outer" and len(pts(m.get("geometry"))) >= 2]
        inner = [LineString(pts(m.get("geometry"))) for m in e["members"]
                 if m["role"] == "inner" and len(pts(m.get("geometry"))) >= 2]
        poly = unary_union(list(polygonize(unary_union(outer))))
        if inner:
            poly = poly.difference(unary_union(list(polygonize(unary_union(inner)))))
        lakes.append(poly)
print(f"lakes kept: {len(lakes)}")

# --- smooth: no nooks and crannies ---------------------------------------
water = unary_union([sea] + river_polys)
water = water.buffer(-0.07).buffer(0.16).buffer(-0.09)   # open-close
water = water.simplify(0.09, preserve_topology=True)


def fill_small_holes(geom, min_km2):
    """Drop river islands below min_km2 - the Fraser east of Port Mann is
    braided around a dozen small islands that read as tangled channels at
    3 mm/km; only Barnston-sized ones are worth a hole."""
    out = []
    for g in getattr(geom, "geoms", [geom]):
        out.append(Polygon(g.exterior, [r for r in g.interiors
                                        if Polygon(r).area >= min_km2]))
    return unary_union(out)


water = fill_small_holes(water, 2.5)
water = unary_union([g for g in getattr(water, "geoms", [water]) if g.area >= 0.6])
lake_union = unary_union(lakes).buffer(0.03).buffer(-0.03).simplify(0.05, preserve_topology=True)
water = unary_union([water, lake_union]).intersection(FRAME)
# clipping at the frame leaves slivers of bays that are mostly outside
# (Mud Bay at the bottom edge) - keep only lakes and substantial pieces
water = unary_union([g for g in getattr(water, "geoms", [water])
                     if g.area >= 0.6 or g.intersects(lake_union)])

# --- stations ----------------------------------------------------------------
d = json.load(open("vancouver.json", encoding="utf-8"))


def norm(s):
    s = s.replace("–", "-").replace("—", "-").lower().strip()
    if s.endswith(" station"):
        s = s[:-8]
    return s


ALIAS = {"bakerview-166 street": "bakerview", "hillcrest-184 street": "hillcrest"}
by_name = {norm(s["name"]): sid for sid, s in d["stations"].items()}
found = {}
for e in load("stations.json")["elements"]:
    n = norm(e["tags"].get("name", ""))
    n = ALIAS.get(n, n)
    sid = by_name.get(n)
    if sid:
        found.setdefault(sid, []).append((e["lat"], e["lon"]))
LL = {sid: (sum(a for a, _ in v) / len(v), sum(b for _, b in v) / len(v))
      for sid, v in found.items()}
# Broadway Subway stations (under construction, not station nodes yet)
LL.update({
    "arbutus": (49.2638, -123.1535), "south-granville": (49.2636, -123.1387),
    "oak-vgh": (49.2632, -123.1271), "mount-pleasant": (49.2634, -123.1010),
    "great-northern-way": (49.2673, -123.0873),
})
LL["seabus"] = (49.3106, -123.0836)   # Lonsdale Quay, North Vancouver
missing = set(d["stations"]) - set(LL)
assert not missing, f"no OSM position for {missing}"
print(f"stations: {len(found)} from OSM, {len(LL) - len(found)} by hand")

KM = {sid: km(*ll) for sid, ll in LL.items()}

# A station on the bank (New Westminster, Waterfront) can fall inside the
# smoothed water - nudge it onto land as the real map shows it.
land = FRAME.difference(water)
for sid, p in KM.items():
    q = Point(p)
    if water.contains(q):
        b = land.boundary.interpolate(land.boundary.project(q))
        vx, vy = b.x - q.x, b.y - q.y
        L = math.hypot(vx, vy) or 1
        KM[sid] = (b.x + vx / L * 0.12, b.y + vy / L * 0.12)

CANVAS = {sid: c(*p) for sid, p in KM.items()}


def push(a, b, min_d):
    dd = math.hypot(b[0] - a[0], b[1] - a[1])
    if dd >= min_d:
        return b
    ux, uy = (b[0] - a[0]) / dd, (b[1] - a[1]) / dd
    return (round(a[0] + ux * min_d, 2), round(a[1] + uy * min_d, 2))


# 3.3 mm: two 1615 LEDs whose DOUT/DIN pads face each other diagonally
# (the footprint rotates to aim at the next LED) need this to keep the
# 0.2 mm pad-to-pad clearance; 2.8 mm only works for axis-aligned pairs.
MIN_PITCH = 3.3 / BOARD
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

# --- copper clearance around every LED -----------------------------------
PAD_CLEAR_MM = 2.2
for sid, (cx, cy) in CANVAS.items():
    water = water.difference(Point(cx / SCALE, cy / SCALE).buffer(PAD_CLEAR_MM / BOARD / SCALE, 12))


def ring_with_holes(poly):
    pts_ = list(poly.exterior.coords)[:-1]
    for ring in poly.interiors:
        hole = list(ring.coords)[:-1]
        if Polygon(hole).area < 0.02:
            continue
        i = min(range(len(pts_)), key=lambda k: (pts_[k][0] - hole[0][0]) ** 2 +
                (pts_[k][1] - hole[0][1]) ** 2)
        pts_ = pts_[:i + 1] + hole + [hole[0]] + [pts_[i]] + pts_[i + 1:]
    return [list(c(*p)) for p in pts_]


geo = []
for i, g in enumerate(sorted(getattr(water, "geoms", [water]), key=lambda p: -p.area)):
    if g.area < 0.02:
        continue
    geo.append({"name": f"water-{i}", "type": "water", "points": ring_with_holes(g)})
print(f"water: {len(geo)} piece(s)")

# --- wordmark on land, clear of water and track ----------------------------
routes = unary_union([LineString([KM_ for KM_ in (
    (CANVAS[a][0] / SCALE, CANVAS[a][1] / SCALE), (CANVAS[b][0] / SCALE, CANVAS[b][1] / SCALE))])
    for line in d["lines"] for path in line["paths"] for a, b in zip(path, path[1:])])
TITLE_MM = 6.0
tw, th = len("VANCOUVER") * 0.85 * TITLE_MM / BOARD / SCALE, 1.3 * TITLE_MM / BOARD / SCALE
spot = None
for lat, lon in [(49.128, -123.02), (49.118, -122.99), (49.135, -122.96),
                 (49.115, -122.93), (49.33, -123.03), (49.325, -122.93)]:
    x, y = km(lat, lon)
    rect = box(x - tw / 2, y - th / 2, x + tw / 2, y + th / 2)
    if FRAME.contains(rect) and not rect.intersects(water.buffer(0.15)) and \
            not rect.intersects(routes.buffer(0.3)):
        spot = (x, y)
        break
assert spot, "no land spot for the wordmark"
tx, ty = c(*spot)
d["geo"] = geo + [{"name": "seabus-route", "type": "line", "dash": "dot", "width": 0.5,
                   "points": [list(CANVAS["waterfront"]), list(CANVAS["seabus"])]}]
d["annotations"] = [{"text": "VANCOUVER", "x": tx, "y": ty, "size": TITLE_MM,
                     "angle": 0, "anchor": "center", "copper": True, "bold": True}]
d["canvas_mm"] = CANVAS_W
d["canvas_h_mm"] = CANVAS_H
json.dump(d, open("vancouver.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print(f"wrote vancouver.json: board {CANVAS_W * BOARD:.0f} x {CANVAS_H * BOARD:.1f} mm, "
      f"{SCALE * BOARD:.2f} mm/km, wordmark at canvas ({tx}, {ty})")

# Overpass queries used (BBOX = 49.08,-123.30,49.36,-122.60):
#  stations:  node["railway"~"^(station|halt)$"]["station"~"light_rail|subway"](BBOX);
#             node["railway"~"^(construction|proposed)$"]["name"](BBOX);   out body;
#  coastline: way["natural"="coastline"](BBOX); out geom;
#  rivers:    (way["waterway"="river"](49.12,-122.90,49.30,-122.60);
#              relation["waterway"="river"](...);); out geom(BBOX);
#  water:     (way["natural"="water"]["name"](BBOX); relation["natural"="water"]["name"](BBOX);
#              ... ["water"~"river|lake"] ...); out geom(BBOX);
