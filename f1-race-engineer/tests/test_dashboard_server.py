from telemetry.state import StateTracker
from dashboard.log import EngineerLog
from dashboard.server import create_app


def test_api_state_returns_expected_shape_and_values():
    tracker = StateTracker()
    tracker.update_lap_data(
        {"last_lap_time_ms": 92104, "current_lap_time_ms": 45230, "sector1_time_ms": 0,
         "sector2_time_ms": 0, "car_position": 4, "current_lap_num": 12},
        gap_ahead_ms=812, gap_behind_ms=1240,
    )
    tracker.update_car_status(fuel_in_tank=34.6, fuel_remaining_laps=3.2)
    tracker.update_car_damage(tyres_wear=[42.0, 38.0, 61.0, 58.0])
    log = EngineerLog()
    log.add_callout("14:32:07", "Purple lap! New session best.")

    app = create_app(tracker, log)
    client = app.test_client()
    response = client.get("/api/state")
    data = response.get_json()

    assert response.status_code == 200
    assert data["current_lap_time_ms"] == 45230
    assert data["car_position"] == 4
    assert data["gap_ahead_ms"] == 812
    assert data["tyres_wear"] == [42.0, 38.0, 61.0, 58.0]
    assert data["pit_rejoin_position"] is None
    assert data["weather"] is None
    assert data["log"] == [{"time": "14:32:07", "type": "callout", "text": "Purple lap! New session best."}]
