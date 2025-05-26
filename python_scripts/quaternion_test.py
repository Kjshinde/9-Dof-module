# pip install pyserial vpython

import math
import serial
from vpython import canvas, box, vector, rate

# 1) Open your ESP32’s serial port (change 'COM3' to your port on Windows, or '/dev/ttyUSB0' on Linux/Mac)
ser = serial.Serial('COM8', 115200, timeout=1)

# 2) Set up the VPython 3D scene
scene = canvas(title="9DoF Cube", width=600, height=600, center=vector(0,0,0))
cube  = box(size=vector(2,2,2), color=vector(0.6,0.2,0.8))

def quaternion_to_axis_angle(w, x, y, z):
    """Convert unit quaternion → (angle, axis_vector)."""
    angle = 2 * math.acos(w)
    s = math.sqrt(1 - w*w)
    if s < 1e-6:
        # if too small, axis defaults to X
        return angle, vector(1,0,0)
    return angle, vector(x/s, y/s, z/s)

while True:
    rate(30)                           # cap to ~30 FPS
    line = ser.readline().decode().strip()
    if not line.startswith("Quat"):   # skip any non-quat lines
        continue

    # Example line: "Quat → w:0.9924 x:-0.0473 y:-0.1140 z:-0.0020"
    # Split and pull out the four floats:
    toks = line.replace("Quat →","").split()
    w = float(toks[0].split(":")[1])
    x = float(toks[1].split(":")[1])
    y = float(toks[2].split(":")[1])
    z = float(toks[3].split(":")[1])

    angle, axis = quaternion_to_axis_angle(w, x, y, z)

    # Reset cube orientation to identity before re-rotating
    cube.axis = vector(1,0,0)
    cube.up   = vector(0,1,0)
    # Apply new rotation
    cube.rotate(angle=angle, axis=axis, origin=vector(0,0,0))
