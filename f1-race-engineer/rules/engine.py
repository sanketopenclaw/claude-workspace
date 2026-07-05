import dataclasses


@dataclasses.dataclass
class Event:
    kind: str
    data: dict


DAMAGE_FAULT_COMPONENTS = {"drs_fault", "ers_fault", "engine_blown", "engine_seized"}
DAMAGE_DELTA_THRESHOLD = 5


class RuleEngine:
    def __init__(self):
        self._last_lap_num_seen = None
        self._prev_best_lap_time_ms = None
        self._fired_tyre_thresholds = set()
        self._fired_fuel_warning = False
        self._last_gap_ahead_alert_lap = None
        self._last_gap_behind_alert_lap = None
        self._last_flag_status = None
        self._last_safety_car_event = None
        self._announced_weather_offsets = set()
        self._last_penalty_seen = None
        self._last_collision_seen = None
        self._last_overtake_seen = None
        self._last_damage_components = None

    def check_lap_completion(self, state):
        events = []
        lap_just_completed = (
            self._last_lap_num_seen is not None
            and state.current_lap_num != self._last_lap_num_seen
        )
        if lap_just_completed:
            if (
                state.last_lap_time_ms
                and self._prev_best_lap_time_ms is not None
                and state.last_lap_time_ms < self._prev_best_lap_time_ms
            ):
                events.append(Event("lap_purple", {"lap_time_ms": state.last_lap_time_ms}))
            self._fired_tyre_thresholds = set()
        self._last_lap_num_seen = state.current_lap_num
        self._prev_best_lap_time_ms = state.best_lap_time_ms
        return events

    def check_tyre_and_fuel(self, state):
        events = []
        worst_tyre_wear = max(state.tyres_wear)
        remaining_pct = 100 - worst_tyre_wear
        for threshold in (30, 15, 5):
            if remaining_pct <= threshold and threshold not in self._fired_tyre_thresholds:
                events.append(Event("tyre_wear", {"threshold": threshold, "remaining_pct": remaining_pct}))
                self._fired_tyre_thresholds.add(threshold)

        if state.fuel_remaining_laps < 2 and not self._fired_fuel_warning:
            events.append(Event("fuel_critical", {"fuel_remaining_laps": state.fuel_remaining_laps}))
            self._fired_fuel_warning = True
        elif state.fuel_remaining_laps >= 2:
            self._fired_fuel_warning = False

        return events

    def check_gaps(self, state):
        events = []
        if state.gap_ahead_ms is not None and state.gap_ahead_ms < 1000:
            if self._last_gap_ahead_alert_lap != state.current_lap_num:
                events.append(Event("gap_closing_ahead", {"gap_ms": state.gap_ahead_ms}))
                self._last_gap_ahead_alert_lap = state.current_lap_num
        if state.gap_behind_ms is not None and state.gap_behind_ms < 1000:
            if self._last_gap_behind_alert_lap != state.current_lap_num:
                events.append(Event("gap_closing_behind", {"gap_ms": state.gap_behind_ms}))
                self._last_gap_behind_alert_lap = state.current_lap_num
        return events

    def check_flag(self, state):
        events = []
        flag = state.flag_status
        if flag is not None and flag != self._last_flag_status:
            if flag in (2, 3):  # 2 = blue, 3 = yellow
                events.append(Event("flag_change", {"flag": flag}))
            elif flag == 1 and self._last_flag_status in (2, 3):  # back to green
                events.append(Event("flag_clear", {}))
            self._last_flag_status = flag
        return events

    def check_safety_car(self, state):
        events = []
        sc_event = state.safety_car_event
        if sc_event is not None and sc_event != self._last_safety_car_event:
            events.append(Event("safety_car", dict(sc_event)))
            self._last_safety_car_event = sc_event
        return events

    def check_weather_forecast(self, state):
        events = []
        for sample in state.weather_forecast:
            if sample["weather"] >= 3 and sample["rain_percentage"] >= 40 and sample["time_offset"] <= 15:
                offset_key = sample["time_offset"]
                if offset_key not in self._announced_weather_offsets:
                    events.append(Event("weather_forecast", dict(sample)))
                    self._announced_weather_offsets.add(offset_key)
                break  # nearest qualifying sample only
        return events

    def check_penalty(self, state):
        events = []
        penalty = state.last_penalty
        if (
            penalty is not None
            and penalty != self._last_penalty_seen
            and state.player_car_index is not None
            and penalty.get("vehicle_idx") == state.player_car_index
        ):
            events.append(Event("penalty", dict(penalty)))
        if penalty is not None:
            self._last_penalty_seen = penalty
        return events

    def check_collision(self, state):
        events = []
        collision = state.last_collision
        if (
            collision is not None
            and collision != self._last_collision_seen
            and state.player_car_index is not None
            and state.player_car_index in (collision.get("vehicle1_idx"), collision.get("vehicle2_idx"))
        ):
            events.append(Event("collision", dict(collision)))
        if collision is not None:
            self._last_collision_seen = collision
        return events

    def check_overtake(self, state):
        events = []
        overtake = state.last_overtake
        if overtake is not None and overtake != self._last_overtake_seen and state.player_car_index is not None:
            if overtake.get("overtaking_vehicle_idx") == state.player_car_index:
                events.append(Event("overtake_made", dict(overtake)))
            elif overtake.get("being_overtaken_vehicle_idx") == state.player_car_index:
                events.append(Event("overtake_lost", dict(overtake)))
        if overtake is not None:
            self._last_overtake_seen = overtake
        return events

    def check_damage_delta(self, state):
        events = []
        current = state.damage_components
        previous = self._last_damage_components
        if previous is not None and current:
            worst_component, worst_delta = None, 0
            for name, value in current.items():
                prev_value = previous.get(name)
                if prev_value is None:
                    continue
                if name in DAMAGE_FAULT_COMPONENTS:
                    if value and not prev_value:
                        events.append(Event("damage_fault", {"component": name}))
                    continue
                delta = value - prev_value
                if delta > worst_delta:
                    worst_component, worst_delta = name, delta
            if worst_component and worst_delta >= DAMAGE_DELTA_THRESHOLD:
                events.append(Event("damage_detected", {"component": worst_component, "delta": worst_delta}))
        if current:
            self._last_damage_components = dict(current)
        return events
