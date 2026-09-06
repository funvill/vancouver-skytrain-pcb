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


def rounded_rect_edges(w, r, h=None):
    h = h if h is not None else w
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
    return (line(r, 0, w - r, 0) + line(w, r, w, h - r) +
            line(r, h, w - r, h) + line(0, r, 0, h - r) +
            arc(0, r, k, k, r, 0) +
            arc(w - r, 0, w - k, k, w, r) +
            arc(w, h - r, w - k, h - k, w - r, h) +
            arc(r, h, k, h - k, 0, h - r))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pcb")
    ap.add_argument("csv")
    ap.add_argument("--board", type=float, default=150.0, help="width mm")
    ap.add_argument("--height", type=float, default=None,
                    help="height mm (default: square)")
    args = ap.parse_args()
    height = args.height if args.height else args.board

    with open(args.csv, encoding="utf-8") as f:
        pos = {row["ref"]: (row["x_mm"], row["y_mm"])
               for row in csv.DictReader(f)}
    c, cy = args.board / 2, height / 2
    pos["U1"] = (c, cy)                      # XIAO centered, USB-C down
    pos.update({"SW1": (c - 18, cy - 12), "SW2": (c - 18, cy + 12),
                "SW3": (c + 18, cy - 12), "SW4": (c + 18, cy + 12)})

    # Three test points (GND / +5V / LED_IN) are hand-placed leftovers from
    # v2's original 100x82.9mm layout, positioned relative to U1's old
    # off-centre spot - they never moved when U1 got recentred for the
    # 150mm board, landing inside its courtyard. Reference-only matching
    # can't fix them (there's a second, unrelated "+5V" test point
    # elsewhere on the board), so key these three by uuid and place them
    # just outside the XIAO courtyard (half-width 8.835mm) on its left,
    # clear of both the courtyard and the SW1/SW2 buttons at c-18.
    uuid_pos = {
        "3b08c00e-5e5e-4e28-8a48-1b276cc8aedb": (c - 12, cy - 4.6),   # GND
        "46ba156a-b5f9-49b6-8fde-9be163fb3450": (c - 12, cy + 0.4),  # +5V
        "9d44b3cc-bb74-4bbe-a707-82358cea217e": (c - 12, cy - 14.8),  # LED_IN
    }

    with open(args.pcb, encoding="utf-8") as f:
        text = f.read()
    header, blocks, footer = split_top_blocks(text)

    moved, kept = 0, []
    for b in blocks:
        if b.startswith("(gr_line") or b.startswith("(gr_arc"):
            if '(layer "Edge.Cuts")' in b:
                continue  # drop old outline
        if b.startswith("(footprint"):
            um = re.search(r'\(uuid "([^"]+)"\)', b)
            if um and um.group(1) in uuid_pos:
                x, y = uuid_pos[um.group(1)]
                b = set_position(b, x, y)
                moved += 1
                kept.append(b)
                continue
            m = re.search(r'\(property "Reference" "([^"]+)"', b)
            if m and m.group(1) in pos:
                x, y = pos[m.group(1)]
                b = set_position(b, x, y)
                moved += 1
        kept.append(b)

    body = "\t" + "\n\t".join(kept) + "\n"
    body += rounded_rect_edges(args.board, CORNER_R, height)
    with open(args.pcb, "w", encoding="utf-8", newline="\n") as f:
        f.write(header + body + footer)
    print(f"moved {moved} footprints; outline set to "
          f"{args.board}x{height}mm r{CORNER_R}")


if __name__ == "__main__":
    main()
