// Multiplatform ESP32 Sensor Streamer
// Sensor -> ESP32 -> Serial CSV + Local Wi-Fi JSON Server
//
// Serial output for Python/Flet:
// time_ms,raw_value,percent,state,indicator
//
// Web/App endpoint:
// http://ESP32_IP/data
//
// JSON output:
// {
//   "time_ms": 12345,
//   "raw": 2450,
//   "percent": 60,
//   "state": "MEDIUM",
//   "indicator": "Pressure Load Index"
// }

#include <WiFi.h>
#include <WebServer.h>

// -------------------------
// Wi-Fi settings
// -------------------------
const char* ssid = "YOUR_WIFI_NAME";
const char* password = "YOUR_WIFI_PASSWORD";

// -------------------------
// Sensor settings
// -------------------------
// Use an ADC pin on ESP32.
// Common analog input pins: 32, 33, 34, 35, 36, 39
// GPIO34 is input-only and good for analog sensors.
const int SENSOR_PIN = 34;

// ESP32 analog range is usually 0–4095
const int ANALOG_MIN = 0;
const int ANALOG_MAX = 4095;

// Thresholds in percentage
const int LOW_THRESHOLD_PERCENT = 35;
const int HIGH_THRESHOLD_PERCENT = 70;

// Change this depending on the project
String indicatorName = "Pressure Load Index";
// Other examples:
// "Flexion Range Index"
// "EMG Effort Index"
// "Arousal Index"
// "Activity Index"
// "Stability Index"

// -------------------------
// Server
// -------------------------
WebServer server(80);

// -------------------------
// Timing
// -------------------------
unsigned long lastSerialPrint = 0;
const unsigned long SERIAL_INTERVAL_MS = 100;

// -------------------------
// Current sensor data
// -------------------------
unsigned long timeMs = 0;
int rawValue = 0;
int percentValue = 0;
String state = "LOW";

void readSensor() {
  timeMs = millis();

  rawValue = analogRead(SENSOR_PIN);

  percentValue = map(rawValue, ANALOG_MIN, ANALOG_MAX, 0, 100);
  percentValue = constrain(percentValue, 0, 100);

  if (percentValue < LOW_THRESHOLD_PERCENT) {
    state = "LOW";
  } 
  else if (percentValue < HIGH_THRESHOLD_PERCENT) {
    state = "MEDIUM";
  } 
  else {
    state = "HIGH";
  }
}

void printSerialCSV() {
  // Format:
  // time_ms,raw_value,percent,state,indicator

  Serial.print(timeMs);
  Serial.print(",");
  Serial.print(rawValue);
  Serial.print(",");
  Serial.print(percentValue);
  Serial.print(",");
  Serial.print(state);
  Serial.print(",");
  Serial.println(indicatorName);
}

void handleData() {
  readSensor();

  String json = "{";
  json += "\"time_ms\":" + String(timeMs) + ",";
  json += "\"raw\":" + String(rawValue) + ",";
  json += "\"percent\":" + String(percentValue) + ",";
  json += "\"state\":\"" + state + "\",";
  json += "\"indicator\":\"" + indicatorName + "\"";
  json += "}";

  // Allows webpage/app requests from another local address
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "application/json", json);
}

void handleRoot() {
  String html = "";
  html += "<!DOCTYPE html><html><head>";
  html += "<meta name='viewport' content='width=device-width, initial-scale=1.0'>";
  html += "<title>ESP32 Sensor Streamer</title>";
  html += "<style>";
  html += "body{font-family:Arial;background:#f4f4f4;padding:30px;}";
  html += ".card{background:white;padding:24px;border-radius:18px;max-width:500px;box-shadow:0 10px 30px rgba(0,0,0,.1);}";
  html += "h1{margin-top:0;} .value{font-size:56px;font-weight:bold;} .state{font-size:26px;margin-top:10px;}";
  html += "</style></head><body>";
  html += "<div class='card'>";
  html += "<h1>ESP32 Sensor Streamer</h1>";
  html += "<p>Open <strong>/data</strong> to get JSON data.</p>";
  html += "<p>Example: <code>http://";
  html += WiFi.localIP().toString();
  html += "/data</code></p>";
  html += "</div>";
  html += "</body></html>";

  server.send(200, "text/html", html);
}

void setup() {
  Serial.begin(9600);

  delay(1000);

  Serial.println("Multiplatform ESP32 Sensor Streamer");
  Serial.println("Connecting to Wi-Fi...");

  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.println("Wi-Fi connected.");
  Serial.print("ESP32 IP address: ");
  Serial.println(WiFi.localIP());

  Serial.println("Serial CSV format:");
  Serial.println("time_ms,raw_value,percent,state,indicator");

  server.on("/", handleRoot);
  server.on("/data", handleData);

  server.begin();

  Serial.println("Local server started.");
}

void loop() {
  server.handleClient();

  readSensor();

  if (millis() - lastSerialPrint >= SERIAL_INTERVAL_MS) {
    lastSerialPrint = millis();
    printSerialCSV();
  }
}