import dataclasses
import threading


@dataclasses.dataclass
class State:
    last_lap_time_ms: int = 0
    current_lap_time_ms: int = 0
    sector1_time_ms: int = 0
    sector2_time_ms: int = 0
    best_lap_time_ms: int = None
    car_position: int = 0
    current_lap_num: int = 0
    gap_ahead_ms: int = None
    gap_behind_ms: int = None
    fuel_in_tank: float = 0.0
    fuel_remaining_laps: float = 0.0
    tyres_wear: list = dataclasses.field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    weather: int = None
    track_temperature: int = None
    air_temperature: int = None
    safety_car_status: int = None
    weather_forecast: list = dataclasses.field(default_factory=list)
    last_penalty: dict = None
    safety_car_event: dict = None
    last_collision: dict = None
    last_overtake: dict = None
    last_retirement: dict = None
    flag_status: int = None
    player_car_index: int = None
    damage_components: dict = dataclasses.field(default_factory=dict)
    fuel_mix: int = None
    ers_deploy_mode: int = None
    ers_store_energy: float = None
    total_laps: int = None
    pit_stop_window_ideal_lap: int = None
    pit_stop_window_latest_lap: int = None
    pit_stop_rejoin_position: int = None
    gap_to_leader_ms: int = None
    leaderboard: list = dataclasses.field(default_factory=list)
    participant_names: dict = dataclasses.field(default_factory=dict)
    session_type: int = None
    lap_distance: float = None
    speed_kmh: float = None
    last_speed_trap: dict = None
    session_ended: bool = False
    track_id: int = None
    car_setup: dict = dataclasses.field(default_factory=dict)


class StateTracker:
    def __init__(self):
        self._lock = threading.Lock()
        self._state = State()

    def update_lap_data(self, my_lap, gap_ahead_ms, gap_behind_ms, all_cars=None):
        with self._lock:
            s = self._state
            s.last_lap_time_ms = my_lap["last_lap_time_ms"]
            s.current_lap_time_ms = my_lap["current_lap_time_ms"]
            s.sector1_time_ms = my_lap["sector1_time_ms"]
            s.sector2_time_ms = my_lap["sector2_time_ms"]
            s.car_position = my_lap["car_position"]
            s.current_lap_num = my_lap["current_lap_num"]
            s.gap_ahead_ms = gap_ahead_ms
            s.gap_behind_ms = gap_behind_ms
            s.gap_to_leader_ms = my_lap["delta_to_race_leader_ms"]
            s.lap_distance = my_lap["lap_distance"]
            if s.last_lap_time_ms and (s.best_lap_time_ms is None or s.last_lap_time_ms < s.best_lap_time_ms):
                s.best_lap_time_ms = s.last_lap_time_ms
            if all_cars is not None:
                s.leaderboard = sorted(
                    (
                        {
                            "car_index": i,
                            "car_position": car["car_position"],
                            "gap_to_leader_ms": car["delta_to_race_leader_ms"],
                            "current_lap_num": car["current_lap_num"],
                        }
                        for i, car in enumerate(all_cars)
                        if car["car_position"] > 0
                    ),
                    key=lambda entry: entry["car_position"],
                )

    def update_car_status(self, car_status):
        with self._lock:
            s = self._state
            s.fuel_in_tank = car_status["fuel_in_tank"]
            s.fuel_remaining_laps = car_status["fuel_remaining_laps"]
            s.flag_status = car_status["vehicle_fia_flags"]
            s.fuel_mix = car_status["fuel_mix"]
            s.ers_deploy_mode = car_status["ers_deploy_mode"]
            s.ers_store_energy = car_status["ers_store_energy"]

    def update_player_car_index(self, player_car_index):
        with self._lock:
            self._state.player_car_index = player_car_index

    def update_car_damage(self, tyres_wear, damage_components=None):
        with self._lock:
            self._state.tyres_wear = list(tyres_wear)
            self._state.damage_components = dict(damage_components or {})

    def update_car_setup(self, setup):
        with self._lock:
            self._state.car_setup = dict(setup)

    def update_motion(self, player_car_index, motion_cars):
        player_motion = motion_cars[player_car_index]
        speed_ms = (
            player_motion["world_velocity_x"] ** 2
            + player_motion["world_velocity_y"] ** 2
            + player_motion["world_velocity_z"] ** 2
        ) ** 0.5
        with self._lock:
            self._state.speed_kmh = speed_ms * 3.6

    def update_session(self, session):
        with self._lock:
            s = self._state
            s.weather = session["weather"]
            s.track_temperature = session["track_temperature"]
            s.air_temperature = session["air_temperature"]
            s.safety_car_status = session["safety_car_status"]
            s.session_type = session["session_type"]
            s.track_id = session["track_id"]
            s.total_laps = session["total_laps"]
            s.pit_stop_window_ideal_lap = session["pit_stop_window_ideal_lap"]
            s.pit_stop_window_latest_lap = session["pit_stop_window_latest_lap"]
            s.pit_stop_rejoin_position = session["pit_stop_rejoin_position"]
            s.weather_forecast = [
                {
                    "time_offset": sample["time_offset"],
                    "weather": sample["weather"],
                    "rain_percentage": sample["rain_percentage"],
                }
                for sample in session["weather_forecast_samples"]
            ]

    _EVENT_STATE_FIELD = {
        "PENA": "last_penalty",
        "SCAR": "safety_car_event",
        "COLL": "last_collision",
        "OVTK": "last_overtake",
        "RTMT": "last_retirement",
        "SPTP": "last_speed_trap",
    }

    def update_event(self, event_code, details):
        if event_code == "SEND":
            with self._lock:
                self._state.session_ended = True
            return
        field = self._EVENT_STATE_FIELD.get(event_code)
        if field is None:
            return
        with self._lock:
            setattr(self._state, field, details)

    def update_participants(self, num_active_cars, participants):
        with self._lock:
            self._state.participant_names = {i: p["name"] for i, p in enumerate(participants)}

    def snapshot(self):
        with self._lock:
            return dataclasses.replace(
                self._state,
                tyres_wear=list(self._state.tyres_wear),
                weather_forecast=list(self._state.weather_forecast),
                damage_components=dict(self._state.damage_components),
                leaderboard=list(self._state.leaderboard),
                participant_names=dict(self._state.participant_names),
                car_setup=dict(self._state.car_setup),
            )
