from telemetry.state import StateTracker
from dashboard.log import EngineerLog
from dashboard.server import create_app


def test_api_state_returns_expected_shape_and_values():
    tracker = StateTracker()
    tracker.update_car_status({
        "fuel_in_tank": 34.6, "fuel_remaining_laps": 3.2, "vehicle_fia_flags": 0,
        "fuel_mix": 1, "ers_deploy_mode": 0, "ers_store_energy": 0.0,
    })
    tracker.update_car_damage(tyres_wear=[42.0, 38.0, 61.0, 58.0])
    tracker.update_participants(2, [{"name": "Me"}, {"name": "L. Rival"}])
    tracker.update_lap_data(
        {"last_lap_time_ms": 92104, "current_lap_time_ms": 45230, "sector1_time_ms": 0,
         "sector2_time_ms": 0, "car_position": 4, "current_lap_num": 12, "delta_to_race_leader_ms": 8500,
         "lap_distance": 1500.0},
        gap_ahead_ms=812, gap_behind_ms=1240,
        all_cars=[
            {"car_position": 4, "delta_to_race_leader_ms": 8500, "current_lap_num": 12},
            {"car_position": 1, "delta_to_race_leader_ms": 0, "current_lap_num": 12},
        ],
    )
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
    assert data["leaderboard"][0]["name"] == "L. Rival"
    assert data["leaderboard"][0]["car_position"] == 1
    assert data["leaderboard"][1]["name"] == "Me"


def test_api_state_wires_pit_and_weather_from_session_data():
    tracker = StateTracker()
    tracker.update_session({
        "weather": 3, "track_temperature": 28, "air_temperature": 19, "safety_car_status": 0,
        "session_type": 10, "total_laps": 50,
        "pit_stop_window_ideal_lap": 22, "pit_stop_window_latest_lap": 28, "pit_stop_rejoin_position": 6,
        "weather_forecast_samples": [],
    })
    log = EngineerLog()

    app = create_app(tracker, log)
    data = app.test_client().get("/api/state").get_json()

    assert data["weather"] == {"code": 3, "name": "light rain", "track_temp": 28, "air_temp": 19}
    assert data["pit_rejoin_position"] == 6
    assert data["pit_window_ideal_lap"] == 22
    assert data["pit_window_latest_lap"] == 28


def test_api_sessions_returns_read_sessions_result(monkeypatch):
    import dashboard.server as server_module

    fake_sessions = [{"ended_at": "2026-07-06T00:00:00", "laps": [], "summary": {"lap_count": 3}}]
    monkeypatch.setattr(server_module, "read_sessions", lambda: fake_sessions)

    app = create_app(StateTracker(), EngineerLog())
    data = app.test_client().get("/api/sessions").get_json()

    assert data == fake_sessions


def test_hud_and_history_pages_serve_html():
    app = create_app(StateTracker(), EngineerLog())
    client = app.test_client()

    hud_resp = client.get("/hud")
    history_resp = client.get("/history")

    assert hud_resp.status_code == 200
    assert b"<title>Race Engineer HUD</title>" in hud_resp.data
    assert history_resp.status_code == 200
    assert b"<title>Session History</title>" in history_resp.data
