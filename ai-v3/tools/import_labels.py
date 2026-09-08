"""Pull hand-edited labels back from the KiCad board into vancouver.json.

export_art.py writes every station label, leader line and annotation with
a deterministic uuid (art_uuid("label:<id>") etc.), so after you move,
rotate, re-anchor, retext or delete them in KiCad this script finds each
one by uuid and updates the data file to match:

  station label   -> label.angle / anchor / dx / dy (board mm from the LED)
                     text edited      -> station "wrap" (list of lines) or
                                         label.short when it is the short form
  leader gr_line  -> label.leader = True if the line still exists, else False
  annotation text -> annotations[i].x / y (city names, wordmark)

Run it BEFORE export_art.py, or the exporter will regenerate the labels
from the old data and overwrite your edits:

    python import_labels.py ../input/vancouver.json ../hardware/vancouver-skytrain-pcb.kicad_pcb
"""
import argparse
import json
import re

import citymap
import export_art
import reposition_board as rb


def parse_text_block(block):
    at = re.search(r'\(at\s+([-\d.]+)\s+([-\d.]+)(?:\s+([-\d.]+))?\)', block)
    text = re.match(r'\(gr_text\s+"((?:[^"\\]|\\.)*)"', block).group(1)
    text = text.replace("\\n", "\n").replace("\\\"", '"')
    just = re.search(r'\(justify\s+([^)]*)\)', block)
    justify = just.group(1).split() if just else []
    anchor = "start" if "left" in justify else ("end" if "right" in justify else "center")
    return (float(at.group(1)), float(at.group(2)),
            float(at.group(3)) if at.group(3) else 0.0, text, anchor)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("pcb")
    args = ap.parse_args()

    d = json.load(open(args.data, encoding="utf-8"))
    city = citymap.load(args.data)
    scale = city.scale
    with open(args.pcb, encoding="utf-8") as f:
        _, blocks, _ = rb.split_top_blocks(f.read())
    by_uuid = {}
    for b in blocks:
        m = re.search(r'\(uuid "([^"]+)"\)', b)
        if m:
            by_uuid[m.group(1)] = b

    changed = 0
    for st in list(city.stations.values()) + city.extras:
        b = by_uuid.get(export_art.art_uuid(f"label:{st.id}"))
        target = d["stations"].get(st.id) or next(e for e in d["extras"] if e["id"] == st.id)
        if b is None:
            print(f"  {st.id}: label not found on the board (deleted?) - kept as is")
            continue
        x, y, kangle, text, anchor = parse_text_block(b)
        angle = (-kangle + 180) % 360 - 180          # KiCad CCW -> our clockwise
        label = {"angle": int(round(angle)) if abs(angle - round(angle)) < 1e-6 else round(angle, 1),
                 "anchor": anchor,
                 "dx": round(x - st.x * scale, 2), "dy": round(y - st.y * scale, 2)}
        if by_uuid.get(export_art.art_uuid(f"leader:{st.id}")) is not None:
            label["leader"] = True
        # text: unchanged / short form / custom line break
        lines = text.split("\n")
        if lines == citymap.display_lines(st):
            if st.label.get("short"):
                label["short"] = True
        else:
            st_short = dict(st.label, short=True)
            probe = citymap.Station(st.id, st.name, st.x, st.y, st.short, st.future,
                                    st.interchange, st_short, st.wrap)
            if lines == citymap.display_lines(probe):
                label["short"] = True
            elif target.get("wrap") != (lines if len(lines) > 1 else False) and lines != [st.name]:
                target["wrap"] = lines if len(lines) > 1 or lines[0] != st.name else False
            elif lines == [st.name]:
                target["wrap"] = False
        if label != st.label or "wrap" in target and target["wrap"] != st.wrap:
            changed += 1
        target["label"] = label

    for i, a in enumerate(d.get("annotations", [])):
        layer = "F.Cu" if a.get("copper") else "F.SilkS"
        b = by_uuid.get(export_art.art_uuid(f"annotation:{i}:{a['text']}:{layer}"))
        if b is None:
            continue
        x, y, kangle, text, _ = parse_text_block(b)
        nx, ny = round(x / scale, 2), round(y / scale, 2)
        if (nx, ny) != (a["x"], a["y"]) or text != a["text"]:
            a["x"], a["y"], a["text"] = nx, ny, text
            a["angle"] = (-kangle + 180) % 360 - 180
            changed += 1

    # Anything the last export wrote that is no longer on the board was
    # deleted by hand (a SeaBus dash, a route segment, a boundary piece...):
    # record its key so export_art.py leaves it out from now on. Labels,
    # leaders and annotations are handled above and never suppressed.
    manifest = export_art.load_manifest(args.pcb + ".art-manifest.json")
    suppressed = set(d.get("suppressed_art", []))
    for u, key in manifest.items():
        if key and u not in by_uuid and not key.startswith(("label:", "leader:", "annotation:")):
            suppressed.add(key)
    if suppressed:
        d["suppressed_art"] = sorted(suppressed)

    json.dump(d, open(args.data, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"imported: {changed} label/annotation change(s), "
          f"{len(suppressed)} deleted art item(s) recorded -> {args.data}")


if __name__ == "__main__":
    main()
