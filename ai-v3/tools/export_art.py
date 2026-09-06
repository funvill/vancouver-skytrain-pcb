"""Generate PCB artwork (station labels + land/water shapes) and inject it
into the KiCad board.

Water technique (see v1/input/natrual/natrual/map.kicad_pcb): a filled
polygon on F.Cu *and* a matching filled polygon on F.Mask, same outline.
The mask opening exposes the copper underneath, so water reads as bare
copper (gold with ENIG) against the black soldermask everywhere else -
the board substrate itself stands in for "land", so land needs no fill,
only an outline where its boundary isn't a coastline (parks, river
islands) drawn as thin F.SilkS strokes.

Station names are gr_text on F.SilkS, positioned/rotated the same way as
the SVG preview (citymap.label_box's placement math), white ink being the
only ink silkscreen has.

Regeneration is idempotent: every block this script writes is recorded by
uuid in <pcb>.art-manifest.json; on the next run those uuids are stripped
before new ones are appended, so re-running after an edit to vancouver.json
never leaves stale or duplicate art behind.

Usage:
    python export_art.py ../input/vancouver.json ../hardware/vancouver-skytrain-pcb.kicad_pcb --scale 1.5
"""
import argparse
import json
import math
import os
import uuid

import citymap
import reposition_board as rb

ART_NAMESPACE = uuid.UUID("6f1b0b1a-b1a1-4a7a-9a1a-76616e636f75")  # fixed, arbitrary
TEXT_H = citymap.TEXT_H
TEXT_THICKNESS = 0.14  # ~1:8 keeps the stroke font's counters open
ROUTE_W = 1.5          # route stroke; the LEDs are the stars, this is the
                       # connective tissue and has to out-weigh the labels
RING_R, RING_W = 1.25, 0.25            # silk ring behind every station LED
RING_R_INT, RING_W_INT = 1.55, 0.4     # ... and a heavier one at interchanges
DASH_STYLES = {  # (dash, gap) in mm for "line" geo and future routes
    "dash": (2.2, 1.4),
    "dot": (0.5, 0.9),
    "dashdot": None,  # handled specially: long dash, gap, dot, gap
}
RIVER_MITRE = 1.0  # extra length added at each river segment end, to close gaps
# citymap.repel() only pushes vertices, not the edges between them, so two
# adjacent vertices each individually clear of a station can still bound an
# edge that swings back close to it - a real risk where several stations
# sit only a few mm apart (e.g. the Expo diagonal crossing the Fraser).
# Any river rectangle whose corner still ends up under this floor is
# dropped rather than emitted too close to call safe; the gap reads as a
# bridge crossing, which is accurate anyway.
RIVER_SAFE_FLOOR = 1.5


def art_uuid(key):
    return str(uuid.uuid5(ART_NAMESPACE, key))


def poly_block(kind, points, layer, fill, key, width=0.1):
    pts = " ".join(f"(xy {x:.3f} {y:.3f})" for x, y in points)
    return (f"({kind}\n\t\t(pts\n\t\t\t{pts}\n\t\t)\n\t\t(stroke\n\t\t\t"
            f"(width {width})\n\t\t\t(type default)\n\t\t)\n\t\t"
            f"(fill {'yes' if fill else 'no'})\n\t\t(layer \"{layer}\")\n\t\t"
            f"(uuid \"{art_uuid(key)}\")\n\t)")


def line_block(p1, p2, layer, key, width=1.0):
    return (f"(gr_line\n\t\t(start {p1[0]:.3f} {p1[1]:.3f})\n\t\t"
            f"(end {p2[0]:.3f} {p2[1]:.3f})\n\t\t(stroke\n\t\t\t"
            f"(width {width})\n\t\t\t(type solid)\n\t\t)\n\t\t"
            f"(layer \"{layer}\")\n\t\t(uuid \"{art_uuid(key)}\")\n\t)")


def dash_points(p1, p2, dash=2.2, gap=1.4):
    """(a, b) endpoint pairs for real physical dashes along p1->p2 - a
    stroke "line style" of dash/dot is a KiCad editor display hint only
    and is dropped on plot/fab/3D-render output, so a genuinely dashed
    silkscreen line has to be built from real solid segments with gaps."""
    ln = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
    if ln < 1e-6:
        return []
    ux, uy = (p2[0] - p1[0]) / ln, (p2[1] - p1[1]) / ln
    period = dash + gap
    out = []
    d = 0.0
    while d < ln:
        a = (p1[0] + ux * d, p1[1] + uy * d)
        end = min(d + dash, ln)
        b = (p1[0] + ux * end, p1[1] + uy * end)
        out.append((a, b))
        d += period
    return out


def circle_block(cx, cy, r, layer, key, width):
    return (f"(gr_circle\n\t\t(center {cx:.3f} {cy:.3f})\n\t\t"
            f"(end {cx + r:.3f} {cy:.3f})\n\t\t(stroke\n\t\t\t"
            f"(width {width})\n\t\t\t(type solid)\n\t\t)\n\t\t(fill no)\n\t\t"
            f"(layer \"{layer}\")\n\t\t(uuid \"{art_uuid(key)}\")\n\t)")


def dashdot_points(p1, p2, dash=3.0, dot=0.4, gap=1.0):
    """Long dash, gap, dot, gap - the cartographic international border."""
    ln = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
    if ln < 1e-6:
        return []
    ux, uy = (p2[0] - p1[0]) / ln, (p2[1] - p1[1]) / ln
    out, d = [], 0.0
    while d < ln:
        for seg in (dash, dot):
            if d >= ln:
                break
            end = min(d + seg, ln)
            out.append(((p1[0] + ux * d, p1[1] + uy * d),
                        (p1[0] + ux * end, p1[1] + uy * end)))
            d = end + gap
    return out


def styled_line_blocks(p1, p2, layer, key, width, dash=None):
    """One solid gr_line, or a run of real short segments for a dashed /
    dotted / dash-dot style (stroke line styles don't survive to fab)."""
    if not dash:
        return [line_block(p1, p2, layer, key, width=width)]
    if dash == "dashdot":
        pairs = dashdot_points(p1, p2)
    else:
        pairs = dash_points(p1, p2, *DASH_STYLES[dash])
    return [line_block(a, b, layer, f"{key}:{j}", width=width)
            for j, (a, b) in enumerate(pairs)]


def text_block(text, x, y, angle, anchor, layer, key, size=None, bold=False):
    justify = ""
    if anchor == "start":
        justify = "\n\t\t\t(justify left)"
    elif anchor == "end":
        justify = "\n\t\t\t(justify right)"
    text = text.replace('"', "'").replace("\n", "\\n")
    h = size if size is not None else TEXT_H
    ratio = 0.22 if bold else TEXT_THICKNESS / TEXT_H
    thickness = max(0.12, h * ratio)
    return (f'(gr_text "{text}"\n\t\t(at {x:.3f} {y:.3f} {angle % 360:.1f})\n'
            f'\t\t(layer "{layer}")\n\t\t(uuid "{art_uuid(key)}")\n\t\t'
            f'(effects\n\t\t\t(font\n\t\t\t\t(size {h} {h})\n'
            f'\t\t\t\t(thickness {thickness:.3f})\n\t\t\t){justify}\n\t\t)\n\t)')


def avoid_points(city, scale):
    return [(st.x * scale, st.y * scale)
            for st in list(city.stations.values()) + city.extras]


def water_blocks(city, scale, geo=None):
    """One F.Cu + one F.Mask filled polygon per water/lake shape, and a
    chain of mitred rectangles for river/linear water. Shapes are already
    repelled from LED pads and inset from the board edge by
    citymap.prepared_geo, so the copper stays DRC-clean."""
    geo = geo if geo is not None else citymap.prepared_geo(
        city, scale, avoid_points(city, scale))
    avoid = avoid_points(city, scale)
    blocks = []
    dropped = []
    for g in geo:
        pts = g["points"]
        if g["type"] in ("water", "lake"):
            for layer in ("F.Cu", "F.Mask"):
                blocks.append(poly_block("gr_poly", pts, layer, True,
                                         f"water:{g['name']}:{layer}"))
        elif g["type"] == "river":
            half = g.get("width", 2.5) * scale / 2
            for i, (p1, p2) in enumerate(zip(pts, pts[1:])):
                dx, dy = p2[0] - p1[0], p2[1] - p1[1]
                ln = math.hypot(dx, dy) or 1.0
                ux, uy = dx / ln * RIVER_MITRE, dy / ln * RIVER_MITRE
                a = (p1[0] - ux, p1[1] - uy)
                b = (p2[0] + ux, p2[1] + uy)
                rect = citymap.seg_rect(a, b, half)
                rect = citymap.clamp_to_board(rect, city.canvas_mm * scale, 2.5)
                closest = min(citymap.poly_point_min_dist(rect, pt)
                             for pt in avoid)
                if closest < RIVER_SAFE_FLOOR:
                    dropped.append((g["name"], i, closest))
                    continue
                for layer in ("F.Cu", "F.Mask"):
                    blocks.append(poly_block(
                        "gr_poly", rect, layer, True,
                        f"river:{g['name']}:{i}:{layer}"))
    if dropped:
        print(f"  dropped {len(dropped)} river segment(s) too close to an "
              f"LED to route safely (reads as a bridge crossing):")
        for name, i, d in dropped:
            print(f"    {name}[{i}]  closest LED {d:.2f}mm "
                  f"(floor {RIVER_SAFE_FLOOR}mm)")
    return blocks


PARK_HATCH_SPACING = 1.6  # mm between hatch lines, matched to the 150mm board


def land_outline_blocks(city, scale, geo=None):
    """Islands: thin white silkscreen outline only (no fill - the board
    substrate itself is the land). Parks: outline + a diagonal hatch fill,
    the single-ink stand-in for the reference map's solid green park areas
    (see TransLink's Future Rapid Transit Network map)."""
    geo = geo if geo is not None else citymap.prepared_geo(
        city, scale, avoid_points(city, scale))
    blocks = []
    for g in geo:
        if g["type"] == "line":
            pts = g["points"]
            for i, (p1, p2) in enumerate(zip(pts, pts[1:])):
                blocks += styled_line_blocks(
                    p1, p2, "F.SilkS", f"line:{g['name']}:{i}",
                    g.get("width", 0.3), g.get("dash"))
            continue
        if g["type"] not in ("island", "park"):
            continue
        blocks.append(poly_block("gr_poly", g["points"], "F.SilkS", False,
                                 f"land:{g['name']}", width=0.15))
        if g["type"] == "park":
            hatch = citymap.hatch_fill(g["points"], PARK_HATCH_SPACING)
            for i, (a, b) in enumerate(hatch):
                blocks.append(line_block(a, b, "F.SilkS",
                                         f"hatch:{g['name']}:{i}", width=0.12))
    return blocks


def route_blocks(city, scale):
    """The transit lines themselves, as F.SilkS strokes between adjacent
    stations - solid for the current network, dashed for segments not
    built yet (either endpoint has future=true), mirroring how the
    official map distinguishes future lines from the current network."""
    blocks = []
    for i, (line_id, p1, p2, a, b) in enumerate(citymap.segments(city)):
        future = city.stations[a].future or city.stations[b].future
        p1s = (p1[0] * scale, p1[1] * scale)
        p2s = (p2[0] * scale, p2[1] * scale)
        if future:
            for j, (da, db) in enumerate(dash_points(p1s, p2s)):
                blocks.append(line_block(da, db, "F.SilkS",
                                         f"route:{i}:{a}:{b}:{j}", width=ROUTE_W))
        else:
            blocks.append(line_block(p1s, p2s, "F.SilkS",
                                     f"route:{i}:{a}:{b}", width=ROUTE_W))
    return blocks


def station_ring_blocks(city, scale):
    """A white silk ring behind every LED so a station reads as the classic
    circle-on-line marker rather than a bare pad interrupting the route;
    interchanges get a visibly heavier ring. Rings sit inside the route
    stroke width at the tightest (2.8 mm) pitches downtown."""
    blocks = []
    for st in list(city.stations.values()) + city.extras:
        r, w = (RING_R_INT, RING_W_INT) if st.interchange else (RING_R, RING_W)
        blocks.append(circle_block(st.x * scale, st.y * scale, r, "F.SilkS",
                                   f"ring:{st.id}", w))
    return blocks


def annotation_blocks(city, scale):
    """River/municipality context labels (vancouver.json's "annotations"
    list) - the equivalent of the reference map's small gray place names
    and "NORTH ARM FRASER RIVER" style water labels."""
    blocks = []
    for i, a in enumerate(city.annotations):
        x, y = a["x"] * scale, a["y"] * scale
        # "copper": exposed-copper lettering (F.Cu + matching F.Mask opening,
        # the same trick as the water) - the wordmark, gold with ENIG.
        layers = ("F.Cu", "F.Mask") if a.get("copper") else ("F.SilkS",)
        for layer in layers:
            blocks.append(text_block(
                a["text"], x, y, a.get("angle", 0), a.get("anchor", "start"),
                layer, f"annotation:{i}:{a['text']}:{layer}",
                size=a.get("size", 1.4), bold=a.get("bold", False)))
    return blocks


def label_blocks(city, scale):
    blocks = []
    for st in list(city.stations.values()) + city.extras:
        x, y = citymap.label_anchor(st, scale)
        blocks.append(text_block(citymap.display_name(st), x, y, -st.label["angle"],
                                 st.label["anchor"], "F.SilkS",
                                 f"label:{st.id}"))
        seg = citymap.leader_segment(st, scale)
        if seg:
            blocks.append(line_block(seg[0], seg[1], "F.SilkS",
                                     f"leader:{st.id}", width=0.15))
    return blocks


def load_manifest(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_manifest(path, uuids):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sorted(uuids), f, indent=2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("pcb")
    ap.add_argument("--scale", type=float, default=1.5)
    args = ap.parse_args()
    city = citymap.load(args.data)
    geo = citymap.prepared_geo(city, args.scale, avoid_points(city, args.scale))
    water = water_blocks(city, args.scale, geo)
    routes = route_blocks(city, args.scale) + station_ring_blocks(city, args.scale)
    land = land_outline_blocks(city, args.scale, geo)
    labels = label_blocks(city, args.scale)
    annotations = annotation_blocks(city, args.scale)
    blocks = water + routes + land + labels + annotations
    new_uuids = set()
    for b in blocks:
        new_uuids.add(b[b.index('(uuid "') + 7: b.index('"', b.index('(uuid "') + 7)])

    manifest_path = args.pcb + ".art-manifest.json"
    old_uuids = load_manifest(manifest_path)

    with open(args.pcb, encoding="utf-8") as f:
        text = f.read()
    header, top_blocks, footer = rb.split_top_blocks(text)
    kept = [b for b in top_blocks if not any(
        f'(uuid "{u}")' in b for u in old_uuids)]

    body = "\t" + "\n\t".join(kept + blocks) + "\n"
    with open(args.pcb, "w", encoding="utf-8", newline="\n") as f:
        f.write(header + body + footer)
    save_manifest(manifest_path, new_uuids)
    print(f"removed {len(top_blocks) - len(kept)} stale art block(s), "
          f"wrote {len(blocks)} art block(s) "
          f"({len(water)} water, {len(routes)} route segments, "
          f"{len(land)} land outline/hatch, {len(labels)} labels, "
          f"{len(annotations)} annotations)")


if __name__ == "__main__":
    main()
