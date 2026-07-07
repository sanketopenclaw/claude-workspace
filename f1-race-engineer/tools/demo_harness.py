"""
Runs the real app pipeline (listener -> state -> rule engine -> dashboard)
against tools/demo_replay.py's synthetic UDP stream, with TTS/wake-word
stubbed out (no mic/speaker needed). Prints every callout as it fires and
dumps the final /api/state-equivalent snapshot, so callout timing/content
and dashboard data can be checked without a real F1 25 session running.
"""
import concurrent.futures
import queue
import sys
import threading
import time

sys.path.insert(0, ".")

import voice.tts
voice.tts.speak = lambda text: None  # no audio device needed for this check

import config
config.UDP_LISTEN_PORT = 20777

from telemetry.state import StateTracker
from telemetry.listener import TelemetryListener
from rules.engine import RuleEngine
from voice.phrasing import event_to_line
from dashboard.log import EngineerLog
from dashboard.server import run_dashboard_server

import demo_replay

_phrasing_executor = concurrent.futures.ThreadPoolExecutor(max_workers=8, thread_name_prefix="event-phrasing")
_announce_queue = queue.Queue()


def _announcer_loop(engineer_log):
    while True:
        submit_ts, future, event = _announce_queue.get()
        line = future.result()
        ts = time.strftime("%H:%M:%S")
        delay = time.time() - submit_ts
        print(f"[callout {ts} +{delay:.1f}s] {event.kind}: {line}")
        engineer_log.add_callout(ts, line)


def run_rule_loop(state_tracker, rule_engine, engineer_log, stop_event):
    while not stop_event.is_set():
        state = state_tracker.snapshot()
        events = []
        events += rule_engine.check_flashback_resync(state)
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
        events += rule_engine.check_speed_trap(state)
        events += rule_engine.check_tyre_wear_imbalance(state)
        for event in events:
            future = _phrasing_executor.submit(event_to_line, event)
            _announce_queue.put((time.time(), future, event))
        time.sleep(0.5)


def main():
    state_tracker = StateTracker()
    rule_engine = RuleEngine()
    engineer_log = EngineerLog()
    stop_event = threading.Event()

    listener = TelemetryListener(state_tracker, ip="127.0.0.1", port=20777)
    threading.Thread(target=listener.start, daemon=True).start()

    threading.Thread(target=run_rule_loop, args=(state_tracker, rule_engine, engineer_log, stop_event), daemon=True).start()

    threading.Thread(target=run_dashboard_server, args=(state_tracker, engineer_log), daemon=True).start()

    threading.Thread(target=_announcer_loop, args=(engineer_log,), daemon=True).start()

    time.sleep(1.0)  # let sockets/Flask bind
    print("[harness] dashboard live at http://127.0.0.1:5000  (Ctrl+C to stop after scenario)")

    demo_replay.run_scenario()

    time.sleep(2.0)  # let final rule-loop tick process last packets
    stop_event.set()

    final = state_tracker.snapshot()
    print("\n[harness] final state snapshot:")
    print(f"  car_position={final.car_position} lap={final.current_lap_num}")
    print(f"  fuel_in_tank={final.fuel_in_tank} fuel_remaining_laps={final.fuel_remaining_laps}")
    print(f"  tyres_wear={final.tyres_wear}")
    print(f"  flag_status={final.flag_status}")
    print(f"  gap_ahead_ms={final.gap_ahead_ms} gap_behind_ms={final.gap_behind_ms} gap_to_leader_ms={final.gap_to_leader_ms}")
    print("\n[harness] full callout log:")
    for entry in engineer_log.snapshot():
        print(f"  {entry}")

    print("\n[harness] leave running for manual dashboard check, or Ctrl+C now.")
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
