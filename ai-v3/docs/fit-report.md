# V3 Text-Fit Test Report

**Question:** does the iconic map with all 68 station names fit on a 100 × 100 mm board?

**Answer: No — as expected. Full station names need ≥ 120 mm. Recommended board: 135 × 135 mm.**

## Method

The reusable pipeline (`ai-v3/tools/`) models every station label as a rotated rectangle
(char width = 0.7 × text height, KiCad-stroke-font-like metrics) and counts collisions:
label↔label, label↔route-line, label↔LED-dot, and label-off-board. Board size scales;
text height does not (silkscreen has a fab minimum), which is exactly why bigger boards
fix text crowding. Reference silkscreen heights: **1.0 mm = JLCPCB minimum**, **1.2 mm =
comfortably readable**.

Layout under test: `ai-v3/input/vancouver.json` — 67 stations + SeaBus = 68 LEDs,
octilinear iconic geometry, validated by `test_vancouver_data.py` (counts, shared
interchanges, 45°/90° segments, ≥ 2.5 mm LED spacing).

## Results (collision counts, lower = better)

| Board | 1.0 mm full | 1.0 mm short | 1.2 mm full | 1.2 mm short |
|-------|------------|--------------|-------------|--------------|
| 100 mm | 5 | 1 | **16** | 4 |
| 120 mm | **0** | 0 | 4 | 1 |
| 135 mm | 0 | 0 | **1** | 0 |
| 150 mm | 0 | 0 | 0 | 0 |

Rendered previews (collisions highlighted red): `ai-v3/test-results/map-*.svg`,
back side: `ai-v3/test-results/back-side.svg`.

## Findings

1. **100 mm fails for full names.** At readable text (1.2 mm) there are 16 collisions and
   five labels run off the board (Coquitlam Central, Vancouver City Centre, Oakridge,
   Sea Island Centre, YVR). The user's expectation that the board must grow is confirmed.
2. **Label geometry matters as much as board size.** The first layout iteration had
   collisions that *no* board size fixed (labels crossing a parallel line 3 mm away scale
   with the board, staying in collision). Fix that worked: move the **Canada Line from
   x=16 → x=19 mm** so the west-Broadway diagonal labels clear it, put King Edward's and
   Broadway–City Hall's labels on the south-east diagonal, and anchor the airport-branch
   labels to the left. After that, collisions became purely text-size-vs-board-size.
   *Lesson encoded for future cities: keep ≥ 7 mm between a vertical line and any station
   to its west whose label points down-right.*
3. **120 mm works at fab-minimum text** (1.0 mm, full names, zero collisions) but 1.0 mm
   white-on-black silk is squint territory.
4. **135 mm works at comfortable text** (1.2 mm) with a single residual collision:
   "29th Avenue" clips the tail of "Great Northern Way–Emily Carr" (the longest name on
   the network, 29 chars ≈ 24 mm of silk). Using its short form "Gt Northern Way" — or a
   future two-line label feature — clears it: **zero collisions**.
5. **150 mm is fully clean** with all full names at 1.2 mm.
6. **Back side is a non-issue at any size.** XIAO SMD courtyard (19.8 × 23 mm incl.
   margin) centered with USB-C toward the bottom edge, 4 × 5.1 mm buttons, 74AHC1G125 and
   bulk caps all fit with huge margins on even the 100 mm board. The board is all-SMD, so
   front LEDs and back parts can overlap in Z with no conflict; only via placement needs
   care during routing. USB-C sits ~57 mm from the bottom edge on a 135 mm board — a
   cable reaches it fine for desk use; for wall mounting, a keyhole slot must avoid the
   board center.

## Recommendation

- **Board: 135 × 135 mm**, text 1.2 mm, full names everywhere except
  "Gt Northern Way" (short form). Nicely, `v2/input/map3.svg` was already drawn at
  150 × 150 — the artwork tradition supports a board in this class, and 135 mm keeps it a
  step smaller while staying collision-free.
- Fallback if cost matters: 120 × 120 mm with 1.0 mm text (JLC minimum) — fits, but
  print a paper mockup first to judge readability.
- 100 × 100 mm remains viable only as a "dots + interchange names" novelty variant; the
  data file already carries `short` names if that route is ever wanted.

## Assumptions verified / still open

| Assumption | Status |
|-----------|--------|
| 68 LEDs (67 stations + SeaBus) covers the full 2029 network | ✔ verified by data test (counts + interchange dedupe) |
| Iconic octilinear layout fits a square canvas | ✔ rendered, visually recognizable as the SkyTrain map |
| 100 mm too small for names | ✔ confirmed (16 collisions @ 1.2 mm) |
| ≥ 2.5 mm LED-to-LED spacing everywhere | ✔ min pitch 3.0 mm (Sapperton–Braid) |
| XIAO + buttons + shifter fit on back | ✔ trivially |
| Land/water geometry co-exists with map | ✔ rendered (inlet, False Creek, Fraser, Sea Island); final art treatment (mask openings vs. silk) still to be chosen |
| Fab: 1.2 mm text / 0.15 mm stroke OK for JLC white silk | ⚠ to confirm against JLC capabilities page at order time |
| Surrey–Langley station names final | ⚠ working names — re-verify before silk |
