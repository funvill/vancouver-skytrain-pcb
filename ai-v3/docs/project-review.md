# Project Review — state as of 2026-08-30

Review of the repository (`vancouver-skytrain-pcb`) before starting version 3.

## Repository layout

```
v1/       Shipped first version (Teardown 2024 era). Hardware + firmware + inputs.
v2/       In-progress second version. Hardware + input SVGs. No firmware folder.
ai-v3/    New — empty except for these docs.
```

Uncommitted work: `v2/input/map3.svg` has significant local changes (+460 lines) that are
not committed. This appears to be the in-progress **150 × 150 mm square iconic map**
drawing and is directly relevant to v3 — it should be committed (or moved into `ai-v3/input/`)
before it gets lost.

---

## V1 — shipped board

**Hardware** (`v1/hardware/vancouver-skytrain-pcb/`, KiCad 8):

- Realistic/geographic map style ("natural"), rounded-rectangle board.
- **127 × XL-1010RGBC-WS2812B** (1.0 × 1.0 mm addressable RGB, LCSC C5349953) — one LED
  *per station per travel direction* (e.g. "Waterfront north" and "Waterfront south" are
  separate LEDs), which is why the count is roughly double the station count. Index 126 is
  the SeaBus.
- **On-board controller: ESP32-WROOM-32E** with 3.3 V LDO (UR133AG), a **74AHC1G125**
  buffer used as the 5 V level shifter for the LED data line, reset/boot buttons, Phoenix
  screw-terminal power input, and a programming header.
- 136 × 1 µF 0402 decoupling caps — essentially one per LED.
- Fun detail worth keeping: 126 test points shaped like bugs, one per LED.

**Firmware** (`v1/firmware/vancouver-skytrain/`, PlatformIO + FastLED):

- Demo mode written for Teardown 2024: multiple "trains" per line advance station-by-station
  with fading, per-line speeds. Lines covered: Expo (both directions, both branches),
  Millennium (both directions, **already includes the six Broadway Extension stations**
  through Arbutus), Canada Line (both directions, both branches), SeaBus.
- Note: `platformio.ini` targets **Raspberry Pi Pico** (`board = pico`), not the ESP32 that
  is on the v1 board. So the firmware in the repo as-is was last built for an RP2040 — this
  is actually convenient for v3 if a XIAO RP2040 is used (same chip family, same FastLED
  setup, just change the board to `seeed_xiao_rp2040`).
- Hard-coded LED-index-to-station tables. `NUM_LEDS = 130`, brightness capped at 32/255.

**What v1 proves:** the svg2shenzhen art pipeline works, the WS2812B chain at ~127 LEDs
works, the demo animation works, and JLC production files (BOM/CPL/gerbers) were generated
successfully.

---

## V2 — in progress

**Hardware** (`v2/hardware/`, KiCad):

- Board outline: **100 × 82.9 mm** rounded rectangle (not square).
- **68 × XL-1615RGBC-WS2812B-1** (1.6 × 1.5 mm, LCSC C5349954) placed — the larger 1615
  package instead of v1's tiny 1010. One LED **per station** this time (68 ≈ 67 unique
  future-network stations + SeaBus — see [station-list.md](station-list.md)).
- **Seeed Studio XIAO RP2040 footprint (SMD variant) already placed on the back (B.Cu)** —
  v2 already adopted the "no on-board controller, XIAO on the back" architecture that v3
  wants. Local libraries exist for XIAO RP2040 and SAMD21, in both DIP and SMD variants.
- 4 push buttons (C318884), 7 × 0402 caps, 5 test points, logos.
- Schematic exists (`vancouver-skytrain-pcb.kicad_sch`).
- Last commit: "part placement" (Nov 2025). No routing/production files yet, no firmware
  folder.

**Inputs** (`v2/input/`):

- `transitmap.svg` — stylized iconic map with 68 station circles (novelty styling, "$0.25"
  fare marks, "VANCOUVER" title).
- `map3.svg` — **150 × 150 mm square** drawing with proper svg2shenzhen layers
  (`Edge.Cuts`, `F.Cu`, `F.Mask`, `F.SilkS`, `B.SilkS`) plus a `station.names` layer, 68
  station markers. **Uncommitted local changes.** This is effectively the starting point
  for v3's artwork.

**What's missing in v2:** power/decoupling design is thin (7 caps for 68 LEDs vs. one-per-LED
in v1), no level-shifter decision recorded, board is not square, no routing, no firmware, and
the newest map work is uncommitted.

---

## Key observations going into v3

1. **v2 already made the two big architectural decisions v3 asks for** — one LED per
   station and a XIAO footprint on the back. v3 is best treated as *finishing v2 on a
   smaller square outline*, not a from-scratch redesign.
2. **The LED part decision is effectively made**: XL-1615RGBC-WS2812B-1 (C5349954), with
   library, 3D model, and 68 placements already in v2. "Same LEDs" should mean this part.
   (v1's 1010 part is fiddlier to hand-rework and gains nothing here.)
3. **The station data already exists twice** — in v1 firmware tables and in the v2 SVG
   markers — but nowhere as a single authoritative list. v3 should create one (see
   [station-list.md](station-list.md)) and generate both the firmware table and the LED
   placement from it.
4. **The firmware is 90 % reusable.** Change the board target to the XIAO, drop from
   two-LEDs-per-station to one, renumber the index tables, and the Teardown demo runs on v3.
5. **Two known electrical gaps to close** (both solved in v1, dropped in v2): LED data-line
   level shifting from a 3.3 V microcontroller to 5 V LEDs, and per-LED (or per-group)
   decoupling.
