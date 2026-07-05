import struct

# F1 25 UDP telemetry — struct formats verified against the official EA spec
# (P403n1x87/f1-packets data/spec.h, "F1 25: 2026 Season Pack" UDP specification).

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
NUM_CARS = 24


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


CAR_STATUS_FORMAT = "<BBBBBfffHHBBHBBBbfffBffffB"
CAR_STATUS_SIZE = struct.calcsize(CAR_STATUS_FORMAT)  # 59 bytes


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


# ---------------------------------------------------------------------------
# Field-spec helper: format string and field names are both derived from one
# list, so they can't drift apart like CAR_STATUS_FORMAT's hand-written
# format string did (see test_struct_sizes_match_official_spec).
# ---------------------------------------------------------------------------

def _spec_format(spec):
    return "<" + "".join(type_char for _, type_char in spec)


def _spec_size(spec):
    return struct.calcsize(_spec_format(spec))


def _unpack_spec(spec, data, offset):
    values = struct.unpack_from(_spec_format(spec), data, offset)
    fields = dict(zip((name for name, _ in spec), values))
    return fields, offset + _spec_size(spec)


def _unpack_array(spec, data, offset, count):
    items = []
    for _ in range(count):
        fields, offset = _unpack_spec(spec, data, offset)
        items.append(fields)
    return items, offset


# ---------------------------------------------------------------------------
# Motion packet (id 0) — parser only; not wired into listener/state until a
# feature actually consumes it (see docs/superpowers/specs/2026-07-05-f1-race-engineer-phase2-design.md)
# ---------------------------------------------------------------------------

CAR_MOTION_SPEC = [
    ("world_position_x", "f"), ("world_position_y", "f"), ("world_position_z", "f"),
    ("world_velocity_x", "f"), ("world_velocity_y", "f"), ("world_velocity_z", "f"),
    ("world_forward_dir_x", "h"), ("world_forward_dir_y", "h"), ("world_forward_dir_z", "h"),
    ("world_right_dir_x", "h"), ("world_right_dir_y", "h"), ("world_right_dir_z", "h"),
    ("g_force_lateral", "h"), ("g_force_longitudinal", "h"), ("g_force_vertical", "h"),
    ("yaw", "f"), ("pitch", "f"), ("roll", "f"),
]
CAR_MOTION_SIZE = _spec_size(CAR_MOTION_SPEC)  # 60 bytes


def parse_motion_packet(data):
    cars, _ = _unpack_array(CAR_MOTION_SPEC, data, HEADER_SIZE, NUM_CARS)
    return cars


# ---------------------------------------------------------------------------
# Session packet (id 1) — full struct parse
# ---------------------------------------------------------------------------

NUM_MARSHAL_ZONES = 21
NUM_WEATHER_FORECAST_SAMPLES = 64
NUM_ACTIVE_AERO_ZONES = 8
NUM_DRS_ZONES = 4
NUM_WEEKEND_STRUCTURE = 12

MARSHAL_ZONE_SPEC = [("zone_start", "f"), ("zone_flag", "b")]
WEATHER_FORECAST_SAMPLE_SPEC = [
    ("session_type", "B"), ("time_offset", "B"), ("weather", "B"),
    ("track_temperature", "b"), ("track_temperature_change", "b"),
    ("air_temperature", "b"), ("air_temperature_change", "b"),
    ("rain_percentage", "B"),
]
AERO_ZONE_SPEC = [("zone_start", "f"), ("zone_end", "f")]  # shared by ActiveAeroZone and DRSZone

SESSION_HEAD1_SPEC = [
    ("weather", "B"), ("track_temperature", "b"), ("air_temperature", "b"),
    ("total_laps", "B"), ("track_length", "H"), ("session_type", "B"),
    ("track_id", "b"), ("formula", "B"), ("session_time_left", "H"),
    ("session_duration", "H"), ("pit_speed_limit", "B"), ("game_paused", "B"),
    ("is_spectating", "B"), ("spectator_car_index", "B"),
    ("sli_pro_native_support", "B"), ("num_marshal_zones", "B"),
]
SESSION_HEAD2_SPEC = [
    ("safety_car_status", "B"), ("network_game", "B"),
    ("num_weather_forecast_samples", "B"),
]
SESSION_HEAD3_SPEC = [
    ("forecast_accuracy", "B"), ("ai_difficulty", "B"),
    ("season_link_identifier", "I"), ("weekend_link_identifier", "I"), ("session_link_identifier", "I"),
    ("pit_stop_window_ideal_lap", "B"), ("pit_stop_window_latest_lap", "B"), ("pit_stop_rejoin_position", "B"),
    ("steering_assist", "B"), ("braking_assist", "B"), ("gearbox_assist", "B"),
    ("pit_assist", "B"), ("pit_release_assist", "B"), ("ers_assist", "B"), ("drs_assist", "B"),
    ("dynamic_racing_line", "B"), ("dynamic_racing_line_type", "B"),
    ("game_mode", "B"), ("rule_set", "B"), ("time_of_day", "I"), ("session_length", "B"),
    ("speed_units_lead_player", "B"), ("temperature_units_lead_player", "B"),
    ("speed_units_secondary_player", "B"), ("temperature_units_secondary_player", "B"),
    ("num_safety_car_periods", "B"), ("num_virtual_safety_car_periods", "B"), ("num_red_flag_periods", "B"),
    ("equal_car_performance", "B"), ("recovery_mode", "B"), ("flashback_limit", "B"),
    ("surface_type", "B"), ("low_fuel_mode", "B"), ("race_starts", "B"),
    ("tyre_temperature", "B"), ("pit_lane_tyre_sim", "B"), ("car_damage", "B"), ("car_damage_rate", "B"),
    ("collisions", "B"), ("collisions_off_for_first_lap_only", "B"),
    ("mp_unsafe_pit_release", "B"), ("mp_off_for_griefing", "B"),
    ("corner_cutting_stringency", "B"), ("parc_ferme_rules", "B"), ("pit_stop_experience", "B"),
    ("safety_car", "B"), ("safety_car_experience", "B"), ("formation_lap", "B"), ("formation_lap_experience", "B"),
    ("red_flags", "B"), ("affects_licence_level_solo", "B"), ("affects_licence_level_mp", "B"),
    ("num_sessions_in_weekend", "B"),
]
SESSION_TAIL1_SPEC = [("sector2_lap_distance_start", "f"), ("sector3_lap_distance_start", "f")]
SESSION_TAIL2_SPEC = [
    ("start_reaction_time", "f"), ("anti_lock_brakes_assist", "B"), ("traction_control_assist", "B"),
    ("dynamic_racing_line_hi_vis", "B"), ("dynamic_racing_line_colour_blind", "B"),
    ("recurring_rewind_prompt", "B"),
]


def parse_session_packet(data):
    session = {}
    offset = HEADER_SIZE

    fields, offset = _unpack_spec(SESSION_HEAD1_SPEC, data, offset)
    session.update(fields)
    marshal_zones, offset = _unpack_array(MARSHAL_ZONE_SPEC, data, offset, NUM_MARSHAL_ZONES)
    session["marshal_zones"] = marshal_zones[:fields["num_marshal_zones"]]

    fields, offset = _unpack_spec(SESSION_HEAD2_SPEC, data, offset)
    session.update(fields)
    weather_forecast_samples, offset = _unpack_array(
        WEATHER_FORECAST_SAMPLE_SPEC, data, offset, NUM_WEATHER_FORECAST_SAMPLES
    )
    session["weather_forecast_samples"] = weather_forecast_samples[:fields["num_weather_forecast_samples"]]

    fields, offset = _unpack_spec(SESSION_HEAD3_SPEC, data, offset)
    session.update(fields)

    weekend_structure = struct.unpack_from(f"<{NUM_WEEKEND_STRUCTURE}B", data, offset)
    offset += NUM_WEEKEND_STRUCTURE
    session["weekend_structure"] = list(weekend_structure[:fields["num_sessions_in_weekend"]])

    fields, offset = _unpack_spec(SESSION_TAIL1_SPEC, data, offset)
    session.update(fields)

    active_aero_track_status, offset = _unpack_spec([("active_aero_track_status", "B")], data, offset)
    session.update(active_aero_track_status)

    num_full, offset = _unpack_spec([("num_active_aero_zones_full", "B")], data, offset)
    session.update(num_full)
    zones_full, offset = _unpack_array(AERO_ZONE_SPEC, data, offset, NUM_ACTIVE_AERO_ZONES)
    session["active_aero_zones_full"] = zones_full[:num_full["num_active_aero_zones_full"]]

    num_partial, offset = _unpack_spec([("num_active_aero_zones_partial", "B")], data, offset)
    session.update(num_partial)
    zones_partial, offset = _unpack_array(AERO_ZONE_SPEC, data, offset, NUM_ACTIVE_AERO_ZONES)
    session["active_aero_zones_partial"] = zones_partial[:num_partial["num_active_aero_zones_partial"]]

    num_drs, offset = _unpack_spec([("num_drs_zones", "B")], data, offset)
    session.update(num_drs)
    drs_zones, offset = _unpack_array(AERO_ZONE_SPEC, data, offset, NUM_DRS_ZONES)
    session["drs_zones"] = drs_zones[:num_drs["num_drs_zones"]]

    fields, offset = _unpack_spec(SESSION_TAIL2_SPEC, data, offset)
    session.update(fields)

    return session


# ---------------------------------------------------------------------------
# Event packet (id 3) — union of ~15 payload variants + 6 no-payload codes
# ---------------------------------------------------------------------------

EVENT_DETAIL_SPECS = {
    "FTLP": [("vehicle_idx", "B"), ("lap_time", "f")],
    "RTMT": [("vehicle_idx", "B"), ("reason", "B")],
    "DRSD": [("reason", "B")],
    "TMPT": [("vehicle_idx", "B")],
    "RCWN": [("vehicle_idx", "B")],
    "PENA": [
        ("penalty_type", "B"), ("infringement_type", "B"), ("vehicle_idx", "B"),
        ("other_vehicle_idx", "B"), ("time", "B"), ("lap_num", "B"), ("places_gained", "B"),
    ],
    "SPTP": [
        ("vehicle_idx", "B"), ("speed", "f"), ("is_overall_fastest_in_session", "B"),
        ("is_driver_fastest_in_session", "B"), ("fastest_vehicle_idx_in_session", "B"),
        ("fastest_speed_in_session", "f"),
    ],
    "STLG": [("num_lights", "B")],
    "DTSV": [("vehicle_idx", "B")],
    "SGSV": [("vehicle_idx", "B"), ("stop_time", "f")],
    "FLBK": [("flashback_frame_identifier", "I"), ("flashback_session_time", "f")],
    "BUTN": [("button_status", "I")],
    "OVTK": [("overtaking_vehicle_idx", "B"), ("being_overtaken_vehicle_idx", "B")],
    "SCAR": [("safety_car_type", "B"), ("event_type", "B")],
    "COLL": [("vehicle1_idx", "B"), ("vehicle2_idx", "B"), ("severity", "B")],
    # SSTA, SEND, DRSE, CHQF, LGOT, RDFL carry no payload.
}
EVENT_STRING_CODE_LEN = 4


def parse_event_packet(data):
    offset = HEADER_SIZE
    event_code = data[offset:offset + EVENT_STRING_CODE_LEN].decode("ascii")
    offset += EVENT_STRING_CODE_LEN

    spec = EVENT_DETAIL_SPECS.get(event_code)
    if spec is None:
        return event_code, None
    details, _ = _unpack_spec(spec, data, offset)
    return event_code, details
