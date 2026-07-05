from cerebras.cloud.sdk import Cerebras
from openai import OpenAI
import config

CANNED_LINES = {
    "lap_purple": "Purple lap! New session best, {lap_time_ms} milliseconds.",
    "tyre_wear": "Tyres at {remaining_pct:.0f} percent, box window opening.",
    "fuel_critical": "Fuel critical, {fuel_remaining_laps:.1f} laps left, look after it.",
    "gap_closing_ahead": "Car ahead, gap closing, {gap_ms} milliseconds.",
    "gap_closing_behind": "Car behind closing, {gap_ms} milliseconds.",
    "flag_change": "{flag_name} flag.",
    "flag_clear": "Green flag, track clear.",
    "safety_car": "Safety car {event_type_name}.",
    "weather_forecast": "{weather_name} expected in {time_offset} minutes, {rain_percentage} percent chance of rain.",
    "penalty": "Penalty, {time} seconds added.",
    "collision": "Contact reported, check the car.",
    "overtake_made": "Nice, place gained.",
    "overtake_lost": "Position lost, car behind through.",
    "damage_detected": "Contact! {component_name} damage, {delta:.0f} percent.",
    "damage_fault": "Warning, {component_name} fault.",
    "fuel_strategy_deficit": "Fuel tight, {deficit_kg:.2f} kilos short, need {required_burn_per_lap:.2f} per lap.",
    "fuel_mix_advice": "Switch to a leaner fuel mix to save it.",
    "ers_conserve": "ERS low, ease off deployment.",
    "pit_window_open": "Pit window open, box this lap if you can.",
    "pit_window_closing": "Last chance to pit, window closing.",
    "gap_to_leader": "Gap to pole, {gap_to_leader_ms} milliseconds.",
    "provisional_pole": "Provisional pole! Nice lap.",
    "rival_retired": "{name} is out of the session.",
}

FLAG_NAMES = {0: "no", 1: "green", 2: "blue", 3: "yellow"}
SAFETY_CAR_EVENT_NAMES = {0: "deployed", 1: "returning to pits", 2: "returned", 3: "resuming race"}
WEATHER_NAMES = {0: "clear", 1: "light cloud", 2: "overcast", 3: "light rain", 4: "heavy rain", 5: "storm"}
COMPONENT_DISPLAY_NAMES = {
    "front_left_wing": "front left wing", "front_right_wing": "front right wing", "rear_wing": "rear wing",
    "floor": "floor", "diffuser": "diffuser", "sidepod": "sidepod", "gear_box": "gearbox", "engine": "engine",
    "drs_fault": "DRS", "ers_fault": "ERS", "engine_blown": "engine", "engine_seized": "engine",
}


def _canned_line(event):
    data = dict(event.data)
    if event.kind == "flag_change":
        data["flag_name"] = FLAG_NAMES.get(data.get("flag"), "flag")
    elif event.kind == "safety_car":
        data["event_type_name"] = SAFETY_CAR_EVENT_NAMES.get(data.get("event_type"), "status change")
    elif event.kind == "weather_forecast":
        data["weather_name"] = WEATHER_NAMES.get(data.get("weather"), "weather change")
    elif event.kind in ("damage_detected", "damage_fault"):
        data["component_name"] = COMPONENT_DISPLAY_NAMES.get(data.get("component"), "car")
    template = CANNED_LINES.get(event.kind, "Note: {kind}")
    try:
        return template.format(kind=event.kind, **data)
    except (KeyError, ValueError):
        return "Note: {}".format(event.kind)


def _try_openrouter(prompt, max_tokens):
    client = OpenAI(base_url=config.OPENROUTER_BASE_URL, api_key=config.get_openrouter_api_key())
    resp = client.chat.completions.create(
        model=config.OPENROUTER_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content


def _try_nvidia(prompt, max_tokens):
    client = OpenAI(base_url=config.NVIDIA_BASE_URL, api_key=config.get_nvidia_api_key())
    resp = client.chat.completions.create(
        model=config.NVIDIA_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content


def _try_cerebras(prompt, max_tokens):
    client = Cerebras(api_key=config.get_cerebras_api_key())
    resp = client.chat.completions.create(
        model=config.CEREBRAS_MODEL,
        max_completion_tokens=max_tokens,
        temperature=0.2,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content


def _try_mistral(prompt, max_tokens):
    client = OpenAI(base_url=config.MISTRAL_BASE_URL, api_key=config.get_mistral_api_key())
    resp = client.chat.completions.create(
        model=config.MISTRAL_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content


PROVIDER_CHAIN = [_try_openrouter, _try_nvidia, _try_cerebras, _try_mistral]


def _call_llm(prompt, max_tokens, provider_chain=None):
    chain = provider_chain if provider_chain is not None else PROVIDER_CHAIN
    for provider_fn in chain:
        try:
            result = provider_fn(prompt, max_tokens)
            if result:
                return result.strip()
        except Exception:
            continue
    return None


def event_to_line(event):
    prompt = (
        "You are a terse F1 race engineer speaking on team radio. "
        f"React to this event in ONE short sentence, no filler: {event.kind} with data {event.data}."
    )
    result = _call_llm(prompt, max_tokens=60)
    return result if result else _canned_line(event)


def answer_question(question, state):
    context = (
        f"Current state: lap {state.current_lap_num}, position {state.car_position}, "
        f"fuel {state.fuel_in_tank:.1f}kg ({state.fuel_remaining_laps:.1f} laps left), "
        f"worst tyre wear {max(state.tyres_wear):.0f}%, "
        f"gap ahead {state.gap_ahead_ms}ms, gap behind {state.gap_behind_ms}ms."
    )
    prompt = (
        f"You are a terse F1 race engineer on team radio. {context}\n"
        f'Driver asks: "{question}"\nAnswer in one or two short sentences.'
    )
    result = _call_llm(prompt, max_tokens=100)
    return result if result else "Radio's breaking up, say again."
