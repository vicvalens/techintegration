// Arduino Sensor Data Streamer
// Sensor connected to A0
// Output format: time_ms,sensor_value,state

const int sensorPin = A0;

const int LOW_THRESHOLD = 350;
const int HIGH_THRESHOLD = 700;

void setup() {
  Serial.begin(9600);
  Serial.println("time_ms,sensor_value,state");
}

void loop() {
  unsigned long timeMs = millis();
  int sensorValue = analogRead(sensorPin);

  String state;

  if (sensorValue < LOW_THRESHOLD) {
    state = "LOW";
  } 
  else if (sensorValue < HIGH_THRESHOLD) {
    state = "MEDIUM";
  } 
  else {
    state = "HIGH";
  }

  Serial.print(timeMs);
  Serial.print(",");
  Serial.print(sensorValue);
  Serial.print(",");
  Serial.println(state);

  delay(100);
}