# F1 Race Engineer — Web Dashboard Design Spec

**Date:** 2026-07-05
**Project:** `C:\Claude\f1-race-engineer\` — replaces Task 16 (tkinter overlay) and adjusts Task 17 (orchestrator) of the Phase 1 plan
**Status:** Approved

---

## Goal

Single-screen live dashboard replacing the plain tkinter overlay: all telemetry, the engineer's spoken/Q&A log, and (later) car setup recommendations, visible at a glance while racing. Runs as a small local web server on the laptop; the driver keeps a browser tab pinned on screen.

Visual design was produced via Claude Design (`claude.ai/design`, project "F1 Live Race Dashboard") and pulled into this repo as source-of-truth for layout, color, and typography. The pulled file (`F1 Race Dashboard.dc.html`) uses Claude Design's proprietary component runtime and cannot run standalone — this spec translates it to plain HTML/CSS/vanilla JS served by Flask.

---

## Architecture

```
C:\Claude\f1-race-engineer\dashboard\
├── server.py       # Flask app: GET /api/state, GET / (serves index.html)
├── index.html       # static page, vanilla JS polling
├── style.css         # dark theme, extracted from the Claude Design file
└── log.py            # EngineerLog: rolling deque of {time, type, text, q}, thread-safe
```

`server.py` runs in a background thread started from `main.py`, alongside the existing telemetry-listener and wake-word threads. It reads `state_tracker.snapshot()` (already built, Task 7) and `EngineerLog.snapshot()` on each `/api/state` request and returns JSON. No WebSocket — the frontend polls every 500ms via `fetch()`, matching the pulled design's own JS.

`main.py`'s orchestrator loop (Task 17) already produces `Event` objects and calls `phrasing.event_to_line()` / `phrasing.answer_question()`. It now also appends each resulting line to the shared `EngineerLog` (timestamp, `"callout"` or `"qa"` type, text, and the original question for `qa` entries) right before/after calling `tts.speak()`.

---

## Panels (visual layout matches the pulled design exactly)

Two-column grid, telemetry on the left (wider), team radio + car setup stacked on the right.

1. **Telemetry** (real data, all from existing `State`):
   - Current lap time (large digits), delta to best (color: purple if new best, green if ahead, red if behind)
   - Position (large number)
   - Gap ahead / gap behind (ms, formatted `+X.XXX`)
   - Tyre wear: 4 values, color-coded (green >50% life, yellow 20-50%, red <20%)
   - Fuel: kg remaining (already in `State.fuel_in_tank`/`fuel_remaining_laps`)

2. **Pit Window** (placeholder for now — see Open Question below):
   - Shows an "awaiting data" state, not fabricated numbers. Real version needs a pit-strategy calculator (rival gaps + pit-lane time loss) that doesn't exist yet — Phase 2 backlog item.

3. **Weather** (placeholder for now, same reasoning):
   - Shows an "awaiting data" state. Real version needs Session-packet parsing (track/air temp, rain%) not yet built — Phase 2 backlog item.

4. **Team Radio / Engineer Log** (real data, from `EngineerLog`):
   - Scrolling timestamped feed, newest at bottom, auto-scrolls. Callout entries and Q&A entries visually distinguished (accent color + tag), matching the pulled design's styling.

5. **Car Setup** (placeholder, unchanged from original plan):
   - "Setup recommendations coming soon" — Phase 3, not designed yet.

**Explicit rule:** any panel without real backend data shows a clearly-labeled placeholder/"awaiting data" state — never a fabricated or simulated number in the shipped app. (The pulled design file has a `_simulate()` demo-data generator for previewing the UI standalone — that stays dev-only, e.g. behind a `?demo=1` query param, and is never reachable during normal `main.py` operation where a real state_tracker is present.)

---

## Data contract: `GET /api/state`

```json
{
  "current_lap_time_ms": 45230,
  "last_lap_time_ms": 92104,
  "best_lap_time_ms": 90500,
  "car_position": 4,
  "current_lap_num": 12,
  "gap_ahead_ms": 812,
  "gap_behind_ms": 1240,
  "fuel_in_tank": 34.6,
  "fuel_remaining_laps": 3.2,
  "tyres_wear": [42.0, 38.0, 61.0, 58.0],
  "pit_rejoin_position": null,
  "weather": null,
  "log": [
    {"time": "14:32:07", "type": "callout", "text": "Purple lap! New session best."},
    {"time": "14:32:41", "type": "qa", "q": "How's fuel looking?", "text": "Fuel is positive, plus half a lap. Push now."}
  ]
}
```

`pit_rejoin_position` and `weather` are always `null` in this phase — frontend renders their panels in the placeholder state whenever the value is `null`, real value whenever populated (so wiring in real data later is a backend-only change, no frontend rework).

---

## Error handling

- If `/api/state` fails to fetch (server not up yet, network hiccup), frontend keeps showing the last good values rather than blanking the screen — matches the pulled design's fallback-to-last-known-state behavior, just without the fake-data simulator active in production.
- Flask server thread failure should not crash `main.py` — wrap its startup in the same style as the wake-word/listener threads (daemon thread, exceptions logged not propagated).

---

## Testing

- `server.py`'s `/api/state` route gets a unit test using Flask's test client against a fixed `StateTracker`/`EngineerLog` fixture — asserts the JSON shape and field values, no real browser needed.
- Manual verification: open the page, confirm live values update during a Task-18-style manual play session, confirm the log scrolls and both entry types render distinctly, confirm Pit Window/Weather show the placeholder state (not blank, not fake numbers).

---

## Open Question — resolved

Pit Window and Weather panels ship as placeholders in this phase (decided over building their real backends now, which would meaningfully extend Phase 1 further). Wiring them up is tracked as Phase 2 backlog: Session-packet parsing for weather, pit-strategy calculator for the pit window.
