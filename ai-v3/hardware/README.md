# v3 Hardware (KiCad)

Copied from the v2 project, then rewritten by the pipeline:

- **Board outline**: 150 × 150 mm, 5 mm rounded corners (was v2's 100 × 82.9 mm)
- **LED1–LED68**: moved to the station positions in `leds.csv` (generated from
  `ai-v3/input/vancouver.json` by `tools/export_placement.py`). LED index =
  ref − 1 = position in the data chain; LED1 is SeaBus, first after the shifter.
- **U1 (XIAO, back)**: centered at (75, 75); **SW1–SW4** flank it. All DNP.
- v2's stale svg2shenzhen art footprints were removed.
- **Station labels + land/water art** (F.SilkS text, F.Cu/F.Mask water,
  F.SilkS land outlines) generated directly into the board by
  `tools/export_art.py` — no Inkscape/svg2shenzhen step needed. See below.
- The coastline in `ai-v3/input/vancouver.json`'s `geo` list is hand-authored
  to resemble Vancouver's real geography (Burrard Inlet with the Port Moody
  arm, the downtown peninsula, False Creek between the Canada Line and
  Broadway corridor, the Fraser River's islands) at the level of detail v1's
  natural map used — not the coarse first-pass shapes from earlier in this
  project. Render `tools/render_board.py` output before touching `geo`
  again, so you're comparing against the current look, not an old shape.

**Render the board as images** (KiCad 9's built-in 3D renderer, top-down):

```
python render_board.py ../hardware/vancouver-skytrain-pcb.kicad_pcb ../test-results
```

Writes `board-top.png` and `board-bottom.png`. Pass `--kicad-cli` if
`kicad-cli.exe` isn't at the default `C:\Program Files\KiCad\9.0\bin\`.

Regenerate placements after any layout change:

```
cd ../tools
python export_placement.py ../input/vancouver.json ../hardware --scale 1.5
python reposition_board.py ../hardware/vancouver-skytrain-pcb.kicad_pcb ../hardware/leds.csv --board 150
python export_art.py ../input/vancouver.json ../hardware/vancouver-skytrain-pcb.kicad_pcb --scale 1.5
```

Run them in that order (placement first, art second — art positions itself
relative to the current LED footprint locations). `export_art.py` is
idempotent: it tracks every block it writes in
`vancouver-skytrain-pcb.kicad_pcb.art-manifest.json` and removes them before
writing fresh ones, so re-running after an edit to `vancouver.json` never
leaves stale or duplicated art behind.

## Station labels, route lines, and land/water art

`export_art.py` writes native KiCad graphics directly into the `.kicad_pcb`
(not through svg2shenzhen — that path is for hand-drawn art; ours is
generated straight from the same station/geo data as everything else),
styled after TransLink's own "Future Rapid Transit Network" map — one water
colour, filled parks, labelled rivers/municipalities, and a distinct look
for future/under-construction line segments:

- **Route lines** (`route_blocks`) — every line segment from
  `vancouver.json`'s `lines` as an F.SilkS `gr_line`, 1.0 mm wide. A segment
  with either endpoint `future: true` (Broadway Extension, Surrey–Langley
  Extension) is drawn as real **dashed segments** (`dash_points()`) instead
  of one solid line — matching the reference map's "future line" styling.
  Important: KiCad's `(stroke (type dash))` line-*style* property is an
  **editor display hint only** — it does not survive to plotted/fab output
  (SVG export, 3D render, gerbers all flatten it to solid), confirmed by
  testing both here. A genuinely dashed silkscreen line has to be built
  from literal short solid segments with real gaps, which is what
  `dash_points()` does.
- **Station names** — `gr_text` on F.SilkS, same position/rotation math as
  the SVG preview (`citymap.label_box`), 0.15 mm stroke at 1.2 mm. Names
  longer than 13 characters are set on **two lines** (split at the
  official en-dash, else at the middle space — `citymap.display_lines`;
  override per station with `"wrap": [...]` or `"wrap": false`), so the
  abbreviated `short` forms are no longer used on the board. Every label
  anchor sits `LABEL_STANDOFF` (1.9 mm) from the LED centre, clear of the
  pad and ring. A label with `"leader": true` is floated out to its dx/dy
  and joined to the LED by a 0.15 mm hairline — `auto_label.py` uses that
  as a last resort for stations with no clean spot beside the pad, and
  prefers one angle per corridor so the eye tracks a single direction.
- **Station rings** (`station_ring_blocks`) — a silk ring behind every LED
  (r 1.25) so the station reads as circle-on-line; interchanges (`
  "interchange": true`) get a heavier r 1.55 ring. Routes are 1.5 mm.
- **Map furniture** — `geo` entries of `"type": "line"` are plain silk
  polylines with an optional `"dash"` of `dash` / `dot` / `dashdot`
  (SeaBus ferry route, the 49th-parallel border, legend swatches); an
  annotation with `"copper": true` is exposed-copper lettering (F.Cu +
  F.Mask, the gold "VANCOUVER" wordmark from v2).
- **Water** (sea, False Creek, Fraser River) — a filled polygon on **F.Cu**
  with a matching filled polygon on **F.Mask**, so the soldermask opens
  over the copper and it reads as bare copper (gold with ENIG) against the
  black board — the same technique v1 used
  (`v1/input/natrual/natrual/map.kicad_pcb`), generated instead of
  hand-drawn.
- **Land — islands**: thin F.SilkS outline only, no fill (the board
  substrate itself *is* the land, so these just need a boundary).
  **Land — parks**: outline *plus* a 45° diagonal hatch fill
  (`citymap.hatch_fill()`, 1.6 mm spacing) — the single-ink silkscreen
  stand-in for the reference map's solid green park colour. `hatch_fill()`
  is a general scan-line polygon fill (even-odd rule, works on concave
  shapes) so it's reusable for any future city's parks too.
- **Annotations** (`annotation_blocks`) — small F.SilkS text (legend
  labels, CANADA / USA at the border) or copper text (the wordmark). No
  municipality names or water-body labels are printed, by request.

### Station positions and geography: OpenStreetMap

Station positions and `vancouver.json`'s water shapes come from
OpenStreetMap via `../input/build_from_osm.py` — real station nodes, the
real shoreline (smoothed), the Fraser and Pitt rivers, and the large
lakes. The board is **150 × 86.2 mm**, the aspect of the lat/lon frame
(Point Grey → Langley, North Shore → below Langley) at 3.1 mm/km; water
runs to the board edge (0.4 mm copper-to-edge, corners pulled inside
the 5 mm radius) — there is no border. Earlier revisions used
TransLink's schematic PDF and then v1's hand-drawn map; see
`../input/README.md`. Deliberately not literal:

- Runs whose real spacing is under the LED pitch (downtown, Richmond,
  Sea Island, Coquitlam) are spread outward along their own direction,
  then any remaining too-close pair is separated symmetrically. The
  pitch floor is **3.3 mm**: LED footprints rotate to aim DOUT at the
  next LED, and two diagonal neighbours' pads need that to keep 0.2 mm.
- A station the smoothing leaves inside water (a river-bank station) is
  nudged onto land, as the real map shows it; every LED then gets a
  2.2 mm clearance disk carved out of the copper water.
- The "VANCOUVER" wordmark is exposed-copper lettering placed on land
  (Delta), at the first candidate spot clear of water and track.

Routes are one solid 1.0 mm style for every segment, built or not.
- The Broadway Extension and Surrey–Langley Extension aren't on the
  current-network PDF (not built yet), so those 14 stations are
  extrapolated by continuing each real corridor's traced direction and
  spacing from its last real station.
- Every station's label **direction** (which side of the dot the name
  sits on) is hand-tuned in `vancouver.json`, not traced — the PDF gives
  dot positions, not a reusable label layout. Real station spacing is
  tight enough in a few spots (the airport branch, the Coquitlam bend,
  New Westminster/Columbia/22nd Street) that some labels sit close to a
  neighbour's dot or to the water fill; `check_fit.py` calls these out
  as `label-geo` (expected for coastal stations) vs. real overlaps
  (`label-label`/`label-dot`/`label-line`, hand-fixed one at a time).

### Keeping copper art DRC-clean: `citymap.prepared_geo`

A water/land shape sized for the map doesn't know where the LEDs are, so
raw coordinates from `vancouver.json` will happily overlap LED pads,
bridge the board edge, or trip solder-mask-bridge/clearance rules.
`citymap.prepared_geo(city, scale, avoid_pts)` fixes this once, and
`render_map.py`, `check_fit.py`, and `export_art.py` all call it — so the
SVG preview, the label-collision report, and the physical board always
agree:

1. `densify()` — long polygon edges get intermediate vertices (so a strait
   crossing an LED cluster mid-edge, not just at a vertex, still gets
   caught).
2. `repel()` — any vertex within `keepout` of an LED is pushed away from it.
3. `clamp_to_board()` — vertices are kept inset from the board edge (copper
   needs edge clearance even where the art is meant to visually "bleed" to
   the frame, like the coastline running to the top of the board).
4. `simplify()` (open shapes only, e.g. rivers) — collapses the extra
   densify() vertices back down once they're no longer needed, so a long
   straight run doesn't turn into dozens of tiny render segments.

For **rivers** specifically (drawn as a chain of rectangles, one per
polyline segment, since they have width but no fill), `export_art.py`
adds a final per-segment safety check
(`citymap.poly_point_min_dist`, `RIVER_SAFE_FLOOR`): any rectangle that
still ends up too close to an LED after all of the above is *dropped*
rather than emitted un-safe, and the drop is printed, not silent. On this
board the Fraser River crosses the same tight diagonal corridor the Expo
Line's SkyBridge stations occupy, so several of its segments are
intentionally omitted — the gaps read as the river passing under a
bridge, which is accurate. If you widen station spacing or move the river
line, re-run `export_art.py` and check its printed drop list.

**Known cosmetic-only DRC warnings** (verified non-blocking,
`kicad-cli pcb drc`, 2026-08-30): a handful of `silk_overlap` /
`silk_over_copper` warnings where a station label or a park/island
outline crosses the water fill or another silk element (e.g. Aberdeen's
label crossing the Lulu Island outline). These are `warning`-severity
(KiCad reports them as "Local override" candidates) and are the expected
look of a coastal transit map with exposed-copper water — no station near
the water was going to avoid overlapping it. `clearance` and
`copper_edge_clearance` (the categories that would actually risk a fab
reject or a short) are both **0** after the fixes above.

## Still manual (open in KiCad)

1. **Rotate LEDs for chain routing** — `leds.csv` has the suggested rotation
   (DOUT toward the next chain index); the script deliberately does not touch
   rotation because pad angles must be rewritten by KiCad itself.
2. **Verify U1 orientation**: USB-C must face the bottom board edge (Y+).
3. **Schematic**: v2's sheet is still the source. Confirm the 68-LED chain
   order matches `leds.csv`, add the **74AHC1G125** (C23654) data buffer at
   5 V + 330 Ω series R, decoupling (100 nF per 2 LEDs + 2 × 22 µF bulk), and
   re-annotate/re-sync with the board.
4. Route the data chain and power/ground pours (front + back).
5. DRC, then JLCPCB fab outputs (gerbers / BOM / CPL). Board finish: black
   soldermask, white silk, ENIG (so the exposed-copper water reads gold).

Pre-existing, not caused by the above (present since the v2 copy — schematic
has no routing yet): `unconnected_items`, `shorting_items` (unrouted nets),
`lib_footprint_mismatch` (library version drift), `courtyards_overlap`
(U1/button placement), one `text_height` warning on U1's hidden reference
field, and a `solder_mask_bridge` pair on nearly every LED footprint's own
pads (the XL-1615 library footprint's pads sit close together at that
package size — a library fix, not something the map art caused).

Firmware lives in `../firmware` (PlatformIO, XIAO RP2040, builds clean);
its index tables (`include/firmware_tables.h`) are generated by the same
export — regenerate both together.
