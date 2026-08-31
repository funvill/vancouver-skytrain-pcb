"""City-agnostic transit-map model for LED PCB generation.

Loads a city JSON file (lines, stations, extras, geography) and provides
geometry helpers shared by the renderer, fit checker, and exporters.
All coordinates are millimeters on the board canvas, y-axis pointing down
(SVG convention).
"""
import json
import math
from dataclasses import dataclass, field


DEFAULT_LABEL = {"angle": -45, "anchor": "start", "dx": 0.9, "dy": -0.9}

# Stroke-font metrics (KiCad-like): average advance per char and total box
# height (ascenders + descenders) as multiples of the nominal text height.
CHAR_W = 0.85  # calibrated against KiCad's stroke font + a safety margin
BOX_H = 1.25
DESCENT = 0.25


@dataclass
class Station:
    id: str
    name: str
    x: float
    y: float
    short: str = ""
    future: bool = False
    interchange: bool = False
    label: dict = field(default_factory=lambda: dict(DEFAULT_LABEL))


@dataclass
class Line:
    id: str
    name: str
    color: str
    paths: list  # list of lists of station ids


@dataclass
class City:
    name: str
    canvas_mm: float
    lines: list
    stations: dict  # id -> Station
    extras: list    # list of Station (SeaBus etc.)
    geo: list       # raw geo dicts
    annotations: list = field(default_factory=list)  # river/municipality labels


def load(path):
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    stations = {}
    for sid, s in raw["stations"].items():
        label = dict(DEFAULT_LABEL)
        label.update(s.get("label", {}))
        stations[sid] = Station(
            id=sid, name=s["name"], x=s["x"], y=s["y"],
            short=s.get("short", s["name"]), future=s.get("future", False),
            interchange=s.get("interchange", False), label=label)
    lines = [Line(l["id"], l["name"], l["color"], l["paths"])
             for l in raw["lines"]]
    extras = []
    for e in raw.get("extras", []):
        label = dict(DEFAULT_LABEL)
        label.update(e.get("label", {}))
        extras.append(Station(id=e["id"], name=e["name"], x=e["x"], y=e["y"],
                              short=e.get("short", e["name"]), label=label))
    return City(raw["city"], raw["canvas_mm"], lines, stations, extras,
                raw.get("geo", []), raw.get("annotations", []))


def led_count(city):
    return len(city.stations) + len(city.extras)


def segments(city):
    """Yield (line_id, (x1,y1), (x2,y2), sid1, sid2) for every drawn segment."""
    for line in city.lines:
        for path in line.paths:
            for a, b in zip(path, path[1:]):
                sa, sb = city.stations[a], city.stations[b]
                yield line.id, (sa.x, sa.y), (sb.x, sb.y), a, b


def is_octilinear(p1, p2, tol=0.01):
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    return (abs(dx) < tol or abs(dy) < tol or abs(abs(dx) - abs(dy)) < tol)


LONG_NAME_THRESHOLD = 17  # names longer than this always use the short form,
                          # even in "full name" mode - see fit-report.md


def display_name(st, use_short=False):
    if use_short or len(st.name) > LONG_NAME_THRESHOLD:
        return st.short
    return st.name


def label_box(st, text_h, scale=1.0, use_short=False):
    """Rotated-rectangle polygon [(x,y)*4] of a station's label, in board mm.

    Station coords scale with the board; text height and label offset do not.
    """
    text = display_name(st, use_short)
    w = max(1.0, len(text) * CHAR_W * text_h)
    ang = math.radians(st.label["angle"])
    d = (math.cos(ang), math.sin(ang))
    n = (math.sin(ang), -math.cos(ang))  # 'above baseline' direction
    px = st.x * scale + st.label["dx"]
    py = st.y * scale + st.label["dy"]
    if st.label["anchor"] == "end":
        px -= d[0] * w
        py -= d[1] * w
    lo, hi = -DESCENT * text_h, (BOX_H - DESCENT) * text_h
    return [
        (px + n[0] * lo, py + n[1] * lo),
        (px + d[0] * w + n[0] * lo, py + d[1] * w + n[1] * lo),
        (px + d[0] * w + n[0] * hi, py + d[1] * w + n[1] * hi),
        (px + n[0] * hi, py + n[1] * hi),
    ]


def seg_rect(p1, p2, half_w):
    """Convert a line segment to a rectangle polygon of width 2*half_w."""
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    ln = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / ln * half_w, dx / ln * half_w
    return [(p1[0] + nx, p1[1] + ny), (p2[0] + nx, p2[1] + ny),
            (p2[0] - nx, p2[1] - ny), (p1[0] - nx, p1[1] - ny)]


def circle_rect(cx, cy, r):
    return [(cx - r, cy - r), (cx + r, cy - r), (cx + r, cy + r),
            (cx - r, cy + r)]


def densify(points, closed, max_seg):
    """Insert extra vertices so no edge is longer than max_seg."""
    out = []
    n = len(points)
    edges = n if closed else n - 1
    for i in range(edges):
        a, b = points[i], points[(i + 1) % n]
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        steps = max(1, int(math.ceil(length / max_seg)))
        for s in range(steps):
            t = s / steps
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    if not closed:
        out.append(points[-1])
    return out


def repel(points, avoid_pts, keepout):
    """Push each vertex away from any avoid point closer than keepout.

    Used to keep water/land art (copper or silkscreen) clear of LED pads:
    run densify() first so long edges get intermediate vertices too, or a
    near miss in the middle of an edge won't be caught.
    """
    out = []
    for (x, y) in points:
        px = py = 0.0
        for (ax, ay) in avoid_pts:
            dx, dy = x - ax, y - ay
            d = math.hypot(dx, dy)
            if 0 < d < keepout:
                f = (keepout - d) / d
                px += dx * f
                py += dy * f
        out.append((x + px, y + py))
    return out


def simplify(points, tol):
    """Ramer-Douglas-Peucker: drop points that don't bend the line by more
    than `tol`. Runs after densify()+repel() on open polylines (rivers) so
    a long, mostly-straight edge doesn't turn into dozens of tiny render
    segments just because densify had to check it for LED proximity."""
    if len(points) < 3:
        return points
    def seg_dist(p, a, b):
        ax, ay = a; bx, by = b; px, py = p
        dx, dy = bx - ax, by - ay
        if dx == dy == 0:
            return math.hypot(px - ax, py - ay)
        t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        return math.hypot(px - (ax + t * dx), py - (ay + t * dy))
    def rdp(pts):
        a, b = pts[0], pts[-1]
        idx, dmax = -1, tol
        for i in range(1, len(pts) - 1):
            d = seg_dist(pts[i], a, b)
            if d > dmax:
                idx, dmax = i, d
        if idx == -1:
            return [a, b]
        return rdp(pts[:idx + 1])[:-1] + rdp(pts[idx:])
    return rdp(points)


def clamp_to_board(points, board_mm, margin):
    """Keep vertices at least `margin` inside the board outline - needed
    where art is meant to touch the coastline/canvas edge (bleeds off the
    top of the map) but copper still needs edge clearance."""
    return [(min(max(x, margin), board_mm - margin),
             min(max(y, margin), board_mm - margin)) for x, y in points]


def prepared_geo(city, scale, avoid_pts, water_keepout=2.0, land_keepout=1.0,
                 edge_margin=2.5, densify_step=2.0):
    """Every geo shape from the city file, scaled to board mm and adjusted
    to clear LED pads and the board edge. Same output feeds the SVG
    preview, the collision checker, and the PCB art exporter, so what you
    see in the preview is exactly what ends up on copper."""
    board_mm = city.canvas_mm * scale
    out = []
    for g in city.geo:
        pts = [(x * scale, y * scale) for x, y in g["points"]]
        closed = g["type"] != "river"
        if g["type"] == "river":
            keepout = water_keepout + g.get("width", 2.5) * scale / 2
        elif g["type"] in ("water", "lake"):
            keepout = water_keepout
        else:
            keepout = land_keepout
        pts = densify(pts, closed, densify_step)
        pts = repel(pts, avoid_pts, keepout)
        pts = clamp_to_board(pts, board_mm, edge_margin)
        if not closed:
            pts = simplify(pts, tol=0.4)
        out.append({**g, "points": pts, "_prepared": True})
    return out


def point_seg_dist(p, a, b):
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    if dx == dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def poly_point_min_dist(poly, p, closed=True):
    """Distance from p to the nearest edge of poly (its boundary, not just
    its vertices - the closest approach is often mid-edge)."""
    n = len(poly)
    edges = n if closed else n - 1
    return min(point_seg_dist(p, poly[i], poly[(i + 1) % n])
              for i in range(edges))


def hatch_fill(poly, spacing, angle_deg=45, closed=True):
    """Parallel scan-line hatch segments filling `poly` (even-odd rule, so
    concave shapes work too). Returns a list of (p1, p2) segment pairs -
    the single-ink-silkscreen stand-in for a filled color area (parks).
    """
    ang = math.radians(angle_deg)
    ux, uy = math.cos(ang), math.sin(ang)   # hatch line direction
    nx, ny = -uy, ux                        # scan axis (perpendicular)
    proj = [x * nx + y * ny for x, y in poly]
    lo, hi = min(proj), max(proj)
    n = len(poly)
    edges = n if closed else n - 1
    segs = []
    k = math.floor(lo / spacing)
    d = k * spacing
    while d <= hi:
        hits = []
        for i in range(edges):
            (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
            p1n, p2n = x1 * nx + y1 * ny, x2 * nx + y2 * ny
            if p1n == p2n:
                continue
            if min(p1n, p2n) <= d <= max(p1n, p2n):
                t = (d - p1n) / (p2n - p1n)
                hx, hy = x1 + t * (x2 - x1), y1 + t * (y2 - y1)
                hits.append((hx * ux + hy * uy, hx, hy))
        hits.sort()
        for i in range(0, len(hits) - 1, 2):
            a, b = hits[i], hits[i + 1]
            if b[0] - a[0] > 1e-6:  # drop degenerate corner-grazing hits
                segs.append(((a[1], a[2]), (b[1], b[2])))
        d += spacing
    return segs


def point_in_polygon(p, poly):
    """Ray-casting point-in-polygon test. Correct for concave polygons,
    unlike polys_intersect() (SAT), which requires convex shapes - use
    this for anything tested against a coastline/river outline."""
    x, y = p
    inside = False
    n = len(poly)
    x1, y1 = poly[-1]
    for x2, y2 in poly:
        if (y1 > y) != (y2 > y):
            xin = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < xin:
                inside = not inside
        x1, y1 = x2, y2
    return inside


def segs_intersect(p1, p2, p3, p4):
    def orient(a, b, c):
        v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        return 0 if abs(v) < 1e-9 else (1 if v > 0 else -1)
    o1, o2 = orient(p1, p2, p3), orient(p1, p2, p4)
    o3, o4 = orient(p3, p4, p1), orient(p3, p4, p2)
    return o1 != o2 and o3 != o4


def box_poly_overlap(box, poly, closed=True):
    """True if the (small, convex) box overlaps the (possibly large,
    concave) poly - any box corner inside poly, any poly vertex inside
    box, or any edge of one crossing an edge of the other."""
    if any(point_in_polygon(c, poly) for c in box):
        return True
    if any(point_in_polygon(v, box) for v in poly):
        return True
    n = len(poly)
    edges = n if closed else n - 1
    for i in range(4):
        a, b = box[i], box[(i + 1) % 4]
        for j in range(edges):
            c, d = poly[j], poly[(j + 1) % n]
            if segs_intersect(a, b, c, d):
                return True
    return False


def _project(poly, axis):
    dots = [p[0] * axis[0] + p[1] * axis[1] for p in poly]
    return min(dots), max(dots)


def polys_intersect(a, b):
    """Separating-axis test for two convex polygons."""
    for poly in (a, b):
        for i in range(len(poly)):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % len(poly)]
            axis = (y1 - y2, x2 - x1)
            amin, amax = _project(a, axis)
            bmin, bmax = _project(b, axis)
            if amax < bmin or bmax < amin:
                return False
    return True
