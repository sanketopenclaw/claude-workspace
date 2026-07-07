"""
Synthetic UDP telemetry replay for manual/visual verification.

Sends a scripted race scenario (fuel burn, tyre wear, lap times, an overtake,
a yellow flag, a pit window, a safety car) over loopback UDP exactly like a
real F1 25 session would, using the same struct formats as telemetry/packets.py.
Run this in one terminal, `python tools/demo_replay.py serve` in another
(or use `both` to do both in one process) to watch the dashboard update live
at http://127.0.0.1:5000 and inspect engineer_log callouts for correctness.
"""
import socket
import struct
import sys
import time

sys.path.insert(0, ".")
from telemetry import packets

HOST, PORT = "127.0.0.1", 20777


def _header(packet_id, player_car_index=0, frame_id=0, session_time=0.0):
    return struct.pack(
        packets.HEADER_FORMAT,
        2025, 25, 1, 5, 1, packet_id,
        123456789, session_time, frame_id, frame_id,
        player_car_index, 255,
    )


def _lap_data_car(last_lap_ms=0, current_lap_ms=0, delta_front_ms=0, delta_leader_ms=0,
                   car_position=1, current_lap_num=1, lap_distance=0.0):
    return struct.pack(
        packets.LAP_DATA_FORMAT,
        last_lap_ms, current_lap_ms,
        30000 % 60000, 30000 // 60000,
        30000 % 60000, 30000 // 60000,
        delta_front_ms % 60000, delta_front_ms // 60000,
        delta_leader_ms % 60000, delta_leader_ms // 60000,
        lap_distance, 200.0, 0.0,
        car_position, current_lap_num,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        0, 0, 0,
        250.0, 255,
    )


def build_lap_data_packet(player_idx, my_car_position, current_lap_num, last_lap_ms,
                           current_lap_ms, delta_front_ms, delta_leader_ms, lap_distance, frame_id):
    # cars[] is indexed by vehicle/array index (player_idx), NOT by car_position --
    # car_position is just a field on each car's row, same as the real UDP packet.
    other_positions = [p for p in range(1, 21) if p != my_car_position]
    cars = [None] * 20
    cars[player_idx] = _lap_data_car(last_lap_ms, current_lap_ms, delta_front_ms, delta_leader_ms,
                                      my_car_position, current_lap_num, lap_distance)
    other_iter = iter(other_positions)
    for i in range(20):
        if cars[i] is None:
            pos = next(other_iter)
            cars[i] = _lap_data_car(88000, 40000, 1000 * pos, 1500 * pos, pos, current_lap_num, 50.0)
    return _header(2, player_idx, frame_id) + b"".join(cars) + b"\xff\xff"


def build_car_status_packet(player_idx, fuel_in_tank, fuel_remaining_laps, flag, frame_id,
                             fuel_mix=1, ers_store_energy=4000000.0, ers_deploy_mode=0):
    def car(fuel=50.0, laps=10.0, f=0, mix=1, ers=4000000.0, deploy=0):
        return struct.pack(
            packets.CAR_STATUS_FORMAT,
            0, 0, mix, 50, 0,
            fuel, 110.0, laps,
            15000, 4000,
            8, 1, 1500,
            16, 16, 5,
            f,
            500.0, 300.0, ers,
            deploy,
            100.0, 50.0, 150.0, 200.0,
            0,
        )
    cars = [
        car(fuel_in_tank, fuel_remaining_laps, flag, fuel_mix, ers_store_energy, ers_deploy_mode)
        if i == player_idx else car()
        for i in range(20)
    ]
    return _header(7, player_idx, frame_id) + b"".join(cars)


def build_car_damage_packet(player_idx, tyres_wear, frame_id, components=None):
    components = components or [0] * 18
    def car(wear, comps):
        return struct.pack(packets.CAR_DAMAGE_FORMAT, *wear, *([0] * 12), *comps)
    cars = [
        car(tyres_wear, components) if i == player_idx else car([5.0, 5.0, 5.0, 5.0], [0] * 18)
        for i in range(20)
    ]
    return _header(10, player_idx, frame_id) + b"".join(cars)


def _pack_spec(spec, values):
    fmt = "<" + "".join(t for _, t in spec)
    return struct.pack(fmt, *[values[name] for name, _ in spec])


def build_session_packet(player_idx, frame_id, total_laps=20, pit_ideal_lap=8, pit_latest_lap=12,
                          weather_samples=None):
    weather_samples = weather_samples or []
    head1 = _pack_spec(packets.SESSION_HEAD1_SPEC, {
        "weather": 0, "track_temperature": 25, "air_temperature": 20,
        "total_laps": total_laps, "track_length": 5000, "session_type": 10,
        "track_id": 0, "formula": 0, "session_time_left": 3000,
        "session_duration": 3600, "pit_speed_limit": 80, "game_paused": 0,
        "is_spectating": 0, "spectator_car_index": 255,
        "sli_pro_native_support": 0, "num_marshal_zones": 0,
    })
    head2 = _pack_spec(packets.SESSION_HEAD2_SPEC, {
        "safety_car_status": 0, "network_game": 0,
        "num_weather_forecast_samples": len(weather_samples),
    })
    samples = b"".join(_pack_spec(packets.WEATHER_FORECAST_SAMPLE_SPEC, s) for s in weather_samples)
    head3 = _pack_spec(packets.SESSION_HEAD3_SPEC, {
        "forecast_accuracy": 0, "ai_difficulty": 50,
        "season_link_identifier": 0, "weekend_link_identifier": 0, "session_link_identifier": 0,
        "pit_stop_window_ideal_lap": pit_ideal_lap, "pit_stop_window_latest_lap": pit_latest_lap,
        "pit_stop_rejoin_position": 5,
        "steering_assist": 0, "braking_assist": 0, "gearbox_assist": 0,
        "pit_assist": 0, "pit_release_assist": 0, "ers_assist": 0, "drs_assist": 0,
        "dynamic_racing_line": 0, "dynamic_racing_line_type": 0,
        "game_mode": 0, "rule_set": 0, "time_of_day": 0, "session_length": 0,
        "speed_units_lead_player": 0, "temperature_units_lead_player": 0,
        "speed_units_secondary_player": 0, "temperature_units_secondary_player": 0,
        "num_safety_car_periods": 0, "num_virtual_safety_car_periods": 0, "num_red_flag_periods": 0,
        "equal_car_performance": 0, "recovery_mode": 0, "flashback_limit": 0,
        "surface_type": 0, "low_fuel_mode": 0, "race_starts": 0,
        "tyre_temperature": 0, "pit_lane_tyre_sim": 0, "car_damage": 0, "car_damage_rate": 0,
        "collisions": 0, "collisions_off_for_first_lap_only": 0,
        "mp_unsafe_pit_release": 0, "mp_off_for_griefing": 0,
        "corner_cutting_stringency": 0, "parc_ferme_rules": 0, "pit_stop_experience": 0,
        "safety_car": 0, "safety_car_experience": 0, "formation_lap": 0, "formation_lap_experience": 0,
        "red_flags": 0, "affects_licence_level_solo": 0, "affects_licence_level_mp": 0,
        "num_sessions_in_weekend": 0,
    })
    tail1 = _pack_spec(packets.SESSION_TAIL1_SPEC, {
        "sector2_lap_distance_start": 1600.0, "sector3_lap_distance_start": 3300.0,
    })
    rest = struct.pack("<BBBBB", 0, 0, 0, 0, 0)  # active_aero_track_status, 3x zone-count=0, num_drs_zones=0
    tail2 = _pack_spec(packets.SESSION_TAIL2_SPEC, {
        "start_reaction_time": 0.0, "anti_lock_brakes_assist": 0, "traction_control_assist": 0,
        "dynamic_racing_line_hi_vis": 0, "dynamic_racing_line_colour_blind": 0,
        "recurring_rewind_prompt": 0,
    })
    return _header(1, player_idx, frame_id) + head1 + head2 + samples + head3 + tail1 + rest + tail2


def build_event_packet(event_code, payload_bytes, player_idx=0, frame_id=0):
    code = event_code.encode("ascii")
    return _header(3, player_idx, frame_id) + code + payload_bytes


def build_participants_packet(player_idx, frame_id):
    def participant(name):
        name_bytes = name.encode("ascii").ljust(32, b"\x00")
        return struct.pack(
            "<BHHHBBB32sBBHBB12s",
            1, 0, 0, 0, 0, 0, 0,
            name_bytes,
            3, 1, 0,
            0, 0, b"\x00" * 12,
        )
    names = [f"Rival {i}" for i in range(20)]
    names[5] = "Hamilton"
    body = b"".join(participant(n) for n in names)
    return _header(4, player_idx, frame_id) + struct.pack("<B", 20) + body


def build_penalty_event(player_idx, seconds, lap_num, frame_id):
    payload = struct.pack("<BBBBBBB", 1, 1, player_idx, 5, seconds, lap_num, 0)
    return build_event_packet("PENA", payload, player_idx, frame_id)


def build_collision_event(player_idx, other_idx, frame_id):
    payload = struct.pack("<BBB", player_idx, other_idx, 2)
    return build_event_packet("COLL", payload, player_idx, frame_id)


def build_retirement_event(vehicle_idx, frame_id):
    payload = struct.pack("<BB", vehicle_idx, 1)
    return build_event_packet("RTMT", payload, 0, frame_id)


def build_speed_trap_event(player_idx, speed, is_overall_best, frame_id):
    payload = struct.pack("<BfBBBf", player_idx, speed, int(is_overall_best), 1, player_idx, speed)
    return build_event_packet("SPTP", payload, player_idx, frame_id)


def build_flashback_event(flashback_frame_id, frame_id):
    payload = struct.pack("<If", flashback_frame_id, 0.0)
    return build_event_packet("FLBK", payload, 0, frame_id)


def send(sock, packet):
    sock.sendto(packet, (HOST, PORT))


def run_scenario():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    player_idx = 0
    frame = 0

    print("[demo] tick 0: green flag, P4, lap 1, fuel healthy")
    send(sock, build_car_status_packet(player_idx, fuel_in_tank=45.0, fuel_remaining_laps=12.0, flag=1, frame_id=frame))
    send(sock, build_car_damage_packet(player_idx, [10.0, 10.0, 10.0, 10.0], frame))
    send(sock, build_lap_data_packet(player_idx, my_car_position=4, current_lap_num=1,
                                      last_lap_ms=0, current_lap_ms=20000, delta_front_ms=1200,
                                      delta_leader_ms=3500, lap_distance=1500.0, frame_id=frame))
    time.sleep(1.0)

    frame += 1
    print("[demo] tick 1: yellow flag out")
    send(sock, build_car_status_packet(player_idx, fuel_in_tank=42.0, fuel_remaining_laps=11.0, flag=3, frame_id=frame))
    time.sleep(1.0)

    frame += 1
    print("[demo] tick 2: overtake made (place gained)")
    send(sock, build_event_packet("OVTK", struct.pack("<BB", player_idx, 5), player_idx, frame))
    time.sleep(1.0)

    frame += 1
    print("[demo] tick 3: lap 2 complete, tyres worn to 55%, flag back to green")
    send(sock, build_car_status_packet(player_idx, fuel_in_tank=38.0, fuel_remaining_laps=9.0, flag=1, frame_id=frame))
    send(sock, build_car_damage_packet(player_idx, [55.0, 55.0, 50.0, 50.0], frame))
    send(sock, build_lap_data_packet(player_idx, my_car_position=3, current_lap_num=2,
                                      last_lap_ms=85000, current_lap_ms=0, delta_front_ms=0,
                                      delta_leader_ms=1800, lap_distance=0.0, frame_id=frame))
    time.sleep(1.0)

    frame += 1
    print("[demo] tick 4: fuel now critical (1.5 laps left)")
    send(sock, build_car_status_packet(player_idx, fuel_in_tank=6.0, fuel_remaining_laps=1.5, flag=1, frame_id=frame))
    time.sleep(1.0)

    frame += 1
    print("[demo] tick 5: same fuel-critical state repeated 3x -- must NOT re-fire the callout")
    for _ in range(3):
        send(sock, build_car_status_packet(player_idx, fuel_in_tank=6.0, fuel_remaining_laps=1.5, flag=1, frame_id=frame))
        time.sleep(0.5)

    frame += 1
    print("[demo] tick 6: participants + session (total_laps=20, pit window 8-12) + rain forecast in 10min")
    send(sock, build_participants_packet(player_idx, frame))
    send(sock, build_session_packet(player_idx, frame, total_laps=20, pit_ideal_lap=8, pit_latest_lap=12,
                                     weather_samples=[{"session_type": 10, "time_offset": 10, "weather": 4,
                                                        "track_temperature": 25, "track_temperature_change": 0,
                                                        "air_temperature": 20, "air_temperature_change": 0,
                                                        "rain_percentage": 80}]))
    time.sleep(1.0)

    frame += 1
    print("[demo] tick 7: 5-second penalty for the player, lap 2")
    send(sock, build_penalty_event(player_idx, seconds=5, lap_num=2, frame_id=frame))
    time.sleep(1.0)

    frame += 1
    print("[demo] tick 8: collision with car 7")
    send(sock, build_collision_event(player_idx, other_idx=7, frame_id=frame))
    time.sleep(1.0)

    frame += 1
    print("[demo] tick 9: rival car 5 (Hamilton) retires")
    send(sock, build_retirement_event(vehicle_idx=5, frame_id=frame))
    time.sleep(1.0)

    frame += 1
    print("[demo] tick 10: player sets fastest speed trap in the session (327 km/h)")
    send(sock, build_speed_trap_event(player_idx, speed=327.0, is_overall_best=True, frame_id=frame))
    time.sleep(1.0)

    frame += 1
    print("[demo] tick 11: ERS store drops low (300000 J) while deploying (mode 2 = balanced)")
    send(sock, build_car_status_packet(player_idx, fuel_in_tank=5.0, fuel_remaining_laps=1.2, flag=1, frame_id=frame,
                                        ers_store_energy=300000.0, ers_deploy_mode=2))
    time.sleep(1.0)

    frame += 1
    print("[demo] tick 12: front-left wing damage jumps 20%% + DRS fault turns on")
    send(sock, build_car_damage_packet(player_idx, [55.0, 55.0, 50.0, 50.0], frame,
                                        components=[0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]))
    time.sleep(0.6)
    send(sock, build_car_damage_packet(player_idx, [55.0, 55.0, 50.0, 50.0], frame,
                                        components=[20, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]))
    time.sleep(1.0)

    frame += 1
    print("[demo] tick 13: severe front/rear tyre wear imbalance (front wearing much faster)")
    send(sock, build_car_damage_packet(player_idx, [20.0, 20.0, 60.0, 60.0], frame,
                                        components=[20, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]))
    time.sleep(1.0)

    frame += 1
    print("[demo] tick 14: driver rewinds (flashback) from lap 2 back to lap 1 -- must NOT fire a bogus lap_completion")
    send(sock, build_flashback_event(flashback_frame_id=frame, frame_id=frame))
    send(sock, build_car_status_packet(player_idx, fuel_in_tank=40.0, fuel_remaining_laps=10.0, flag=1, frame_id=frame))
    send(sock, build_lap_data_packet(player_idx, my_car_position=3, current_lap_num=1,
                                      last_lap_ms=88000, current_lap_ms=15000, delta_front_ms=500,
                                      delta_leader_ms=1200, lap_distance=800.0, frame_id=frame))
    time.sleep(1.0)

    frame += 1
    print("[demo] tick 15: driver completes lap 1 for real post-rewind -- THIS should fire lap_completion")
    send(sock, build_lap_data_packet(player_idx, my_car_position=3, current_lap_num=2,
                                      last_lap_ms=87000, current_lap_ms=0, delta_front_ms=0,
                                      delta_leader_ms=1000, lap_distance=0.0, frame_id=frame))
    time.sleep(1.0)

    print("[demo] scenario complete")


if __name__ == "__main__":
    run_scenario()
