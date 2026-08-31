# SkyTrain PCB v3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A 100 × 100 mm (size to be confirmed by the text-fit test) square PCB of the iconic Vancouver SkyTrain map — one WS2812B per station including all future stations, XIAO footprint (DNP) centered on the back with USB-C down, level shifter, SeaBus LED, iconic land/water geometry, white silkscreen on black soldermask.

**Architecture:** A city-agnostic Python pipeline (`ai-v3/tools/`) turns a per-city data file (`ai-v3/input/vancouver.json` — lines, stations, coordinates, geography) into (a) rendered SVG previews with collision/fit reports, (b) svg2shenzhen-ready artwork layers, and (c) LED placement + firmware index tables. The KiCad board consumes the pipeline output. The pipeline is the reusable component for future cities; only the JSON data file is city-specific.

**Tech Stack:** Python 3 (stdlib only — no pip deps, so it runs anywhere), SVG, KiCad 8, svg2shenzhen (Inkscape extension), PlatformIO + FastLED.

## Global Constraints

- Board: square, starting hypothesis **100 × 100 mm**; expand only if the text-fit test proves names don't fit (test heights: 1.0 mm fab minimum, 1.2 mm comfortable).
- Finish: **white silkscreen on black soldermask** (black board). Route lines rendered as silkscreen and/or exposed copper; art must read in white-on-black.
- LEDs: **XL-1615RGBC-WS2812B-1 (LCSC C5349954)**, one per station, plus **1 SeaBus LED** — **68 LEDs total** (67 unique stations + SeaBus).
- Stations: full 2029 network — Expo 32 (incl. 8 Surrey–Langley, ~2029), Millennium 23 (incl. 6 Broadway Extension, ~2027), Canada 17 (incl. Capstan), minus 5 shared interchange stations.
- Controller: **no controller populated**. Seeed **XIAO SMD footprint on the back, DNP, centered, USB-C pointing down** (toward the bottom board edge). Buttons also on back, **DNP**.
- Level shifter: **74AHC1G125** (SOT-23-5, LCSC C23654) on the LED data line, powered at 5 V, as in v1.
- Geography: iconic land/water shapes (Burrard Inlet, downtown peninsula, Fraser River, Sea Island) on the artwork layers.
- Reusability: tools must not hard-code Vancouver anything; all city data lives in the input JSON.

---

## Phase A — Assumption tests (before any board work)

### Task 1: City data schema + Vancouver data file

**Files:**
- Create: `ai-v3/input/vancouver.json`
- Create: `ai-v3/tools/citymap.py` (shared loader/model)
- Test: `ai-v3/tools/test_vancouver_data.py`

**Interfaces:**
- Produces: `citymap.load(path) -> City` where `City` has `.stations` (dict id → Station with `name, short, x, y, future, label` fields), `.lines` (list of Line with `id, name, color, paths` = lists of station ids), `.extras` (SeaBus), `.geo` (water/land polygons), `.canvas_mm`.
- JSON schema (city-agnostic):

```json
{
  "city": "vancouver",
  "canvas_mm": 100,
  "lines": [
    {"id": "expo", "name": "Expo Line", "color": "#005DAA",
     "paths": [["waterfront", "burrard", "..."], ["columbia", "scott-road", "..."]]}
  ],
  "stations": {
    "waterfront": {"name": "Waterfront", "x": 16, "y": 10,
                    "label": {"angle": 0, "anchor": "end"}, "future": false}
  },
  "extras": [{"id": "seabus", "name": "SeaBus", "x": 20, "y": 5}],
  "geo": [{"name": "burrard-inlet", "type": "water", "points": [[0,0], [100,0], "..."]}]
}
```

- [ ] **Step 1: Write failing validation test** (`test_vancouver_data.py`): 68 LEDs total (stations + extras); every path id resolves; the 5 interchange stations appear in ≥ 2 lines but exist once; every consecutive station pair is octilinear (horizontal, vertical, or 45°); all coordinates within canvas with ≥ 3 mm margin; every station has a non-empty name.
- [ ] **Step 2: Run it** — fails (no data file).
- [ ] **Step 3: Author `vancouver.json`** — all 67 stations + SeaBus with iconic octilinear coordinates on a 100 mm canvas, per-station label angle/anchor, `short` names for long stations, geography polygons.
- [ ] **Step 4: Run test — passes.**
- [ ] **Step 5: Commit** (`git -c user.name="SWS-Chipkin" -c user.email="sws-dev@chipkin.com" commit`).

### Task 2: SVG renderer

**Files:**
- Create: `ai-v3/tools/render_map.py`
- Test: rendered output inspected + self-checks in `test_vancouver_data.py` extended

**Interfaces:**
- Consumes: `citymap.load()`.
- Produces: `render(city, scale=1.0, text_h=1.2, use_short=False) -> str (svg)`; CLI `python render_map.py vancouver.json out.svg --scale 1.0 --text 1.2`.
- SVG in mm units: black board rect, water polygons, route polylines (line colors for preview; final art is white), station dots + 1.6 × 1.5 mm LED body outline, rotated labels, XIAO 17.8 × 21 mm outline centered (back-side ghost), board outline.

- [ ] **Step 1:** Implement renderer.
- [ ] **Step 2:** Render at scale 1.0 and view in browser — layout is recognizable as the SkyTrain map, no gross errors.
- [ ] **Step 3:** Commit.

### Task 3: Fit checker (the actual assumption test)

**Files:**
- Create: `ai-v3/tools/check_fit.py`
- Output: `ai-v3/test-results/fit-report.md`, `ai-v3/test-results/map-*.svg`

**Interfaces:**
- Consumes: `citymap.load()`, same geometry code as renderer.
- Produces: `check(city, scale, text_h, use_short) -> FitResult(collisions: list, board_mm: float)`; label boxes modeled as rotated rectangles (char width = 0.7 × height + stroke), collision = label∩label, label∩other-line, label∩other-dot via SAT polygon intersection.

- [ ] **Step 1:** Unit test SAT intersection with two known rects (overlap / no overlap).
- [ ] **Step 2:** Implement checker.
- [ ] **Step 3:** Run the experiment matrix: {100 mm, 120 mm, 135 mm, 150 mm} × {1.0, 1.2 mm text} × {full, short names}. Record collision counts.
- [ ] **Step 4:** Write `fit-report.md` with the matrix, the verdict on 100 mm, and the recommended board size. Render an annotated SVG (collisions highlighted red) for the chosen candidates.
- [ ] **Step 5:** Commit.

### Task 4: Back-side fit check (XIAO + buttons + level shifter)

**Files:**
- Modify: `ai-v3/tools/render_map.py` (back-side view mode)
- Output: `ai-v3/test-results/back-side.svg`

- [ ] **Step 1:** Render back view: XIAO-SMD courtyard (17.8 × 21 mm + 1 mm) centered, USB-C edge toward board bottom, 4 button courtyards (5.1 × 5.1 mm), 74AHC1G125, bulk caps; confirm no conflict with front LED thru-hole-free zone (all SMD, so only via keepouts matter).
- [ ] **Step 2:** Note reset/boot access and USB-C cable clearance in the report.
- [ ] **Step 3:** Commit.

**Decision gate:** present fit-report to the user; board size is locked here.

---

## Phase B — Board (after size is locked)

### Task 5: Pipeline outputs for KiCad

**Files:**
- Create: `ai-v3/tools/export_placement.py` — emits `leds.csv` (ref, x, y, rotation, station id) with chain order = the station-list order; emits `firmware_tables.h` (per-line index arrays) from the same data.
- Create: `ai-v3/tools/export_art.py` — emits svg2shenzhen-layered SVG (`Edge.Cuts`, `F.SilkS` = names + land outlines in white, `F.Mask` openings for copper route lines, `B.SilkS` credits block).
- Test: round-trip check — 68 rows in `leds.csv`, chain neighbors ≤ 25 mm apart (data-line routing sanity).

### Task 6: KiCad project

- Copy v2 KiCad project to `ai-v3/hardware/`; keep local libs (`C5349954-led`, `Seeed Studio XIAO`, `C318884-button`).
- Schematic: 68 LEDs chained, 74AHC1G125 buffer (input from XIAO D-pin, OE tied active, 5 V supply), 330 Ω series R at buffer output, 1 × 100 nF per 2 LEDs + 2 × 22 µF bulk, XIAO symbol (DNP), 4 buttons (DNP) to XIAO GPIOs with no external pull-ups (internal), SeaBus LED last in chain.
- Import `leds.csv` positions (KiCad "Position from file" / pcbnew script), import art via svg2shenzhen, place XIAO centered on B.Cu USB-C down, route 5 V/GND pours front+back, route data chain.
- DRC clean; JLCPCB production files (gerbers, BOM, CPL) with black soldermask + white silk + ENIG selected.

### Task 7: Firmware

- Copy `v1/firmware` → `ai-v3/firmware`; `platformio.ini`: `board = seeed_xiao_rp2040`.
- Replace index tables with generated `firmware_tables.h`; `NUM_LEDS = 68`; add `FastLED.setMaxPowerInVoltsAndMilliamps(5, 1500)`; keep demo animation; buttons on internal pull-ups for mode/brightness.
- Build passes; (bench test after boards arrive).

### Task 8: Reusable-pipeline extraction (after Vancouver ships)

- Move `ai-v3/tools/` to repo-root `tools/` (or its own repo) unchanged; document the JSON schema in `tools/README.md`; prove reuse by drafting a second city data file stub.

## Self-Review notes

- Spec coverage: 100 mm test (Task 3), expansion expectation (Task 3 matrix), new lines (Task 1 data), one LED/station (Task 1 test), XIAO back/DNP/centered/USB-down (Tasks 4, 6), buttons DNP (Tasks 4, 6), SeaBus (Task 1), level shifter (Task 6), land geometry (Tasks 1, 2, 5), white-on-black (Tasks 2, 5, 6), reusable components (schema-driven tools, Task 8). ✔
- Types consistent: `citymap.City` consumed by render/check/export. ✔
