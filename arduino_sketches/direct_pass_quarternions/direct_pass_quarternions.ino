#include <Wire.h>
#include <SparkFunLSM9DS1.h>
#include "MadgwickAHRS.h"      // your local copy with getQuaternion()

// IMU + filter
LSM9DS1   imu;
Madgwick  filter;

// Sync byte for framing
const uint8_t SYNC = 0xAA;

void setup() {
  Serial.begin(921600);    // keep high USB-Serial speed
  Wire.begin();

  if (!imu.begin()) {
    while (1);             // hang if IMU missing
  }
  imu.calibrate();         // optional bias calibration

  // Run filter at 400 Hz (IMU-only, no mag)
  filter.begin(400.0f);
}

void loop() {
  // 1) read accel + gyro
  if (imu.accelAvailable()) imu.readAccel();
  if (imu.gyroAvailable())  imu.readGyro();

  // 2) convert to physical units
  float ax = imu.calcAccel(imu.ax);
  float ay = imu.calcAccel(imu.ay);
  float az = imu.calcAccel(imu.az);

  float gx = imu.calcGyro(imu.gx) * DEG_TO_RAD;
  float gy = imu.calcGyro(imu.gy) * DEG_TO_RAD;
  float gz = imu.calcGyro(imu.gz) * DEG_TO_RAD;

  // 3) update the IMU‐only Madgwick filter
  filter.updateIMU(gx, gy, gz, ax, ay, az);

  // 4) pull out quaternion [w, x, y, z]
  float quat[4];
  filter.getQuaternion(quat);

  // 5) send framed packet (1-byte SYNC + 16-byte payload)
  Serial.write(SYNC);
  Serial.write(reinterpret_cast<uint8_t*>(quat), sizeof(quat));

  // 6) wait ~2.5 ms to match 400 Hz
  delayMicroseconds(2500);
}
