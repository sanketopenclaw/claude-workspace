from telemetry.state import StateTracker


def test_update_lap_data_tracks_best_lap_time():
    tracker = StateTracker()
    tracker.update_lap_data(
        {"last_lap_time_ms": 0, "current_lap_time_ms": 20000, "sector1_time_ms": 0,
         "sector2_time_ms": 0, "car_position": 3, "current_lap_num": 1, "delta_to_race_leader_ms": 5000,
         "lap_distance": 100.0},
        gap_ahead_ms=1000, gap_behind_ms=2000,
    )
    tracker.update_lap_data(
        {"last_lap_time_ms": 92000, "current_lap_time_ms": 5000, "sector1_time_ms": 0,
         "sector2_time_ms": 0, "car_position": 3, "current_lap_num": 2, "delta_to_race_leader_ms": 4800,
         "lap_distance": 200.0},
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
    tracker.update_car_status({
        "fuel_in_tank": 25.0, "fuel_remaining_laps": 4.0, "vehicle_fia_flags": 3,
        "fuel_mix": 2, "ers_deploy_mode": 1, "ers_store_energy": 3000000.0,
    })
    tracker.update_car_damage(tyres_wear=[10.0, 11.0, 9.0, 12.0], damage_components={"rear_wing": 5})

    snapshot = tracker.snapshot()

    assert snapshot.fuel_in_tank == 25.0
    assert snapshot.fuel_remaining_laps == 4.0
    assert snapshot.tyres_wear == [10.0, 11.0, 9.0, 12.0]
    assert snapshot.flag_status == 3
    assert snapshot.damage_components == {"rear_wing": 5}
    assert snapshot.fuel_mix == 2
    assert snapshot.ers_deploy_mode == 1
    assert snapshot.ers_store_energy == 3000000.0


def test_update_player_car_index():
    tracker = StateTracker()
    tracker.update_player_car_index(4)

    assert tracker.snapshot().player_car_index == 4


def test_update_session_populates_weather_and_safety_car_snapshot():
    tracker = StateTracker()
    tracker.update_session({
        "weather": 2,
        "track_temperature": 34,
        "air_temperature": 22,
        "safety_car_status": 0,
        "session_type": 10,
        "total_laps": 50,
        "pit_stop_window_ideal_lap": 22,
        "pit_stop_window_latest_lap": 28,
        "pit_stop_rejoin_position": 6,
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
    assert snapshot.session_type == 10
    assert snapshot.total_laps == 50
    assert snapshot.pit_stop_window_ideal_lap == 22
    assert snapshot.pit_stop_window_latest_lap == 28
    assert snapshot.pit_stop_rejoin_position == 6
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


def test_update_lap_data_builds_leaderboard_sorted_by_position():
    tracker = StateTracker()
    all_cars = [
        {"car_position": 2, "delta_to_race_leader_ms": 500, "current_lap_num": 4},
        {"car_position": 1, "delta_to_race_leader_ms": 0, "current_lap_num": 4},
        {"car_position": 0, "delta_to_race_leader_ms": 0, "current_lap_num": 0},  # inactive slot, filtered out
    ]
    tracker.update_lap_data(
        {"last_lap_time_ms": 0, "current_lap_time_ms": 0, "sector1_time_ms": 0, "sector2_time_ms": 0,
         "car_position": 2, "current_lap_num": 4, "delta_to_race_leader_ms": 500, "lap_distance": 300.0},
        gap_ahead_ms=500, gap_behind_ms=None, all_cars=all_cars,
    )

    leaderboard = tracker.snapshot().leaderboard

    assert len(leaderboard) == 2
    assert leaderboard[0]["car_position"] == 1
    assert leaderboard[1]["car_position"] == 2


def test_update_participants_populates_names():
    tracker = StateTracker()
    tracker.update_participants(2, [{"name": "L. Rival"}, {"name": "M. Teammate"}])

    names = tracker.snapshot().participant_names

    assert names == {0: "L. Rival", 1: "M. Teammate"}


def test_update_motion_derives_speed_kmh_for_player_car():
    tracker = StateTracker()
    motion_cars = [
        {"world_velocity_x": 0.0, "world_velocity_y": 0.0, "world_velocity_z": 0.0},
        {"world_velocity_x": 30.0, "world_velocity_y": 0.0, "world_velocity_z": 40.0},  # 50 m/s -> 180 km/h
    ]

    tracker.update_motion(player_car_index=1, motion_cars=motion_cars)

    assert tracker.snapshot().speed_kmh == 180.0


def test_update_event_send_marks_session_ended():
    tracker = StateTracker()
    tracker.update_event("SEND", None)

    assert tracker.snapshot().session_ended is True
