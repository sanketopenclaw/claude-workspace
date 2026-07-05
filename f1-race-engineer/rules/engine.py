import dataclasses


@dataclasses.dataclass
class Event:
    kind: str
    data: dict


class RuleEngine:
    def __init__(self):
        self._last_lap_num_seen = None
        self._prev_best_lap_time_ms = None
        self._fired_tyre_thresholds = set()
        self._fired_fuel_warning = False
        self._last_gap_ahead_alert_lap = None
        self._last_gap_behind_alert_lap = None

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
