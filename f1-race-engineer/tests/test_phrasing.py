from rules.engine import Event
from voice import phrasing


def test_call_llm_returns_first_successful_provider_and_skips_failures():
    def fails(prompt, max_tokens):
        raise RuntimeError("simulated failure")

    def succeeds(prompt, max_tokens):
        return "  engineer line  "

    result = phrasing._call_llm("test prompt", 60, provider_chain=[fails, succeeds])

    assert result == "engineer line"


def test_call_llm_returns_none_when_all_providers_fail():
    def fails(prompt, max_tokens):
        raise RuntimeError("simulated failure")

    result = phrasing._call_llm("test prompt", 60, provider_chain=[fails, fails])

    assert result is None


def test_event_to_line_falls_back_to_canned_when_all_providers_fail(monkeypatch):
    monkeypatch.setattr(phrasing, "_call_llm", lambda prompt, max_tokens: None)
    event = Event("tyre_wear", {"threshold": 30, "remaining_pct": 28.0})

    result = phrasing.event_to_line(event)

    assert result == "Tyres at 28 percent, box window opening."


def test_canned_line_for_flag_change_uses_flag_name():
    event = Event("flag_change", {"flag": 3})
    assert phrasing._canned_line(event) == "yellow flag."


def test_canned_line_for_safety_car_uses_event_type_name():
    event = Event("safety_car", {"safety_car_type": 1, "event_type": 0})
    assert phrasing._canned_line(event) == "Safety car deployed."


def test_canned_line_for_weather_forecast_uses_weather_name():
    event = Event("weather_forecast", {"time_offset": 5, "weather": 4, "rain_percentage": 70})
    assert phrasing._canned_line(event) == "heavy rain expected in 5 minutes, 70 percent chance of rain."


def test_canned_line_for_damage_detected_uses_component_name():
    event = Event("damage_detected", {"component": "rear_wing", "delta": 20})
    assert phrasing._canned_line(event) == "Contact! rear wing damage, 20 percent."


def test_canned_line_for_fuel_strategy_deficit():
    event = Event("fuel_strategy_deficit", {
        "deficit_kg": 1.333, "avg_burn_per_lap": 5.33, "required_burn_per_lap": 4.0,
    })
    assert phrasing._canned_line(event) == "Fuel tight, 1.33 kilos short, need 4.00 per lap."


def test_canned_line_for_pit_window_open():
    event = Event("pit_window_open", {"lap": 20})
    assert phrasing._canned_line(event) == "Pit window open, box this lap if you can."


def test_canned_line_for_rival_retired():
    event = Event("rival_retired", {"vehicle_idx": 7, "name": "L. Rival"})
    assert phrasing._canned_line(event) == "L. Rival is out of the session."


def test_canned_line_for_coaching_slower():
    event = Event("coaching_slower", {"bucket_m": 300, "delta_kmh": 22.0})
    assert phrasing._canned_line(event) == "Losing time at 300 metres, 22 down on your best."


def test_canned_line_for_debrief_ready():
    event = Event("debrief_ready", {"lap_count": 5, "best_lap_ms": 90000, "avg_lap_ms": 91500.0})
    assert phrasing._canned_line(event) == "Session done. 5 laps, best 90000 milliseconds, average 91500."


def test_answer_question_falls_back_to_canned_line_when_all_providers_fail(monkeypatch):
    from telemetry.state import State

    monkeypatch.setattr(phrasing, "_call_llm", lambda prompt, max_tokens: None)
    state = State(current_lap_num=5, car_position=3)

    result = phrasing.answer_question("how's fuel?", state)

    assert result == "Radio's breaking up, say again."
