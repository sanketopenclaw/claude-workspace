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


LAP_DATA_FORMAT = "<IIHBHBHBHBfffBBBBBBBBBBBBBBBHHBfB"
LAP_DATA_SIZE = struct.calcsize(LAP_DATA_FORMAT)  # 57 bytes
NUM_CARS = 22


def _combine_delta(ms_part, minutes_part):
    return minutes_part * 60000 + ms_part


def parse_lap_data_packet(data, player_car_index):
    cars = []
    offset = HEADER_SIZE
    for _ in range(NUM_CARS):
        f = struct.unpack_from(LAP_DATA_FORMAT, data, offset)
        cars.append({
            "last_lap_time_ms": f[0],
            "current_lap_time_ms": f[1],
            "sector1_time_ms": _combine_delta(f[2], f[3]),
            "sector2_time_ms": _combine_delta(f[4], f[5]),
            "delta_to_car_in_front_ms": _combine_delta(f[6], f[7]),
            "delta_to_race_leader_ms": _combine_delta(f[8], f[9]),
            "car_position": f[13],
            "current_lap_num": f[14],
        })
        offset += LAP_DATA_SIZE

    my_lap = cars[player_car_index]
    gap_ahead_ms = my_lap["delta_to_car_in_front_ms"]

    gap_behind_ms = None
    my_position = my_lap["car_position"]
    for car in cars:
        if car["car_position"] == my_position + 1:
            gap_behind_ms = car["delta_to_car_in_front_ms"]
            break

    return my_lap, gap_ahead_ms, gap_behind_ms


CAR_STATUS_FORMAT = "<BBBBBfffHHBBHBBBbfffBfffB"
CAR_STATUS_SIZE = struct.calcsize(CAR_STATUS_FORMAT)  # 55 bytes


def parse_car_status_packet(data, player_car_index):
    offset = HEADER_SIZE + player_car_index * CAR_STATUS_SIZE
    f = struct.unpack_from(CAR_STATUS_FORMAT, data, offset)
    fuel_in_tank = f[5]
    fuel_remaining_laps = f[7]
    return fuel_in_tank, fuel_remaining_laps


CAR_DAMAGE_FORMAT = "<4f4B4B4B18B"
CAR_DAMAGE_SIZE = struct.calcsize(CAR_DAMAGE_FORMAT)  # 46 bytes


def parse_car_damage_packet(data, player_car_index):
    offset = HEADER_SIZE + player_car_index * CAR_DAMAGE_SIZE
    f = struct.unpack_from(CAR_DAMAGE_FORMAT, data, offset)
    return list(f[0:4])
