# Vancouver SkyTrain PCB — Version 3 (ai-v3)

Documentation for the third revision of the SkyTrain LED map PCB.

## Goal for v3

A **smaller, square board** showing the **iconic (schematic-style) SkyTrain map**, with:

- The same WS2812B addressable RGB LEDs used in v2 (XL-1615RGBC-WS2812B-1, LCSC C5349954)
- One LED per station, including **all new and under-construction stations**
  (Capstan, the Broadway Extension, and the Surrey–Langley Extension)
- **No controller populated on the board.** Instead, a Seeed Studio **XIAO footprint on the
  back** of the board so any XIAO-family module (RP2040, ESP32-C3, SAMD21, nRF52840…) can be
  soldered on.

## Documents

| File | Contents |
|------|----------|
| [project-review.md](project-review.md) | Review of v1 and v2 in their current state — what was built, what works, what's unfinished |
| [v3-recommendations.md](v3-recommendations.md) | Recommendations and a step-by-step plan for building v3 |
| [station-list.md](station-list.md) | Complete station list (including future stations), interchange notes, and a proposed LED chain order |
| [plan.md](plan.md) | Implementation plan (assumption tests → board → firmware → reusable pipeline) |
| [fit-report.md](fit-report.md) | Results of the 100 mm text-fit test — verdict: 135 × 135 mm recommended |
