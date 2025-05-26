# imu_wireframe_cube_event.py

import sys, struct, threading
import serial
from serial.threaded import ReaderThread, Protocol
import pygame
from pygame.locals import DOUBLEBUF, OPENGL, QUIT, KEYDOWN, K_ESCAPE
from OpenGL.GL import *
from OpenGL.GLU import gluPerspective

# ─── Configuration ────────────────────────────────────────
PORT      = 'COM8'      # change to your COM port
BAUD      = 921600
SYNC      = 0xAA        # 1-byte header
FRAME_SZ  = 1 + 16      # header + 4 floats

# ─── Shared Quaternion State ─────────────────────────────
current_quat = [1.0, 0.0, 0.0, 0.0]
_quat_lock   = threading.Lock()

# ─── Serial Protocol ──────────────────────────────────────
class QuatProtocol(Protocol):
    def __init__(self):
        super().__init__()
        self.buffer = bytearray()

    def data_received(self, data):
        # append new data
        self.buffer.extend(data)
        # parse all complete frames
        while len(self.buffer) >= FRAME_SZ:
            if self.buffer[0] != SYNC:
                # skip until we find sync header
                self.buffer.pop(0)
                continue
            # extract payload
            packet = self.buffer[1:FRAME_SZ]
            del self.buffer[:FRAME_SZ]
            # unpack floats
            w, x, y, z = struct.unpack('<4f', packet)
            # update shared quaternion
            with _quat_lock:
                current_quat[0] = w
                current_quat[1] = x
                current_quat[2] = y
                current_quat[3] = z

# ─── Wireframe Cube ───────────────────────────────────────
vertices = (
    (-1,-1,-1),(-1,-1,1),(-1,1,1),(-1,1,-1),
    (1,-1,-1),(1,-1,1),(1,1,1),(1,1,-1),
)
edges = (
    (0,1),(1,2),(2,3),(3,0),
    (4,5),(5,6),(6,7),(7,4),
    (0,4),(1,5),(2,6),(3,7),
)

def draw_wire_cube():
    glBegin(GL_LINES)
    glColor3f(1,1,1)
    for e in edges:
        for v in e:
            glVertex3fv(vertices[v])
    glEnd()

def quat_to_matrix(w, x, y, z):
    return [
        1-2*(y*y+z*z),   2*(x*y - z*w), 2*(x*z + y*w), 0,
        2*(x*y + z*w),   1-2*(x*x+z*z), 2*(y*z - x*w), 0,
        2*(x*z - y*w),   2*(y*z + x*w), 1-2*(x*x+y*y), 0,
        0,                0,              0,             1,
    ]

# ─── Main ────────────────────────────────────────────────
def main():
    # (1) Start the serial ReaderThread
    ser = serial.Serial(PORT, BAUD, timeout=0)
    reader = ReaderThread(ser, QuatProtocol)
    reader.start()

    # (2) Init Pygame + OpenGL
    pygame.init()
    screen = pygame.display.set_mode((800,600), DOUBLEBUF|OPENGL)
    pygame.display.set_caption("Wireframe Cube ▶ IMU Quaternion (Event-Driven)")

    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(45, 800/600, 0.1, 100.0)
    glMatrixMode(GL_MODELVIEW)
    glEnable(GL_DEPTH_TEST)

    clock = pygame.time.Clock()

    # (3) Render loop
    running = True
    while running:
        for evt in pygame.event.get():
            if evt.type in (QUIT, KEYDOWN) and getattr(evt, 'key', None)==K_ESCAPE:
                running = False

        # grab latest quaternion
        with _quat_lock:
            w, x, y, z = current_quat

        # clear & reset
        glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        glTranslatef(0,0,-5)

        # apply rotation
        mat = quat_to_matrix(w, x, y, z)
        glMultMatrixf(mat)

        draw_wire_cube()

        pygame.display.flip()
        clock.tick(60)

    # cleanup
    reader.close()
    ser.close()
    pygame.quit()

if __name__ == "__main__":
    main()
