# simulated_quaternion_source.py

import argparse
import math
import socket
import time

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5005
DEFAULT_RATE_HZ = 1000.0 / 16.0


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


def simulated_orientation(elapsed_seconds):
    """Generate a smooth, IMU-like orientation that keeps the cube moving."""
    roll = math.radians(35.0) * math.sin(elapsed_seconds * 0.9)
    pitch = math.radians(25.0) * math.sin(elapsed_seconds * 0.55 + 0.8)
    yaw = elapsed_seconds * 0.7
    return quaternion_from_euler(roll, pitch, yaw)


def format_quaternion_line(quat):
    w, x, y, z = quat
    return f"Quat → w:{w:.4f} x:{x:.4f} y:{y:.4f} z:{z:.4f}"


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
    return parser.parse_args()


def main():
    args = parse_args()
    period_seconds = 1.0 / args.rate_hz
    destination = (args.host, args.port)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    start_time = time.perf_counter()
    next_send_time = start_time

    try:
        while True:
            now = time.perf_counter()
            elapsed = now - start_time
            if args.duration is not None and elapsed >= args.duration:
                break

            line = format_quaternion_line(simulated_orientation(elapsed))
            sock.sendto(line.encode("utf-8"), destination)

            if args.print_lines:
                print(line, flush=True)

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
