# Station List & Proposed LED Chain — v3

One LED per unique station. Network as of 2026 **plus stations under construction**:
Capstan (opened Dec 2024), the Broadway Extension (6 stations, ~2027), and the
Surrey–Langley Extension (8 stations, ~2029).

**Totals:** Expo 32 + Millennium 23 + Canada 17 = 72 line-stations − 5 shared
(Commercial–Broadway, Lougheed Town Centre, Production Way–University, Waterfront,
Broadway–City Hall) = **67 unique stations**, + 1 SeaBus marker = **68 LEDs**.
This matches the 68 markers already drawn in `v2/input/map3.svg`.

Chain order below is a proposal: contiguous per line, so firmware tables are simple ranges.
Interchange LEDs are owned by the first line that reaches them; later lines reference the
existing index (marked ↩).

## Expo Line (LED 0–31)

| LED | Station | Notes |
|-----|---------|-------|
| 0 | Waterfront | Interchange: Canada Line, SeaBus |
| 1 | Burrard | |
| 2 | Granville | |
| 3 | Stadium–Chinatown | |
| 4 | Main Street–Science World | |
| 5 | Commercial–Broadway | Interchange: Millennium |
| 6 | Nanaimo | |
| 7 | 29th Avenue | |
| 8 | Joyce–Collingwood | |
| 9 | Patterson | |
| 10 | Metrotown | |
| 11 | Royal Oak | |
| 12 | Edmonds | |
| 13 | 22nd Street | |
| 14 | New Westminster | |
| 15 | Columbia | Branch point |
| 16 | Sapperton | Production Way branch |
| 17 | Braid | |
| 18 | Lougheed Town Centre | Interchange: Millennium |
| 19 | Production Way–University | Interchange: Millennium |
| 20 | Scott Road | King George branch |
| 21 | Gateway | |
| 22 | Surrey Central | |
| 23 | King George | |
| 24 | Green Timbers | **Future (Surrey–Langley, ~2029)** |
| 25 | 152 St | **Future** |
| 26 | Fleetwood | **Future** |
| 27 | Bakerview–166 St | **Future** |
| 28 | Hillcrest–184 St | **Future** |
| 29 | Clayton | **Future** |
| 30 | Willowbrook | **Future** |
| 31 | Langley City Centre | **Future** |

## Millennium Line (LED 32–49, + 5 shared/↩)

| LED | Station | Notes |
|-----|---------|-------|
| 32 | Arbutus | **Future (Broadway Ext., ~2027)** — western terminus |
| 33 | South Granville | **Future** |
| 34 | Oak–VGH | **Future** |
| 35 | Broadway–City Hall | **Future on Millennium**; interchange: Canada Line (LED shared, owned here or by Canada — pick one) |
| 36 | Mount Pleasant | **Future** |
| 37 | Great Northern Way–Emily Carr | **Future** |
| 38 | VCC–Clark | Current western terminus |
| ↩ 5 | Commercial–Broadway | shared with Expo |
| 39 | Renfrew | |
| 40 | Rupert | |
| 41 | Gilmore | |
| 42 | Brentwood Town Centre | |
| 43 | Holdom | |
| 44 | Sperling–Burnaby Lake | |
| 45 | Lake City Way | |
| ↩ 19 | Production Way–University | shared with Expo |
| ↩ 18 | Lougheed Town Centre | shared with Expo |
| 46 | Burquitlam | |
| 47 | Moody Centre | |
| 48 | Inlet Centre | |
| 49 | Coquitlam Central | |
| 50 | Lincoln | |
| 51 | Lafarge Lake–Douglas | Eastern terminus |

## Canada Line (LED 52–66, + 2 shared/↩)

| LED | Station | Notes |
|-----|---------|-------|
| ↩ 0 | Waterfront | shared with Expo |
| 52 | Vancouver City Centre | |
| 53 | Yaletown–Roundhouse | |
| 54 | Olympic Village | |
| ↩ 35 | Broadway–City Hall | shared with Millennium (post-extension) |
| 55 | King Edward | |
| 56 | Oakridge–41st Avenue | |
| 57 | Langara–49th Avenue | |
| 58 | Marine Drive | |
| 59 | Bridgeport | Branch point |
| 60 | Templeton | Airport branch |
| 61 | Sea Island Centre | |
| 62 | YVR–Airport | |
| 63 | Capstan | **New (opened Dec 2024)** — Richmond branch |
| 64 | Aberdeen | |
| 65 | Lansdowne | |
| 66 | Richmond–Brighouse | |

## Extras

| LED | Marker | Notes |
|-----|--------|-------|
| 67 | SeaBus (Burrard Inlet crossing) | v1 had this (index 126); optionally animate as a slow ferry blink between Waterfront and Lonsdale Quay |

## Notes for implementation

- **Verify names against TransLink before silkscreen** — the Surrey–Langley working names
  (Green Timbers, 152 St, Fleetwood, Bakerview–166 St, Hillcrest–184 St, Clayton,
  Willowbrook, Langley City Centre) could still change before opening.
- v1 firmware already contains the Broadway Extension stations in its Millennium tables,
  so its animation logic needs no new concepts — only renumbering to the single-LED-per-
  station indices above.
- Physical chain routing may prefer a different order than the logical one — that's fine.
  Keep the *logical* table in one CSV/JSON file and generate both the firmware header and a
  cross-check against the KiCad reference designators from it.
