// Vancouver SkyTrain LED map - v3 firmware
// One WS2812B (XL-1615RGBC) per station, 68 LEDs total.
// Index tables are GENERATED from ai-v3/input/vancouver.json by
// tools/export_placement.py -> include/firmware_tables.h. Regenerate after
// any layout/chain change; never edit the tables by hand.
//
// Board: XIAO RP2040 on the back (DNP footprint).
//   D0 -> 74AHC1G125 -> LED data chain
//   D1..D4 -> buttons SW1..SW4 (DNP), active low, internal pull-ups

#include <Arduino.h>
#include "FastLED.h"
#include "firmware_tables.h"

const int PIN_LED_DATA = D0;
const int PIN_BTN_MODE = D1;
const int PIN_BTN_BRIGHT = D2;
const int PIN_BTN_SPEED = D3;
const int PIN_BTN_LINE = D4;
const uint32_t BAUD_RATE = 115200;
const uint8_t BUILD_NUMBER = 1;

CRGB leds[NUM_LEDS];

uint8_t brightness = 48;
uint16_t stepMs = 700;          // train advance interval
const uint8_t FADE_PER_FRAME = 24;

// TransLink line colours
const CRGB COLOR_EXPO = CRGB(0x00, 0x5D, 0xAA);
const CRGB COLOR_MILLENNIUM = CRGB(0xFD, 0xD0, 0x05);
const CRGB COLOR_CANADA = CRGB(0x00, 0x9A, 0xC7);
const CRGB COLOR_SEABUS = CRGB(0xC0, 0xC0, 0xC0);

struct Route {
  const int *idx;    // LED index per station along the route
  int count;
  CRGB color;
  int trains;        // simultaneous trains on this route
  int pos[4];        // per-train station cursor (max 4 trains)
  int dir[4];        // +1 / -1
};

Route routes[] = {
  {LINE_EXPO_LANGLEY_CITY_CENTRE, LINE_EXPO_LANGLEY_CITY_CENTRE_COUNT,
   COLOR_EXPO, 3, {0}, {0}},
  {LINE_EXPO_PRODUCTION_WAY, LINE_EXPO_PRODUCTION_WAY_COUNT,
   COLOR_EXPO, 2, {0}, {0}},
  {LINE_MILLENNIUM, LINE_MILLENNIUM_COUNT, COLOR_MILLENNIUM, 3, {0}, {0}},
  {LINE_CANADA_YVR, LINE_CANADA_YVR_COUNT, COLOR_CANADA, 2, {0}, {0}},
  {LINE_CANADA_RICHMOND_BRIGHOUSE, LINE_CANADA_RICHMOND_BRIGHOUSE_COUNT,
   COLOR_CANADA, 2, {0}, {0}},
};
const int ROUTE_COUNT = sizeof(routes) / sizeof(routes[0]);

void setup() {
  Serial.begin(BAUD_RATE);
  Serial.println("SkyTrain map v3 build " + String(BUILD_NUMBER));

  pinMode(PIN_BTN_MODE, INPUT_PULLUP);
  pinMode(PIN_BTN_BRIGHT, INPUT_PULLUP);
  pinMode(PIN_BTN_SPEED, INPUT_PULLUP);
  pinMode(PIN_BTN_LINE, INPUT_PULLUP);

  FastLED.addLeds<NEOPIXEL, PIN_LED_DATA>(leds, NUM_LEDS);
  FastLED.setBrightness(brightness);
  // USB powered: hard cap regardless of brightness/animation choices
  FastLED.setMaxPowerInVoltsAndMilliamps(5, 1500);

  for (int r = 0; r < ROUTE_COUNT; r++) {
    for (int t = 0; t < routes[r].trains; t++) {
      routes[r].pos[t] = (routes[r].count * t) / routes[r].trains;
      routes[r].dir[t] = (t % 2 == 0) ? 1 : -1;
    }
  }
}

void advanceTrains() {
  for (int r = 0; r < ROUTE_COUNT; r++) {
    Route &rt = routes[r];
    for (int t = 0; t < rt.trains; t++) {
      rt.pos[t] += rt.dir[t];
      if (rt.pos[t] >= rt.count) {          // bounce at the terminus
        rt.pos[t] = rt.count - 2;
        rt.dir[t] = -1;
      } else if (rt.pos[t] < 0) {
        rt.pos[t] = 1;
        rt.dir[t] = 1;
      }
    }
  }
}

void handleButtons() {
  static uint32_t lastPress = 0;
  if (millis() - lastPress < 250) return;   // debounce
  if (digitalRead(PIN_BTN_BRIGHT) == LOW) {
    brightness = (brightness >= 224) ? 16 : brightness + 32;
    FastLED.setBrightness(brightness);
    lastPress = millis();
  }
  if (digitalRead(PIN_BTN_SPEED) == LOW) {
    stepMs = (stepMs <= 200) ? 1200 : stepMs - 200;
    lastPress = millis();
  }
  // PIN_BTN_MODE / PIN_BTN_LINE reserved for future animation modes
}

void loop() {
  handleButtons();

  EVERY_N_MILLISECONDS_I(trainTimer, 700) {
    trainTimer.setPeriod(stepMs);
    advanceTrains();
  }

  // fade trails, then draw trains at full line colour
  fadeToBlackBy(leds, NUM_LEDS, FADE_PER_FRAME);
  for (int r = 0; r < ROUTE_COUNT; r++) {
    Route &rt = routes[r];
    for (int t = 0; t < rt.trains; t++) {
      leds[rt.idx[rt.pos[t]]] = rt.color;
    }
  }
  // SeaBus: slow breathing pulse
  leds[LINE_SEABUS[0]] = COLOR_SEABUS;
  leds[LINE_SEABUS[0]].nscale8(beatsin8(6, 20, 255));

  FastLED.show();
  delay(16);
}
