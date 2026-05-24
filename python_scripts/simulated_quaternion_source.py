# simulated_quaternion_source.py

import argparse
import math
import socket
import time

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5005
DEFAULT_RATE_HZ = 1000.0 / 16.0
STEP_INTERVAL_SECONDS = 0.75
NS_PER_SECOND = 1_000_000_000
STEP_POSES_DEGREES = (
    (0.0, 0.0, 0.0),
    (70.0, 0.0, 0.0),
    (-70.0, 25.0, 0.0),
    (0.0, -55.0, 90.0),
    (45.0, 45.0, -120.0),
    (-35.0, -45.0, 170.0),
    (85.0, -15.0, -45.0),
    (0.0, 60.0, 135.0),
)


def quaternion_from_euler(roll, pitch, yaw):
    """Match the Euler-to-quaternion math used in the Arduino sketch."""
    cy = math.cos(yaw * 0.5)
    sy = math.sin(yaw * 0.5)
    cp = math.cos(pitch * 0.5)
    sp = math.sin(pitch * 0.5)
    cr = math.cos(roll * 0.5)
    sr = math.sin(roll * 0.5)

    qw = cr * cp * cy + sr * sp * sy
    qx = sr * cp * cy - cr * sp * sy
    qy = cr * sp * cy + sr * cp * sy
    qz = cr * cp * sy - sr * sp * cy

    return qw, qx, qy, qz


def smooth_simulated_orientation(elapsed_seconds):
    """Generate a smooth, IMU-like orientation that keeps the cube moving."""
    roll = math.radians(35.0) * math.sin(elapsed_seconds * 0.9)
    pitch = math.radians(25.0) * math.sin(elapsed_seconds * 0.55 + 0.8)
    yaw = elapsed_seconds * 0.7
    return quaternion_from_euler(roll, pitch, yaw)


def stepped_pose(elapsed_seconds):
    pose_index = int(elapsed_seconds / STEP_INTERVAL_SECONDS)
    return pose_index, STEP_POSES_DEGREES[pose_index % len(STEP_POSES_DEGREES)]


def simulated_orientation(elapsed_seconds):
    """Generate abrupt pose changes to test how quickly the cube responds."""
    _pose_index, (roll_deg, pitch_deg, yaw_deg) = stepped_pose(elapsed_seconds)

    return quaternion_from_euler(
        math.radians(roll_deg),
        math.radians(pitch_deg),
        math.radians(yaw_deg),
    )


def format_quaternion_line(
    quat,
    seq=None,
    sent_ns=None,
    pose=None,
    pose_ns=None,
):
    w, x, y, z = quat
    metadata = []
    if seq is not None:
        metadata.append(f"seq:{seq}")
    if sent_ns is not None:
        metadata.append(f"sent_ns:{sent_ns}")
    if pose is not None:
        metadata.append(f"pose:{pose}")
    if pose_ns is not None:
        metadata.append(f"pose_ns:{pose_ns}")

    metadata_text = " ".join(metadata)
    if metadata_text:
        metadata_text += " "

    return f"Quat → {metadata_text}w:{w:.4f} x:{x:.4f} y:{y:.4f} z:{z:.4f}"


def positive_float(value):
    number = float(value)
    if number <= 0.0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Generate simulated quaternion values at the same 16 ms cadence "
            "as the Arduino COM-port stream."
        )
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"UDP destination host. Default: {DEFAULT_HOST}",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"UDP destination port. Default: {DEFAULT_PORT}",
    )
    parser.add_argument(
        "--rate-hz",
        type=positive_float,
        default=DEFAULT_RATE_HZ,
        help=f"Quaternion send rate. Default: {DEFAULT_RATE_HZ:.1f} Hz",
    )
    parser.add_argument(
        "--duration",
        type=positive_float,
        default=None,
        help="Optional run duration in seconds. Default: run until Ctrl+C.",
    )
    parser.add_argument(
        "--print",
        dest="print_lines",
        action="store_true",
        help="Also print each generated line to the terminal.",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print send-rate and current-pose diagnostics once per second.",
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
    period_seconds = 1.0 / args.rate_hz
    destination = (args.host, args.port)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    start_time = time.perf_counter()
    start_wall_ns = time.time_ns()
    next_send_time = start_time
    next_seq = 0
    last_stats_time = start_time
    last_stats_seq = 0

    try:
        while True:
            now = time.perf_counter()
            elapsed = now - start_time
            if args.duration is not None and elapsed >= args.duration:
                break

            pose_index, _pose_degrees = stepped_pose(elapsed)
            pose_ns = start_wall_ns + int(
                pose_index * STEP_INTERVAL_SECONDS * NS_PER_SECOND
            )
            sent_ns = time.time_ns()
            line = format_quaternion_line(
                simulated_orientation(elapsed),
                seq=next_seq,
                sent_ns=sent_ns,
                pose=pose_index,
                pose_ns=pose_ns,
            )
            sock.sendto(line.encode("utf-8"), destination)
            next_seq += 1

            if args.print_lines:
                print(line, flush=True)

            if args.stats and now - last_stats_time >= args.stats_interval:
                stats_elapsed = now - last_stats_time
                sent_delta = next_seq - last_stats_seq
                sent_hz = sent_delta / stats_elapsed
                print(
                    "source stats "
                    f"target_hz:{args.rate_hz:.1f} "
                    f"sent_hz:{sent_hz:.1f} "
                    f"seq:{next_seq - 1} "
                    f"pose:{pose_index}",
                    flush=True,
                )
                last_stats_time = now
                last_stats_seq = next_seq

            next_send_time += period_seconds
            sleep_seconds = next_send_time - time.perf_counter()
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
            else:
                next_send_time = time.perf_counter()
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()


if __name__ == "__main__":
    main()
