// Blink the onboard STAT LED on a SparkFun ESP32 Thing

const int LED_PIN = 5;  // STAT LED on GPIO 13

void setup() {
  pinMode(LED_PIN, OUTPUT);     // Configure the LED pin as an output
  Serial.begin(115200);         // (Optional) initialize serial for debug
  // while (!Serial);           // Uncomment if you want to wait for serial
}

void loop() {
  digitalWrite(LED_PIN, HIGH);  // LED on
  delay(1000);                  // wait 1 second
  digitalWrite(LED_PIN, LOW);   // LED off
  delay(1000);                  // wait 1 second
}
