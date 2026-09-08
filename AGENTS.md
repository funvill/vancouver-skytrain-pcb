# Instructions for AI agents working in this repository

This repo is a PCB that is a transit map (Vancouver SkyTrain, one LED per
station). Version 3 lives in `ai-v3/` and is **generated**: the KiCad board
is produced from `ai-v3/input/vancouver.json` by the scripts in
`ai-v3/tools/`. Read this before touching anything under `ai-v3/`.

## The one rule that matters

**Never run `export_art.py` on a board that may contain hand edits without
running `import_labels.py` first.** The board's labels are edited by hand in
KiCad; the exporter regenerates every label from the data file and will
silently destroy those edits. The safe sequence is always:

```
python import_labels.py ../input/vancouver.json ../hardware/vancouver-skytrain-pcb.kicad_pcb   # board -> data
python export_art.py    ../input/vancouver.json ../hardware/vancouver-skytrain-pcb.kicad_pcb --scale 2.0   # data -> board
```

If the board file's header shows a newer `generator_version` than the last
commit, or its `art-manifest.json` count differs from the art on the board,
a human has been in it: import first, and take a backup
(`ai-v3/hardware/backups/`) before regenerating.

## Layout of `ai-v3/`

| Path | Role |
|---|---|
| `input/vancouver.json` | **Single source of truth**: lines, stations (canvas x/y, `label`, `wrap`), extras (SeaBus), `geo` (water polygons, silk/copper lines), `annotations` (copper text), `chain` (LED order), `canvas_mm` / `canvas_h_mm` / `board_scale`, `suppressed_art` |
| `input/geo_fwa.py` | Land / water from the BC Freshwater Atlas (cached WFS responses in `input/osm/`). `python geo_fwa.py` renders a geography-only preview |
| `input/build_from_fwa.py` | Builds `vancouver.json`: geography, OSM station positions, pitch spreading, LED clearance disks, UBC boundary, copper city labels, wordmark. Preserves labels and `suppressed_art` |
| `input/osm_station_latlon.json` | Station lat/lon (OSM nodes + hand entries for stations under construction) |
| `input/build_from_osm.py`, `build_from_v1.py`, `build_vancouver_json.py` | Superseded builders, kept for history — do not use |
| `tools/citymap.py` | Data model and geometry helpers (label boxes, leaders, `prepared_geo` keepouts, collision primitives) |
| `tools/check_fit.py` | Collision checker (labels vs labels / pads / routes / leaders / furniture / annotations / water) |
| `tools/auto_label.py` | Label optimiser: greedy pass then simulated annealing over `candidates()` |
| `tools/preview_map.py` | Board-accurate matplotlib PNG of the data file (use this, not KiCad, while iterating) |
| `tools/export_placement.py` | `leds.csv` + `firmware_tables.h` from the chain |
| `tools/reposition_board.py` | Moves LED/XIAO/button footprints, rewrites the board outline (`--board W --height H`) |
| `tools/export_art.py` | Writes water (F.Cu + F.Mask), routes, rings, labels, leaders, copper text/lines into the `.kicad_pcb`; idempotent via the uuid→key manifest; honours `suppressed_art` |
| `tools/import_labels.py` | Reads hand edits back from the board (see above) |
| `tools/render_board.py` | `kicad-cli pcb render` top/bottom PNGs, newest installed KiCad |
| `tools/test_vancouver_data.py` | Hard checks: LED count (68), chain integrity, 2.5 mm pitch in board mm, margins |
| `hardware/` | The KiCad project; `README.md` there has the fab-side details |
| `test-results/` | Rendered previews and the last DRC report (`drc.json`) |

## Conventions the scripts rely on

- **Units.** `vancouver.json` coordinates are canvas units; board mm =
  canvas × `board_scale` (2.0 for the 200 × 109 mm board). Label `dx`/`dy`
  and all `LABEL_*` constants are board mm. Text height is
  `citymap.TEXT_H` (1.1 mm) — the one place it is set.
- **Deterministic uuids.** Every art block's uuid is `uuid5(namespace, key)`
  with keys like `label:<station>`, `leader:<station>`,
  `annotation:<i>:<text>:<layer>`, `line:<name>:<seg>:<layer>:<dash>`. The
  importer, the manifest and `suppressed_art` all depend on them; never
  change the key scheme without migrating the manifest.
- **Labels.** `label = {angle, anchor, dx, dy, leader?, short?}`; angle is
  clockwise-positive in the data (the exporter writes `-angle` to KiCad),
  kept in `[-90, 90]` because KiCad renders other angles upside-down;
  `anchor` is `start` / `end` / `center`. `wrap` on a station is `false`,
  or a list of lines. Long names wrap at the en-dash by default
  (`citymap.display_lines`).
- **Copper art** is a filled polygon on F.Cu **and** the same on F.Mask
  (soldermask opening → bare copper). Copper must keep 0.4 mm from the
  board edge (`citymap.EDGE_MARGIN`, corner-aware) and 2.2 mm from every
  LED (clearance disks in the builder plus `prepared_geo` repel).
- **LED pitch floor is 3.3 mm** (`build_from_fwa.MIN_PITCH`): LED
  footprints rotate to aim DOUT at the next LED and diagonal neighbours'
  pads violate 0.2 mm clearance below that.
- **Dashed lines are real segments.** KiCad's stroke `type dash` is an
  editor hint that does not survive to fab/render; `export_art.dash_points`
  builds dashes from short solid lines.

## Verifying a change

Run, in this order, and report the results faithfully:

```
python test_vancouver_data.py                                   # must PASS
python check_fit.py ../input/vancouver.json --scale 2.0 -v      # label-geo is acceptable; anything else is a real overlap
python export_art.py ... ; python export_art.py ...             # second run must report the same counts (idempotent)
grep -o 'uuid "[^"]*"' ../hardware/*.kicad_pcb | sort | uniq -d | wc -l   # must be 0
kicad-cli pcb drc ../hardware/vancouver-skytrain-pcb.kicad_pcb -o ../test-results/drc.json --format json --severity-error --severity-warning
python render_board.py ../hardware/vancouver-skytrain-pcb.kicad_pcb ../test-results
```

In the DRC report, `clearance`, `copper_edge_clearance`, `shorting_items`
and `courtyards_overlap` must be zero. `silk_over_copper`, `silk_overlap`,
`solder_mask_bridge`, `lib_footprint_mismatch`, `text_height` and
`unconnected_items` are expected for this exposed-copper-art board and
are documented in `hardware/README.md`.

Before declaring a visual change done, look at the render (or
`preview_map.py` output) — the checkers model boxes, not what the eye
sees.

## Geography and station data

Use authoritative polygon sources; do not trace pictures or schematic
maps. The current sources and why the earlier ones were dropped are in
`ai-v3/input/README.md` and [lessons-learned.md](lessons-learned.md).
The frame (lat/lon box) and board size live at the top of
`input/geo_fwa.py`.

## Things not to do

- Do not edit `hardware/vancouver-skytrain-pcb.kicad_pcb` art by script
  except through `export_art.py`.
- Do not "fix" station positions by hand in the data — change the source
  (`osm_station_latlon.json`) or the spreading rules in the builder.
- Do not commit a regenerated board together with a data file it was not
  generated from; run the import/export pair and the verification above
  first.
- Do not use the 9.0 `kicad-cli` on a board saved by KiCad 10 — it fails
  with "Failed to load board".
