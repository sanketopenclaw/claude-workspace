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
