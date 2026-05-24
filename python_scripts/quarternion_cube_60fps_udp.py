# quat_cube_modern_gl_udp.py

import argparse
import re
import socket
import threading

import glfw
import moderngl
import numpy as np
from pyrr import Matrix44, Quaternion

# CONFIG
UDP_HOST = "127.0.0.1"
UDP_PORT = 5005
RECV_TIMEOUT_SECONDS = 0.25

# Shared quaternion [w, x, y, z]
quat = [1.0, 0.0, 0.0, 0.0]
quat_lock = threading.Lock()

QUAT_LINE_RE = re.compile(
    r"\bw\s*:\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)\s+"
    r"x\s*:\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)\s+"
    r"y\s*:\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)\s+"
    r"z\s*:\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)"
)

# FLAT SHADERS
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

# CUBE VERTICES
# 36 verts (12 tris) x 3 coords
vertices = np.array([
    # front
    -1, -1, 1,   1, -1, 1,   1, 1, 1,
    -1, -1, 1,   1, 1, 1,  -1, 1, 1,
    # back
     1, -1, -1,  -1, -1, -1,  -1, 1, -1,
     1, -1, -1,  -1, 1, -1,   1, 1, -1,
    # left
    -1, -1, -1,  -1, -1, 1,  -1, 1, 1,
    -1, -1, -1,  -1, 1, 1,  -1, 1, -1,
    # right
     1, -1, 1,   1, -1, -1,   1, 1, -1,
     1, -1, 1,   1, 1, -1,   1, 1, 1,
    # top
    -1, 1, -1,  -1, 1, 1,   1, 1, 1,
    -1, 1, -1,   1, 1, 1,   1, 1, -1,
    # bottom
    -1, -1, -1,   1, -1, -1,   1, -1, 1,
    -1, -1, -1,   1, -1, 1,  -1, -1, 1,
], dtype='f4')


def parse_quaternion_line(line):
    """Parse the same text frame produced by the Arduino serial sketch."""
    if not line.startswith("Quat"):
        return None

    match = QUAT_LINE_RE.search(line)
    if not match:
        return None

    try:
        return [float(value) for value in match.groups()]
    except ValueError:
        return None


def set_quat(next_quat):
    global quat
    with quat_lock:
        quat = next_quat


def get_quat():
    with quat_lock:
        return tuple(quat)


def udp_quaternion_reader(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, port))
    sock.settimeout(RECV_TIMEOUT_SECONDS)
    print(f"Listening for quaternion UDP packets on {host}:{port}")

    while True:
        try:
            payload, _addr = sock.recvfrom(4096)
        except socket.timeout:
            continue

        text = payload.decode("utf-8", errors="ignore")
        for line in text.splitlines():
            next_quat = parse_quaternion_line(line.strip())
            if next_quat is not None:
                set_quat(next_quat)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Render the quaternion cube using data from another local script "
            "instead of a COM port."
        )
    )
    parser.add_argument(
        "--host",
        default=UDP_HOST,
        help=f"UDP host/interface to bind. Default: {UDP_HOST}",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=UDP_PORT,
        help=f"UDP port to listen on. Default: {UDP_PORT}",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Start local script data receiver.
    threading.Thread(
        target=udp_quaternion_reader,
        args=(args.host, args.port),
        daemon=True,
    ).start()

    # init glfw + GL context
    if not glfw.init():
        return
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, glfw.TRUE)

    window = glfw.create_window(640, 640, "Quat Cube - UDP Source", None, None)
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

    while not glfw.window_should_close(window):
        glfw.poll_events()
        ctx.clear(0.2, 0.2, 0.2)

        # build projection & camera (static)
        proj = Matrix44.perspective_projection(45.0, 1.0, 0.1, 100.0)
        look = Matrix44.look_at(
            eye=(3, 3, 3), target=(0, 0, 0), up=(0, 1, 0)
        )

        # quaternion to rotation matrix
        w, x, y, z = get_quat()
        # Note: pyrr.Quaternion takes (x, y, z, w)
        q = Quaternion([x, y, z, w])
        rot = Matrix44.from_quaternion(q)

        # final MVP
        mvp = proj * look * rot
        mvp_uniform.write(mvp.astype('f4').tobytes())

        vao.render()
        glfw.swap_buffers(window)

    glfw.terminate()


if __name__ == '__main__':
    main()
