import os
from flask import Flask, jsonify, send_from_directory
from voice.phrasing import WEATHER_NAMES
from dashboard.history import read_sessions


def create_app(state_tracker, engineer_log):
    app = Flask(__name__, static_folder=os.path.dirname(os.path.abspath(__file__)), static_url_path="")

    @app.route("/api/state")
    def api_state():
        state = state_tracker.snapshot()
        weather = None
        if state.weather is not None:
            weather = {
                "code": state.weather,
                "name": WEATHER_NAMES.get(state.weather, "unknown"),
                "track_temp": state.track_temperature,
                "air_temp": state.air_temperature,
            }
        return jsonify({
            "current_lap_time_ms": state.current_lap_time_ms,
            "last_lap_time_ms": state.last_lap_time_ms,
            "best_lap_time_ms": state.best_lap_time_ms,
            "car_position": state.car_position,
            "current_lap_num": state.current_lap_num,
            "gap_ahead_ms": state.gap_ahead_ms,
            "gap_behind_ms": state.gap_behind_ms,
            "fuel_in_tank": state.fuel_in_tank,
            "fuel_remaining_laps": state.fuel_remaining_laps,
            "tyres_wear": state.tyres_wear,
            "pit_rejoin_position": state.pit_stop_rejoin_position,
            "pit_window_ideal_lap": state.pit_stop_window_ideal_lap,
            "pit_window_latest_lap": state.pit_stop_window_latest_lap,
            "weather": weather,
            "car_setup": state.car_setup or None,
            "leaderboard": [
                {**entry, "name": state.participant_names.get(entry["car_index"], f"Car {entry['car_index']}")}
                for entry in state.leaderboard
            ],
            "log": engineer_log.snapshot(),
        })

    @app.route("/api/sessions")
    def api_sessions():
        return jsonify(read_sessions())

    @app.route("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.route("/hud")
    def hud():
        return send_from_directory(app.static_folder, "hud.html")

    @app.route("/history")
    def history_page():
        return send_from_directory(app.static_folder, "history.html")

    return app


def run_dashboard_server(state_tracker, engineer_log, port=5000):
    app = create_app(state_tracker, engineer_log)
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
