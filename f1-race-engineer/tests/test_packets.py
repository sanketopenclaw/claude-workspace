import struct
from telemetry import packets


def _build_header(packet_id, player_car_index=0):
    return struct.pack(
        packets.HEADER_FORMAT,
        2025, 25, 1, 5, 1, packet_id,
        123456789, 12.5, 1000, 1000,
        player_car_index, 255,
    )


def test_parse_header_extracts_packet_id_and_player_index():
    data = _build_header(packet_id=2, player_car_index=3) + b"\x00" * 100
    header = packets.parse_header(data)
    assert header["packet_id"] == 2
    assert header["player_car_index"] == 3
    assert header["packet_format"] == 2025


def _build_lap_data_car(last_lap_ms=90000, current_lap_ms=45000, sector1_ms=30000, sector2_ms=30000,
                         delta_front_ms=800, delta_leader_ms=5000, car_position=5, current_lap_num=3):
    return struct.pack(
        packets.LAP_DATA_FORMAT,
        last_lap_ms, current_lap_ms,
        sector1_ms % 60000, sector1_ms // 60000,
        sector2_ms % 60000, sector2_ms // 60000,
        delta_front_ms % 60000, delta_front_ms // 60000,
        delta_leader_ms % 60000, delta_leader_ms // 60000,
        100.0, 200.0, 0.0,
        car_position, current_lap_num,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        0, 0, 0,
        250.0, 255,
    )


def test_parse_lap_data_packet_extracts_player_car_and_gaps():
    header = _build_header(packet_id=2, player_car_index=1)
    car_p2_behind_player = _build_lap_data_car(car_position=2, delta_front_ms=750)
    car_player = _build_lap_data_car(car_position=1, delta_front_ms=0)
    filler_cars = [_build_lap_data_car(car_position=p) for p in range(3, 23)]
    cars = [car_p2_behind_player, car_player] + filler_cars
    data = header + b"".join(cars) + b"\xff\xff"

    my_lap, gap_ahead_ms, gap_behind_ms = packets.parse_lap_data_packet(data, player_car_index=1)

    assert my_lap["car_position"] == 1
    assert my_lap["current_lap_num"] == 3
    assert gap_ahead_ms == 0
    assert gap_behind_ms == 750


def _build_car_status_car(fuel_in_tank=45.5, fuel_remaining_laps=12.3):
    return struct.pack(
        packets.CAR_STATUS_FORMAT,
        0, 0, 1, 50, 0,
        fuel_in_tank, 110.0, fuel_remaining_laps,
        15000, 4000,
        8, 1, 1500,
        16, 16, 5,
        0,
        500.0, 300.0, 4000000.0,
        0,
        100.0, 50.0, 150.0,
        0,
    )


def test_parse_car_status_packet_extracts_fuel_for_player_car():
    header = _build_header(packet_id=7, player_car_index=2)
    cars = [_build_car_status_car() for _ in range(22)]
    cars[2] = _build_car_status_car(fuel_in_tank=30.0, fuel_remaining_laps=3.0)
    data = header + b"".join(cars)

    fuel_in_tank, fuel_remaining_laps = packets.parse_car_status_packet(data, player_car_index=2)

    assert fuel_in_tank == 30.0
    assert fuel_remaining_laps == 3.0
