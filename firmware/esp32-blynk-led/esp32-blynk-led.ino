/*
 * ESP32 Blynk IoT Node - remote LED / appliance control over Wi-Fi
 * ------------------------------------------------------------------
 * Data path:  Blynk web/mobile dashboard -> Blynk Cloud (TLS) -> ESP32 -> GPIO
 *
 * Datastreams (Blynk template "IOT LED"):
 *   V0  Switch   integer 0..1   user command (write)
 *   V1  LED      integer 0..1   state feedback shown on the dashboard (read)
 *
 * Security:
 *   - TLS to Blynk Cloud (BlynkSimpleEsp32_SSL.h), token never sent in cleartext
 *   - secrets kept out of source control (secrets.h is git-ignored)
 *
 * Reliability:
 *   - non-blocking connect (Blynk.config + Blynk.connect) instead of Blynk.begin
 *   - watchdog timer re-establishes Wi-Fi and cloud sessions every 10 s
 *   - BLYNK_CONNECTED() re-syncs the last commanded state after a reconnect
 *   - input validation: only 0/1 are accepted on V0
 *
 * Credentials live in secrets.h (git-ignored). Copy secrets.example.h first.
 * Board: "ESP32 Dev Module" | Library: Blynk >= 1.3.2
 */

#include "secrets.h"  // must define BLYNK_TEMPLATE_* before the Blynk headers

#define BLYNK_PRINT Serial
#include <WiFi.h>
// TLS transport (port 443). The plain <BlynkSimpleEsp32.h> header talks to
// blynk.cloud:80 in cleartext, exposing the auth token on the network.
#include <BlynkSimpleEsp32_SSL.h>

constexpr uint8_t LED_PIN = 2;                 // on-board LED / relay input
constexpr unsigned long WATCHDOG_MS = 10000UL;  // connection supervision period

BlynkTimer timer;

void applyState(int value) {
  digitalWrite(LED_PIN, value ? HIGH : LOW);
  Blynk.virtualWrite(V1, value);  // closed-loop feedback to the dashboard
  Serial.printf("[node] LED %s\n", value ? "ON" : "OFF");
}

BLYNK_WRITE(V0) {
  const int value = param.asInt();
  if (value != 0 && value != 1) {
    Serial.printf("[node] rejected invalid command: %d\n", value);
    return;
  }
  applyState(value);
}

BLYNK_CONNECTED() {
  Serial.println("[node] cloud session established, syncing state");
  Blynk.syncVirtual(V0);
}

void connectionWatchdog() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[node] Wi-Fi lost, reconnecting...");
    WiFi.reconnect();
    return;
  }
  if (!Blynk.connected()) {
    Serial.println("[node] Blynk cloud lost, reconnecting...");
    Blynk.connect(5000);
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);  // fail-safe default: OFF

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Blynk.config(BLYNK_AUTH_TOKEN);
  Blynk.connect(10000);

  timer.setInterval(WATCHDOG_MS, connectionWatchdog);
}

void loop() {
  if (Blynk.connected()) {
    Blynk.run();
  }
  timer.run();
}
