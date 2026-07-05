from telemetry.state import State
from rules.engine import RuleEngine


def test_lap_completion_fires_purple_event_on_new_best():
    engine = RuleEngine()
    lap1 = State(current_lap_num=1, last_lap_time_ms=0)
    lap2 = State(current_lap_num=2, last_lap_time_ms=92000, best_lap_time_ms=92000)
    lap3 = State(current_lap_num=3, last_lap_time_ms=90500, best_lap_time_ms=90500)
    lap4 = State(current_lap_num=4, last_lap_time_ms=91000, best_lap_time_ms=90500)

    events1 = engine.check_lap_completion(lap1)
    events2 = engine.check_lap_completion(lap2)
    events3 = engine.check_lap_completion(lap3)
    events4 = engine.check_lap_completion(lap4)

    assert events1 == []
    assert events2 == []  # first completed lap, nothing to beat yet
    assert len(events3) == 1
    assert events3[0].kind == "lap_purple"
    assert events3[0].data["lap_time_ms"] == 90500
    assert events4 == []  # slower lap, no event


def test_tyre_wear_fires_once_per_threshold():
    engine = RuleEngine()
    state = State(tyres_wear=[65.0, 60.0, 55.0, 50.0], fuel_remaining_laps=5.0)  # worst = 65% worn -> 35% remaining

    events_first = engine.check_tyre_and_fuel(state)
    events_second = engine.check_tyre_and_fuel(state)  # same state, should not refire

    assert events_first == []  # 35% remaining hasn't crossed 30 yet
    assert events_second == []

    worn_more = State(tyres_wear=[72.0, 60.0, 55.0, 50.0], fuel_remaining_laps=5.0)  # 28% remaining -> crosses 30
    events_third = engine.check_tyre_and_fuel(worn_more)
    events_fourth = engine.check_tyre_and_fuel(worn_more)

    assert len(events_third) == 1
    assert events_third[0].kind == "tyre_wear"
    assert events_third[0].data["threshold"] == 30
    assert events_fourth == []  # already fired for this threshold


def test_fuel_critical_fires_once_when_below_two_laps():
    engine = RuleEngine()
    plenty_fuel = State(fuel_remaining_laps=5.0)
    low_fuel = State(fuel_remaining_laps=1.5)

    events_ok = engine.check_tyre_and_fuel(plenty_fuel)
    events_low_first = engine.check_tyre_and_fuel(low_fuel)
    events_low_second = engine.check_tyre_and_fuel(low_fuel)

    assert events_ok == []
    assert len(events_low_first) == 1
    assert events_low_first[0].kind == "fuel_critical"
    assert events_low_second == []


def test_gap_closing_fires_once_per_lap_per_direction():
    engine = RuleEngine()
    close_ahead = State(current_lap_num=1, gap_ahead_ms=800, gap_behind_ms=5000)

    events_first = engine.check_gaps(close_ahead)
    events_second = engine.check_gaps(close_ahead)  # same lap, no refire

    assert len(events_first) == 1
    assert events_first[0].kind == "gap_closing_ahead"
    assert events_first[0].data["gap_ms"] == 800
    assert events_second == []

    next_lap_still_close = State(current_lap_num=2, gap_ahead_ms=700, gap_behind_ms=5000)
    events_next_lap = engine.check_gaps(next_lap_still_close)

    assert len(events_next_lap) == 1  # new lap, allowed to fire again


def test_gap_closing_fires_independently_per_direction():
    engine = RuleEngine()
    # Both gaps close on lap 1
    both_close = State(current_lap_num=1, gap_ahead_ms=800, gap_behind_ms=900)

    events = engine.check_gaps(both_close)

    assert len(events) == 2
    kinds = {e.kind for e in events}
    assert kinds == {"gap_closing_ahead", "gap_closing_behind"}
    assert next(e for e in events if e.kind == "gap_closing_ahead").data["gap_ms"] == 800
    assert next(e for e in events if e.kind == "gap_closing_behind").data["gap_ms"] == 900


def test_gap_closing_does_not_fire_at_exactly_1000ms():
    engine = RuleEngine()
    exactly_1000 = State(current_lap_num=1, gap_ahead_ms=1000, gap_behind_ms=1000)

    events = engine.check_gaps(exactly_1000)

    assert events == []  # threshold is strictly under 1000


def test_gap_closing_handles_none_values():
    engine = RuleEngine()
    # None values should not crash
    state_with_nones = State(current_lap_num=1, gap_ahead_ms=None, gap_behind_ms=None)

    events = engine.check_gaps(state_with_nones)

    assert events == []


def test_check_flag_fires_on_change_to_yellow_and_back_to_green():
    engine = RuleEngine()
    green = State(flag_status=1)
    yellow = State(flag_status=3)
    still_yellow = State(flag_status=3)
    back_to_green = State(flag_status=1)

    assert engine.check_flag(green) == []  # first reading, no prior state to compare
    events_yellow = engine.check_flag(yellow)
    assert len(events_yellow) == 1
    assert events_yellow[0].kind == "flag_change"
    assert events_yellow[0].data["flag"] == 3
    assert engine.check_flag(still_yellow) == []  # unchanged, no refire
    events_clear = engine.check_flag(back_to_green)
    assert len(events_clear) == 1
    assert events_clear[0].kind == "flag_clear"


def test_check_safety_car_fires_once_per_new_event():
    engine = RuleEngine()
    deployed = State(safety_car_event={"safety_car_type": 1, "event_type": 0})
    same = State(safety_car_event={"safety_car_type": 1, "event_type": 0})
    resuming = State(safety_car_event={"safety_car_type": 1, "event_type": 3})

    events_first = engine.check_safety_car(deployed)
    events_repeat = engine.check_safety_car(same)
    events_resume = engine.check_safety_car(resuming)

    assert len(events_first) == 1
    assert events_first[0].kind == "safety_car"
    assert events_repeat == []
    assert len(events_resume) == 1


def test_check_weather_forecast_fires_once_for_nearest_qualifying_rain():
    engine = RuleEngine()
    state = State(weather_forecast=[
        {"time_offset": 5, "weather": 4, "rain_percentage": 70},
        {"time_offset": 20, "weather": 5, "rain_percentage": 90},
    ])

    events_first = engine.check_weather_forecast(state)
    events_repeat = engine.check_weather_forecast(state)

    assert len(events_first) == 1
    assert events_first[0].data["time_offset"] == 5
    assert events_repeat == []


def test_check_weather_forecast_ignores_dry_or_low_probability():
    engine = RuleEngine()
    state = State(weather_forecast=[
        {"time_offset": 5, "weather": 1, "rain_percentage": 0},
        {"time_offset": 10, "weather": 4, "rain_percentage": 10},
    ])

    assert engine.check_weather_forecast(state) == []


def test_check_penalty_only_fires_for_player_car():
    engine = RuleEngine()
    rival_penalty = State(player_car_index=0, last_penalty={"vehicle_idx": 5, "time": 5})
    my_penalty = State(player_car_index=0, last_penalty={"vehicle_idx": 0, "time": 10})

    assert engine.check_penalty(rival_penalty) == []
    events = engine.check_penalty(my_penalty)
    assert len(events) == 1
    assert events[0].kind == "penalty"
    assert events[0].data["time"] == 10


def test_check_collision_fires_when_player_involved():
    engine = RuleEngine()
    not_involved = State(player_car_index=0, last_collision={"vehicle1_idx": 4, "vehicle2_idx": 5, "severity": 1})
    involved = State(player_car_index=0, last_collision={"vehicle1_idx": 0, "vehicle2_idx": 5, "severity": 2})

    assert engine.check_collision(not_involved) == []
    events = engine.check_collision(involved)
    assert len(events) == 1
    assert events[0].kind == "collision"


def test_check_overtake_distinguishes_made_vs_lost():
    engine = RuleEngine()
    made = State(player_car_index=0, last_overtake={"overtaking_vehicle_idx": 0, "being_overtaken_vehicle_idx": 3})
    lost = State(player_car_index=0, last_overtake={"overtaking_vehicle_idx": 3, "being_overtaken_vehicle_idx": 0})

    events_made = engine.check_overtake(made)
    events_lost = engine.check_overtake(lost)

    assert events_made[0].kind == "overtake_made"
    assert events_lost[0].kind == "overtake_lost"


def test_check_damage_delta_fires_on_big_jump():
    engine = RuleEngine()
    before = State(damage_components={"rear_wing": 0, "floor": 0})
    after_hit = State(damage_components={"rear_wing": 20, "floor": 2})

    events_baseline = engine.check_damage_delta(before)  # first reading, nothing to compare
    events_hit = engine.check_damage_delta(after_hit)
    events_repeat = engine.check_damage_delta(after_hit)  # unchanged, no refire

    assert events_baseline == []
    assert len(events_hit) == 1
    assert events_hit[0].kind == "damage_detected"
    assert events_hit[0].data["component"] == "rear_wing"  # biggest jump
    assert events_hit[0].data["delta"] == 20
    assert events_repeat == []


def test_check_damage_delta_ignores_small_wear_increase():
    engine = RuleEngine()
    before = State(damage_components={"rear_wing": 0})
    slight_wear = State(damage_components={"rear_wing": 2})

    engine.check_damage_delta(before)
    events = engine.check_damage_delta(slight_wear)

    assert events == []


def test_check_damage_delta_fires_fault_event_on_transition():
    engine = RuleEngine()
    before = State(damage_components={"engine_blown": 0})
    blown = State(damage_components={"engine_blown": 1})

    engine.check_damage_delta(before)
    events = engine.check_damage_delta(blown)

    assert len(events) == 1
    assert events[0].kind == "damage_fault"
    assert events[0].data["component"] == "engine_blown"
