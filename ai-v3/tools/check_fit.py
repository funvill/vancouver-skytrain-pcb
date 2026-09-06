"""Text-fit / collision checker for the LED map.

Models every station label as a rotated rectangle and reports collisions:
  label vs label, label vs other station's LED dot, label vs route segments
  (excluding segments that touch the label's own station), label off-board.

Usage:
    python check_fit.py ../input/vancouver.json           # full matrix
    python check_fit.py ../input/vancouver.json --scale 1.0 --text 1.2
"""
import argparse
import math
from dataclasses import dataclass

import citymap

EDGE_MARGIN = 1.0  # labels must stay this far inside the board edge
DOT_R = 1.1
OWN_R = 1.7        # own LED + ring: a label may not start on top of it
LEADER_DOT_R = 2.8 # a leader-floated label keeps this far from other LEDs
LINE_HALF_W = 1.1  # half the route stroke (0.75) plus 0.35 mm breathing room


@dataclass
class Collision:
    kind: str      # label-label | label-line | label-dot | off-board
    a: str
    b: str
    poly: list     # polygon of offending label (for overlay rendering)


class Context:
    """Everything that doesn't change while labels are being moved -
    scaled route rectangles, LED dots, prepared geo - built once so a
    label optimiser can re-check one station cheaply."""

    def __init__(self, city, scale=1.0, text_h=citymap.TEXT_H, use_short=False):
        self.city, self.scale, self.text_h, self.use_short = (
            city, scale, text_h, use_short)
        self.size = city.canvas_mm * scale
        self.size_h = city.height * scale
        self.all_st = list(city.stations.values()) + city.extras
        self.segs = []
        for lid, p1, p2, a, b in citymap.segments(city):
            p1 = (p1[0] * scale, p1[1] * scale)
            p2 = (p2[0] * scale, p2[1] * scale)
            self.segs.append((f"{lid}:{a}-{b}", a, b, p1, p2,
                              citymap.seg_rect(p1, p2, LINE_HALF_W)))
        avoid_pts = [(st.x * scale, st.y * scale) for st in self.all_st]
        self.geo = [g for g in citymap.prepared_geo(city, scale, avoid_pts)
                    if g["type"] not in ("river", "line")]
        self.dots = {st.id: (st.x * scale, st.y * scale) for st in self.all_st}

    def box(self, st):
        return citymap.label_box(st, self.text_h, self.scale, self.use_short)

    def collisions_for(self, sid, boxes=None, others=True):
        """Collisions involving station sid's label. `boxes` caches the
        other labels' boxes; with others=False only label-label pairs
        where sid sorts first are reported (for a full-matrix pass)."""
        st = next(s for s in self.all_st if s.id == sid)
        box = self.box(st)
        out = []
        for x, y in box:
            if not (EDGE_MARGIN <= x <= self.size - EDGE_MARGIN and
                    EDGE_MARGIN <= y <= self.size_h - EDGE_MARGIN):
                out.append(Collision("off-board", sid, "", box))
                break
        leader = citymap.leader_segment(st, self.scale)
        for o in self.all_st:
            if o.id == sid:
                continue
            ob = boxes[o.id] if boxes else self.box(o)
            if citymap.polys_intersect(box, ob):
                out.append(Collision("label-label", sid, o.id, box))
            # a leader may not cross another label, nor another leader
            ol = citymap.leader_segment(o, self.scale)
            if leader and citymap.seg_box_overlap(leader, ob):
                out.append(Collision("leader-label", sid, o.id, box))
            if ol and citymap.seg_box_overlap(ol, box):
                out.append(Collision("leader-label", o.id, sid, box))
            if leader and ol and citymap.segs_intersect(leader[0], leader[1], ol[0], ol[1]):
                out.append(Collision("leader-leader", sid, o.id, box))
        for oid, (cx, cy) in self.dots.items():
            if oid == sid:
                r = OWN_R
            elif leader:
                r = LEADER_DOT_R  # a floated label must not read as theirs
            else:
                r = DOT_R
            if citymap.polys_intersect(box, citymap.circle_rect(cx, cy, r)):
                out.append(Collision("label-dot", sid, oid, box))
        for name, a, b, p1, p2, rect in self.segs:
            if sid in (a, b):
                # own segment: the part beyond the standoff still counts -
                # a label lying along its own line is unreadable
                own = self.dots[sid]
                far = p2 if a == sid else p1
                dx, dy = far[0] - own[0], far[1] - own[1]
                ln = math.hypot(dx, dy)
                if ln <= OWN_R + 0.5:
                    continue
                near = (own[0] + dx / ln * (OWN_R + 0.5),
                        own[1] + dy / ln * (OWN_R + 0.5))
                rect = citymap.seg_rect(near, far, LINE_HALF_W)
            if citymap.polys_intersect(box, rect):
                out.append(Collision("label-line", sid, name, box))
            if leader and sid not in (a, b) and citymap.segs_intersect(
                    leader[0], leader[1], p1, p2):
                out.append(Collision("leader-line", sid, name, box))
        # park outlines / copper water: readable but ugly, flagged so a
        # label ends up there deliberately, not by accident
        for g in self.geo:
            if citymap.box_poly_overlap(box, g["points"]):
                out.append(Collision("label-geo", sid, g["name"], box))
        return out


def find_collisions(city, scale=1.0, text_h=citymap.TEXT_H, use_short=False):
    ctx = Context(city, scale, text_h, use_short)
    boxes = {st.id: ctx.box(st) for st in ctx.all_st}
    ids = [st.id for st in ctx.all_st]
    seen = set()
    out = []
    for sid in ids:
        for c in ctx.collisions_for(sid, boxes):
            if c.kind == "label-label":
                key = frozenset((c.a, c.b))
                if key in seen:
                    continue
                seen.add(key)
            out.append(c)
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
    ap.add_argument("--text", type=float, default=citymap.TEXT_H)
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
