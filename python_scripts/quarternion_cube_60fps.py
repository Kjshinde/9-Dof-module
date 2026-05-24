# quat_cube_modern_gl.py

import argparse
import threading
import math
import serial
import time
import glfw
import moderngl
import numpy as np
from pyrr import Matrix44, Quaternion

# ─── CONFIG ─────────────────────────────────────────────────────────────────────
SERIAL_PORT = 'COM8'   # change to your port, e.g. '/dev/ttyUSB0'
BAUD_RATE   = 256000   # match this to your Arduino Serial.begin()

# Shared quaternion [w, x, y, z]
quat = [1.0, 0.0, 0.0, 0.0]
quat_lock = threading.Lock()
serial_stats = {
    "packets": 0,
    "last_recv_ns": None,
}

# ─── FLAT SHADERS ─────────────────────────────────────────────────────────────────
VERT_SHADER = '''
#version 330 core
in vec3 in_pos;
uniform mat4 mvp;
void main() {
    gl_Position = mvp * vec4(in_pos, 1.0);
}
'''
FRAG_SHADER = '''
#version 330 core
out vec4 f_color;
void main() {
    f_color = vec4(0.6, 0.2, 0.8, 1.0);
}
'''

# ─── CUBE VERTICES ────────────────────────────────────────────────────────────────
# 36 verts (12 tris) × 3 coords
vertices = np.array([
    # front
    -1,-1, 1,   1,-1, 1,   1, 1, 1,
    -1,-1, 1,   1, 1, 1,  -1, 1, 1,
    # back
     1,-1,-1,  -1,-1,-1,  -1, 1,-1,
     1,-1,-1,  -1, 1,-1,   1, 1,-1,
    # left
    -1,-1,-1,  -1,-1, 1,  -1, 1, 1,
    -1,-1,-1,  -1, 1, 1,  -1, 1,-1,
    # right
     1,-1, 1,   1,-1,-1,   1, 1,-1,
     1,-1, 1,   1, 1,-1,   1, 1, 1,
    # top
    -1, 1,-1,  -1, 1, 1,   1, 1, 1,
    -1, 1,-1,   1, 1, 1,   1, 1,-1,
    # bottom
    -1,-1,-1,   1,-1,-1,   1,-1, 1,
    -1,-1,-1,   1,-1, 1,  -1,-1, 1,
], dtype='f4')

# ─── SERIAL READER THREAD ────────────────────────────────────────────────────────
def serial_reader():
    global quat
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    while True:
        line = ser.readline().decode(errors='ignore').strip()
        if not line.startswith("Quat"):
            continue
        # Expect: "Quat → w:0.9924 x:-0.0473 y:-0.1140 z:-0.0020"
        parts = line.replace("Quat →", "").split()
        try:
            w = float(parts[0].split(":")[1])
            x = float(parts[1].split(":")[1])
            y = float(parts[2].split(":")[1])
            z = float(parts[3].split(":")[1])
            with quat_lock:
                quat = [w, x, y, z]
                serial_stats["packets"] += 1
                serial_stats["last_recv_ns"] = time.time_ns()
        except (IndexError, ValueError):
            pass


def get_quat():
    with quat_lock:
        return tuple(quat)


def get_stats_snapshot():
    with quat_lock:
        return dict(serial_stats)


def positive_float(value):
    number = float(value)
    if number <= 0.0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def parse_args():
    parser = argparse.ArgumentParser(
        description="Render the quaternion cube from the COM-port text stream."
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print render FPS, serial receive rate, and latest-packet age.",
    )
    parser.add_argument(
        "--stats-interval",
        type=positive_float,
        default=1.0,
        help="Seconds between --stats reports. Default: 1.0",
    )
    return parser.parse_args()


# ─── MAIN ────────────────────────────────────────────────────────────────────────
def main():
    args = parse_args()

    # start serial thread
    threading.Thread(target=serial_reader, daemon=True).start()

    # init glfw + GL context
    if not glfw.init():
        return
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, glfw.TRUE)

    window = glfw.create_window(640, 640, "Quat Cube", None, None)
    if not window:
        glfw.terminate()
        return
    glfw.make_context_current(window)
    ctx = moderngl.create_context()

    # compile & link shaders
    prog = ctx.program(vertex_shader=VERT_SHADER, fragment_shader=FRAG_SHADER)
    mvp_uniform = prog['mvp']

    # upload VBO + VAO
    vbo = ctx.buffer(vertices.tobytes())
    vao = ctx.vertex_array(prog, [(vbo, '3f', 'in_pos')])

    frame_count = 0
    last_stats_time = time.perf_counter()
    last_stats_packets = 0

    while not glfw.window_should_close(window):
        glfw.poll_events()
        ctx.clear(0.2, 0.2, 0.2)
        frame_count += 1

        # build projection & camera (static)
        proj = Matrix44.perspective_projection(45.0, 1.0, 0.1, 100.0)
        look = Matrix44.look_at(
            eye=(3, 3, 3), target=(0, 0, 0), up=(0, 1, 0)
        )

        # quaternion → rotation matrix
        w, x, y, z = get_quat()
        # Note: pyrr.Quaternion takes (x, y, z, w)
        q = Quaternion([x, y, z, w])
        rot = Matrix44.from_quaternion(q)

        # final MVP
        mvp = proj * look * rot
        mvp_uniform.write(mvp.astype('f4').tobytes())

        vao.render()
        glfw.swap_buffers(window)

        if args.stats:
            now = time.perf_counter()
            elapsed = now - last_stats_time
            if elapsed >= args.stats_interval:
                stats = get_stats_snapshot()
                packet_delta = stats["packets"] - last_stats_packets
                render_fps = frame_count / elapsed
                rx_hz = packet_delta / elapsed
                last_recv_ns = stats["last_recv_ns"]
                latest_age_ms = (
                    (time.time_ns() - last_recv_ns) / 1_000_000.0
                    if last_recv_ns is not None
                    else None
                )
                age_text = (
                    "n/a" if latest_age_ms is None else f"{latest_age_ms:.2f}"
                )
                print(
                    "serial cube stats "
                    f"render_fps:{render_fps:.1f} "
                    f"rx_hz:{rx_hz:.1f} "
                    f"latest_age_ms:{age_text} "
                    f"packets:{stats['packets']}",
                    flush=True,
                )

                frame_count = 0
                last_stats_time = now
                last_stats_packets = stats["packets"]

    glfw.terminate()

if __name__ == '__main__':
    main()
