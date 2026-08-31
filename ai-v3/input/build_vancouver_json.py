"""Assemble the final vancouver.json from PDF-traced station positions
(station_coords_final.py's STATIONS table below) and PDF-traced geo
shapes (geo_canvas.json). Run once; output is hand-reviewed afterward."""
import json

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

vcc = CANVAS_XY["vcc-clark"]
bch = CANVAS_XY["broadway-city-hall"]
step1 = ((bch[0] - vcc[0]) / 3, (bch[1] - vcc[1]) / 3)
CANVAS_XY["great-northern-way"] = (round(vcc[0] + step1[0], 2), round(vcc[1] + step1[1], 2))
CANVAS_XY["mount-pleasant"] = (round(vcc[0] + 2 * step1[0], 2), round(vcc[1] + 2 * step1[1], 2))
step2 = step1  # continue the same per-step delta past Broadway-City Hall
CANVAS_XY["oak-vgh"] = (round(bch[0] + step2[0], 2), round(bch[1] + step2[1], 2))
CANVAS_XY["south-granville"] = (round(bch[0] + 2 * step2[0], 2), round(bch[1] + 2 * step2[1], 2))
CANVAS_XY["arbutus"] = (round(bch[0] + 3 * step2[0], 2), round(bch[1] + 3 * step2[1], 2))

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

wf = CANVAS_XY["waterfront"]
CANVAS_XY["seabus"] = (wf[0], max(MARGIN, wf[1] - 8.0))  # north of Waterfront, unlabelled on this PDF

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
d["geo"] = new_geo

json.dump(d, open("../input/vancouver.json", "w", encoding="utf-8"),
          indent=2, ensure_ascii=False)
print(f"wrote vancouver.json: {len(CANVAS_XY)} PDF-traced/extrapolated "
     f"stations, {len(new_geo)} geo shapes")
