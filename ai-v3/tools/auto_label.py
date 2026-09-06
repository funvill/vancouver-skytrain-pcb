"""Choose a label angle/anchor for every station so nothing collides.

Scoring, per candidate placement of one station (lower is better):
  * real collisions (label-label, label-dot, label-line, off-board) x 100
  * label-geo collisions (park hatch, copper water) x 10 - readable but
    ugly, so avoided when anything cleaner exists
  * angle not in the readable set {0, +-45, +-90}: x 3
  * angle differs from the previous station's on the same path: +2 -
    the eye tracks one direction along a corridor
  * a leader label: +5 plus 0.3/mm of leader length - last resort for the
    stations that have nowhere clean to sit next to their pad

Angles outside [-90, 90] render upside-down in KiCad (rigid rotation),
so those are never tried. Stations are placed in path order so the
consistency bonus chains along each corridor.

Usage:
    python auto_label.py [--only sid,sid,...]
"""
import argparse
import json
import math

import citymap
import check_fit

PATH = "../input/vancouver.json"
ANGLES = [0, -45, 45, -90, 90, -60, 60, -30, 30, -75, 75]
LEADER_RING = [6.0, 9.0, 12.0, 15.0]
LEADER_DIRS = [(1, 0), (-1, 0), (0.7, 0.7), (-0.7, 0.7), (0.7, -0.7),
               (-0.7, -0.7), (0, 1), (0, -1)]


def find_station(city, sid):
    if sid in city.stations:
        return city.stations[sid]
    return next(e for e in city.extras if e.id == sid)


def path_order(city):
    """Station ids in corridor order (each once) plus each one's
    predecessor on its path, for the consistency bonus."""
    order, prev = [], {}
    for line in city.lines:
        for path in line.paths:
            for a, b in zip([None] + path, path):
                if b not in prev:
                    prev[b] = a
                    order.append(b)
    for e in city.extras:
        if e.id not in prev:
            prev[e.id] = None
            order.append(e.id)
    return order, prev


def score(ctx, sid, prev_angle):
    cols = ctx.collisions_for(sid)
    st = find_station(ctx.city, sid)
    s = 0
    for c in cols:
        s += 30 if c.kind == "label-geo" else 100
    if st.label["angle"] not in (0, 45, -45, 90, -90):
        s += 3
    if prev_angle is not None and st.label["angle"] != prev_angle:
        s += 2
    if st.label.get("leader"):
        s += 12 + 0.5 * math.hypot(st.label["dx"], st.label["dy"])
    return s


def candidates(st):
    for angle in ANGLES:
        for anchor in ("start", "end"):
            dx, dy = citymap.label_offset(angle, anchor)
            yield {"angle": angle, "anchor": anchor, "dx": dx, "dy": dy}
    for r in LEADER_RING:
        for ux, uy in LEADER_DIRS:
            anchor = "end" if ux < 0 else "start"
            yield {"angle": 0, "anchor": anchor, "dx": round(ux * r, 2),
                   "dy": round(uy * r, 2), "leader": True}


def best_label(ctx, sid, prev_angle):
    st = find_station(ctx.city, sid)
    best = None
    for cand in candidates(st):
        st.label = cand
        s = score(ctx, sid, prev_angle)
        if best is None or s < best[0]:
            best = (s, dict(cand))
        if s == 0:
            break
    st.label = best[1]
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="",
                    help="comma-separated station ids to (re)place; default all")
    ap.add_argument("--passes", type=int, default=2)
    args = ap.parse_args()
    only = set(filter(None, args.only.split(",")))

    d = json.load(open(PATH, encoding="utf-8"))
    city = citymap.load(PATH)
    ctx = check_fit.Context(city, 1.5, citymap.TEXT_H, False)
    order, prev = path_order(city)
    for p in range(args.passes):
        total = 0
        for sid in order:
            if only and sid not in only:
                continue
            pa = find_station(city, prev[sid]).label["angle"] if prev[sid] else None
            s, label = best_label(ctx, sid, pa)
            total += s
            target = d["stations"].get(sid)
            if target is None:
                target = next(e for e in d["extras"] if e["id"] == sid)
            target["label"] = label
        print(f"pass {p}: total score {total:.0f}")
    json.dump(d, open(PATH, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    cols = [c for c in check_fit.find_collisions(city, 1.5, citymap.TEXT_H, False)
            if c.kind != "label-geo"]
    print(f"remaining real collisions: {len(cols)}")
    for c in cols:
        print(" ", c.kind, c.a, c.b)
    leaders = [s.id for s in list(city.stations.values()) + city.extras
               if s.label.get("leader")]
    print(f"leader labels: {leaders}")


if __name__ == "__main__":
    main()
