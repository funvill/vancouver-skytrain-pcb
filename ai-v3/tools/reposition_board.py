"""Rewrite footprint positions in the KiCad board from the pipeline outputs.

- LED1..LED68 moved to the station coordinates in leds.csv (position only;
  rotation is left at the v2 value - rotate for chain routing inside KiCad,
  which keeps pad geometry consistent)
- U1 (XIAO, back side) centered, SW1..SW4 flanking it
- Edge.Cuts replaced with a BOARD_MM x BOARD_MM rounded square (r=5mm)

Usage:
    python reposition_board.py ../hardware/vancouver-skytrain-pcb.kicad_pcb \
        ../hardware/leds.csv --board 150
"""
import argparse
import csv
import re

CORNER_R = 5.0


def split_top_blocks(text):
    """Split file into (header, [top-level blocks], footer=')')."""
    open_idx = text.index("(kicad_pcb")
    depth = 0
    blocks = []
    start = None
    i = open_idx
    header_end = None
    while i < len(text):
        c = text[i]
        if c == "(":
            depth += 1
            if depth == 2:
                if header_end is None:
                    header_end = i
                start = i
        elif c == ")":
            depth -= 1
            if depth == 1 and start is not None:
                blocks.append(text[start:i + 1])
                start = None
            elif depth == 0:
                break
        i += 1
    return text[:header_end], blocks, text[i:]


def set_position(block, x, y):
    """Replace the footprint-level (at ...) line, preserving rotation."""
    def repl(m):
        rot = m.group("rot") or ""
        return f"(at {x} {y}{rot})"
    return re.sub(r"\(at\s+[-\d.]+\s+[-\d.]+(?P<rot>\s+[-\d.]+)?\)",
                  repl, block, count=1)


def rounded_rect_edges(size, r):
    s = size
    def line(x1, y1, x2, y2):
        return (f"\t(gr_line\n\t\t(start {x1} {y1})\n\t\t(end {x2} {y2})\n"
                f"\t\t(stroke\n\t\t\t(width 0.1)\n\t\t\t(type default)\n\t\t)\n"
                f"\t\t(layer \"Edge.Cuts\")\n\t)\n")
    def arc(x1, y1, xm, ym, x2, y2):
        return (f"\t(gr_arc\n\t\t(start {x1} {y1})\n\t\t(mid {xm} {ym})\n"
                f"\t\t(end {x2} {y2})\n"
                f"\t\t(stroke\n\t\t\t(width 0.1)\n\t\t\t(type default)\n\t\t)\n"
                f"\t\t(layer \"Edge.Cuts\")\n\t)\n")
    k = 1.464  # r * (1 - cos45) approximation for the arc midpoint at r=5
    return (line(r, 0, s - r, 0) + line(s, r, s, s - r) +
            line(r, s, s - r, s) + line(0, r, 0, s - r) +
            arc(0, r, k, k, r, 0) +
            arc(s - r, 0, s - k, k, s, r) +
            arc(s, s - r, s - k, s - k, s - r, s) +
            arc(r, s, k, s - k, 0, s - r))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pcb")
    ap.add_argument("csv")
    ap.add_argument("--board", type=float, default=150.0)
    args = ap.parse_args()

    with open(args.csv, encoding="utf-8") as f:
        pos = {row["ref"]: (row["x_mm"], row["y_mm"])
               for row in csv.DictReader(f)}
    c = args.board / 2
    pos["U1"] = (c, c)                       # XIAO centered, USB-C down
    pos.update({"SW1": (c - 18, c - 12), "SW2": (c - 18, c + 12),
                "SW3": (c + 18, c - 12), "SW4": (c + 18, c + 12)})

    with open(args.pcb, encoding="utf-8") as f:
        text = f.read()
    header, blocks, footer = split_top_blocks(text)

    moved, kept = 0, []
    for b in blocks:
        if b.startswith("(gr_line") or b.startswith("(gr_arc"):
            if '(layer "Edge.Cuts")' in b:
                continue  # drop old outline
        if b.startswith("(footprint"):
            m = re.search(r'\(property "Reference" "([^"]+)"', b)
            if m and m.group(1) in pos:
                x, y = pos[m.group(1)]
                b = set_position(b, x, y)
                moved += 1
        kept.append(b)

    body = "\t" + "\n\t".join(kept) + "\n"
    body += rounded_rect_edges(args.board, CORNER_R)
    with open(args.pcb, "w", encoding="utf-8", newline="\n") as f:
        f.write(header + body + footer)
    print(f"moved {moved} footprints; outline set to "
          f"{args.board}x{args.board}mm r{CORNER_R}")


if __name__ == "__main__":
    main()
