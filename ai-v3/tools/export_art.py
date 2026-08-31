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
TEXT_H = 1.2
TEXT_THICKNESS = 0.2
RIVER_MITRE = 1.0  # extra length added at each river segment end, to close gaps
# citymap.repel() only pushes vertices, not the edges between them, so two
# adjacent vertices each individually clear of a station can still bound an
# edge that swings back close to it - a real risk where several stations
# sit only a few mm apart (e.g. the Expo diagonal crossing the Fraser).
# Any river rectangle whose corner still ends up under this floor is
# dropped rather than emitted too close to call safe; the gap reads as a
# bridge crossing, which is accurate anyway.
RIVER_SAFE_FLOOR = 2.6


def art_uuid(key):
    return str(uuid.uuid5(ART_NAMESPACE, key))


def poly_block(kind, points, layer, fill, key, width=0.1):
    pts = " ".join(f"(xy {x:.3f} {y:.3f})" for x, y in points)
    return (f"({kind}\n\t\t(pts\n\t\t\t{pts}\n\t\t)\n\t\t(stroke\n\t\t\t"
            f"(width {width})\n\t\t\t(type default)\n\t\t)\n\t\t"
            f"(fill {'yes' if fill else 'no'})\n\t\t(layer \"{layer}\")\n\t\t"
            f"(uuid \"{art_uuid(key)}\")\n\t)")


def text_block(text, x, y, angle, anchor, layer, key):
    justify = ""
    if anchor == "start":
        justify = "\n\t\t\t(justify left)"
    elif anchor == "end":
        justify = "\n\t\t\t(justify right)"
    text = text.replace('"', "'")
    return (f'(gr_text "{text}"\n\t\t(at {x:.3f} {y:.3f} {angle % 360:.1f})\n'
            f'\t\t(layer "{layer}")\n\t\t(uuid "{art_uuid(key)}")\n\t\t'
            f'(effects\n\t\t\t(font\n\t\t\t\t(size {TEXT_H} {TEXT_H})\n'
            f'\t\t\t\t(thickness {TEXT_THICKNESS})\n\t\t\t){justify}\n\t\t)\n\t)')


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
                rect = citymap.clamp_to_board(rect, city.canvas_mm * scale, 1.0)
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


def land_outline_blocks(city, scale, geo=None):
    """Islands and parks as thin white silkscreen outlines only (no fill -
    the board substrate itself is the land)."""
    geo = geo if geo is not None else citymap.prepared_geo(
        city, scale, avoid_points(city, scale))
    blocks = []
    for g in geo:
        if g["type"] in ("island", "park"):
            blocks.append(poly_block("gr_poly", g["points"], "F.SilkS",
                                     False, f"land:{g['name']}", width=0.15))
    return blocks


def label_blocks(city, scale):
    blocks = []
    for st in list(city.stations.values()) + city.extras:
        x = st.x * scale + st.label["dx"]
        y = st.y * scale + st.label["dy"]
        blocks.append(text_block(citymap.display_name(st), x, y, -st.label["angle"],
                                 st.label["anchor"], "F.SilkS",
                                 f"label:{st.id}"))
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
    land = land_outline_blocks(city, args.scale, geo)
    labels = label_blocks(city, args.scale)
    blocks = water + land + labels
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
          f"({len(water)} water, {len(land)} land outline, "
          f"{len(labels)} labels)")


if __name__ == "__main__":
    main()
