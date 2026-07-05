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

    def update_car_status(self, fuel_in_tank, fuel_remaining_laps):
        with self._lock:
            self._state.fuel_in_tank = fuel_in_tank
            self._state.fuel_remaining_laps = fuel_remaining_laps

    def update_car_damage(self, tyres_wear):
        with self._lock:
            self._state.tyres_wear = list(tyres_wear)

    def snapshot(self):
        with self._lock:
            return dataclasses.replace(self._state, tyres_wear=list(self._state.tyres_wear))
