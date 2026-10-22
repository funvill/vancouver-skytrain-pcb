// Vancouver SkyTrain LED map - v3 firmware
// One WS2812B (XL-1615RGBC) per station, 68 LEDs total.
// Index tables are GENERATED from ai-v3/input/vancouver.json by
// tools/export_placement.py -> include/firmware_tables.h. Regenerate after
// any layout/chain change; never edit the tables by hand.
//
// Board: any XIAO module on the back (U1, DNP footprint). Pin assignments
// read off the PCB itself, not assumed - XIAO pad -> net:
//   pad 8  = D7 -> LED_IN, straight into LED1 DI (no level shifter on v3)
//   pad 1  = D0 -> BUTTON_01 (SW1)      pad 3 = D2 -> BUTTON_03 (SW3)
//   pad 2  = D1 -> BUTTON_02 (SW2)      pad 4 = D3 -> BUTTON_04 (SW4)
//   pad 13 = GND, pad 14 = 5V (VBUS) -> the LED +5V rail
// The switches are DNP; their pins idle high on the internal pull-ups.
// D7 is GPIO20 on the ESP32-C3 (GPIO1 on the RP2040) - the name is what
// matters, the core maps it to the right GPIO per board.
//
// Because SW1..SW4 are unpopulated, the only button on the assembly is the
// XIAO module's own BOOT button. On the ESP32-C3 that button is wired to
// GPIO9 = D9 with an external pull-up, and D9 is not connected to anything
// on this PCB, so it is free to use as the mode button. GPIO9 is a strapping
// pin: held low at reset the chip enters serial download mode instead of
// running this sketch, so it is only ever read after boot, and as a plain
// INPUT - the module already has the pull-up and enabling the internal one
// in parallel would only lower its value.

#include <Arduino.h>
#include "FastLED.h"
#include "firmware_tables.h"

constexpr uint8_t PIN_LED_DATA = D7;
constexpr uint8_t PIN_BTN_MODE = D0;   // SW1, DNP - harmless to read
constexpr uint8_t PIN_BTN_BOOT = D9;   // XIAO BOOT button, GPIO9
const uint32_t BAUD_RATE = 115200;
const uint8_t BUILD_NUMBER = 6;

// Bring-up staging. The LED driver is brought up from loop() rather than
// setup() so the heartbeat below starts printing before the RMT driver is
// touched: on a USB-CDC board the boot banner is gone before a monitor can
// attach, so "which stage did it reach" is the only thing you can actually
// read back. 0 = booted, 1 = FastLED up, 2 = chain tested, 3 = animating.
volatile uint8_t stage = 0;
const uint32_t LED_INIT_DELAY_MS = 4000;   // let USB CDC enumerate first

CRGB leds[NUM_LEDS];

uint8_t brightness = 40;

// 68 LEDs at full white would pull ~4 A; the board is fed from the XIAO's
// USB connector, so cap well under what a PC port and the module's VBUS
// trace will carry. Raise it when running from a dedicated 5 V supply on
// the +5V test point.
const uint32_t MAX_MILLIAMPS = 900;

// Two modes, toggled by the BOOT button.
//   DEMO - trains sweep the map fast enough to read at a glance. The boot
//          default, so the board explains itself when it powers on.
//   LIVE - the pace of the real system: about two minutes per station hop.
//          Nothing here is a schedule and there is no clock on this board;
//          "live" means faithful motion, not accurate departures.
enum Mode : uint8_t { MODE_DEMO = 0, MODE_LIVE = 1 };
Mode mode = MODE_DEMO;

const float LIVE_HOP_SECONDS = 120.0f;

// Service level in LIVE, and the one number worth tuning. Train count falls
// out of it: a round trip takes loopLen * LIVE_HOP_SECONDS, so trains in
// service = round_trip / headway. 720 s is late-evening service and leaves
// dark gaps between trains; 300 s is peak and lights roughly two thirds of
// the Expo Line at once.
const float LIVE_HEADWAY_SECONDS = 720.0f;

// Only DEMO leaves trails - LIVE redraws from black because its trains are
// drawn across two LEDs at fractional brightness and a fade would fight it.
const uint8_t DEMO_FADE_PER_FRAME = 24;

// A frame longer than this (a mode-change flash, a USB stall) advances the
// trains by this much at most, so the map never lurches.
const float MAX_FRAME_SECONDS = 0.1f;

// Full white on all 68 is the harshest thing this board does; the self test
// only has to prove each LED lights, so it does it well below full scale.
const CRGB SELFTEST_WHITE = CRGB(0x50, 0x50, 0x50);

// One colour per route, not per line. TransLink's own palette cannot work
// here: Expo's two branches cover 48 of the 68 station slots and Canada
// Line's teal (0x009AC7) is within a few degrees of Expo's blue (0x005DAA),
// which at this brightness makes the whole map read blue and yellow. So the
// two branch routes get hues of their own and Canada Line is pushed well
// away from blue. Hues are spread around the wheel (~15, 50, 165, 210, 285)
// to stay separable on a WS2812 at brightness 40.
const CRGB COLOR_EXPO = CRGB(0x00, 0x5D, 0xAA);          // TransLink blue, kept
const CRGB COLOR_EXPO_BRANCH = CRGB(0xA0, 0x20, 0xFF);   // violet
const CRGB COLOR_MILLENNIUM = CRGB(0xFD, 0xD0, 0x05);    // TransLink yellow, kept
const CRGB COLOR_CANADA = CRGB(0x00, 0xD0, 0x90);        // green-cyan
const CRGB COLOR_CANADA_BRANCH = CRGB(0xFF, 0x40, 0x00); // orange-red
const CRGB COLOR_SEABUS = CRGB(0xC0, 0xC0, 0xC0);

// Trains are positions on an out-and-back loop rather than objects that walk
// to a terminus and reverse: the loop is 2*(count-1) hops long, and N trains
// sit evenly spaced around it, all advancing together. Train count then costs
// nothing - 20 trains is the same work as 2 - and the spacing is exact.
struct Route {
  const int *idx;          // LED index per station along the route
  int count;
  CRGB color;
  float demoHopSeconds;    // each track gets its own DEMO cadence, 1-3 s
  float head;              // lead train, in fractional station-hops
};

Route routes[] = {
  {LINE_EXPO_LANGLEY_CITY_CENTRE, LINE_EXPO_LANGLEY_CITY_CENTRE_COUNT,
   COLOR_EXPO, 1.0f, 0.0f},
  {LINE_EXPO_PRODUCTION_WAY, LINE_EXPO_PRODUCTION_WAY_COUNT,
   COLOR_EXPO_BRANCH, 1.5f, 0.0f},
  {LINE_MILLENNIUM, LINE_MILLENNIUM_COUNT, COLOR_MILLENNIUM, 2.0f, 0.0f},
  {LINE_CANADA_YVR, LINE_CANADA_YVR_COUNT, COLOR_CANADA, 2.5f, 0.0f},
  {LINE_CANADA_RICHMOND_BRIGHOUSE, LINE_CANADA_RICHMOND_BRIGHOUSE_COUNT,
   COLOR_CANADA_BRANCH, 3.0f, 0.0f},
};
const int ROUTE_COUNT = sizeof(routes) / sizeof(routes[0]);

inline int loopLen(const Route &rt) {
  return (rt.count > 1) ? 2 * (rt.count - 1) : 1;
}

// Loop position -> station. 0..count-1 runs out to the far terminus, then
// back down to 1, so the loop closes without parking a train at either end.
inline int stationAt(const Route &rt, int p) {
  const int L = loopLen(rt);
  p %= L;
  if (p < 0) p += L;
  return (p < rt.count) ? p : (L - p);
}

inline int trainCount(const Route &rt) {
  if (mode == MODE_DEMO) return (loopLen(rt) >= 40) ? 3 : 2;
  const int n =
      (int)lroundf(loopLen(rt) * LIVE_HOP_SECONDS / LIVE_HEADWAY_SECONDS);
  return (n < 1) ? 1 : n;
}

// Power-on chain check: walk one lit LED from the first to the last, then
// flash every LED once. On a new board this shows at a glance that all 68
// are alive and in chain order - if the walk stops part way, the break is
// at the LED it stopped on.
void chainSelfTest() {
  for (int i = 0; i < NUM_LEDS; i++) {
    fill_solid(leds, NUM_LEDS, CRGB::Black);
    leds[i] = SELFTEST_WHITE;
    FastLED.show();
    delay(18);
  }
  for (int f = 0; f < 2; f++) {
    fill_solid(leds, NUM_LEDS, SELFTEST_WHITE);
    FastLED.show();
    delay(120);
    fill_solid(leds, NUM_LEDS, CRGB::Black);
    FastLED.show();
    delay(120);
  }
}

void setup() {
  Serial.begin(BAUD_RATE);
#if defined(ARDUINO_ARCH_ESP32)
  Serial.setTxTimeoutMs(0);   // never block waiting for a USB host to attach
#endif
  Serial.println("SkyTrain map v3 build " + String(BUILD_NUMBER));

  pinMode(PIN_BTN_MODE, INPUT_PULLUP);
  pinMode(PIN_BTN_BOOT, INPUT);   // module already pulls GPIO9 up
}

void startLeds() {
  FastLED.addLeds<WS2812B, PIN_LED_DATA, GRB>(leds, NUM_LEDS);
  FastLED.setBrightness(brightness);
  // USB powered: hard cap regardless of brightness/animation choices
  FastLED.setMaxPowerInVoltsAndMilliamps(5, MAX_MILLIAMPS);
}

void advanceTrains(float dtSeconds) {
  for (int r = 0; r < ROUTE_COUNT; r++) {
    Route &rt = routes[r];
    const float hop =
        (mode == MODE_DEMO) ? rt.demoHopSeconds : LIVE_HOP_SECONDS;
    rt.head = fmodf(rt.head + dtSeconds / hop, (float)loopLen(rt));
  }
}

void drawTrains() {
  for (int r = 0; r < ROUTE_COUNT; r++) {
    Route &rt = routes[r];
    const int L = loopLen(rt);
    const int n = trainCount(rt);
    const float spacing = (float)L / (float)n;
    for (int t = 0; t < n; t++) {
      const float p = fmodf(rt.head + spacing * (float)t, (float)L);
      const int p0 = (int)floorf(p);
      // A train between two stations lights both, split by how far along it
      // is. At two minutes a hop this glide is the only visible motion, and
      // it is what keeps LIVE from looking like a still map that twitches.
      const uint8_t w1 = (uint8_t)lroundf((p - (float)p0) * 255.0f);
      const uint8_t w0 = 255 - w1;
      // Additive, so an interchange carrying two lines blends their colours.
      leds[rt.idx[stationAt(rt, p0)]] += CRGB(rt.color).nscale8(w0);
      leds[rt.idx[stationAt(rt, p0 + 1)]] += CRGB(rt.color).nscale8(w1);
    }
  }
}

// Switching into LIVE makes the map go nearly still, which looks like a
// crash. Light every route in its own colour once so the press is visibly
// acknowledged.
void flashModeCue() {
  fill_solid(leds, NUM_LEDS, CRGB::Black);
  for (int r = 0; r < ROUTE_COUNT; r++) {
    for (int i = 0; i < routes[r].count; i++) {
      leds[routes[r].idx[i]] = routes[r].color;
    }
  }
  leds[LINE_SEABUS[0]] = COLOR_SEABUS;
  FastLED.show();
  delay(180);
  fill_solid(leds, NUM_LEDS, CRGB::Black);
  FastLED.show();
  delay(120);
}

void setMode(Mode m) {
  mode = m;
  Serial.printf("mode -> %s\n", (m == MODE_DEMO) ? "demo" : "live");
  flashModeCue();
}

void handleButtons() {
  static uint32_t lastChange = 0;
  static bool prevPressed = false;
  // Both are active-low: BOOT through the module's external pull-up, SW1
  // through the internal one (and SW1 is DNP, so it never really reads low).
  const bool pressed = (digitalRead(PIN_BTN_BOOT) == LOW) ||
                       (digitalRead(PIN_BTN_MODE) == LOW);
  if (pressed && !prevPressed && (millis() - lastChange) > 250) {
    lastChange = millis();
    setMode((mode == MODE_DEMO) ? MODE_LIVE : MODE_DEMO);
  }
  prevPressed = pressed;
}

void loop() {
  // Heartbeat first, so it reports even if a later stage wedges.
  EVERY_N_MILLISECONDS(2000) {
    Serial.printf("build %u alive %lus stage %u mode %s\n",
                  BUILD_NUMBER, millis() / 1000, stage,
                  (mode == MODE_DEMO) ? "demo" : "live");
  }

  if (stage == 0) {
    if (millis() < LED_INIT_DELAY_MS) return;
    startLeds();
    stage = 1;
    return;
  }
  if (stage == 1) {
    chainSelfTest();
    stage = 2;
    return;
  }
  if (stage == 2) {
    stage = 3;
  }

  handleButtons();

  static uint32_t lastFrame = 0;
  const uint32_t now = millis();
  if (lastFrame == 0) lastFrame = now;
  float dt = (float)(now - lastFrame) / 1000.0f;
  lastFrame = now;
  if (dt > MAX_FRAME_SECONDS) dt = MAX_FRAME_SECONDS;
  advanceTrains(dt);

  if (mode == MODE_DEMO) {
    fadeToBlackBy(leds, NUM_LEDS, DEMO_FADE_PER_FRAME);
  } else {
    fill_solid(leds, NUM_LEDS, CRGB::Black);
  }
  drawTrains();

  // SeaBus: slow breathing pulse
  leds[LINE_SEABUS[0]] = COLOR_SEABUS;
  leds[LINE_SEABUS[0]].nscale8(beatsin8(6, 20, 255));

  FastLED.show();
  delay(16);
}
