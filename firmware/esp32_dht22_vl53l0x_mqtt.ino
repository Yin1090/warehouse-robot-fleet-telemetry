/*
 * esp32_dht22_vl53l0x_mqtt.ino
 * Warehouse Robot Fleet Telemetry Node (R1)
 *
 * Sensors:
 *   - DHT22 temperature & humidity on GPIO 27
 *   - VL53L0X Time-of-Flight rangefinder on I2C (SDA/SCL)
 * Transport:
 *   - Wi-Fi STA + Authenticated MQTT (port 1883)
 *   - Status topic:    robot/R1/status
 *   - Telemetry topic: robot/R1/sensor/dht22
 *   - Cadence:         5000 ms
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <Adafruit_VL53L0X.h>
#include "DHT.h"
#include "secrets.h"

#define DHTPIN   27
#define DHTTYPE  DHT22
#define ROBOT_ID "R1"

static const unsigned long PUBLISH_INTERVAL_MS = 5000UL;
static const char* TOPIC_STATUS = "robot/R1/status";
static const char* TOPIC_DHT22  = "robot/R1/sensor/dht22";

WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);
DHT dht(DHTPIN, DHTTYPE);
Adafruit_VL53L0X lox;
bool vl53Ready = false;
unsigned long lastPublishMs = 0;

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) {
    return;
  }
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println(" connected.");
}

void connectMQTT() {
  while (!mqtt.connected()) {
    Serial.print("Connecting MQTT...");
    if (mqtt.connect("robot_R1", MQTT_USER, MQTT_PASSWORD)) {
      Serial.println(" connected.");
      mqtt.publish(TOPIC_STATUS, "online", true);
    } else {
      Serial.print(" failed, rc=");
      Serial.println(mqtt.state());
      delay(2000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  dht.begin();
  Wire.begin();

  if (lox.begin()) {
    vl53Ready = true;
    Serial.println("VL53L0X initialized.");
  } else {
    Serial.println("VL53L0X not detected; continuing with DHT22 only.");
  }

  connectWiFi();
  mqtt.setServer(MQTT_BROKER, MQTT_PORT);
  connectMQTT();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }
  if (!mqtt.connected()) {
    connectMQTT();
  }
  mqtt.loop();

  unsigned long now = millis();
  if (now - lastPublishMs < PUBLISH_INTERVAL_MS) {
    return;
  }
  lastPublishMs = now;

  float t = dht.readTemperature();
  float h = dht.readHumidity();
  if (isnan(t) || isnan(h)) {
    Serial.println("Error reading DHT22 sensor!");
    return;
  }

  int distanceMm = -1;
  if (vl53Ready) {
    VL53L0X_RangingMeasurementData_t measure;
    lox.rangingTest(&measure, false);
    if (measure.RangeStatus != 4) {
      distanceMm = static_cast<int>(measure.RangeMilliMeter);
    }
  }

  char payload[160];
  if (distanceMm >= 0) {
    snprintf(
        payload,
        sizeof(payload),
        "{\"robot_id\":\"%s\",\"sensor\":\"DHT22\",\"temp\":%.2f,\"hum\":%.2f,\"distance_mm\":%d}",
        ROBOT_ID, t, h, distanceMm);
  } else {
    snprintf(
        payload,
        sizeof(payload),
        "{\"robot_id\":\"%s\",\"sensor\":\"DHT22\",\"temp\":%.2f,\"hum\":%.2f}",
        ROBOT_ID, t, h);
  }

  Serial.println(payload);
  mqtt.publish(TOPIC_DHT22, payload);
}
