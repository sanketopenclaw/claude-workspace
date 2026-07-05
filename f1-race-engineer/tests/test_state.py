from telemetry.state import StateTracker


def test_update_lap_data_tracks_best_lap_time():
    tracker = StateTracker()
    tracker.update_lap_data(
        {"last_lap_time_ms": 0, "current_lap_time_ms": 20000, "sector1_time_ms": 0,
         "sector2_time_ms": 0, "car_position": 3, "current_lap_num": 1},
        gap_ahead_ms=1000, gap_behind_ms=2000,
    )
    tracker.update_lap_data(
        {"last_lap_time_ms": 92000, "current_lap_time_ms": 5000, "sector1_time_ms": 0,
         "sector2_time_ms": 0, "car_position": 3, "current_lap_num": 2},
        gap_ahead_ms=900, gap_behind_ms=2100,
    )

    snapshot = tracker.snapshot()

    assert snapshot.last_lap_time_ms == 92000
    assert snapshot.best_lap_time_ms == 92000
    assert snapshot.current_lap_num == 2
    assert snapshot.gap_ahead_ms == 900
    assert snapshot.gap_behind_ms == 2100


def test_update_car_status_and_damage_populate_snapshot():
    tracker = StateTracker()
    tracker.update_car_status(fuel_in_tank=25.0, fuel_remaining_laps=4.0)
    tracker.update_car_damage(tyres_wear=[10.0, 11.0, 9.0, 12.0])

    snapshot = tracker.snapshot()

    assert snapshot.fuel_in_tank == 25.0
    assert snapshot.fuel_remaining_laps == 4.0
    assert snapshot.tyres_wear == [10.0, 11.0, 9.0, 12.0]


def test_update_session_populates_weather_and_safety_car_snapshot():
    tracker = StateTracker()
    tracker.update_session({
        "weather": 2,
        "track_temperature": 34,
        "air_temperature": 22,
        "safety_car_status": 0,
        "weather_forecast_samples": [
            {"time_offset": 0, "weather": 2, "rain_percentage": 10, "session_type": 1,
             "track_temperature": 34, "track_temperature_change": 0,
             "air_temperature": 22, "air_temperature_change": 0},
            {"time_offset": 15, "weather": 3, "rain_percentage": 60, "session_type": 1,
             "track_temperature": 30, "track_temperature_change": 1,
             "air_temperature": 21, "air_temperature_change": 1},
        ],
    })

    snapshot = tracker.snapshot()

    assert snapshot.weather == 2
    assert snapshot.track_temperature == 34
    assert snapshot.air_temperature == 22
    assert snapshot.safety_car_status == 0
    assert snapshot.weather_forecast == [
        {"time_offset": 0, "weather": 2, "rain_percentage": 10},
        {"time_offset": 15, "weather": 3, "rain_percentage": 60},
    ]


def test_update_event_routes_backlog_relevant_codes_to_typed_fields():
    tracker = StateTracker()
    tracker.update_event("PENA", {"penalty_type": 1, "vehicle_idx": 3})
    tracker.update_event("SCAR", {"safety_car_type": 1, "event_type": 0})
    tracker.update_event("COLL", {"vehicle1_idx": 2, "vehicle2_idx": 5, "severity": 1})
    tracker.update_event("OVTK", {"overtaking_vehicle_idx": 4, "being_overtaken_vehicle_idx": 6})
    tracker.update_event("RTMT", {"vehicle_idx": 7, "reason": 3})
    tracker.update_event("BUTN", {"button_status": 12345})  # not a promoted code, should be ignored

    snapshot = tracker.snapshot()

    assert snapshot.last_penalty == {"penalty_type": 1, "vehicle_idx": 3}
    assert snapshot.safety_car_event == {"safety_car_type": 1, "event_type": 0}
    assert snapshot.last_collision == {"vehicle1_idx": 2, "vehicle2_idx": 5, "severity": 1}
    assert snapshot.last_overtake == {"overtaking_vehicle_idx": 4, "being_overtaken_vehicle_idx": 6}
    assert snapshot.last_retirement == {"vehicle_idx": 7, "reason": 3}
