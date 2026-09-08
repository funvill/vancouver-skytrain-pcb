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
import random

import citymap
import check_fit

PATH = "../input/vancouver.json"
ANGLES = [0, -45, 45, -90, 90, -60, 60, -30, 30, -75, 75]
LEADER_RING = [5.0, 7.0, 9.0, 12.0, 15.0, 18.0]
LEADER_DIRS = [(math.cos(math.radians(a)), math.sin(math.radians(a)))
               for a in range(0, 360, 22)]


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
    cols = ctx.collisions_for(sid, getattr(ctx, "boxes", None))
    st = find_station(ctx.city, sid)
    s = 0
    for c in cols:
        s += 60 if c.kind == "label-geo" else 100
    if st.label["angle"] not in (0, 45, -45, 90, -90):
        s += 3
    if prev_angle is not None and st.label["angle"] != prev_angle:
        s += 2
    if st.label.get("leader"):
        s += 12 + 0.5 * math.hypot(st.label["dx"], st.label["dy"])
        # in a cluster, leaders should fan outward: penalise a leader that
        # points toward the centroid of the neighbours within 9 mm
        near = [(o.x, o.y) for o in ctx.all_st
                if o.id != sid and math.hypot(o.x - st.x, o.y - st.y) * ctx.scale < 9.0]
        if near:
            mx = sum(p[0] for p in near) / len(near) - st.x
            my = sum(p[1] for p in near) / len(near) - st.y
            L = math.hypot(mx, my)
            dl = math.hypot(st.label["dx"], st.label["dy"])
            if L > 1e-6 and dl > 1e-6:
                toward = (mx / L) * (st.label["dx"] / dl) + (my / L) * (st.label["dy"] / dl)
                s += 8 * (toward + 1)     # 0 when pointing straight away, 16 toward
    if st.label.get("short"):
        s += 8
    return s


def candidates(st):
    for short in (False, True):
        if short and not (len(st.name) > citymap.WRAP_OVER and
                          any(dd in st.name for dd in citymap.DASHES)):
            continue
        for angle in ANGLES:
            for anchor in ("start", "end"):
                dx, dy = citymap.label_offset(angle, anchor)
                yield {"angle": angle, "anchor": anchor, "dx": dx, "dy": dy,
                       **({"short": True} if short else {})}
                # the same text shifted sideways so it runs *beside* the
                # pad (and its own line) instead of away from it - the
                # only way a label fits along a corridor of stations
                a = math.radians(angle)
                nx, ny = -math.sin(a) * 1.9, math.cos(a) * 1.9
                for sgn in (1, -1):
                    yield {"angle": angle, "anchor": anchor,
                           "dx": round(dx * 0.4 + nx * sgn, 2),
                           "dy": round(dy * 0.4 + ny * sgn, 2),
                           **({"short": True} if short else {})}
        for r in LEADER_RING:
            for ux, uy in LEADER_DIRS:
                anchor = "end" if ux < -0.05 else "start"
                yield {"angle": 0, "anchor": anchor, "dx": round(ux * r, 2),
                       "dy": round(uy * r, 2), "leader": True,
                       **({"short": True} if short else {})}


def best_label(ctx, sid, prev_angle, exclude=None):
    st = find_station(ctx.city, sid)
    best = None
    for cand in candidates(st):
        if exclude and cand in exclude:
            continue
        st.label = cand
        s = score(ctx, sid, prev_angle)
        if best is None or s < best[0]:
            best = (s, dict(cand))
        if s == 0:
            break
    st.label = best[1]
    return best


def anneal(ctx, prev, d, iters=40000, t0=60.0, t1=0.5, seed=1):
    """Simulated annealing over every label: propose one station's label
    from its candidate list, accept by the change in that station's score
    (its collisions are symmetric, so this tracks the total), cooling
    geometrically. Finds the joint layouts greedy placement can't."""
    rng = random.Random(seed)
    all_st = ctx.all_st
    cands = {st.id: list(candidates(st)) for st in all_st}
    boxes = {st.id: ctx.box(st) for st in all_st}
    ctx.boxes = boxes

    def sc(sid):
        pa = find_station(ctx.city, prev[sid]).label["angle"] if prev.get(sid) else None
        return score(ctx, sid, pa)

    cur = {st.id: sc(st.id) for st in all_st}
    total = sum(cur.values())
    best_total, best = total, {st.id: dict(st.label) for st in all_st}
    for i in range(iters):
        t = t0 * (t1 / t0) ** (i / iters)
        st = all_st[rng.randrange(len(all_st))]
        old_label, old_s = st.label, cur[st.id]
        st.label = rng.choice(cands[st.id])
        boxes[st.id] = ctx.box(st)
        new_s = sc(st.id)
        delta = new_s - old_s
        if delta <= 0 or rng.random() < math.exp(-delta / t):
            cur[st.id] = new_s
            total += delta
            if total < best_total:
                best_total, best = total, {s.id: dict(s.label) for s in all_st}
        else:
            st.label = old_label
            boxes[st.id] = ctx.box(st)
        if i % 5000 == 0:
            print(f"anneal {i}: T={t:.1f} total={total:.0f} best={best_total:.0f}")
    for st in all_st:
        st.label = best[st.id]
        boxes[st.id] = ctx.box(st)
        target = d["stations"].get(st.id) or next(e for e in d["extras"] if e["id"] == st.id)
        target["label"] = st.label
    ctx.boxes = None
    return best_total


def real_collisions(ctx):
    return [c for c in check_fit.find_collisions(ctx.city, ctx.scale)
            if c.kind != "label-geo"]


def repair(ctx, prev, d, rounds=40):
    """Greedy placement leaves collisions made by later neighbours: keep
    re-placing every station in a remaining collision (its previous choice
    barred, so a pair can't just swap back and forth) until clean."""
    tried = {}
    for r in range(rounds):
        cols = real_collisions(ctx)
        if not cols:
            return True
        involved = sorted({c.a for c in cols} | {c.b for c in cols if c.b in ctx.city.stations
                                                  or c.b in {e.id for e in ctx.city.extras}})
        for sid in involved:
            st = find_station(ctx.city, sid)
            tried.setdefault(sid, []).append(dict(st.label))
            pa = find_station(ctx.city, prev[sid]).label["angle"] if prev.get(sid) else None
            _, label = best_label(ctx, sid, pa, exclude=tried[sid][-6:])
            target = d["stations"].get(sid) or next(e for e in d["extras"] if e["id"] == sid)
            target["label"] = label
        print(f"repair {r}: {len(cols)} collision(s) -> {involved}")
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="",
                    help="comma-separated station ids to (re)place; default all")
    ap.add_argument("--passes", type=int, default=1)
    ap.add_argument("--iters", type=int, default=40000)
    args = ap.parse_args()
    only = set(filter(None, args.only.split(",")))

    d = json.load(open(PATH, encoding="utf-8"))
    city = citymap.load(PATH)
    ctx = check_fit.Context(city, city.scale, citymap.TEXT_H, False)
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
    anneal(ctx, prev, d, iters=args.iters)
    json.dump(d, open(PATH, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    cols = real_collisions(ctx)
    print(f"remaining real collisions: {len(cols)}")
    for c in cols:
        print(" ", c.kind, c.a, c.b)
    leaders = [s.id for s in list(city.stations.values()) + city.extras
               if s.label.get("leader")]
    print(f"leader labels: {leaders}")


if __name__ == "__main__":
    main()
