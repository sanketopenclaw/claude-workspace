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
    filler_cars = [_build_lap_data_car(car_position=p) for p in range(3, 25)]
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
        100.0, 50.0, 150.0, 200.0,
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


def _build_car_damage_car(tyres_wear=(10.0, 12.0, 8.0, 9.0)):
    zeros_30 = (0,) * 30
    return struct.pack(packets.CAR_DAMAGE_FORMAT, *tyres_wear, *zeros_30)


def test_parse_car_damage_packet_extracts_tyre_wear_for_player_car():
    header = _build_header(packet_id=10, player_car_index=5)
    cars = [_build_car_damage_car() for _ in range(22)]
    cars[5] = _build_car_damage_car(tyres_wear=(40.0, 42.0, 38.0, 39.0))
    data = header + b"".join(cars)

    tyres_wear = packets.parse_car_damage_packet(data, player_car_index=5)

    assert tyres_wear == [40.0, 42.0, 38.0, 39.0]


def test_struct_sizes_match_official_spec():
    # Pins byte sizes against P403n1x87/f1-packets data/spec.h ("F1 25: 2026 Season
    # Pack" UDP spec) so a future season-pack field/grid-size change fails loud
    # here instead of silently corrupting offsets (see CAR_STATUS_FORMAT fix:
    # missing m_ersDeployedThisLap float made every non-zero player_car_index
    # read fuel/tyre data from the wrong byte offset).
    assert packets.NUM_CARS == 24
    assert packets.LAP_DATA_SIZE == 57
    assert packets.CAR_STATUS_SIZE == 59
    assert packets.CAR_DAMAGE_SIZE == 46


def _pack_spec(spec, values):
    fmt = "<" + "".join(type_char for _, type_char in spec)
    return struct.pack(fmt, *(values[name] for name, _ in spec))


def _build_car_motion_car(**overrides):
    values = {
        "world_position_x": 100.0, "world_position_y": 0.0, "world_position_z": 200.0,
        "world_velocity_x": 10.0, "world_velocity_y": 0.0, "world_velocity_z": 5.0,
        "world_forward_dir_x": 0, "world_forward_dir_y": 0, "world_forward_dir_z": 0,
        "world_right_dir_x": 0, "world_right_dir_y": 0, "world_right_dir_z": 0,
        "g_force_lateral": 0, "g_force_longitudinal": 0, "g_force_vertical": 0,
        "yaw": 0.0, "pitch": 0.0, "roll": 0.0,
    }
    values.update(overrides)
    return _pack_spec(packets.CAR_MOTION_SPEC, values)


def test_parse_motion_packet_extracts_all_cars():
    header = _build_header(packet_id=0, player_car_index=1)
    cars = [_build_car_motion_car() for _ in range(packets.NUM_CARS)]
    cars[1] = _build_car_motion_car(world_position_x=555.0, world_velocity_z=42.0)
    data = header + b"".join(cars)

    motion = packets.parse_motion_packet(data)

    assert len(motion) == packets.NUM_CARS
    assert motion[1]["world_position_x"] == 555.0
    assert motion[1]["world_velocity_z"] == 42.0


def _build_marshal_zone(zone_start=0.0, zone_flag=0):
    return _pack_spec(packets.MARSHAL_ZONE_SPEC, {"zone_start": zone_start, "zone_flag": zone_flag})


def _build_weather_forecast_sample(time_offset=0, weather=0, rain_percentage=0):
    values = {
        "session_type": 1, "time_offset": time_offset, "weather": weather,
        "track_temperature": 30, "track_temperature_change": 0,
        "air_temperature": 20, "air_temperature_change": 0,
        "rain_percentage": rain_percentage,
    }
    return _pack_spec(packets.WEATHER_FORECAST_SAMPLE_SPEC, values)


def _build_aero_zone(zone_start=0.0, zone_end=0.0):
    return _pack_spec(packets.AERO_ZONE_SPEC, {"zone_start": zone_start, "zone_end": zone_end})


def _build_session_packet(weather=2, safety_car_status=0, track_temperature=34, air_temperature=22,
                           forecast_samples=((0, 2, 10), (15, 3, 60))):
    head1 = {
        "weather": weather, "track_temperature": track_temperature, "air_temperature": air_temperature,
        "total_laps": 50, "track_length": 5000, "session_type": 10,
        "track_id": 0, "formula": 0, "session_time_left": 3000,
        "session_duration": 3600, "pit_speed_limit": 80, "game_paused": 0,
        "is_spectating": 0, "spectator_car_index": 255,
        "sli_pro_native_support": 0, "num_marshal_zones": 2,
    }
    data = _pack_spec(packets.SESSION_HEAD1_SPEC, head1)
    data += b"".join(_build_marshal_zone(zone_start=i / 21) for i in range(packets.NUM_MARSHAL_ZONES))

    head2 = {"safety_car_status": safety_car_status, "network_game": 0,
             "num_weather_forecast_samples": len(forecast_samples)}
    data += _pack_spec(packets.SESSION_HEAD2_SPEC, head2)
    samples = [_build_weather_forecast_sample(*s) for s in forecast_samples]
    samples += [_build_weather_forecast_sample()] * (packets.NUM_WEATHER_FORECAST_SAMPLES - len(samples))
    data += b"".join(samples)

    head3 = {name: 0 for name, _ in packets.SESSION_HEAD3_SPEC}
    head3["num_sessions_in_weekend"] = 1
    data += _pack_spec(packets.SESSION_HEAD3_SPEC, head3)
    data += struct.pack(f"<{packets.NUM_WEEKEND_STRUCTURE}B", *([0] * packets.NUM_WEEKEND_STRUCTURE))

    data += _pack_spec(packets.SESSION_TAIL1_SPEC, {"sector2_lap_distance_start": 0.0, "sector3_lap_distance_start": 0.0})
    data += struct.pack("<B", 0)  # active_aero_track_status
    data += struct.pack("<B", 1)  # num_active_aero_zones_full
    data += b"".join(_build_aero_zone() for _ in range(packets.NUM_ACTIVE_AERO_ZONES))
    data += struct.pack("<B", 1)  # num_active_aero_zones_partial
    data += b"".join(_build_aero_zone() for _ in range(packets.NUM_ACTIVE_AERO_ZONES))
    data += struct.pack("<B", 1)  # num_drs_zones
    data += b"".join(_build_aero_zone() for _ in range(packets.NUM_DRS_ZONES))
    data += _pack_spec(packets.SESSION_TAIL2_SPEC, {name: 0 for name, _ in packets.SESSION_TAIL2_SPEC})

    return data


def test_parse_session_packet_extracts_weather_and_trims_arrays():
    header = _build_header(packet_id=1)
    data = header + _build_session_packet()

    session = packets.parse_session_packet(data)

    assert session["weather"] == 2
    assert session["track_temperature"] == 34
    assert session["air_temperature"] == 22
    assert session["safety_car_status"] == 0
    assert len(session["marshal_zones"]) == 2
    assert len(session["weather_forecast_samples"]) == 2
    assert session["weather_forecast_samples"][1]["weather"] == 3
    assert session["weather_forecast_samples"][1]["rain_percentage"] == 60
    assert len(session["active_aero_zones_full"]) == 1
    assert len(session["active_aero_zones_partial"]) == 1
    assert len(session["drs_zones"]) == 1


def test_parse_event_packet_penalty_variant():
    header = _build_header(packet_id=3)
    payload = _pack_spec(packets.EVENT_DETAIL_SPECS["PENA"], {
        "penalty_type": 1, "infringement_type": 2, "vehicle_idx": 3,
        "other_vehicle_idx": 255, "time": 5, "lap_num": 4, "places_gained": 0,
    })
    data = header + b"PENA" + payload

    event_code, details = packets.parse_event_packet(data)

    assert event_code == "PENA"
    assert details == {
        "penalty_type": 1, "infringement_type": 2, "vehicle_idx": 3,
        "other_vehicle_idx": 255, "time": 5, "lap_num": 4, "places_gained": 0,
    }


def test_parse_event_packet_no_payload_code_returns_none_details():
    header = _build_header(packet_id=3)
    data = header + b"CHQF" + b"\x00" * 12

    event_code, details = packets.parse_event_packet(data)

    assert event_code == "CHQF"
    assert details is None
