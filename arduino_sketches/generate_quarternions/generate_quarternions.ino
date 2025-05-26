#include <Wire.h>
#include <SparkFunLSM9DS1.h>
#include <MadgwickAHRS.h>

LSM9DS1 imu;
Madgwick filter;

const float sampleRate = 119.0f;

void setup() {
  Serial.begin(256000);
  delay(500);
  Wire.begin(21, 22);
  if (!imu.begin()) {
    Serial.println("LSM9DS1 init failed!");
    while (1);
  }
  filter.begin(sampleRate);
}

void loop() {
  imu.readAccel();  imu.readGyro();

  float ax = imu.calcAccel(imu.ax),
        ay = imu.calcAccel(imu.ay),
        az = imu.calcAccel(imu.az);
  float gx = imu.calcGyro(imu.gx)*DEG_TO_RAD,
        gy = imu.calcGyro(imu.gy)*DEG_TO_RAD,
        gz = imu.calcGyro(imu.gz)*DEG_TO_RAD;

  filter.updateIMU(gx, gy, gz, ax, ay, az);

  // **Compute quaternion from Euler**
  float roll  = filter.getRollRadians();
  float pitch = filter.getPitchRadians();
  float yaw   = filter.getYawRadians();

  float cy = cos(yaw   * 0.5f), sy = sin(yaw   * 0.5f);
  float cp = cos(pitch * 0.5f), sp = sin(pitch * 0.5f);
  float cr = cos(roll  * 0.5f), sr = sin(roll  * 0.5f);

  float qw = cr*cp*cy + sr*sp*sy;
  float qx = sr*cp*cy - cr*sp*sy;
  float qy = cr*sp*cy + sr*cp*sy;
  float qz = cr*cp*sy - sr*sp*cy;

  // Serial.printf("Quat → w:%0.4f x:%0.4f y:%0.4f z:%0.4f\n",
  //               qw, qx, qy, qz);

  delay(16);
}
