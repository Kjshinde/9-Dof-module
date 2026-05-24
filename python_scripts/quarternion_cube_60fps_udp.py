# quat_cube_modern_gl_udp.py

import argparse
import re
import socket
import threading
import time

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
latest_sample = {
    "quat": tuple(quat),
    "seq": None,
    "sent_ns": None,
    "pose": None,
    "pose_ns": None,
    "recv_ns": None,
}
receiver_stats = {
    "packets": 0,
    "dropped": 0,
    "last_seq": None,
    "latency_count": 0,
    "latency_sum_ms": 0.0,
    "latency_max_ms": 0.0,
    "last_pose": None,
    "last_pose_latency_ms": None,
}

QUAT_LINE_RE = re.compile(
    r"\bw\s*:\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)\s+"
    r"x\s*:\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)\s+"
    r"y\s*:\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)\s+"
    r"z\s*:\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)"
)
TOKEN_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([^\s]+)")

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
        sample = {"quat": [float(value) for value in match.groups()]}
    except ValueError:
        return None

    for key, value in TOKEN_RE.findall(line):
        if key in {"seq", "sent_ns", "pose", "pose_ns"}:
            try:
                sample[key] = int(value)
            except ValueError:
                pass

    return sample


def set_sample(sample):
    global latest_sample, quat
    recv_ns = time.time_ns()
    next_quat = sample["quat"]

    with quat_lock:
        quat = next_quat
        latest_sample = {
            "quat": tuple(next_quat),
            "seq": sample.get("seq"),
            "sent_ns": sample.get("sent_ns"),
            "pose": sample.get("pose"),
            "pose_ns": sample.get("pose_ns"),
            "recv_ns": recv_ns,
        }

        receiver_stats["packets"] += 1

        seq = sample.get("seq")
        last_seq = receiver_stats["last_seq"]
        if seq is not None:
            if last_seq is not None and seq > last_seq + 1:
                receiver_stats["dropped"] += seq - last_seq - 1
            receiver_stats["last_seq"] = seq

        sent_ns = sample.get("sent_ns")
        if sent_ns is not None:
            latency_ms = (recv_ns - sent_ns) / 1_000_000.0
            if latency_ms >= 0.0:
                receiver_stats["latency_count"] += 1
                receiver_stats["latency_sum_ms"] += latency_ms
                receiver_stats["latency_max_ms"] = max(
                    receiver_stats["latency_max_ms"], latency_ms
                )

        pose = sample.get("pose")
        if pose is not None and pose != receiver_stats["last_pose"]:
            receiver_stats["last_pose"] = pose
            pose_ns = sample.get("pose_ns")
            if pose_ns is not None:
                receiver_stats["last_pose_latency_ms"] = (
                    recv_ns - pose_ns
                ) / 1_000_000.0


def get_quat():
    with quat_lock:
        return tuple(quat)


def get_stats_snapshot():
    with quat_lock:
        return dict(latest_sample), dict(receiver_stats)


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
            sample = parse_quaternion_line(line.strip())
            if sample is not None:
                set_sample(sample)


def positive_float(value):
    number = float(value)
    if number <= 0.0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


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
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print render, receive-rate, packet-age, and latency diagnostics.",
    )
    parser.add_argument(
        "--stats-interval",
        type=positive_float,
        default=1.0,
        help="Seconds between --stats reports. Default: 1.0",
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

        if args.stats:
            now = time.perf_counter()
            elapsed = now - last_stats_time
            if elapsed >= args.stats_interval:
                sample, stats = get_stats_snapshot()
                packets = stats["packets"]
                packet_delta = packets - last_stats_packets
                render_fps = frame_count / elapsed
                rx_hz = packet_delta / elapsed
                recv_ns = sample.get("recv_ns")
                latest_age_ms = (
                    (time.time_ns() - recv_ns) / 1_000_000.0
                    if recv_ns is not None
                    else None
                )
                latency_count = stats["latency_count"]
                avg_latency_ms = (
                    stats["latency_sum_ms"] / latency_count
                    if latency_count
                    else None
                )

                def ms_text(value):
                    return "n/a" if value is None else f"{value:.2f}"

                print(
                    "cube stats "
                    f"render_fps:{render_fps:.1f} "
                    f"rx_hz:{rx_hz:.1f} "
                    f"latest_age_ms:{ms_text(latest_age_ms)} "
                    f"avg_rx_latency_ms:{ms_text(avg_latency_ms)} "
                    f"max_rx_latency_ms:{stats['latency_max_ms']:.2f} "
                    "last_pose_latency_ms:"
                    f"{ms_text(stats['last_pose_latency_ms'])} "
                    f"dropped:{stats['dropped']} "
                    f"seq:{sample.get('seq')} "
                    f"pose:{sample.get('pose')}",
                    flush=True,
                )

                frame_count = 0
                last_stats_time = now
                last_stats_packets = packets

    glfw.terminate()


if __name__ == '__main__':
    main()
