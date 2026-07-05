import dataclasses


@dataclasses.dataclass
class Event:
    kind: str
    data: dict


DAMAGE_FAULT_COMPONENTS = {"drs_fault", "ers_fault", "engine_blown", "engine_seized"}
DAMAGE_DELTA_THRESHOLD = 5
FUEL_BURN_WINDOW = 3
ERS_LOW_THRESHOLD = 500000.0
# Session type enum (standard F1 UDP appendix, stable across F1 22-25): 5=Q1, 6=Q2,
# 7=Q3, 8=Short Q, 9=OSQ. Gap-to-pole callout only makes sense in qualifying -
# firing it every race lap would just be noise (gap_ahead/gap_behind cover races).
QUALIFYING_SESSION_TYPES = {5, 6, 7, 8, 9}
COACHING_BUCKET_METERS = 100
COACHING_SPEED_DELTA_THRESHOLD_KMH = 15
TYRE_IMBALANCE_THRESHOLD = 15  # percentage points, front avg wear vs rear avg wear


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
        self._fuel_lap_tracker_lap_num = None
        self._fuel_lap_tracker_fuel = None
        self._burn_rates = []
        self._last_fuel_deficit_fired_lap = None
        self._fired_ers_warning = False
        self._fired_pit_window_ideal = False
        self._fired_pit_window_latest = False
        self._last_retirement_seen = None
        self._current_lap_reference = {}
        self._best_lap_reference = {}
        self._coaching_fired_buckets = set()
        self._lap_history = []
        self._last_speed_trap_seen = None
        self._debrief_fired = False
        self._last_track_id_seen_for_setup = None
        self._fired_tyre_imbalance_direction = None

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
            if state.session_type in QUALIFYING_SESSION_TYPES and state.gap_to_leader_ms is not None:
                if state.gap_to_leader_ms == 0:
                    events.append(Event("provisional_pole", {}))
                else:
                    events.append(Event("gap_to_leader", {"gap_to_leader_ms": state.gap_to_leader_ms}))
            self._fired_tyre_thresholds = set()

            # Coaching reference: the lap that just finished becomes the new
            # "ghost" to beat whenever it improved the session best (including
            # the very first completed lap, which has nothing to beat yet but
            # still needs to seed the reference).
            new_best = state.best_lap_time_ms is not None and state.best_lap_time_ms != self._prev_best_lap_time_ms
            if new_best:
                self._best_lap_reference = dict(self._current_lap_reference)
                if state.car_setup and state.track_id is not None:
                    events.append(Event("new_best_lap_setup", {
                        "track_id": state.track_id,
                        "setup": dict(state.car_setup),
                        "lap_time_ms": state.best_lap_time_ms,
                    }))
            self._current_lap_reference = {}
            self._coaching_fired_buckets = set()

            self._lap_history.append({
                "lap_num": self._last_lap_num_seen,
                "lap_time_ms": state.last_lap_time_ms,
                "sector1_time_ms": state.sector1_time_ms,
                "sector2_time_ms": state.sector2_time_ms,
                "worst_tyre_wear": max(state.tyres_wear) if state.tyres_wear else None,
            })
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

    def check_fuel_strategy(self, state):
        events = []
        lap_num = state.current_lap_num
        if lap_num != self._fuel_lap_tracker_lap_num:
            if self._fuel_lap_tracker_lap_num is not None and self._fuel_lap_tracker_fuel is not None:
                burn = self._fuel_lap_tracker_fuel - state.fuel_in_tank
                if burn > 0:
                    self._burn_rates.append(burn)
                    self._burn_rates = self._burn_rates[-FUEL_BURN_WINDOW:]
            self._fuel_lap_tracker_lap_num = lap_num
            self._fuel_lap_tracker_fuel = state.fuel_in_tank

        if not self._burn_rates or state.total_laps is None:
            return events
        avg_burn_per_lap = sum(self._burn_rates) / len(self._burn_rates)
        laps_remaining = state.total_laps - lap_num
        if laps_remaining <= 0:
            return events

        fuel_needed = laps_remaining * avg_burn_per_lap
        deficit_kg = fuel_needed - state.fuel_in_tank
        if deficit_kg > 0 and self._last_fuel_deficit_fired_lap != lap_num:
            events.append(Event("fuel_strategy_deficit", {
                "deficit_kg": deficit_kg,
                "avg_burn_per_lap": avg_burn_per_lap,
                "required_burn_per_lap": state.fuel_in_tank / laps_remaining,
            }))
            self._last_fuel_deficit_fired_lap = lap_num
            if state.fuel_mix in (2, 3):
                events.append(Event("fuel_mix_advice", {"current_mix": state.fuel_mix}))
        return events

    def check_ers(self, state):
        events = []
        if state.ers_store_energy is None or state.ers_deploy_mode is None:
            return events
        if state.ers_store_energy < ERS_LOW_THRESHOLD and state.ers_deploy_mode in (2, 3):
            if not self._fired_ers_warning:
                events.append(Event("ers_conserve", {"ers_store_energy": state.ers_store_energy}))
                self._fired_ers_warning = True
        elif state.ers_store_energy >= ERS_LOW_THRESHOLD:
            self._fired_ers_warning = False
        return events

    def check_pit_window(self, state):
        events = []
        lap_num = state.current_lap_num
        if (
            state.pit_stop_window_ideal_lap
            and lap_num == state.pit_stop_window_ideal_lap
            and not self._fired_pit_window_ideal
        ):
            events.append(Event("pit_window_open", {"lap": lap_num}))
            self._fired_pit_window_ideal = True
        if (
            state.pit_stop_window_latest_lap
            and lap_num == state.pit_stop_window_latest_lap
            and not self._fired_pit_window_latest
        ):
            events.append(Event("pit_window_closing", {"lap": lap_num}))
            self._fired_pit_window_latest = True
        return events

    def check_retirement(self, state):
        events = []
        retirement = state.last_retirement
        if retirement is not None and retirement != self._last_retirement_seen:
            vehicle_idx = retirement.get("vehicle_idx")
            name = state.participant_names.get(vehicle_idx, "a rival")
            events.append(Event("rival_retired", {"vehicle_idx": vehicle_idx, "name": name}))
        if retirement is not None:
            self._last_retirement_seen = retirement
        return events

    def check_coaching(self, state):
        events = []
        if state.lap_distance is None or state.speed_kmh is None or state.lap_distance < 0:
            return events
        bucket = int(state.lap_distance // COACHING_BUCKET_METERS)
        self._current_lap_reference[bucket] = state.speed_kmh
        reference_speed = self._best_lap_reference.get(bucket)
        if reference_speed is not None and bucket not in self._coaching_fired_buckets:
            delta = reference_speed - state.speed_kmh
            if delta >= COACHING_SPEED_DELTA_THRESHOLD_KMH:
                events.append(Event("coaching_slower", {
                    "bucket_m": bucket * COACHING_BUCKET_METERS,
                    "delta_kmh": delta,
                }))
                self._coaching_fired_buckets.add(bucket)
        return events

    def check_speed_trap(self, state):
        events = []
        trap = state.last_speed_trap
        if (
            trap is not None
            and trap != self._last_speed_trap_seen
            and state.player_car_index is not None
            and trap.get("vehicle_idx") == state.player_car_index
        ):
            if trap.get("is_overall_fastest_in_session"):
                events.append(Event("speed_trap_overall_best", dict(trap)))
            elif trap.get("is_driver_fastest_in_session"):
                events.append(Event("speed_trap_personal_best", dict(trap)))
        if trap is not None:
            self._last_speed_trap_seen = trap
        return events

    def check_debrief(self, state):
        events = []
        if state.session_ended and not self._debrief_fired:
            self._debrief_fired = True
            lap_times = [lap["lap_time_ms"] for lap in self._lap_history if lap["lap_time_ms"]]
            if lap_times:
                events.append(Event("debrief_ready", {
                    "lap_count": len(self._lap_history),
                    "best_lap_ms": min(lap_times),
                    "avg_lap_ms": sum(lap_times) / len(lap_times),
                }))
        return events

    def get_lap_history(self):
        return list(self._lap_history)

    def check_setup_recommendation(self, state, lookup_fn=None):
        events = []
        if lookup_fn is None or state.track_id is None:
            return events
        if state.track_id == self._last_track_id_seen_for_setup:
            return events
        self._last_track_id_seen_for_setup = state.track_id
        best = lookup_fn(state.track_id)
        if best is not None:
            events.append(Event("setup_reference_available", {
                "track_id": state.track_id,
                "lap_time_ms": best["lap_time_ms"],
            }))
        return events

    def check_tyre_wear_imbalance(self, state):
        events = []
        if not state.tyres_wear or len(state.tyres_wear) < 4:
            return events
        front_avg = (state.tyres_wear[0] + state.tyres_wear[1]) / 2
        rear_avg = (state.tyres_wear[2] + state.tyres_wear[3]) / 2
        diff = front_avg - rear_avg
        if diff >= TYRE_IMBALANCE_THRESHOLD:
            direction = "front"
        elif diff <= -TYRE_IMBALANCE_THRESHOLD:
            direction = "rear"
        else:
            direction = None

        if direction is not None and direction != self._fired_tyre_imbalance_direction:
            events.append(Event("setup_hint_tyre_imbalance", {"direction": direction, "diff": abs(diff)}))
        self._fired_tyre_imbalance_direction = direction
        return events
