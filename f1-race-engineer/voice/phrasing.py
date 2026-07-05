from cerebras.cloud.sdk import Cerebras
from openai import OpenAI
import config

CANNED_LINES = {
    "lap_purple": "Purple lap! New session best, {lap_time_ms} milliseconds.",
    "tyre_wear": "Tyres at {remaining_pct:.0f} percent, box window opening.",
    "fuel_critical": "Fuel critical, {fuel_remaining_laps:.1f} laps left, look after it.",
    "gap_closing_ahead": "Car ahead, gap closing, {gap_ms} milliseconds.",
    "gap_closing_behind": "Car behind closing, {gap_ms} milliseconds.",
}


def _canned_line(event):
    template = CANNED_LINES.get(event.kind, "Note: {kind}")
    try:
        return template.format(kind=event.kind, **event.data)
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
