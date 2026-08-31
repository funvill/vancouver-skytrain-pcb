# V3 Recommendations

Target: a smaller **square** board, iconic map, one WS2812B per station (all new stations
included), no controller populated — a **XIAO footprint on the back** instead.

## 1. Treat v3 as "v2 finished on a square outline"

v2 already has the right architecture (68 LEDs, XIAO-on-back, iconic map). Recommended
starting move:

1. Create `ai-v3/hardware/` by copying the v2 KiCad project, and `ai-v3/input/` by moving
   `v2/input/map3.svg` there (commit it first — it currently has uncommitted changes).
2. Keep the v2 local libraries as-is: `C5349954-led` (XL-1615RGBC-WS2812B-1),
   `Seeed Studio XIAO`, `C318884-button`.

## 2. Board size — decide first, everything else follows

`map3.svg` is drawn at 150 × 150 mm; v2's board was 100 × 82.9 mm. Options:

| Size | Pros | Cons |
|------|------|------|
| **100 × 100 mm (recommended)** | JLCPCB/PCBWay cheap-prototype sweet spot; noticeably smaller than v1; iconic map with 68 stations fits comfortably | Station-name silkscreen gets small (~1 mm text) — still readable but near the limit |
| 150 × 150 mm | map3.svg needs no rescaling; roomy labels | Not really "smaller"; higher fab cost |
| 70–80 mm square | Very cute, coaster-sized | 68 × 1615 LEDs + names get very tight; Expo/Millennium shared corridor gets congested; probably drop station names |

Recommendation: **100 × 100 mm**, scale map3.svg down 2/3 in Inkscape (svg2shenzhen carries
mm through faithfully). Verify minimum silkscreen text height (JLC: ≥ 1 mm height,
≥ 0.15 mm stroke) after scaling; if names don't fit, keep names for interchanges/termini
only and put the full legend on the back silkscreen.

## 3. XIAO footprint on the back

- Use the **XIAO-*-SMD variant** (castellated pads, module lies flat) on `B.Cu`, as v2
  already does. Also add the two **B.Cu keep-out / courtyard** considerations:
  - Nothing on the front side directly opposite the module if you ever want the DIP
    (through-hole header) variant as a fallback — consider placing both footprints
    overlapped (SMD pads + DIP holes), a common trick that supports either mounting.
- **Pin budget is tiny and that's fine**: 5 V, GND, one data pin, plus 2–4 GPIOs for
  buttons. All XIAO family members pin out 5V/GND/3V3 identically, so the board stays
  controller-agnostic (RP2040, ESP32-C3 for WiFi clock/real-time data, nRF52840…).
- Orient the module so the **USB-C connector faces (and slightly overhangs or sits at) the
  board edge** — this is the power inlet and programming port. The XIAO's reset/boot
  buttons face away from the board when surface-mounted, so they stay accessible, but add
  labelled test points or two small pads for RESET/BOOT anyway.
- If the board will hang on a wall, USB-C at the **bottom edge** hides the cable best.

## 4. Electrical design (close the two v2 gaps)

- **Level shifting.** The XIAO drives data at 3.3 V; WS2812B at 5 V wants VIH ≥ 0.7 × VDD
  = 3.5 V. It often works anyway, but don't ship marginal: reuse v1's proven
  **74AHC1G125** (SOT-23-5, C23654) powered at 5 V as a data buffer. It costs pennies and
  removes the #1 flicker risk.
- **Decoupling.** 7 caps for 68 LEDs (v2) is too thin. The XL-1615 is small; a pragmatic
  middle ground is **one 100 nF–1 µF 0402 per 2–4 LEDs** distributed along the chain, plus
  **2 × 22 µF bulk** near the XIAO 5 V feed. (v1 used one 1 µF per LED — fine too, but
  doubles placement count.)
- **Power budget.** 68 LEDs × 60 mA worst case ≈ 4 A — far beyond USB. Not a hardware
  problem if firmware caps it: keep v1's brightness limit and add FastLED's
  `setMaxPowerInVoltsAndMilliamps(5, 1500)`. At demo brightness (32/255) the whole board
  draws well under 500 mA. Make 5 V and GND pours wide (front pour + back pour) since the
  chain snakes the whole board.
- **Series resistor** (~300 Ω) on the data line at the buffer output, and keep v1's
  bug-shaped test points if there's room — they were a signature detail.

## 5. LED chain and station data

- **One authoritative station list** drives everything — see
  [station-list.md](station-list.md): 67 stations + SeaBus = **68 LEDs**, matching the 68
  markers already in map3.svg/v2.
- Chain order recommendation: route the data chain **line by line** (Expo including both
  branches → Millennium → Canada Line including both branches → SeaBus) so firmware line
  tables are contiguous ranges instead of scattered indices. Interchange stations get **one
  LED, owned by one line**, and the other line's table simply references that index (v1's
  firmware already works this way for Production Way/Lougheed).
- Mark future stations (Broadway Extension opens ~2027, Surrey–Langley ~2029, already
  under construction) with a distinct silkscreen ring so the map is honest today and
  correct later. Firmware can skip/dim them in "current network" mode.

## 6. Artwork / fab finish

- Keep the svg2shenzhen pipeline from v1/v2 (`Edge.Cuts`, `F.Cu`, `F.Mask`, `F.SilkS`,
  `B.SilkS` layers in map3.svg are already set up for it).
- Silkscreen is single-colour, so line identity must come from geometry: the classic trick
  (used in v1) is drawing the route lines as **exposed copper (F.Cu + F.Mask openings)** so
  they render as gold/silver traces, with silkscreen for names and water/background. With
  ENIG + black soldermask this looks excellent. Optional: order variants with different
  soldermask colours per batch.
- Put the credits, LED index legend, and firmware URL/QR code on the back silkscreen around
  the XIAO.

## 7. Firmware

- Copy `v1/firmware` to `ai-v3/firmware`, change `platformio.ini` to
  `board = seeed_xiao_rp2040` (it already targets the `raspberrypi` platform, so this is a
  one-line change), set `NUM_LEDS = 68`, and regenerate the index tables from the station
  list. The two-directional-LEDs concept collapses to one index per station; keep the
  multi-train animation by fading a train through the single per-station LED.
- Wire the 2–4 buttons (v2 already placed 4) to mode/brightness/speed/next-line, active-low
  with internal pull-ups — no external resistors needed.
- Generate the station table from `station-list.md` (or a CSV) with a small script rather
  than hand-numbering 68 entries again.

## 8. Process / repo hygiene

1. **Commit `v2/input/map3.svg` now** (its 460-line local change is the newest map work).
2. Structure `ai-v3/` as `hardware/`, `firmware/`, `input/`, `docs/` (matching v1).
3. Before ordering: run DRC, generate JLC BOM/CPL like v1's `production/` folder, and
   sanity-check the LED chain order visually (KiCad 8 can highlight the DIN/DOUT net path).
4. Order a **5-board prototype**; hand-solder one XIAO to validate before committing to a
   panel run.

## Open questions (decide before layout)

1. **Board size** — 100 × 100 mm recommended; confirm.
2. **Station names on front?** At 100 mm they're marginal; interchanges-only is the safe call.
3. **Include SeaBus LED** (v1 had it; the 68th marker suggests v2 kept it) — keep?
4. **Buttons: how many and which face?** Back-side buttons keep the front clean but are
   awkward wall-mounted; edge-adjacent front buttons are friendlier.
5. **Mounting**: M3 holes in corners, or a single keyhole slot on the back for wall hanging?
6. **Which XIAO ships as the "reference" module** — RP2040 (cheapest, matches existing
   firmware) or ESP32-C3 (enables live TransLink data / clock modes later)? The footprint
   supports both; the choice only affects documentation and default firmware.
