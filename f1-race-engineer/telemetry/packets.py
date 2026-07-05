import struct

# F1 25 UDP telemetry — struct formats verified against MacManley/f1-25-udp
# (github.com/MacManley/f1-25-udp), matching the official F1 25 spec.

HEADER_FORMAT = "<HBBBBBQfIIBB"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)  # 29 bytes


def parse_header(data):
    fields = struct.unpack_from(HEADER_FORMAT, data, 0)
    (packet_format, game_year, game_major, game_minor, packet_version, packet_id,
     session_uid, session_time, frame_id, overall_frame_id,
     player_car_index, secondary_player_car_index) = fields
    return {
        "packet_format": packet_format,
        "packet_id": packet_id,
        "player_car_index": player_car_index,
    }
