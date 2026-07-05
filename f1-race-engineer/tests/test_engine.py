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
