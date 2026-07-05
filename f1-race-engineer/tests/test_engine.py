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


def test_lap_completion_fires_gap_to_leader_only_in_qualifying():
    engine = RuleEngine()
    race_lap1 = State(current_lap_num=1, session_type=10, gap_to_leader_ms=5000)
    race_lap2 = State(current_lap_num=2, session_type=10, gap_to_leader_ms=4800)

    engine.check_lap_completion(race_lap1)
    events_race = engine.check_lap_completion(race_lap2)

    assert events_race == []  # session_type 10 = Race, not qualifying - no noise


def test_lap_completion_fires_gap_to_leader_in_qualifying():
    engine = RuleEngine()
    q1_lap1 = State(current_lap_num=1, session_type=6, gap_to_leader_ms=5000)
    q1_lap2 = State(current_lap_num=2, session_type=6, gap_to_leader_ms=350)
    q1_lap3_on_pole = State(current_lap_num=3, session_type=6, gap_to_leader_ms=0)

    engine.check_lap_completion(q1_lap1)
    events_gap = engine.check_lap_completion(q1_lap2)
    events_pole = engine.check_lap_completion(q1_lap3_on_pole)

    assert len(events_gap) == 1
    assert events_gap[0].kind == "gap_to_leader"
    assert events_gap[0].data["gap_to_leader_ms"] == 350
    assert len(events_pole) == 1
    assert events_pole[0].kind == "provisional_pole"


def test_check_retirement_fires_once_with_rival_name():
    engine = RuleEngine()
    state = State(
        last_retirement={"vehicle_idx": 7, "reason": 3},
        participant_names={7: "L. Rival"},
    )
    same_state = State(
        last_retirement={"vehicle_idx": 7, "reason": 3},
        participant_names={7: "L. Rival"},
    )

    events = engine.check_retirement(state)
    events_repeat = engine.check_retirement(same_state)

    assert len(events) == 1
    assert events[0].kind == "rival_retired"
    assert events[0].data["name"] == "L. Rival"
    assert events_repeat == []


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


def test_check_fuel_strategy_fires_deficit_when_burn_rate_wont_finish_race():
    engine = RuleEngine()
    # 3 laps burning 3.0kg/lap, then 2 laps remaining but only 4.0kg left (needs 6.0kg)
    lap1 = State(current_lap_num=1, fuel_in_tank=20.0, total_laps=5)
    lap2 = State(current_lap_num=2, fuel_in_tank=17.0, total_laps=5)
    lap3 = State(current_lap_num=3, fuel_in_tank=14.0, total_laps=5)
    lap4_short_on_fuel = State(current_lap_num=4, fuel_in_tank=4.0, total_laps=5)

    assert engine.check_fuel_strategy(lap1) == []  # no burn history yet
    assert engine.check_fuel_strategy(lap2) == []
    assert engine.check_fuel_strategy(lap3) == []

    events = engine.check_fuel_strategy(lap4_short_on_fuel)
    events_repeat = engine.check_fuel_strategy(lap4_short_on_fuel)  # same lap, no refire

    assert len(events) == 1
    assert events[0].kind == "fuel_strategy_deficit"
    assert events[0].data["deficit_kg"] > 0
    assert events_repeat == []


def test_check_fuel_strategy_also_advises_leaner_mix_when_rich():
    engine = RuleEngine()
    lap1 = State(current_lap_num=1, fuel_in_tank=20.0, total_laps=3, fuel_mix=3)
    lap2_short = State(current_lap_num=2, fuel_in_tank=1.0, total_laps=3, fuel_mix=3)

    engine.check_fuel_strategy(lap1)
    events = engine.check_fuel_strategy(lap2_short)

    kinds = {e.kind for e in events}
    assert kinds == {"fuel_strategy_deficit", "fuel_mix_advice"}


def test_check_fuel_strategy_silent_when_plenty_of_fuel():
    engine = RuleEngine()
    lap1 = State(current_lap_num=1, fuel_in_tank=20.0, total_laps=5)
    lap2_plenty = State(current_lap_num=2, fuel_in_tank=19.0, total_laps=5)

    engine.check_fuel_strategy(lap1)
    events = engine.check_fuel_strategy(lap2_plenty)

    assert events == []


def test_check_ers_fires_once_when_low_and_aggressive_mode():
    engine = RuleEngine()
    low_and_aggressive = State(ers_store_energy=100000.0, ers_deploy_mode=3)
    recovered = State(ers_store_energy=1000000.0, ers_deploy_mode=3)

    events_first = engine.check_ers(low_and_aggressive)
    events_repeat = engine.check_ers(low_and_aggressive)
    events_after_recovery = engine.check_ers(recovered)
    events_low_again = engine.check_ers(low_and_aggressive)

    assert len(events_first) == 1
    assert events_first[0].kind == "ers_conserve"
    assert events_repeat == []
    assert events_after_recovery == []
    assert len(events_low_again) == 1  # re-armed after recovery


def test_check_ers_silent_in_conservative_mode():
    engine = RuleEngine()
    low_but_conservative = State(ers_store_energy=100000.0, ers_deploy_mode=1)

    assert engine.check_ers(low_but_conservative) == []


def test_check_pit_window_fires_once_at_ideal_and_latest_lap():
    engine = RuleEngine()
    before = State(current_lap_num=19, pit_stop_window_ideal_lap=20, pit_stop_window_latest_lap=25)
    at_ideal = State(current_lap_num=20, pit_stop_window_ideal_lap=20, pit_stop_window_latest_lap=25)
    at_ideal_repeat = State(current_lap_num=20, pit_stop_window_ideal_lap=20, pit_stop_window_latest_lap=25)
    at_latest = State(current_lap_num=25, pit_stop_window_ideal_lap=20, pit_stop_window_latest_lap=25)

    assert engine.check_pit_window(before) == []
    events_ideal = engine.check_pit_window(at_ideal)
    events_ideal_repeat = engine.check_pit_window(at_ideal_repeat)
    events_latest = engine.check_pit_window(at_latest)

    assert len(events_ideal) == 1
    assert events_ideal[0].kind == "pit_window_open"
    assert events_ideal_repeat == []
    assert len(events_latest) == 1
    assert events_latest[0].kind == "pit_window_closing"
