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


def test_answer_question_falls_back_to_canned_line_when_all_providers_fail(monkeypatch):
    from telemetry.state import State

    monkeypatch.setattr(phrasing, "_call_llm", lambda prompt, max_tokens: None)
    state = State(current_lap_num=5, car_position=3)

    result = phrasing.answer_question("how's fuel?", state)

    assert result == "Radio's breaking up, say again."
