# 9-DoF IMU Quaternion Module

This repository contains Arduino sketches and Python visualization tools for a
SparkFun ESP32 Thing connected to an LSM9DS1 9-DoF IMU. The main workflow is:

1. Verify the ESP32 with the blink sketch.
2. Verify the LSM9DS1 is visible on I2C.
3. Stream IMU-derived quaternions from the ESP32.
4. Visualize the orientation as a rotating 3D cube on the host computer.

Several paths and filenames currently use `quarternion`/`quartenion` spelling;
the README keeps those names as-is so commands match the repo.

## Hardware Assumptions

- SparkFun ESP32 Thing or a compatible ESP32 board.
- SparkFun LSM9DS1 9-DoF IMU.
- I2C wiring:
  - `3.3V` to sensor `VCC`
  - `GND` to sensor `GND`
  - ESP32 `GPIO 21` to sensor `SDA`
  - ESP32 `GPIO 22` to sensor `SCL`
- Use 3.3 V logic/power for the LSM9DS1.

## Repository Layout

```text
.
+-- arduino_sketches/
|   +-- sp_esp32_thing_blink/
|   |   +-- sp_esp32_thing_blink.ino
|   +-- I2C_diagnostic_9DOF/
|   |   +-- I2C_diagnostic_9DOF.ino
|   +-- generate_quarternions/
|   |   +-- generate_quarternions.ino
|   +-- direct_pass_quarternions/
|       +-- direct_pass_quarternions.ino
|       +-- MadgwickAHRS.cpp
|       +-- MadgwickAHRS.h
|       +-- libraries/
+-- python_scripts/
|   +-- direct_quartenion.py
|   +-- quarternion_cube_60fps.py
|   +-- quarternion_cube_60fps_udp.py
|   +-- quaternion_test.py
|   +-- simulated_quaternion_source.py
+-- requirements.txt
```

## Python Setup

Create a virtual environment and install the Python dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The visualizers use OpenGL, so you may also need platform OpenGL/graphics
drivers installed. The ModernGL visualizers use `#version 330 core` shaders and
request an OpenGL 3.3 core profile through GLFW. On macOS, serial ports usually
look like `/dev/cu.usbserial-*` or `/dev/cu.SLAB_USBtoUART`; on Windows they
look like `COM8`. Update the serial port constants in the scripts before
running them.

## Arduino Setup

Install or make available these Arduino libraries:

- SparkFun LSM9DS1 Arduino Library
- Madgwick AHRS

The `direct_pass_quarternions` sketch also includes a local modified
`MadgwickAHRS.h/.cpp` with `getQuaternion(float *q)`. If the Arduino IDE cannot
resolve the bundled libraries under
`arduino_sketches/direct_pass_quarternions/libraries`, install them through the
Arduino Library Manager or copy the bundled folders into your Arduino
`libraries` directory.

Select the ESP32 board and the correct upload port in the Arduino IDE, then use
the sketches in the order below.

## Validation Flow

### 1. Blink Test

Upload:

```text
arduino_sketches/sp_esp32_thing_blink/sp_esp32_thing_blink.ino
```

This toggles `LED_PIN = 5` once per second and starts serial at `115200`. It is
a basic board/upload check.

Note: the sketch comment says the STAT LED is on GPIO 13, but the code uses
GPIO 5. If the LED does not blink, confirm the LED pin for the exact ESP32 Thing
revision you are using.

### 2. I2C Scanner

Upload:

```text
arduino_sketches/I2C_diagnostic_9DOF/I2C_diagnostic_9DOF.ino
```

Open the Serial Monitor at `115200`. The sketch scans addresses `0x01` through
`0x7E` using `Wire.begin(21, 22)`. A working LSM9DS1 should appear as one or
more discovered I2C devices.

### 3. Quaternion Streaming

There are two quaternion stream styles in the repo.

#### Text quaternion stream

Sketch:

```text
arduino_sketches/generate_quarternions/generate_quarternions.ino
```

This sketch reads accelerometer and gyro values, updates a Madgwick IMU filter,
computes quaternion values from roll/pitch/yaw, and is set up to print lines
that begin with `Quat` and contain `w:`, `x:`, `y:`, and `z:` values.

Important: the `Serial.printf(...)` line is currently commented out in the
sketch. Uncomment it before using text-based Python visualizers. The Python
text parsers currently expect the same right-arrow glyph used in the commented
Arduino print statement; if you change the printed prefix, update the parsers
too.

Defaults:

- Serial baud: `256000`
- I2C pins: `SDA = 21`, `SCL = 22`
- Filter sample rate: `119 Hz`
- Loop delay: `16 ms`

Compatible Python scripts:

- `python_scripts/quarternion_cube_60fps.py`
- `python_scripts/quaternion_test.py`

#### Binary framed quaternion stream

Sketch:

```text
arduino_sketches/direct_pass_quarternions/direct_pass_quarternions.ino
```

This sketch reads accelerometer and gyro values, updates a Madgwick IMU filter,
gets the filter quaternion directly, and writes binary frames:

```text
0xAA + 4 little-endian float32 values: w, x, y, z
```

Defaults:

- Serial baud: `921600`
- Sync byte: `0xAA`
- Payload size: `16 bytes`
- Frame size: `17 bytes`
- Filter sample rate: `400 Hz`
- Loop delay: `2500 us`

Compatible Python script:

- `python_scripts/direct_quartenion.py`

## Python Visualizers

### Binary serial cube

Use this with `direct_pass_quarternions.ino`:

```bash
python python_scripts/direct_quartenion.py
```

Before running, edit these constants in `direct_quartenion.py`:

```python
PORT = 'COM8'
BAUD = 921600
```

The script reads framed binary quaternion packets and renders a wireframe cube
with Pygame and PyOpenGL.

### Text serial ModernGL cube

Use this with the text stream from `generate_quarternions.ino`:

```bash
python python_scripts/quarternion_cube_60fps.py
```

Before running, edit:

```python
SERIAL_PORT = 'COM8'
BAUD_RATE = 256000
```

The script expects lines beginning with `Quat` and renders a shaded cube with
GLFW/ModernGL. It explicitly requests an OpenGL 3.3 core, forward-compatible
context before creating the window.

### VPython text serial cube

Use this with the text stream from `generate_quarternions.ino`:

```bash
python python_scripts/quaternion_test.py
```

Before running, edit the serial port and baud in the script. The current script
uses `COM8` at `115200`, so make that match the Arduino sketch you uploaded.

### Simulated UDP cube

You can test the ModernGL cube without hardware by running the UDP receiver and
simulator in two terminals.

Terminal 1:

```bash
python python_scripts/quarternion_cube_60fps_udp.py
```

Terminal 2:

```bash
python python_scripts/simulated_quaternion_source.py --print
```

Defaults:

- UDP host: `127.0.0.1`
- UDP port: `5005`
- Simulation rate: about `62.5 Hz`

Both scripts accept `--host` and `--port` if you need to change the UDP
endpoint. The simulator also supports `--rate-hz` and `--duration`.

## Code Review Notes

- `generate_quarternions.ino` computes text quaternion output but does not emit
  it until the `Serial.printf(...)` line is uncommented.
- `quaternion_test.py` currently opens `COM8` at `115200`, while
  `generate_quarternions.ino` uses `256000`. Match those values before using
  them together.
- Both Arduino quaternion sketches multiply `imu.calcGyro(...)` by
  `DEG_TO_RAD` before calling `filter.updateIMU(...)`. The bundled
  `MadgwickAHRS.cpp` also converts gyro inputs from degrees/sec to radians/sec
  inside `updateIMU(...)`. If you use this bundled implementation, pass the
  `calcGyro(...)` values directly or confirm the expected units for the exact
  Madgwick library version you compile against.
- The blink sketch has a pin/comment mismatch: the code uses `LED_PIN = 5`,
  while the comment mentions GPIO 13.
- The Python serial scripts hard-code `COM8`. Change this to the active port on
  the host machine before running.
- The ModernGL scripts request an OpenGL 3.3 core profile, which matches their
  shader version. If a machine cannot create that context, use the Pygame or
  VPython visualizer path instead.

## Troubleshooting

- If no I2C devices are found, re-check `3.3V`, `GND`, `SDA`, and `SCL`, and
  make sure the scanner is using GPIO 21/22.
- If a serial visualizer shows a static cube, confirm the Arduino sketch and
  Python script use the same protocol and baud rate.
- If text visualizers do not update, confirm `Serial.printf(...)` is uncommented
  in `generate_quarternions.ino`.
- If the binary visualizer does not update, confirm the ESP32 is running
  `direct_pass_quarternions.ino` and the Python script is using `921600` baud.
- If the OpenGL window fails to start, verify that `glfw`, `moderngl`, `pygame`,
  and `PyOpenGL` installed successfully and that the machine can create an
  OpenGL 3.3 core context.

## Current Task Checklist

- [x] Blink sketch exists for ESP32 upload/LED checks.
- [x] I2C diagnostic sketch exists for the 9-DoF sensor.
- [x] Quaternion-generation sketches exist.
- [x] Python cube visualizers exist.
- [x] Simulated UDP quaternion source exists for hardware-free visualization
  tests.
- [ ] Physically verify the ESP32 upload path with the blink sketch.
- [ ] Confirm the physical ESP32 LED pin for the exact board revision.
- [ ] Confirm the detected LSM9DS1 I2C addresses on the wired hardware.
- [ ] Confirm and fix the gyro unit conversion before relying on orientation
  accuracy.
- [ ] Decide whether the project should standardize on text serial,
  binary serial, or both.
