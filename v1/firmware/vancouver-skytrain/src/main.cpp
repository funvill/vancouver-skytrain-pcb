#include <Arduino.h>
#include "FastLED.h"


const int PIN_LED_STATUS = 13; // IO-13 or pin 16
const int PIN_LED_TRAIN = D7;        // 14;           // IO-14 or pin 13
const uint32_t BAUD_RATE = 115200;

// The build version is shown on the loading screen.
// the version is shown in the serial prompt and the web page.
const uint8_t BUILD_NUMBER = 3;

const uint16_t NUM_LEDS = 130;
CRGB leds[NUM_LEDS];

#define BRIGHTNESS 32

// How many trains are on each line
const int TRAIN_COUNT = 2;
const int BASE_TRAIN_PROGRESS_SPEED = 1000;

const int lineExpoNorthStationCount = 20;
static int lineExpoNorthStationOffset[TRAIN_COUNT];
const int LINE_EXPO_NORTH_OFFSET_TO_LED_INDEX[] = {
    0,  // East - King George
    1,  // East - Surrey Central
    2,  // East - Gateway
    3,  // East - Scott Road
    4,  // North - Columbia
    5,  // North - New Westminster
    6,  // North - 22nd Street
    7,  // North - Edmonds
    8,  // North - Royal Oak
    9,  // North - Metrotown
    10, // North - Patterson
    11, // North - Joyce-Collingwood
    12, // North - 29th Avenue
    13, // North - Nanaimo
    14, // North - Commercial-Broadway
    15, // North - Main Street-Science World
    16, // North - Stadium-Chinatown
    17, // North - Granville
    18, // North - Burrard
    19, // North - Waterfront
};

const int lineExpoSouthStationCount = 28;
static int lineExpoSouthStationOffset[TRAIN_COUNT];
const int LINE_EXPO_SOUTH_OFFSET_TO_LED_INDEX[] = {
    20, // South - Waterfront
    21, // South - Burrard
    22, // South - Granville
    23, // South - Stadium-Chinatown
    24, // South - Main Street-Science World
    25, // South - Commercial-Broadway
    26, // South - Nanaimo
    27, // South - 29th Avenue
    28, // South - Joyce-Collingwood
    29, // South - Patterson
    30, // South - Metrotown
    31, // South - Royal Oak
    32, // South - Edmonds
    33, // South - 22nd Street
    34, // South - New Westminster
    35, // South - Columbia
    36, // South - Sapperton
    37, // South - Braid
    38, // South - Lougheed Town Centre
    39, // North - Production Way-University
    40, // South - Production Way-University
    41, // South - Lougheed Town Centre
    42, // South - Braid
    43, // South - Sapperton
    44, // West - Scott Road
    45, // West - Gateway
    46, // West - Surrey Central
    47, // West - King George
};

const int lineMillenniumEastWestStationCount = 28;
static int lineMillenniumEastWestStationOffset[TRAIN_COUNT];
const int LINE_MILLENNIUM_EAST_WEST_OFFSET_TO_LED_INDEX[] = {
    48, // West - Lafarge Lake-Douglas
    49, // West - Lincoln
    50, // West - Coquitlam Central
    51, // West - Inlet Centre
    52, // West - Moody Centre
    53, // West - Burquitlam
    54, // West - Lougheed Town Centre
    55, // West - Production Way-University
    56, // West - Lake City Way
    57, // West - Sperling-Burnaby Lake
    58, // West - Holdom
    59, // West - Brentwood Town Centre
    60, // West - Gilmore
    61, // West - Rupert
    62, // West - Renfrew
    63, // West - Commercial-Broadway
    64, // West - VCC-Clark
    65, // West - Great Northern Way-Emily Carr
    66, // West - Mount Pleasant
    67, // West - Broadway-City Hall
    68, // West - Oak-VGH
    69, // West - South Granville
    70, // West - Arbutus
};

const int lineMillenniumWestEastStationCount = 28;
static int lineMillenniumWestEastStationOffset[TRAIN_COUNT];
const int LINE_MILLENNIUM_WEST_EAST_OFFSET_TO_LED_INDEX[] = {
    71, // East - Arbutus
    72, // East - South Granville
    73, // East - Oak-VGH
    74, // East - Broadway-City Hall
    75, // East - Mount Pleasant
    76, // East - Great Northern Way-Emily Carr
    77, // East - VCC-Clark
    78, // East - Commercial-Broadway
    79, // East - Renfrew
    80, // East - Rupert
    81, // East - Gilmore
    82, // East - Brentwood Town Centre
    83, // East - Holdom
    84, // East - Sperling-Burnaby Lake
    85, // East - Lake City Way
    86, // East - Production Way-University
    87, // East - Lougheed Town Centre
    88, // East - Burquitlam
    89, // East - Moody Centre
    90, // East - Inlet Centre
    91, // East - Coquitlam Central
    92, // East - Lincoln
    93, // East - Lafarge Lake-Douglas
};

const int lineCanadaLineSouthNorthStationCount = 13;
static int lineCanadaLineSouthNorthStationOffset[TRAIN_COUNT];
const int LINE_CANADA_LINE_SOUTH_TO_NORTH_OFFSET_TO_LED_INDEX[] = {
    94,  // East - Richmond-Brighouse
    95,  // East - Lansdowne
    96,  // East - Aberdeen
    97,  // East - Bridgeport
    98,  // East - Marine Drive
    99,  // East - Langara-49th Avenue
    100, // East - Oakridge-41st Avenue
    101, // East - King Edward
    102, // East - Broadway-City Hall
    103, // East - Olympic Village
    104, // East - Yaletown-Roundhouse
    105, // East - Vancouver City Centre
    106, // East - Waterfront
};

const int lineCanadaLineNorthSouthStationCount = 19;
static int lineCanadaLineNorthSouthStationOffset[TRAIN_COUNT];
const int LINE_CANADA_LINE_NORTH_TO_SOUTH_OFFSET_TO_LED_INDEX[] = {
    107, // West - Waterfront
    108, // West - Vancouver City Centre
    109, // West - Yaletown-Roundhouse
    110, // West - Olympic Village
    111, // West - Broadway-City Hall
    112, // West - King Edward
    113, // West - Oakridge-41st Avenue
    114, // West - Langara-49th Avenue
    115, // West - Marine Drive
    116, // West - Bridgeport
    117, // North - Templeton
    118, // North - Sea Island Centre
    119, // North - YVR-Airport
    120, // South - YVR-Airport
    121, // South - Sea Island Centre
    122, // South - Templeton
    123, // West - Aberdeen
    124, // West - Lansdowne
    125, // West - Richmond-Brighouse
};

const int LINE_SEABUS_LED_INDEX = 126;

void flipTheStatusLED()
{
  static bool statusLEDState = LOW;
  statusLEDState = !statusLEDState;
  digitalWrite(PIN_LED_STATUS, statusLEDState);
}

void SetTrainStartingPosition(const int stationCount, const int trainCount, int *lineTrainOffset)
{
  // Set the starting position of the train
  for (int i = 0; i < trainCount; i++)
  {
    lineTrainOffset[i] = (stationCount / trainCount) * i;
  }
}

void setup()
{
  // Set the status led to an output
  // This shows that there is power to the boards
  pinMode(PIN_LED_STATUS, OUTPUT);
  digitalWrite(PIN_LED_STATUS, HIGH);

  // Set up the serial port for debugging
  // this prevents the button_next, and button_prev from working
  Serial.begin(BAUD_RATE);

  // Print a message to the serial port
  Serial.println("Vancouver PCB Map v" + String(BUILD_NUMBER));

  // Configure the LEDs
  FastLED.addLeds<NEOPIXEL, PIN_LED_TRAIN>(leds, NUM_LEDS);
  FastLED.setBrightness(BRIGHTNESS);

  SetTrainStartingPosition(lineExpoNorthStationCount, TRAIN_COUNT, lineExpoNorthStationOffset);
  SetTrainStartingPosition(lineExpoSouthStationCount, TRAIN_COUNT, lineExpoSouthStationOffset);
  SetTrainStartingPosition(lineMillenniumEastWestStationCount, TRAIN_COUNT, lineMillenniumEastWestStationOffset);
  SetTrainStartingPosition(lineMillenniumWestEastStationCount, TRAIN_COUNT, lineMillenniumWestEastStationOffset);

  SetTrainStartingPosition(lineCanadaLineSouthNorthStationCount, TRAIN_COUNT, lineCanadaLineSouthNorthStationOffset);
  SetTrainStartingPosition(lineCanadaLineNorthSouthStationCount, TRAIN_COUNT, lineCanadaLineNorthSouthStationOffset);
}

void ProgressDemoTrain(int *line, int lineStationCount)
{
  for (int i = 0; i < TRAIN_COUNT; i++)
  {
    // If odd number, move in the positive direction
    // if even number, move in the negative direction
    if (i % 2 == 0)
    {
      line[i]++;
    }
    else
    {
      line[i]--;
    }

    if (line[i] >= lineStationCount)
    {
      line[i] = 0;
    }
    else if (line[i] < 0)
    {
      line[i] = lineStationCount;
    }
  }
}

void loop()
{
  // Flash the status LED
  EVERY_N_SECONDS(1)
  {
    Serial.println("Flip " + String(millis()));
    flipTheStatusLED();
  }

  EVERY_N_MILLISECONDS_I(DEMO_EXPO_NORTH, BASE_TRAIN_PROGRESS_SPEED + 100 )
  {
    ProgressDemoTrain(lineExpoNorthStationOffset, lineExpoNorthStationCount);
  }
  EVERY_N_MILLISECONDS_I(DEMO_EXPO_SOUTH, BASE_TRAIN_PROGRESS_SPEED + 120)
  {
    ProgressDemoTrain(lineExpoSouthStationOffset, lineExpoSouthStationCount);
  }
  EVERY_N_MILLISECONDS_I(DEMO_MILLENNIUM_EAST_WEST, BASE_TRAIN_PROGRESS_SPEED + 150)
  {
    ProgressDemoTrain(lineMillenniumEastWestStationOffset, lineMillenniumEastWestStationCount);
  }
  EVERY_N_MILLISECONDS_I(DEMO_MILLENNIUM_WEST_EAST, BASE_TRAIN_PROGRESS_SPEED + 170 )
  {
    ProgressDemoTrain(lineMillenniumWestEastStationOffset, lineMillenniumWestEastStationCount);
  }
  EVERY_N_MILLISECONDS_I(DEMO_CANADA_LINE_SOUTH_TO_NORTH, BASE_TRAIN_PROGRESS_SPEED + 250 )
  {
    ProgressDemoTrain(lineCanadaLineSouthNorthStationOffset, lineCanadaLineSouthNorthStationCount);
  }
  EVERY_N_MILLISECONDS_I(DEMO_CANADA_LINE_NORTH_TO_SOUTH, BASE_TRAIN_PROGRESS_SPEED + 270 )
  {
    ProgressDemoTrain(lineCanadaLineNorthSouthStationOffset, lineCanadaLineNorthSouthStationCount);
  }

  static bool seabusEnabled = true;
  EVERY_N_MILLISECONDS_I(DEMO_SEA_BUS, BASE_TRAIN_PROGRESS_SPEED )
  {
    seabusEnabled = !seabusEnabled;
  }

  EVERY_N_MILLISECONDS_I(FADE, 10)
  {
    fadeToBlackBy(leds, NUM_LEDS, 10);

    // Draw the trains
    for (int i = 0; i < TRAIN_COUNT; i++)
    {
      leds[LINE_EXPO_NORTH_OFFSET_TO_LED_INDEX[lineExpoNorthStationOffset[i]]] = CRGB::Red;
      leds[LINE_EXPO_SOUTH_OFFSET_TO_LED_INDEX[lineExpoSouthStationOffset[i]]] = CRGB::Orange ;

      leds[LINE_MILLENNIUM_EAST_WEST_OFFSET_TO_LED_INDEX[lineMillenniumEastWestStationOffset[i]]] = CRGB::LightBlue ;
      leds[LINE_MILLENNIUM_WEST_EAST_OFFSET_TO_LED_INDEX[lineMillenniumWestEastStationOffset[i]]] = CRGB::Blue ;

      leds[LINE_CANADA_LINE_SOUTH_TO_NORTH_OFFSET_TO_LED_INDEX[lineCanadaLineSouthNorthStationOffset[i]]] = CRGB::Yellow ;
      leds[LINE_CANADA_LINE_NORTH_TO_SOUTH_OFFSET_TO_LED_INDEX[lineCanadaLineNorthSouthStationOffset[i]]] = CRGB::Green ;

      if( seabusEnabled )
      {
        leds[LINE_SEABUS_LED_INDEX] = CRGB::Purple;
      } else {
        // 19, // North - Waterfront
        leds[19] = CRGB::Purple;
      }
    }
  }

  FastLED.show();
}
