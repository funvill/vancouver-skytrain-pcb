"""Assemble the final vancouver.json from PDF-traced station positions
(station_coords_final.py's STATIONS table below) and PDF-traced geo
shapes (geo_canvas.json). Run once; output is hand-reviewed afterward."""
import json
import math

PAGE_W, PAGE_H = 514.8, 406.99


MARGIN = 4.0  # canvas units of edge inset
# Single uniform scale (not independent x/y) so real angles/proportions
# from the PDF are preserved exactly - the source page is wider than
# tall, so this leaves blank canvas at the bottom rather than stretching
# the network vertically to fill a square.
SCALE = (100 - 2 * MARGIN) / PAGE_W


def c(x, y):
    return (round(MARGIN + x * SCALE, 2), round(MARGIN + y * SCALE, 2))


# PDF-point coordinates traced from skytrain-network-map.pdf, resolved by
# matching text anchors + station-dot circles to their line topology (see
# session notes - the auto text/circle matcher was unreliable for angled
# labels, so ambiguous ones were hand-resolved against known line order).
PDF_XY = {
 "waterfront": (112.9, 46.0),
 "burrard": (111.4, 59.35),
 "granville": (109.9, 72.7),
 "stadium": (131.35, 92.8),
 "main-street": (152.8, 112.9),
 "commercial-broadway": (174.25, 133.0),
 "nanaimo": (174.1, 173.8),
 "29th-avenue": (189.6, 189.3),
 "joyce": (205.0, 204.8),
 "patterson": (220.5, 220.3),
 "metrotown": (235.9, 235.8),
 "royal-oak": (263.5, 256.1),
 "edmonds": (289.8, 256.2),
 "22nd-street": (316.1, 256.1),
 "new-westminster": (343.5, 236.0),
 "columbia": (359.0, 220.5),
 "sapperton": (390.2, 189.3),
 "braid": (405.7, 173.8),
 "lougheed": (412.6, 138.5),
 "production-way": (385.55, 135.75),
 "lake-city-way": (358.5, 133.0),
 "sperling": (332.1, 133.0),
 "holdom": (305.8, 133.0),
 "brentwood": (279.5, 133.0),
 "gilmore": (253.2, 133.0),
 "rupert": (226.9, 133.0),
 "renfrew": (200.6, 133.0),
 "vcc-clark": (147.9, 133.0),
 "burquitlam": (419.0, 95.7),
 "moody-centre": (432.1, 82.9),
 "inlet-centre": (462.3, 82.9),
 "coquitlam-central": (492.9, 82.9),
 "lincoln": (505.8, 58.0),
 "lafarge": (505.8, 36.3),
 "scott-road": (419.0, 220.5),
 "gateway": (418.9, 247.9),
 "surrey-central": (418.9, 275.4),
 "king-george": (419.0, 302.8),
 "vancouver-city-centre": (86.3, 72.7),
 "yaletown": (90.6, 95.7),
 "olympic-village": (100.7, 118.9),
 "broadway-city-hall": (100.7, 146.4),
 "king-edward": (100.7, 173.8),
 "oakridge": (100.7, 201.3),
 "langara": (100.7, 228.7),
 "marine-drive": (100.7, 256.2),
 "bridgeport": (100.7, 283.6),
 "capstan": (100.7, 311.1),
 "aberdeen": (100.6, 338.5),
 "lansdowne": (100.7, 366.0),
 "richmond-brighouse": (100.7, 393.4),
 "templeton": (73.9, 297.5),
 "sea-island-centre": (45.4, 297.5),
 "yvr": (17.0, 297.5),
}

# Broadway Extension + Surrey-Langley Extension: not on the current-network
# PDF (not built yet). Extrapolated in the *canvas* frame from the real
# neighbouring stations above, continuing each corridor's real direction
# and spacing rather than reusing the old invented layout.
d = json.load(open("../input/vancouver.json", encoding="utf-8"))


def get(sid):
    return d["stations"][sid]["x"], d["stations"][sid]["y"]


CANVAS_XY = {sid: c(*xy) for sid, xy in PDF_XY.items()}

# The Broadway corridor (the real Millennium trunk VCC-Clark..Lake City Way,
# plus its future westward extension to Arbutus) is one straight street in
# reality - keep it a single flat line on the board too, at the y of
# Broadway-City Hall (its interchange point with the Canada Line, which
# stays wherever the Canada Line column puts it). The real-traced portion
# is already flat in the source PDF; this just re-levels the whole row to
# the interchange's y instead of letting it slope down toward it.
bch = CANVAS_XY["broadway-city-hall"]
broadway_row = ["renfrew", "rupert", "gilmore", "brentwood", "holdom",
                "sperling", "lake-city-way"]
for sid in broadway_row:
    CANVAS_XY[sid] = (CANVAS_XY[sid][0], bch[1])

vcc = CANVAS_XY["vcc-clark"]
CANVAS_XY["vcc-clark"] = (vcc[0], bch[1])
# Arbutus..VCC-Clark is one continuous 6-gap sequence centred on
# Broadway-City Hall (a real, traced, fixed point on the Canada Line
# column) at gap 3 and VCC-Clark (also real/fixed) at gap 6 - a single
# step size keeps every gap equal instead of two independently-anchored
# half-chains that can overlap.
step_x = (vcc[0] - bch[0]) / 3
CANVAS_XY["mount-pleasant"] = (round(bch[0] + step_x, 2), bch[1])
CANVAS_XY["great-northern-way"] = (round(bch[0] + 2 * step_x, 2), bch[1])
CANVAS_XY["oak-vgh"] = (round(bch[0] - step_x, 2), bch[1])
CANVAS_XY["south-granville"] = (round(bch[0] - 2 * step_x, 2), bch[1])
CANVAS_XY["arbutus"] = (round(bch[0] - 3 * step_x, 2), bch[1])

kg = CANVAS_XY["king-george"]
diag = [(2.1, 2.1)] * 4
pt = kg
surrey_ext = ["green-timbers", "152-street", "fleetwood", "bakerview"]
for sid, (dx, dy) in zip(surrey_ext, diag):
    pt = (round(pt[0] + dx, 2), round(pt[1] + dy, 2))
    CANVAS_XY[sid] = pt
vert = [(0.0, 3.55)] * 4
langley_ext = ["hillcrest", "clayton", "willowbrook", "langley-city-centre"]
for sid, (dx, dy) in zip(langley_ext, vert):
    pt = (round(pt[0] + dx, 2), round(pt[1] + dy, 2))
    CANVAS_XY[sid] = pt

def point_in_ring(x, y, ring):
    inside = False
    x1, y1 = ring[-1]
    for x2, y2 in ring:
        if (y1 > y) != (y2 > y):
            xin = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < xin:
                inside = not inside
        x1, y1 = x2, y2
    return inside


wf = CANVAS_XY["waterfront"]
br = CANVAS_XY["burrard"]
water_ring = json.load(open("geo_canvas.json", encoding="utf-8"))["water"][0]
# SeaBus sits right at Waterfront in real life; the board needs it visibly
# separate and on the land side of the traced coast (not floating in the
# water fill), so grid-search for the closest land point that clears a
# safe LED pitch from both Waterfront and Burrard.
MIN_D = 3.0
best = None
x0, x1 = int((wf[0] - 6) * 5), int((wf[0] + 2) * 5)
y0, y1 = int((wf[1] - 8) * 5), int((wf[1] + 6) * 5)
for xi in range(x0, x1):
    for yi in range(y0, y1):
        x, y = xi / 5, yi / 5
        if point_in_ring(x, y, water_ring):
            continue
        dwf = math.hypot(x - wf[0], y - wf[1])
        dbr = math.hypot(x - br[0], y - br[1])
        if dwf >= MIN_D and dbr >= MIN_D:
            score = dwf + dbr
            if best is None or score < best[0]:
                best = (score, x, y)
CANVAS_XY["seabus"] = (round(best[1], 2), round(best[2], 2))

# Waterfront/Burrard/Granville trace closer together in the real map than
# a 2.5mm LED pitch can physically be soldered (~2.4mm as traced) - spread
# them apart by a fixed physical margin, keeping their real line direction
# exactly (this is the one place real proportions are knowingly broken,
# and only by the minimum needed to be buildable).
wf, br, gr = CANVAS_XY["waterfront"], CANVAS_XY["burrard"], CANVAS_XY["granville"]
def push(a, b, min_d=2.8):
    d = math.hypot(b[0] - a[0], b[1] - a[1])
    if d >= min_d:
        return b
    ux, uy = (b[0] - a[0]) / d, (b[1] - a[1]) / d
    return (round(a[0] + ux * min_d, 2), round(a[1] + uy * min_d, 2))
br = push(wf, br)
gr = push(br, gr)
CANVAS_XY["burrard"], CANVAS_XY["granville"] = br, gr

for sid, (x, y) in CANVAS_XY.items():
    if sid in d["stations"]:
        d["stations"][sid]["x"] = x
        d["stations"][sid]["y"] = y
    else:
        for e in d["extras"]:
            if e["id"] == sid:
                e["x"], e["y"] = x, y

geo_canvas = json.load(open("geo_canvas.json", encoding="utf-8"))
new_geo = []
for i, pts in enumerate(geo_canvas["water"]):
    new_geo.append({"name": f"water-{i}", "type": "water", "points": pts})
park_names = {
 "park_coquitlam": "colony-farm-park", "park_stanley": "stanley-park",
 "park_burnaby_central": "burnaby-park", "park_patterson": "central-park",
}
for key, pts in geo_canvas["parks"].items():
    new_geo.append({"name": park_names[key], "type": "park", "points": pts})

# --- Map furniture (canvas units; board mm = canvas * 1.5) ---------------
# "line" geo = a silkscreen polyline (optionally dashed/dotted) - used for
# things that are neither water nor land: the SeaBus ferry route, the
# 49th-parallel border along the bottom, and the legend swatches.
sb = CANVAS_XY["seabus"]
new_geo.append({"name": "seabus-route", "type": "line", "dash": "dot",
                "width": 0.5,
                "points": [[sb[0], sb[1] - 1.2], [sb[0], 5.0]]})
new_geo.append({"name": "us-border", "type": "line", "dash": "dashdot",
                "width": 0.3, "points": [[21.0, 94.3], [97.0, 94.3]]})
LEG_X, LEG_Y = 73.0, 85.5   # legend block, bottom-right (below Langley)
for i, (dash, w) in enumerate([(None, 1.5), ("dash", 1.5), ("dot", 0.5)]):
    y = LEG_Y + i * 2.7
    new_geo.append({"name": f"legend-{i}", "type": "line", "dash": dash,
                    "width": w, "points": [[LEG_X, y], [LEG_X + 6.0, y]]})
d["geo"] = new_geo

# Text furniture. "copper": exposed-copper lettering (F.Cu + F.Mask), the
# v2 board's gold "VANCOUVER" wordmark; everything else is white silk.
d["annotations"] = [
    {"text": "VANCOUVER", "x": 42.0, "y": 85.0, "size": 7.5, "angle": 0,
     "anchor": "center", "copper": True, "bold": True},
    {"text": "Existing line", "x": LEG_X + 7.5, "y": LEG_Y, "size": 1.3},
    {"text": "Future (2027-2029)", "x": LEG_X + 7.5, "y": LEG_Y + 2.7,
     "size": 1.3},
    {"text": "SeaBus", "x": LEG_X + 7.5, "y": LEG_Y + 5.4, "size": 1.3},
    {"text": "CANADA", "x": 88.0, "y": 93.0, "size": 1.2},
    {"text": "USA", "x": 88.0, "y": 95.7, "size": 1.2},
]
for sid in ("columbia", "bridgeport", "production-way"):
    d["stations"][sid]["interchange"] = True

json.dump(d, open("../input/vancouver.json", "w", encoding="utf-8"),
          indent=2, ensure_ascii=False)
print(f"wrote vancouver.json: {len(CANVAS_XY)} PDF-traced/extrapolated "
     f"stations, {len(new_geo)} geo shapes")
