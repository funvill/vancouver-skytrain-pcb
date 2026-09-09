# JLCPCB outputs

Generated from `vancouver-skytrain-pcb.kicad_pcb` / `.kicad_sch` with KiCad 10
`kicad-cli` (see the commands at the bottom). Regenerate after any board change.

| File | Upload as |
|---|---|
| `vancouver-skytrain-pcb-gerbers.zip` | **Gerber file** on the order page — 9 layers (F/B Cu, Paste, Mask, Silk + Edge.Cuts, Protel extensions), Excellon drill `.drl` (PTH + NPTH merged) and the drill map |
| `bom-jlcpcb.csv` | **BOM** on the SMT assembly page — `Comment, Designator, Footprint, LCSC Part #` |
| `cpl-jlcpcb.csv` | **CPL / pick-and-place** — `Designator, Mid X, Mid Y, Layer, Rotation` (mm, KiCad position-file convention) |

Assembly covers the **68 WS2812B LEDs** (C5349954, top side) and the **8 × 10 µF
0402 capacitors** (C52923). Everything else is not placed by JLC:

- **SW1–SW4** are DNP in the schematic.
- **U1** (Seeed XIAO) is a module soldered by hand.
- Test points and mounting holes have no part.

`pos-raw.csv` and `bom-raw.csv` are the untouched `kicad-cli` outputs the two
JLC files were derived from.

**Check on the JLC page before ordering:** the LED rotation. JLC's part
library orientation for C5349954 may differ from the KiCad footprint's by a
constant; the placement preview shows pin 1 — if every LED is off by the same
angle, correct the `Rotation` column by that constant (all LEDs share the
same footprint, so one offset fixes all 68).

Board: 200 × 109 mm, 2 layers, ENIG recommended (the exposed-copper water is
the artwork — HASL works but reads silver), any soldermask colour; the design
was previewed in dark green with white silkscreen.

```
kicad-cli pcb export gerbers vancouver-skytrain-pcb.kicad_pcb -o jlcpcb/gerbers/ \
    -l F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts \
    --subtract-soldermask --no-x2 --no-netlist --check-zones
kicad-cli pcb export drill vancouver-skytrain-pcb.kicad_pcb -o jlcpcb/gerbers/ \
    --format excellon --excellon-units mm --generate-map --map-format gerberx2
kicad-cli pcb export pos vancouver-skytrain-pcb.kicad_pcb -o jlcpcb/pos-raw.csv \
    --format csv --units mm --side both --exclude-dnp
kicad-cli sch export bom vancouver-skytrain-pcb.kicad_sch -o jlcpcb/bom-raw.csv \
    --fields "Reference,Value,Footprint,LCSC Part,LCSC,DNP" --group-by "Value,Footprint,LCSC Part,LCSC" --exclude-dnp
python ../tools/make_jlcpcb.py      # -> bom-jlcpcb.csv, cpl-jlcpcb.csv, gerbers zip
```
