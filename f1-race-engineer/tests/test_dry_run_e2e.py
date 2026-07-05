from telemetry import packets
from telemetry.listener import TelemetryListener
from telemetry.state import StateTracker
from rules.engine import RuleEngine
from dashboard.log import EngineerLog
from dashboard.server import create_app
from voice import phrasing
from tests.test_packets import _build_header, _build_lap_data_car, _build_car_status_car, _build_car_damage_car

PLAYER_INDEX = 0


def _lap_data_packet():
    player = _build_lap_data_car(car_position=3, current_lap_num=5, delta_front_ms=800)
    behind = _build_lap_data_car(car_position=4, delta_front_ms=600)
    fillers = [_build_lap_data_car(car_position=p) for p in range(5, 25)]
    cars = [player, behind] + fillers
    header = _build_header(packet_id=2, player_car_index=PLAYER_INDEX)
    return header + b"".join(cars) + b"\xff\xff"


def _car_status_packet():
    header = _build_header(packet_id=7, player_car_index=PLAYER_INDEX)
    cars = [_build_car_status_car(fuel_in_tank=3.0, fuel_remaining_laps=1.5) for _ in range(22)]
    return header + b"".join(cars)


def _car_damage_packet():
    header = _build_header(packet_id=10, player_car_index=PLAYER_INDEX)
    cars = [_build_car_damage_car(tyres_wear=(72.0, 70.0, 68.0, 69.0)) for _ in range(22)]
    return header + b"".join(cars)


def test_dry_run_full_pipeline_without_network_or_llm(monkeypatch):
    monkeypatch.setattr(phrasing, "PROVIDER_CHAIN", [])  # force canned lines, no real API calls

    state_tracker = StateTracker()
    rule_engine = RuleEngine()
    engineer_log = EngineerLog()
    listener = TelemetryListener(state_tracker)

    listener._dispatch(_lap_data_packet())
    listener._dispatch(_car_status_packet())
    listener._dispatch(_car_damage_packet())

    state = state_tracker.snapshot()
    events = rule_engine.check_tyre_and_fuel(state) + rule_engine.check_gaps(state)
    kinds = {e.kind for e in events}
    assert kinds == {"tyre_wear", "fuel_critical", "gap_closing_ahead", "gap_closing_behind"}

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
