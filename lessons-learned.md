# Lessons learned — building a transit-map LED PCB

Collected while building v3 of the Vancouver SkyTrain board. Written for
the next board of this kind (another city, another network), so each
lesson says what to do, not just what went wrong.

## 1. Get the landmass right first, on its own, before anything touches the PCB

The single biggest time sink of this project was geography. Five
successive sources were tried before the shape was right:

| Attempt | Source | Why it failed |
|---|---|---|
| 1 | Hand-authored polygons "resembling" Vancouver | Invented coastline; every review found something wrong |
| 2 | TransLink's schematic network map (PDF, vector-traced) | A schematic is not a map: its page is 1.26:1 where the region is 2:1, so everything south of Broadway was stretched and the Fraser became a 45° band; it also draws no coastline where it doesn't need one, so "the left edge should end in water" had no data behind it |
| 3 | The v1 project's hand-drawn "natural" map | Better shape, but a hand drawing: squeezed north–south, station layout not geographic, and it had to be registered to the board by fitting dots in a PNG |
| 4 | OpenStreetMap coastline via Overpass | Correct where it exists — but in this region OSM's `natural=coastline` stops at Burrard Inlet; the Fraser's arms are `natural=water` riverbank polygons that were never loaded, so Sea Island, Lulu Island and the whole estuary collapsed into land |
| 5 | **BC Freshwater Atlas (provincial 1:20k hydrography, WFS)** | Worked first time |

What made #5 work is worth generalising:

- **Prefer sources that give polygons, not lines.** Assembling coastline
  *lines* into land/sea faces (polygonize + orientation votes) is where
  the OSM attempt went wrong. The FWA gives land (watershed groups end at
  the coast → sea = frame − land), rivers and lakes all as polygons; there
  was nothing to assemble.
- **Prefer the national / provincial mapping agency over crowd-sourced
  data for water.** Look for a WFS with a bbox parameter (BC:
  `openmaps.gov.bc.ca/geo/pub/wfs`; most provinces/states/countries have
  an equivalent). Cache the raw responses in the repo so the build runs
  offline and is reproducible.
- **Make a standalone geography render** (`geo_fwa.py`) and get it
  approved before wiring it into the board pipeline. Iterating on the
  shape through KiCad renders costs minutes per round; matplotlib costs
  seconds.
- **Simplify deliberately, not by accident.** A morphological open/close
  (`buffer(-d).buffer(2d).buffer(-d)`) plus `simplify()` removes nooks;
  filling river islands below a size threshold and dropping bay tips that
  are mostly outside the frame keeps the picture clean. Keep lakes by a
  *name whitelist* — an area threshold lets 10 ha ponds in.
- **Check the obvious landmarks by eye**: the airport island, the river
  reaching the sea, the big lakes. Every one of those was missing at some
  point and no checker caught it; a human did.

## 2. Use real station positions, then bend them only where physics demands

Station positions came, in order, from a schematic, a hand drawing and
finally OSM nodes (`railway=station` + `station=subway`). Real positions
put stations on the correct side of rivers automatically — "Surrey
Central is in the water" is a symptom of a bad source, not something to
patch.

The only justified distortion is the LED pitch: downtown stations are
~500 m apart, which is 1.6 mm at 3.1 mm/km. Spread them along their own
line direction, then run a global pairwise separation, and record the
floor as a constant with the reason next to it. **The floor is 3.3 mm,
not the 2.5 mm the package suggests**: LED footprints rotate to aim DOUT
at the next LED, and two diagonal neighbours' pads overlap at 2.8 mm.
Found by DRC after the layout looked fine.

## 3. Size the board to the map's aspect, not the other way round

A square board for a 2:1 region wastes half the area and pushes the map
scale down until labels stop fitting. Decide the frame (lat/lon box)
first, derive the board size from it at the largest width the fab and
budget allow, and treat "leave a blank band" as a warning sign. Going
from 150 mm square to 200 × 109 mm raised the scale 40 % and solved more
label problems than any algorithm did.

## 4. Labels: the tight cluster decides everything — plan for it

Downtown (six stations inside 1 km, three lines crossing) is where every
labelling scheme broke. What eventually held:

- One shared text height (1.1 mm, 0.14 mm stroke — a 1:8 ratio keeps the
  stroke font's counters open), a fixed standoff from the LED, two-line
  wrapping at the name's en-dash instead of abbreviations, a "beside the
  line" candidate so labels can run along a corridor, and leader lines
  as a last resort.
- A checker that models everything on the board — other labels with a
  breathing gap, pads (own and others'), routes including the label's
  own segment beyond the standoff, leaders vs everything, silk furniture,
  copper text — because every unmodelled thing became a real overlap.
- **Greedy placement does not converge in a cluster**; a repair loop
  cycled forever. Simulated annealing over all labels found joint layouts
  the greedy pass couldn't, and even that left a handful for a human.
  Budget for a hand pass and make it round-trip safe (next lesson).
- Some things are not label problems: "Vancouver City Centre" and
  "Granville" are 300 m apart; no layout algorithm fixes that, a bigger
  board does.

## 5. Make hand edits survive regeneration — deterministic ids + an importer

The generated board is edited by hand in KiCad; the generator regenerates
it. Without a round trip, one of them always loses. What worked:

- Every generated item gets a **deterministic uuid** (`uuid5(namespace,
  key)`, keys like `label:waterfront`), and the exporter keeps a manifest
  of uuid → key so it can remove exactly what it wrote last time
  (idempotent regeneration, verified by running it twice and checking for
  duplicate uuids).
- An **importer** finds each item on the board by uuid and writes the
  human's changes back into the data (position, rotation, justification,
  text, deleted leaders). Things the human *deleted* are recorded as a
  `suppressed_art` list the exporter honours.
- Prove it with an import → export comparison on the real board: 0 of 99
  text items differing is the bar.

And the mistake that made this urgent: the user had started editing in
KiCad while the generator was still being run. `git add` swept their
edits into a commit, a regeneration overwrote them on disk, and a
"refresh the backup" step overwrote the backup too. Git had the edits.
**Take the backup before the first regeneration, never overwrite a backup,
and tag the commit.**

## 6. Model the fab's reality, not the editor's

- KiCad's stroke `type dash` line style is an **editor display hint**; it
  does not survive to gerbers, SVG export or 3D render. Draw dashes as
  real short segments.
- Text angles outside [−90°, 90°] render upside-down; rotation is rigid.
- KiCad's bold stroke font is ~10 % wider than a 0.85 × size-per-character
  estimate; the wordmark walked into a river because of it. Measure once
  from a render and put the factor in the code.
- Bare-copper "water" needs an F.Cu polygon **and** the same polygon on
  F.Mask; keep it 0.4 mm from the edge (and inside the corner radius) and
  ≥ 2 mm from every pad — carve clearance disks in the data, and repel
  edges again at export time. A real coastline puts stations *inside*
  water (ferry terminals, river banks); nudge those onto land.
- `silk_over_copper`, `silk_overlap` and `solder_mask_bridge` DRC warnings
  are the price of this aesthetic; `clearance`, `copper_edge_clearance`
  and `shorting_items` are not negotiable. Say which is which in the
  README so the next person doesn't panic (or ignore the wrong one).
- A newer KiCad silently upgrades the file format on save; an older
  `kicad-cli` then fails with "Failed to load board". Pin the CLI to the
  newest install.

## 7. Process lessons

- **Verify against the source, not against the previous fix.** Two rounds
  were spent adding a "missing" peninsula that the source map never
  showed. Re-read the source before patching a mismatch.
- **Sub-agent design critiques were worth it**: an independent
  composition / cartography / labelling review produced the list that
  drove the whole redesign (water to the edge, thin uniform routes,
  station rings, wordmark on land, drop the legend).
- **Keep every generated intermediate in the repo** (cached WFS/Overpass
  responses, station tables, preview PNGs). Builds stay reproducible and
  reviewers can see what changed.
- **Write the "what's wrong with this picture" checklist down**: river
  reaches the sea, airport island present, big lakes present, all
  stations on land, no label on bare copper, wordmark on land, nothing
  in the corner radius. Run it by eye on every render.
- **Automate the screenshot.** `kicad-cli pcb render` (and the matplotlib
  preview) after every change meant problems were seen the same minute
  they were made.

## 8. Reusing this for another city

The pipeline is city-agnostic below `vancouver.json`. For a new city you
need: (a) a lat/lon frame and board width in `geo_fwa.py`'s successor,
(b) polygon hydrography for the region (agency WFS first, OSM
`natural=water` second), (c) station lat/lon (OSM nodes, checked by eye),
(d) the line definitions and LED chain order, (e) a pitch floor for the
LED package and footprint rotation you use. Then: geography preview →
approve → data build → `auto_label` → `preview_map` → hand pass in KiCad
→ `import_labels` → verification list → render.
