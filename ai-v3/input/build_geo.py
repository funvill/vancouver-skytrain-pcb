import json
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

PAGE_W, PAGE_H = 514.8, 406.99

shapes = json.load(open("geo_shapes.json", encoding="utf-8"))
land_names = [k for k in shapes if k.startswith("land_")]
park_names = [k for k in shapes if k.startswith("park_")]

land_polys = [Polygon(shapes[n]).buffer(0) for n in land_names]
land_union = unary_union(land_polys)

MARGIN = 4.0  # must match build_vancouver_json.py's MARGIN
SCALE = (100 - 2 * MARGIN) / PAGE_W  # uniform, matches build_vancouver_json.py

# The source page is wider than tall; the board is square. Everything the
# PDF draws ends at PAGE_H, but the frame we cut water out of runs down to
# the bottom of the square canvas so the map can carry on below the page
# edge (Delta, the South Arm, Boundary Bay) instead of stopping dead.
FRAME_H = (100 - 2 * MARGIN) / SCALE  # = PAGE_W: square canvas in pt

# --- Cartographic licence, deliberately ---------------------------------
# The PDF draws no coastline west of the Cambie corridor: Point Grey / UBC
# is off its detail, so a pure trace has solid land running into the left
# board edge from English Bay down to the North Arm. The earlier v2 board
# and the real geography both end that edge in water (English Bay above,
# Sturgeon Bank / the Strait below, with the Point Grey tip between). The
# PDF's own idiom is 45-degree shorelines, so the tip is drawn the same
# way: two cuts out of the traced land, continuing the traced English Bay
# shore and meeting the traced Fraser North Arm diagonal exactly.
point_grey_cuts = [
    # Spanish Banks: continue the English Bay shore (traced vertex
    # (53.1,110.4)) down-left at 45 deg to the left edge.
    Polygon([(53.1, 110.4), (-10, 110.4), (-10, 173.4)]),
    # Sturgeon Bank: near-vertical bank from the edge down to (14,245.4),
    # which lies on the traced North Arm bank (-6.6,224.8)->(34.5,265.9).
    Polygon([(-10, 195), (0, 201.4), (14, 245.4), (-10, 245.4)]),
]

# Below the PDF page: Delta. Its north edge is the South Arm's south bank -
# continuing land_SE_surrey's traced diagonal (257,352)->(196,413) down-left
# to (183,426) then running west, parallel to Richmond's flat south shore
# at y~412, so Lulu Island reads as the island it is. Boundary Bay is the
# 45-degree bite out of Delta's south-west corner; the Strait strip west
# of Richmond (x<35) carries on down to meet it.
FRAME_B = FRAME_H + 10  # a little past the frame so the union is clean
land_delta = Polygon([
    (183, 426), (196, 413), (520, 413), (520, FRAME_B),
    (105, FRAME_B), (95, FRAME_H), (48, FRAME_H - 47), (48, 426),
])

land_union = unary_union([land_union, land_delta])
land_union = land_union.difference(unary_union(point_grey_cuts))

board = box(0, 0, PAGE_W, FRAME_H)
water = board.difference(land_union)
water = water.simplify(2.0, preserve_topology=True)


def scale(pt):
    x, y = pt
    return [round(MARGIN + x * SCALE, 2), round(MARGIN + y * SCALE, 2)]


def to_canvas_with_holes(poly):
    """A single point ring for gr_poly (which has no hole concept) using
    the standard bridge trick: walk out to each interior ring (an island)
    and back along the same seam, so the fill still reads as solid water
    with the island cut out."""
    pts = list(poly.exterior.coords)[:-1]
    for ring in poly.interiors:
        hole_pts = list(ring.coords)[:-1]
        # bridge from the nearest exterior point to the nearest hole point
        ex_i = min(range(len(pts)), key=lambda i: (
            (pts[i][0] - hole_pts[0][0]) ** 2 +
            (pts[i][1] - hole_pts[0][1]) ** 2))
        pts = (pts[:ex_i + 1] + hole_pts + [hole_pts[0]] +
              [pts[ex_i]] + pts[ex_i + 1:])
    return [scale(p) for p in pts]


water_pieces = []
geoms = water.geoms if water.geom_type == "MultiPolygon" else [water]
for g in geoms:
    if g.area < 20:   # drop slivers (PDF rounding, tiny gaps)
        continue
    water_pieces.append(to_canvas_with_holes(g))

print(f"water: {len(water_pieces)} piece(s), sizes "
     f"{[len(p) for p in water_pieces]} points")

parks_canvas = {}
for n in park_names:
    p = Polygon(shapes[n]).buffer(0).simplify(1.5, preserve_topology=True)
    parks_canvas[n] = [scale(pt) for pt in list(p.exterior.coords)[:-1]]
    print(n, len(parks_canvas[n]), "points")

json.dump({"water": water_pieces, "parks": parks_canvas},
          open("geo_canvas.json", "w"), indent=2)
