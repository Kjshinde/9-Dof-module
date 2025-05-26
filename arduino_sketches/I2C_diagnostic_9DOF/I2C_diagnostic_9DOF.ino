#include <Wire.h>

void setup() {
  Serial.begin(115200);
  delay(1000);                     // give the USB-serial adapter a moment
  Serial.println("\nI²C Scanner"); // now you should see this in the monitor

  Wire.begin(21, 22);              // SDA = D21, SCL = D22
  Serial.println("Scanning 0x01–0x7E...");
  
  for (uint8_t addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    uint8_t err = Wire.endTransmission();
    if (err == 0) {
      Serial.print("→ Found device at 0x");
      if (addr < 16) Serial.print('0');
      Serial.println(addr, HEX);
    } else if (err == 4) {
      Serial.print("→ Unknown error at 0x");
      if (addr < 16) Serial.print('0');
      Serial.println(addr, HEX);
    }
    delay(5);  // small pause to give the bus time
  }

  Serial.println("Scan complete.");
}

void loop() {
  // nothing to do here
}
