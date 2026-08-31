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
CHAR_W = 0.70
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
                raw.get("geo", []))


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


def label_box(st, text_h, scale=1.0, use_short=False):
    """Rotated-rectangle polygon [(x,y)*4] of a station's label, in board mm.

    Station coords scale with the board; text height and label offset do not.
    """
    text = st.short if use_short else st.name
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
