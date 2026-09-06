# Input data

- **`vancouver.json`** — the city data file the whole `ai-v3/tools/`
  pipeline reads (schema documented in `../docs/plan.md`).
- **`build_from_osm.py`** — **the current source of station positions and
  geography.** Builds `vancouver.json` from OpenStreetMap: real station
  nodes, the `natural=coastline` ways (land is on the left of a coastline
  way — that's how sea and land are told apart), the Fraser/Pitt river
  centrelines buffered where the coastline stops, and only the large
  named lakes (Burnaby, Deer, Trout, Como, Lost Lagoon…). The shoreline
  is smoothed (morphological open/close + simplify) so it reads clean at
  3 mm/km. The frame is a lat/lon box (Point Grey → past Langley, North
  Shore → below Langley) and the board takes its aspect: **150 × 86.2 mm**,
  water running to the board edge. Raw Overpass responses are cached in
  `osm/` (queries listed at the bottom of the script) so it runs offline.
  Run it, then `../tools/auto_label.py`, then the hardware pipeline with
  `reposition_board.py --board 150 --height 86.2`.
- `build_from_v1.py` — superseded: built the map from the v1 project's
  hand-drawn natural map, kept for reference (its `v1_*.json` inputs too).
- **`skytrain-network-map.pdf`** — TransLink's official current-network
  map. It was the tracing source for an earlier revision (below); its
  schematic page is 1.26:1 where the real region is ~2:1, so everything
  south of Broadway came out stretched and the Fraser turned into a
  45° band — which is why the v1 natural map replaced it.

## (Superseded) How `vancouver.json` was traced from the PDF

Station positions and land/water/park shapes are **not hand-drawn** — they
were extracted from the PDF's actual vector content (text + path data),
not eyeballed from a rendered image. Rerun this pipeline after swapping in
a newer PDF (a future TransLink map revision, or the Broadway/Surrey–Langley
version once it exists):

```
pip install pdfplumber pymupdf shapely   # one-time
python match_stations.py     # words.json + circles.json -> station_coords.json
python build_geo.py          # geo_shapes.json -> geo_canvas.json (water/park polygons)
python build_vancouver_json.py   # writes ../input/vancouver.json
```

1. **`match_stations.py`** — `pdfplumber` extracts every text label's exact
   (x, y); `pymupdf` (`fitz`) extracts every station-dot circle (drawn as a
   small filled circle, colour-coded by line — teal `(0,0.61,0.78)` =
   Canada Line, medium blue `(0,0.37,0.67)` = Expo Line, yellow
   `(1,0.83,0)` = Millennium Line, navy `(0,0.21,0.37)` = an
   interchange/major-hub marker). Each station gets one reliable,
   document-unique anchor word (`ANCHOR` in `match_stations.py`) and is
   matched to its nearest circle. Diagonal/angled labels near line
   junctions (Commercial–Broadway, Lougheed Town Centre, Sapperton, Lake
   City Way, VCC–Clark…) came out as garbled individual characters from
   pdfplumber (the angled text confuses its word-grouping) — those were
   resolved by hand against the known real line topology (station order,
   even spacing along a row/diagonal) instead of by text matching; see
   `build_vancouver_json.py`'s `PDF_XY` table for the final values used.
2. **`build_geo.py`** — the PDF draws land as opaque cream polygons over a
   full-page water-blue background, the opposite of our board (water is
   the explicit exposed-copper shape, land is just the bare board). This
   script extracts every land polygon's vector points, unions them with
   Shapely, and subtracts that union from the page rectangle — the
   remainder *is* the water, matching the PDF exactly, including the
   Fraser's arms and Sea Island / Lulu Island falling out as holes
   automatically (no river/island shape was hand-drawn or guessed).
   Park polygons are extracted the same way and kept separate for the
   hatch-fill treatment.
3. **`build_vancouver_json.py`** — converts every PDF-point coordinate to
   the 0–100 canvas with a uniform affine transform (a fixed margin inset
   + independent-axis scale to fill the square board — the real network
   is wider than it is tall, so this is the one deliberate distortion;
   everything else preserves the source proportions exactly). The Broadway
   Extension and Surrey–Langley Extension stations aren't on this PDF (not
   built yet) — they're extrapolated by continuing each real corridor's
   traced direction and spacing from its last real station, not traced
   from a source.
4. Label **angle/anchor** (which side of the dot the name sits on) still
   has to be tuned per station in `vancouver.json` afterward — the PDF
   trace gives the *dot* position, not a usable label layout, since the
   official map's real labels are hand-placed by a cartographer and
   pdfplumber's per-character extraction for angled ones isn't reliable
   enough to reuse directly. `../tools/auto_label.py` automates this: it
   brute-forces every angle in `[-90, 90]` (angles outside that range
   render the glyphs upside-down/mirrored in KiCad — rotation is rigid,
   there's no auto-flip for readability) crossed with `start`/`end`
   anchor for each station `check_fit.py` flags a real collision on
   (`label-label`/`label-dot`/`label-line` — not `label-geo`, which is
   expected for a station that's genuinely next to water or a park), and
   keeps the option with the fewest collisions. Re-run it after any
   position change; `check_fit.py -v` on its own shows what's left.

`words.json` / `circles.json` / `geo_shapes.json` / `geo_canvas.json` /
`station_coords.json` are the intermediate extraction artifacts (kept for
inspection/debugging) — none of them are hand-authored, and none should be
edited directly; edit `vancouver.json` instead, or rerun the pipeline
against a new PDF.
