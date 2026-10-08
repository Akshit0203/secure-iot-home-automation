/*
 * Smart Light Automation - Arduino UNO R4 WiFi
 * --------------------------------------------
 * An LDR in a voltage divider on A0 measures ambient light. At night the relay
 * switches an AC bulb ON; during the day it is switched OFF.
 *
 * Hysteresis: separate ON/OFF thresholds stop the relay from chattering when
 * the light level hovers around a single set point (dusk / dawn).
 *
 * The relay module is active-LOW (IN=LOW energises the coil -> bulb ON).
 * !! The relay switches MAINS VOLTAGE - insulate all high-voltage terminals.
 *
 * Calibrate the thresholds with the Serial Plotter (9600 baud).
 */

constexpr uint8_t LDR_PIN = A0;
constexpr uint8_t RELAY_PIN = 8;

constexpr int DARK_THRESHOLD = 25;   // reading <= this -> night  -> bulb ON
constexpr int LIGHT_THRESHOLD = 35;  // reading >= this -> day    -> bulb OFF
constexpr unsigned long SAMPLE_MS = 100;

bool bulbOn = false;

void setBulb(bool on) {
  bulbOn = on;
  digitalWrite(RELAY_PIN, on ? LOW : HIGH);  // active-LOW relay
}

void setup() {
  Serial.begin(9600);
  pinMode(LDR_PIN, INPUT);
  pinMode(RELAY_PIN, OUTPUT);
  setBulb(false);
}

void loop() {
  const int light = analogRead(LDR_PIN);

  if (!bulbOn && light <= DARK_THRESHOLD) {
    setBulb(true);
  } else if (bulbOn && light >= LIGHT_THRESHOLD) {
    setBulb(false);
  }

  Serial.print("light:");
  Serial.print(light);
  Serial.print(" bulb:");
  Serial.println(bulbOn ? 1 : 0);
  delay(SAMPLE_MS);
}
