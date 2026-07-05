import datetime
import threading
import time
from telemetry.state import StateTracker
from telemetry.listener import TelemetryListener
from rules.engine import RuleEngine
from voice.phrasing import event_to_line, answer_question
from voice.tts import speak
from voice.wakeword import WakeWordListener
from voice.stt import record_question, transcribe
from dashboard.log import EngineerLog
from dashboard.server import run_dashboard_server
from dashboard.history import append_session
from rules.setup_library import save_best_setup, load_best_setup
import config


def _now_str():
    return datetime.datetime.now().strftime("%H:%M:%S")


def run_telemetry_loop(state_tracker, rule_engine, engineer_log):
    listener = TelemetryListener(state_tracker, ip=config.UDP_LISTEN_IP, port=config.UDP_LISTEN_PORT)
    threading.Thread(target=listener.start, daemon=True).start()

    while True:
        state = state_tracker.snapshot()
        events = []
        events += rule_engine.check_lap_completion(state)
        events += rule_engine.check_tyre_and_fuel(state)
        events += rule_engine.check_gaps(state)
        events += rule_engine.check_flag(state)
        events += rule_engine.check_safety_car(state)
        events += rule_engine.check_weather_forecast(state)
        events += rule_engine.check_penalty(state)
        events += rule_engine.check_collision(state)
        events += rule_engine.check_damage_delta(state)
        events += rule_engine.check_overtake(state)
        events += rule_engine.check_fuel_strategy(state)
        events += rule_engine.check_ers(state)
        events += rule_engine.check_pit_window(state)
        events += rule_engine.check_retirement(state)
        events += rule_engine.check_coaching(state)
        events += rule_engine.check_speed_trap(state)
        events += rule_engine.check_debrief(state)
        events += rule_engine.check_setup_recommendation(state, lookup_fn=load_best_setup)
        events += rule_engine.check_tyre_wear_imbalance(state)
        for event in events:
            line = event_to_line(event)
            engineer_log.add_callout(_now_str(), line)
            speak(line)
            if event.kind == "debrief_ready":
                append_session(rule_engine.get_lap_history(), event.data)
            elif event.kind == "new_best_lap_setup":
                save_best_setup(event.data["track_id"], event.data["setup"], event.data["lap_time_ms"])
        time.sleep(0.5)


def on_wake_word(state_tracker, engineer_log):
    wav_path = record_question()
    question = transcribe(wav_path)
    if not question:
        return
    state = state_tracker.snapshot()
    answer = answer_question(question, state)
    engineer_log.add_qa(_now_str(), question, answer)
    speak(answer)


def main():
    state_tracker = StateTracker()
    rule_engine = RuleEngine()
    engineer_log = EngineerLog()

    threading.Thread(
        target=run_telemetry_loop, args=(state_tracker, rule_engine, engineer_log), daemon=True
    ).start()

    threading.Thread(
        target=run_dashboard_server, args=(state_tracker, engineer_log), daemon=True
    ).start()

    wake_listener = WakeWordListener(on_wake=lambda: on_wake_word(state_tracker, engineer_log))
    wake_listener.start()

    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
