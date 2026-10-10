# Runbook: starting a new city map

How to take this project — a PCB that is a transit map, one addressable LED
per station — and do it again for another city. Written from the Vancouver
build ([`ai-v3/`](ai-v3/)); the mistakes it avoids are catalogued in
[lessons-learned.md](lessons-learned.md).

Everything below `<city>.json` is city-agnostic. The work in a new city is
getting that file right, plus about a third of the geography code.

---

## Phase 0 — Decide the scope before writing anything

| Decision | Why it binds everything else |
|---|---|
| **Which stations** — current only, or under construction / funded too? | Sets the LED count, the frame, and whether you need hand-entered positions for stations OSM doesn't have yet |
| **LED count** | Drives cost (JLC charges per placement), power, and board size. Vancouver: 68 |
| **Board width** | With the frame's aspect fixed, width sets mm/km, which sets whether labels fit. Vancouver: 200 mm wide, 4.33 mm/km |
| **Power source** | N LEDs x 60 mA at full white. 68 LEDs is about 4 A — far past a USB port. Either cap brightness in firmware or design a barrel jack in |
| **Controller** | Vancouver uses a bare XIAO footprint (DNP) so any XIAO module fits. Keep this unless you have a reason not to |

**Gate:** write the station list down before anything else. Everything
downstream is derived from it.

---

## Phase 1 — Set up the project

Copy [`ai-v3/`](ai-v3/) to `<city>/` and strip the Vancouver specifics:

```bash
cp -r ai-v3 <city>
cd <city>
rm -rf input/osm/* input/*.json input/build_from_osm.py input/build_from_v1.py \
       input/build_vancouver_json.py input/build_geo.py input/match_stations.py \
       input/parse_v1_coast.py input/*.pdf test-results/* firmware/.pio
```

Keep everything in `tools/` — none of it is Vancouver-specific except the
constants named in Phase 5. Keep `hardware/` as the KiCad starting point
(Phase 7) and `firmware/` as-is (Phase 9).

---

## Phase 2 — Station positions from OpenStreetMap

Pick a bbox covering the network, then one Overpass query. Fetch with `curl`
rather than Python — on this machine Python's SSL store rejects the Overpass
certificate:

```bash
BBOX="49.08,-123.30,49.36,-122.60"
curl -s -A "transit-pcb/1.0" --max-time 300 \
  https://overpass-api.de/api/interpreter \
  --data-urlencode "data=[out:json][timeout:120];(node[\"railway\"~\"^(station|halt)$\"][\"station\"~\"light_rail|subway\"]($BBOX);node[\"railway\"~\"^(construction|proposed)$\"][\"name\"]($BBOX);node[\"public_transport\"=\"station\"][\"subway\"=\"yes\"]($BBOX););out body;" \
  -o osm/stations.json
```

The bbox order is south,west,north,east. Adjust the tags to the mode:
`station=subway|light_rail` for metro, `railway=tram_stop` for trams.

Reduce the result to `<city>_station_latlon.json`, a flat
`{"station-id": [lat, lon]}` map — averaging duplicate nodes, since big
interchanges are tagged more than once — and hand-add anything under
construction that OSM lacks. Vancouver needed six by hand (the five Broadway
extension stations, plus SeaBus at Lonsdale Quay).

**Gate:** count the stations and read the names out. A wrong station list
discovered later costs a board respin.

---

## Phase 3 — Geography (budget the most time here)

This took more effort than everything else combined, across five attempted
sources. The rules that came out of it:

1. **Prefer polygons over lines.** Assembling coastline *lines* into
   land/sea faces is where the OSM attempt silently lost an entire island
   and the whole river estuary. A source that hands you land, rivers and
   lakes as ready-made polygons needs no assembly and cannot get
   inside/outside backwards.
2. **Prefer the government mapping agency over crowd-sourced data for
   water.** Look for a WFS endpoint that accepts a bbox:
   - **BC** — `openmaps.gov.bc.ca/geo/pub/wfs`; layers
     `FWA_WATERSHED_GROUPS_POLY` (land), `FWA_RIVERS_POLY`, `FWA_LAKES_POLY`
   - **US** — USGS National Hydrography Dataset (NHD / WBD), ArcGIS services
     at `hydro.nationalmap.gov`
   - **EU** — Copernicus EU-Hydro, plus the national services alongside it
   - **Anywhere** — OSM `natural=water` **polygons** (not `natural=coastline`
     lines) as the fallback; Natural Earth for coarse coastline
3. **Land coverage beats coastline tracing.** The trick in BC was that
   watershed-group polygons cover land only, so `sea = frame - land` with no
   tracing at all. Look for the local equivalent — admin areas or land cover
   will often do it.

```bash
curl -s --max-time 180 -o osm/LAYERNAME.json \
  "https://HOST/geo/pub/wfs?service=WFS&version=2.0.0&request=GetFeature&typeName=LAYERNAME&outputFormat=json&srsName=EPSG:4326&bbox=WEST,SOUTH,EAST,NORTH,EPSG:4326"
```

Cache every raw response in `input/osm/` and commit it, so the build runs
offline and reproducibly.

Copy [`input/geo_fwa.py`](ai-v3/input/geo_fwa.py) to `geo_<city>.py`. What
carries over unchanged: the equirectangular `km()` projection, the smoothing,
and `render()`. What you replace:

- the frame constants (`LON0/LON1/LAT0/LAT1`, `BOARD_W_MM`) — Phase 4
- `land_raw()` / `rivers_raw()` / `lakes_raw()` — your layers
- `KEEP_LAKES` — **whitelist lakes by name, not by area.** An area threshold
  lets ponds through and the map turns to confetti
- `MIN_RIVER_WIDTH_KM` (0.10) — drops creeks that render as hairlines
- `MIN_ISLAND_KM2`, `MIN_PIECE_KM2` — fills braided river islands, drops bay
  tips that are mostly outside the frame

Smoothing that worked at about 4 mm/km: a morphological open/close
(`buffer(-d).buffer(2d).buffer(-d)` with d around 35 m) then `simplify(50 m)`.

```bash
python geo_<city>.py        # writes ../test-results/geo-preview.png
```

**Gate — do not touch the PCB until this picture is approved.** Check by eye,
every time: does the river reach the sea, is the airport island there, are
the big lakes present and the ponds gone? Iterating here costs seconds;
iterating through KiCad renders costs minutes.

---

## Phase 4 — Frame and board size

Crop the lat/lon box to the network plus room for the outermost labels, then
let the board take the frame's aspect:

```
mm_per_km  = BOARD_W_MM / frame_width_km
board_h_mm = frame_height_km * mm_per_km
```

Vancouver: a 46.2 x 25.2 km frame at 200 mm wide gives 200 x 109 mm and
4.33 mm/km.

Sanity-check the scale against your tightest cluster. Downtown Vancouver
stations sit about 500 m apart, which is 2.2 mm — below the 3.3 mm pitch
floor, so they get spread apart. If much of your network is that tight, raise
the board width rather than fighting it later in the label optimiser. **A
square board for a 2:1 region wastes half the area** and pushes the scale
down until labels stop fitting.

---

## Phase 5 — Build the data file

Copy [`input/build_from_fwa.py`](ai-v3/input/build_from_fwa.py) to
`build_from_<city>.py`. The city-specific pieces:

| In the script | What it is |
|---|---|
| `BOARD`, `CANVAS_W` | board mm per canvas unit (2.0), canvas width (100) |
| `MIN_PITCH` | **3.3 mm** for the XL-1615 — see below |
| `PAD_CLEAR_MM` | 2.2 mm copper keepout disc around each LED |
| the chain lists in the pitch-spreading loop | runs that are too tight in reality (downtown, branch lines) |
| `LABEL` dict and the boundary layer | municipality names in exposed copper; optional |
| the `wrap = False` list | stations on tight runs whose two-line labels would collide |
| `TITLE_MM` and the wordmark placement | the city name in copper, placed on land clear of track |

**The pitch floor is 3.3 mm, not the 2.5 mm the package suggests.** LED
footprints rotate to aim DOUT at the next LED, so two diagonal neighbours'
pads break the 0.2 mm clearance below 3.3 mm. This was found by DRC after the
layout already looked fine.

**The LED chain order is hand-authored** — the `chain` array in
`<city>.json`, one station id per LED in daisy-chain order. There is no
script for it. It is the physical routing order, so walk the network the way
the copper will: down a branch and back, not hopping across the board.
`export_placement.py` derives the firmware's per-line index tables from it.

Then update `tools/test_<city>_data.py`: `EXPECTED_LEDS`,
`EXPECTED_STATIONS`, and `SHARED` (interchanges that appear in two lines but
must exist exactly once).

```bash
python build_from_<city>.py
cd ../tools && python test_<city>_data.py        # must PASS
```

---

## Phase 6 — Labels

```bash
python auto_label.py
python preview_map.py ../input/<city>.json ../test-results/preview.png --collisions
python check_fit.py ../input/<city>.json --scale 2.0 -v
```

`preview_map.py` draws exactly what the exporter will, in seconds, with
collisions in red — use it rather than KiCad while iterating.

Expect to finish by hand. The optimiser clears the open country and leaves a
handful in the dense core; that is normal and not worth more algorithm. Do
the hand pass in KiCad (Phase 7) and pull it back with `import_labels.py`.

---

## Phase 7 — Hardware

The KiCad project in [`hardware/`](ai-v3/hardware/) is the starting point,
but **the schematic is per-LED-count**: a different station count means
adding or deleting LED symbols and re-annotating. Budget for it — it is the
one genuinely manual step in the hardware flow.

```bash
python export_placement.py ../input/<city>.json ../hardware --scale 2.0
python reposition_board.py ../hardware/<city>.kicad_pcb ../hardware/leds.csv --board 200 --height 109
python export_art.py ../input/<city>.json ../hardware/<city>.kicad_pcb --scale 2.0
```

**The one rule:** never run `export_art.py` on a board that may contain hand
edits without running `import_labels.py` first — see [AGENTS.md](AGENTS.md).
Take a backup and a git tag before the first regeneration, and never
overwrite a backup.

Verification, in this order, reported honestly:

```bash
python test_<city>_data.py                               # PASS
python check_fit.py ../input/<city>.json --scale 2.0 -v  # only label-geo is acceptable
python export_art.py ... ; python export_art.py ...      # same counts twice = idempotent
grep -o 'uuid "[^"]*"' ../hardware/*.kicad_pcb | sort | uniq -d | wc -l   # 0
kicad-cli pcb drc ../hardware/<city>.kicad_pcb -o ../test-results/drc.json --format json --severity-error --severity-warning
python render_board.py ../hardware/<city>.kicad_pcb ../test-results
```

`clearance`, `copper_edge_clearance`, `shorting_items`, `courtyards_overlap`
and `unconnected_items` must be zero. `silk_over_copper`, `silk_overlap`,
`solder_mask_bridge` and `text_height` are expected for exposed-copper art.

**Look at the render before calling it done.** The checkers model boxes, not
what the eye sees — every geography error in this project was caught by a
human looking at a picture, never by a checker.

---

## Phase 8 — Fabrication

```bash
cd ../hardware && python ../tools/make_jlcpcb.py     # after the kicad-cli exports
```

The exact `kicad-cli` commands and the upload map are in
[`hardware/jlcpcb/README.md`](ai-v3/hardware/jlcpcb/README.md). Before paying:

- **Check the LED rotation** in JLC's placement preview. Their library
  orientation often differs from the KiCad footprint by a constant; every LED
  shares one footprint, so a single offset corrects all of them.
- **ENIG, not HASL** — the exposed copper *is* the artwork, and HASL reads
  dull silver instead of gold.

---

## Phase 9 — Firmware

**Read the pin assignments off the board; do not assume them.** The Vancouver
firmware shipped with data on `D0` and buttons on `D1`-`D4`, while the board
actually has data on pad 8 (`D7`) and buttons on pads 1-4 (`D0`-`D3`) — so it
drove the LED chain out of a button pin:

```bash
"C:/Program Files/KiCad/10.0/bin/python.exe" -c "import pcbnew; b=pcbnew.LoadBoard('<city>.kicad_pcb'); [print(p.GetNumber(), p.GetPinFunction(), p.GetNetname()) for fp in b.GetFootprints() if fp.GetReference()=='U1' for p in fp.Pads()]"
```

XIAO pads are physically the same across the family: pads 1-11 are `D0`-`D10`,
12 is 3V3, 13 is GND, 14 is 5V. Use the `D` names in the source and one build
serves every XIAO; only the PlatformIO environment changes. On the ESP32-C3,
force Serial to the native USB CDC (`-DARDUINO_USB_MODE=1` and
`-DARDUINO_USB_CDC_ON_BOOT=1`) because `D7` is GPIO20, which is also UART0 RX.

`include/firmware_tables.h` is generated by `export_placement.py` — never
edit it by hand, and regenerate it after any chain change.

---

## Phase 10 — Bring-up

Keep the power-on chain self-test in
[`firmware/src/main.cpp`](ai-v3/firmware/src/main.cpp): it walks one lit LED
through the whole chain, so a break shows exactly which LED it stops on, then
flashes the board twice.

- Start with a conservative `setMaxPowerInVoltsAndMilliamps` (900 mA) and low
  brightness. Raise it only on a dedicated 5 V supply.
- If the first LED misbehaves while the rest are fine, that is 3.3 V data
  into 5 V LEDs with no level shifter — a real marginality of this design.
- If a USB-CDC board goes silent, remember the boot banner is gone before a
  monitor can attach; print a periodic heartbeat instead of trusting it.

---

## Quick reference: what carries over

| Reusable unchanged | Needs a city-specific version |
|---|---|
| `tools/citymap.py`, `check_fit.py`, `auto_label.py` | `input/geo_<city>.py` (data sources, lake whitelist) |
| `tools/preview_map.py`, `render_board.py` | `input/build_from_<city>.py` (constants, labels, spreading) |
| `tools/export_art.py`, `import_labels.py` | `input/<city>_station_latlon.json` |
| `tools/export_placement.py`, `reposition_board.py` | `<city>.json`: `chain`, `lines`, station names |
| `tools/make_jlcpcb.py`, `update_footprints.py` | `tools/test_<city>_data.py` constants |
| `firmware/` (pin names, animation, self-test) | KiCad schematic — LED count |

## Gates

1. Station list written down and checked
2. Geography preview approved — **before** any PCB work
3. `test_<city>_data.py` passes
4. `preview_map --collisions` clean enough to hand-finish
5. DRC clean in the categories that matter
6. Render looked at by a human
7. JLC placement preview checked for LED rotation

## Further reading

- [lessons-learned.md](lessons-learned.md) — the eight things this project
  learned the hard way, including the five geography sources that failed
- [AGENTS.md](AGENTS.md) — conventions the scripts depend on: units,
  deterministic uuids, the label schema, copper rules
- [`ai-v3/input/README.md`](ai-v3/input/README.md) — data sources and the
  superseded builders
- [`ai-v3/hardware/README.md`](ai-v3/hardware/README.md) — fab-side detail
