import socket
import struct
import time


def write_packet(f, data):
    f.write(struct.pack("<I", len(data)))
    f.write(data)


def record_session(output_path, ip="0.0.0.0", port=20777, duration_seconds=60):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((ip, port))
    sock.settimeout(1.0)
    end_time = time.time() + duration_seconds
    with open(output_path, "wb") as f:
        while time.time() < end_time:
            try:
                data, _ = sock.recvfrom(2048)
            except socket.timeout:
                continue
            write_packet(f, data)
    sock.close()


def replay_session(input_path, on_packet, delay_seconds=0.0):
    with open(input_path, "rb") as f:
        while True:
            size_bytes = f.read(4)
            if len(size_bytes) < 4:
                break
            (size,) = struct.unpack("<I", size_bytes)
            data = f.read(size)
            on_packet(data)
            if delay_seconds:
                time.sleep(delay_seconds)
