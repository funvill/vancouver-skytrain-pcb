"""Validation tests for the Vancouver city data file.

Run: python test_vancouver_data.py
Plain asserts, no pytest dependency, so it runs on any machine with Python 3.
"""
import os
import sys

import citymap

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "input", "vancouver.json")

EXPECTED_LEDS = 68          # 67 unique stations + SeaBus
EXPECTED_STATIONS = 67
MARGIN_MM = 3.0

SHARED = ["waterfront", "commercial-broadway", "broadway-city-hall",
          "lougheed", "production-way"]


def main():
    city = citymap.load(DATA)
    errors = []

    # LED / station counts
    if len(city.stations) != EXPECTED_STATIONS:
        errors.append(f"station count {len(city.stations)} != {EXPECTED_STATIONS}")
    if citymap.led_count(city) != EXPECTED_LEDS:
        errors.append(f"LED count {citymap.led_count(city)} != {EXPECTED_LEDS}")

    # Every path id resolves
    for line in city.lines:
        for path in line.paths:
            for sid in path:
                if sid not in city.stations:
                    errors.append(f"line {line.id}: unknown station id '{sid}'")

    # Shared interchange stations appear in >= 2 lines but exist exactly once
    for sid in SHARED:
        count = sum(1 for line in city.lines for path in line.paths
                    if sid in path)
        if count < 2:
            errors.append(f"'{sid}' should be used by >=2 line paths, got {count}")

    # Octilinearity of every drawn segment
    for line_id, p1, p2, a, b in citymap.segments(city):
        if not citymap.is_octilinear(p1, p2):
            errors.append(f"{line_id}: segment {a}->{b} not octilinear "
                          f"{p1}->{p2}")

    # Coordinates on canvas with margin
    for st in list(city.stations.values()) + city.extras:
        if not (MARGIN_MM <= st.x <= city.canvas_mm - MARGIN_MM and
                MARGIN_MM <= st.y <= city.canvas_mm - MARGIN_MM):
            errors.append(f"'{st.id}' at ({st.x},{st.y}) violates "
                          f"{MARGIN_MM}mm margin")
        if not st.name.strip():
            errors.append(f"'{st.id}' has empty name")

    # No two LEDs closer than 2.5 mm (1615 package + courtyard)
    pts = [(s.id, s.x, s.y) for s in list(city.stations.values()) + city.extras]
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            d = ((pts[i][1] - pts[j][1]) ** 2 + (pts[i][2] - pts[j][2]) ** 2) ** 0.5
            if d < 2.5:
                errors.append(f"LEDs '{pts[i][0]}' and '{pts[j][0]}' only "
                              f"{d:.2f}mm apart")

    # Chain + export invariants
    import export_placement as ep
    chain = ep.load_chain(DATA, city)  # raises if incomplete/dupes
    rows = ep.led_rows(city, chain, 1.5)
    if len(rows) != EXPECTED_LEDS:
        errors.append(f"led_rows: {len(rows)} != {EXPECTED_LEDS}")
    if [r[1] for r in rows[:2]] != ["LED1", "LED2"]:
        errors.append("led_rows: refs must start LED1, LED2, ...")
    for name, route in ep.routes(city):
        for sid in route:
            if sid not in chain:
                errors.append(f"route {name}: '{sid}' not in chain")
    n_routes = len(ep.routes(city))
    if n_routes != 6:  # expo x2 branches, millennium, canada x2, seabus
        errors.append(f"expected 6 firmware routes, got {n_routes}")

    # SAT self-test
    a = [(0, 0), (2, 0), (2, 2), (0, 2)]
    b = [(1, 1), (3, 1), (3, 3), (1, 3)]
    c = [(5, 5), (6, 5), (6, 6), (5, 6)]
    assert citymap.polys_intersect(a, b), "SAT: overlapping rects not detected"
    assert not citymap.polys_intersect(a, c), "SAT: disjoint rects flagged"

    if errors:
        print(f"FAIL: {len(errors)} problem(s)")
        for e in errors:
            print("  -", e)
        sys.exit(1)
    print(f"PASS: {len(city.stations)} stations + {len(city.extras)} extras = "
          f"{citymap.led_count(city)} LEDs, all checks green")


if __name__ == "__main__":
    main()
