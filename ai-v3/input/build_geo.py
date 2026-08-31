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


# Two earlier passes tried to patch extra water down the whole left edge,
# assuming the gap between the top (English Bay) and bottom (Sea Island)
# traced water was a tracing gap to fill. Re-checking the source PDF
# directly: it isn't a gap - that whole middle band (Vancouver City
# Centre down through Marine Drive) really is solid land colour all the
# way to the page edge in the original map, no coastline drawn there at
# all (west of the Cambie corridor is off the detail this map bothers
# with). Both patches, including the invented "Point Grey peninsula",
# were fixing a mismatch with the PDF that didn't exist. Left as a pure
# trace: water = page minus every traced land polygon, nothing added.
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
