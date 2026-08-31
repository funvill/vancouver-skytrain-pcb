"""Text-fit / collision checker for the LED map.

Models every station label as a rotated rectangle and reports collisions:
  label vs label, label vs other station's LED dot, label vs route segments
  (excluding segments that touch the label's own station), label off-board.

Usage:
    python check_fit.py ../input/vancouver.json           # full matrix
    python check_fit.py ../input/vancouver.json --scale 1.0 --text 1.2
"""
import argparse
from dataclasses import dataclass

import citymap

EDGE_MARGIN = 1.0  # labels must stay this far inside the board edge
DOT_R = 1.1
LINE_HALF_W = 0.7


@dataclass
class Collision:
    kind: str      # label-label | label-line | label-dot | off-board
    a: str
    b: str
    poly: list     # polygon of offending label (for overlay rendering)


def find_collisions(city, scale=1.0, text_h=1.2, use_short=False):
    size = city.canvas_mm * scale
    all_st = list(city.stations.values()) + city.extras
    boxes = {st.id: citymap.label_box(st, text_h, scale, use_short)
             for st in all_st}
    segs = [(lid, (p1[0] * scale, p1[1] * scale),
             (p2[0] * scale, p2[1] * scale), a, b)
            for lid, p1, p2, a, b in citymap.segments(city)]
    avoid_pts = [(st.x * scale, st.y * scale) for st in all_st]
    geo = citymap.prepared_geo(city, scale, avoid_pts)
    out = []

    ids = [st.id for st in all_st]
    for i, sid in enumerate(ids):
        box = boxes[sid]
        # off-board
        for x, y in box:
            if not (EDGE_MARGIN <= x <= size - EDGE_MARGIN and
                    EDGE_MARGIN <= y <= size - EDGE_MARGIN):
                out.append(Collision("off-board", sid, "", box))
                break
        # label vs label
        for other in ids[i + 1:]:
            if citymap.polys_intersect(box, boxes[other]):
                out.append(Collision("label-label", sid, other, box))
        # label vs dots
        for st in all_st:
            if st.id == sid:
                continue
            dot = citymap.circle_rect(st.x * scale, st.y * scale, DOT_R)
            if citymap.polys_intersect(box, dot):
                out.append(Collision("label-dot", sid, st.id, box))
        # label vs line segments not touching own station
        for lid, p1, p2, a, b in segs:
            if sid in (a, b):
                continue
            rect = citymap.seg_rect(p1, p2, LINE_HALF_W)
            if citymap.polys_intersect(box, rect):
                out.append(Collision("label-line", sid, f"{lid}:{a}-{b}", box))
        # label vs land/water shapes (park + island outlines matter most -
        # a label sitting on a filled water/exposed-copper area is also
        # flagged so it can be moved deliberately, not by accident)
        for g in geo:
            if g["type"] == "river":
                continue
            if citymap.polys_intersect(box, g["points"]):
                out.append(Collision("label-geo", sid, g["name"], box))
    return out


def summarize(cols):
    by_kind = {}
    for c in cols:
        by_kind.setdefault(c.kind, []).append(c)
    return by_kind


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--scale", type=float)
    ap.add_argument("--text", type=float, default=1.2)
    ap.add_argument("--short", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    city = citymap.load(args.data)

    if args.scale:
        matrix = [(args.scale, args.text, args.short)]
    else:
        matrix = [(s, t, sh)
                  for s in (1.0, 1.2, 1.35, 1.5)
                  for t in (1.0, 1.2)
                  for sh in (False, True)]

    print(f"{'board':>7} {'text':>5} {'names':>6} {'total':>6} "
          f"{'lbl-lbl':>8} {'lbl-line':>9} {'lbl-dot':>8} {'off':>4}")
    for s, t, sh in matrix:
        cols = find_collisions(city, s, t, sh)
        k = summarize(cols)
        print(f"{city.canvas_mm * s:6.0f}mm {t:4.1f}mm "
              f"{'short' if sh else 'full':>6} {len(cols):6d} "
              f"{len(k.get('label-label', [])):8d} "
              f"{len(k.get('label-line', [])):9d} "
              f"{len(k.get('label-dot', [])):8d} "
              f"{len(k.get('off-board', [])):4d}")
        if args.verbose:
            for c in cols:
                print(f"    {c.kind:12} {c.a:22} {c.b}")


if __name__ == "__main__":
    main()
