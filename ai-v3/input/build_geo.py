import json
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

PAGE_W, PAGE_H = 514.8, 406.99

shapes = json.load(open("geo_shapes.json", encoding="utf-8"))
land_names = [k for k in shapes if k.startswith("land_")]
park_names = [k for k in shapes if k.startswith("park_")]

land_polys = [Polygon(shapes[n]).buffer(0) for n in land_names]
land_union = unary_union(land_polys)

board = box(0, 0, PAGE_W, PAGE_H)
water = board.difference(land_union)

MARGIN = 4.0  # must match build_vancouver_json.py's MARGIN
SCALE = (100 - 2 * MARGIN) / PAGE_W  # uniform, matches build_vancouver_json.py


def canvas_to_pdf(cx, cy):
    return ((cx - MARGIN) / SCALE, (cy - MARGIN) / SCALE)


# The source PDF only details the coastline near stations - west of the
# Cambie corridor (Point Grey / English Bay / Georgia Strait, no stations
# there) it's just flat land colour, leaving the board's left edge landlocked
# for a stretch. Real Vancouver has open water the whole way down that
# coast, so patch a strip in to connect the two traced water pieces along
# the left margin instead of leaving a gap.
west_strip = box(*canvas_to_pdf(4, 16), *canvas_to_pdf(13, 50))

# The first version of that patch just paved straight over Point Grey (the
# real UBC/Kitsilano peninsula, which pokes out into English Bay right at
# Arbutus's latitude) with a flat rectangle of water, clipping it off at
# the board edge. Carve a rounded cape shape back out of the patch - not
# traced (no station sits on it to anchor a trace to), but a real,
# well-known landform, not an invented one.
peninsula_canvas = [
    (13.2, 25.5), (10.5, 24.3), (7.8, 25.2), (5.3, 27.7), (4.4, 31.0),
    (5.1, 34.4), (7.6, 36.7), (10.4, 37.2), (13.2, 35.9),
]
peninsula = Polygon([canvas_to_pdf(x, y) for x, y in peninsula_canvas])
west_strip = west_strip.difference(peninsula)

water = unary_union([water, west_strip])
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
