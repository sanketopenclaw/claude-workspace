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


class StateTracker:
    def __init__(self):
        self._lock = threading.Lock()
        self._state = State()

    def update_lap_data(self, my_lap, gap_ahead_ms, gap_behind_ms):
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
            if s.last_lap_time_ms and (s.best_lap_time_ms is None or s.last_lap_time_ms < s.best_lap_time_ms):
                s.best_lap_time_ms = s.last_lap_time_ms

    def update_car_status(self, fuel_in_tank, fuel_remaining_laps, vehicle_fia_flags):
        with self._lock:
            self._state.fuel_in_tank = fuel_in_tank
            self._state.fuel_remaining_laps = fuel_remaining_laps
            self._state.flag_status = vehicle_fia_flags

    def update_player_car_index(self, player_car_index):
        with self._lock:
            self._state.player_car_index = player_car_index

    def update_car_damage(self, tyres_wear, damage_components=None):
        with self._lock:
            self._state.tyres_wear = list(tyres_wear)
            self._state.damage_components = dict(damage_components or {})

    def update_session(self, session):
        with self._lock:
            s = self._state
            s.weather = session["weather"]
            s.track_temperature = session["track_temperature"]
            s.air_temperature = session["air_temperature"]
            s.safety_car_status = session["safety_car_status"]
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
    }

    def update_event(self, event_code, details):
        field = self._EVENT_STATE_FIELD.get(event_code)
        if field is None:
            return
        with self._lock:
            setattr(self._state, field, details)

    def snapshot(self):
        with self._lock:
            return dataclasses.replace(
                self._state,
                tyres_wear=list(self._state.tyres_wear),
                weather_forecast=list(self._state.weather_forecast),
                damage_components=dict(self._state.damage_components),
            )
