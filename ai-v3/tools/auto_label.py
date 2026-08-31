"""Brute-force the best label angle/anchor for stations flagged by
check_fit.py (excluding label-geo, which is expected for coastal
stations). Iterates until clean or no more improvement is found.
"""
import json
import citymap
import check_fit

PATH = "../input/vancouver.json"


def real_collisions(city, scale=1.5, text_h=1.2):
    cols = check_fit.find_collisions(city, scale, text_h, False)
    return [c for c in cols if c.kind != "label-geo"]


def offset_for(angle, anchor, mag=1.8):
    import math
    a = math.radians(angle)
    dx, dy = math.cos(a) * mag * 0.5, math.sin(a) * mag * 0.5
    if anchor == "end":
        dx, dy = -dx, -dy
    return round(dx, 2), round(dy, 2)


def find_station(city, sid):
    if sid in city.stations:
        return city.stations[sid]
    return next(e for e in city.extras if e.id == sid)


def best_label(city, sid, current_others_count):
    st = find_station(city, sid)
    orig = dict(st.label)
    best = None
    # angles outside [-90, 90] render the glyphs upside-down/mirrored in
    # KiCad (rotation is rigid, there's no auto-flip for readability) -
    # stay in the readable half-circle; anchor start/end covers left/right.
    for angle in range(-90, 91, 5):
        for anchor in ("start", "end"):
            dx, dy = offset_for(angle, anchor)
            st.label = {"angle": angle, "anchor": anchor, "dx": dx, "dy": dy}
            cols = real_collisions(city)
            n = sum(1 for c in cols if c.a == sid or c.b == sid)
            if best is None or n < best[0]:
                best = (n, dict(st.label))
            if n == 0:
                return best
    return best


def main():
    d = json.load(open(PATH, encoding="utf-8"))
    for round_i in range(6):
        city = citymap.load(PATH)
        cols = real_collisions(city)
        involved = sorted({c.a for c in cols} | {c.b for c in cols if c.b in city.stations})
        if not involved:
            print(f"round {round_i}: clean")
            break
        print(f"round {round_i}: {len(cols)} real collisions, fixing {involved}")
        for sid in involved:
            n, label = best_label(city, sid, len(cols))
            city.stations[sid].label = label
            d["stations"][sid]["label"] = label
        json.dump(d, open(PATH, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    else:
        print("gave up after 6 rounds, remaining:")
        city = citymap.load(PATH)
        for c in real_collisions(city):
            print(" ", c.kind, c.a, c.b)


if __name__ == "__main__":
    main()
