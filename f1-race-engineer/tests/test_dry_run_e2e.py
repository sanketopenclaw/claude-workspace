import struct
from telemetry import packets
from telemetry.listener import TelemetryListener
from telemetry.state import StateTracker
from rules.engine import RuleEngine
from dashboard.log import EngineerLog
from dashboard.server import create_app
from voice import phrasing
from tests.test_packets import (
    _build_header, _build_lap_data_car, _build_car_status_car, _build_car_damage_car,
    _build_session_packet, _pack_spec, _build_participant, _build_car_motion_car, _build_car_setup,
)

PLAYER_INDEX = 0


def _lap_data_packet():
    player = _build_lap_data_car(car_position=3, current_lap_num=5, delta_front_ms=800)
    behind = _build_lap_data_car(car_position=4, delta_front_ms=600)
    fillers = [_build_lap_data_car(car_position=p) for p in range(5, 27)]
    cars = [player, behind] + fillers
    header = _build_header(packet_id=2, player_car_index=PLAYER_INDEX)
    return header + b"".join(cars) + b"\xff\xff"


def _car_status_packet():
    header = _build_header(packet_id=7, player_car_index=PLAYER_INDEX)
    cars = [_build_car_status_car(fuel_in_tank=3.0, fuel_remaining_laps=1.5) for _ in range(24)]
    cars[PLAYER_INDEX] = _build_car_status_car(fuel_in_tank=3.0, fuel_remaining_laps=1.5, vehicle_fia_flags=3)
    return header + b"".join(cars)


def _car_damage_packet():
    header = _build_header(packet_id=10, player_car_index=PLAYER_INDEX)
    cars = [_build_car_damage_car(tyres_wear=(72.0, 70.0, 68.0, 69.0)) for _ in range(24)]
    return header + b"".join(cars)


def _session_packet():
    header = _build_header(packet_id=1, player_car_index=PLAYER_INDEX)
    return header + _build_session_packet(weather=4, safety_car_status=2)


def _penalty_event_packet():
    header = _build_header(packet_id=3, player_car_index=PLAYER_INDEX)
    payload = _pack_spec(packets.EVENT_DETAIL_SPECS["PENA"], {
        "penalty_type": 1, "infringement_type": 2, "vehicle_idx": 0,
        "other_vehicle_idx": 3, "time": 5, "lap_num": 5, "places_gained": 0,
    })
    return header + b"PENA" + payload


def _safety_car_event_packet():
    header = _build_header(packet_id=3, player_car_index=PLAYER_INDEX)
    payload = _pack_spec(packets.EVENT_DETAIL_SPECS["SCAR"], {"safety_car_type": 2, "event_type": 0})
    return header + b"SCAR" + payload


def _retirement_event_packet(vehicle_idx):
    header = _build_header(packet_id=3, player_car_index=PLAYER_INDEX)
    payload = _pack_spec(packets.EVENT_DETAIL_SPECS["RTMT"], {"vehicle_idx": vehicle_idx, "reason": 3})
    return header + b"RTMT" + payload


def _participants_packet():
    header = _build_header(packet_id=4, player_car_index=PLAYER_INDEX)
    participants = [_build_participant(name=f"Driver {i}") for i in range(packets.NUM_CARS)]
    participants[7] = _build_participant(name="L. Rival")
    return header + struct.pack("<B", packets.NUM_CARS) + b"".join(participants)


def _motion_packet():
    header = _build_header(packet_id=0, player_car_index=PLAYER_INDEX)
    cars = [_build_car_motion_car() for _ in range(packets.NUM_CARS)]
    cars[PLAYER_INDEX] = _build_car_motion_car(world_velocity_x=30.0, world_velocity_y=0.0, world_velocity_z=40.0)
    return header + b"".join(cars)


def _session_end_event_packet():
    header = _build_header(packet_id=3, player_car_index=PLAYER_INDEX)
    return header + b"SEND" + b"\x00" * 12


def _car_setup_packet():
    header = _build_header(packet_id=5, player_car_index=PLAYER_INDEX)
    cars = [_build_car_setup() for _ in range(packets.NUM_CARS)]
    cars[PLAYER_INDEX] = _build_car_setup(front_wing=28, rear_wing=42)
    return header + b"".join(cars) + struct.pack("<f", 0.0)


def test_dry_run_full_pipeline_without_network_or_llm(monkeypatch):
    monkeypatch.setattr(phrasing, "PROVIDER_CHAIN", [])  # force canned lines, no real API calls

    state_tracker = StateTracker()
    rule_engine = RuleEngine()
    engineer_log = EngineerLog()
    listener = TelemetryListener(state_tracker)

    listener._dispatch(_lap_data_packet())
    listener._dispatch(_car_status_packet())
    listener._dispatch(_car_damage_packet())
    listener._dispatch(_session_packet())
    listener._dispatch(_penalty_event_packet())
    listener._dispatch(_safety_car_event_packet())
    listener._dispatch(_participants_packet())
    listener._dispatch(_retirement_event_packet(vehicle_idx=7))
    listener._dispatch(_motion_packet())
    listener._dispatch(_session_end_event_packet())
    listener._dispatch(_car_setup_packet())

    state = state_tracker.snapshot()
    assert state.car_setup["front_wing"] == 28
    assert state.car_setup["rear_wing"] == 42
    assert state.weather == 4
    assert state.safety_car_status == 2
    assert state.last_penalty["vehicle_idx"] == 0
    assert state.last_penalty["other_vehicle_idx"] == 3
    assert state.flag_status == 3
    assert state.participant_names[7] == "L. Rival"
    assert len(state.leaderboard) >= 2
    assert state.speed_kmh == 180.0  # sqrt(30^2+40^2) m/s = 50 m/s -> 180 km/h
    assert state.session_ended is True

    events = (
        rule_engine.check_tyre_and_fuel(state)
        + rule_engine.check_gaps(state)
        + rule_engine.check_flag(state)
        + rule_engine.check_safety_car(state)
        + rule_engine.check_weather_forecast(state)
        + rule_engine.check_penalty(state)
        + rule_engine.check_retirement(state)
    )
    kinds = {e.kind for e in events}
    assert kinds == {
        "tyre_wear", "fuel_critical", "gap_closing_ahead", "gap_closing_behind",
        "flag_change", "safety_car", "weather_forecast", "penalty", "rival_retired",
    }
    retirement_event = next(e for e in events if e.kind == "rival_retired")
    assert retirement_event.data["name"] == "L. Rival"

    for event in events:
        line = phrasing.event_to_line(event)
        assert line
        engineer_log.add_callout("00:00:00", line)

    app = create_app(state_tracker, engineer_log)
    body = app.test_client().get("/api/state").get_json()

    assert body["car_position"] == 3
    assert body["current_lap_num"] == 5
    assert body["gap_ahead_ms"] == 800
    assert body["gap_behind_ms"] == 600
    assert body["fuel_remaining_laps"] == 1.5
    assert body["tyres_wear"] == [72.0, 70.0, 68.0, 69.0]
    assert len(body["log"]) == len(events)
