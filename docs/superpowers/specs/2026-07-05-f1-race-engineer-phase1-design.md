# F1 25 AI Race Engineer — Phase 1 (MVP) Design Spec

**Date:** 2026-07-05
**Project:** new project, deployed/run on the game PC (separate machine from this session, which also has Claude Code)
**Status:** Approved

---

## Goal

Live AI race engineer for F1 25 (PC). Listens to real telemetry while user races, speaks proactive callouts (lap delta, tyre/fuel, gap to rivals), and answers free-form spoken questions on demand — like a real F1 pit-wall engineer.

Data source: F1 25's built-in UDP telemetry broadcast (official EA feature, read-only, no memory injection/input automation — no anti-cheat/ban risk). Not screenshots, not phone camera — that approach was rejected in favor of the game's native telemetry API once it was confirmed available.

---

## Scope

**Phase 1 (this spec):** telemetry pipeline + 3 proactive triggers + voice Q&A. Locked, build this first.

**Phase 2 (backlog, future spec):** pit/strategy calls (undercut/overcut, pit window calc), ERS deploy/harvest advice, fuel mix advice, flag/weather/track-limit warnings, coaching + post-session debrief report, radio-static audio polish, voice personality options, session history DB.

**Phase 3 (backlog, future spec):** car setup calibration — profile user's driving style from multi-lap telemetry (braking points, throttle trace, lock-ups/spins, cornering G via Motion packet) and recommend track-specific setup deltas (wings, gears, suspension, brake bias, differential, tyre pressure).

Phase 2 and 3 are intentionally out of scope for this spec — each is its own subsystem and gets its own design pass later.

---

## Architecture

```
<game-pc>\f1-race-engineer\
├── main.py                  # orchestrator: starts listener, rule engine, wake-word thread, overlay
├── telemetry/
│   ├── listener.py          # UDP socket (port 20777), parses F1 25 packet format
│   ├── state.py             # rolling State object: lap/sector times, tyre wear, fuel, gaps
│   └── replay.py            # dev tool: record real session to file, replay for offline testing
├── rules/
│   └── engine.py            # threshold checks against State -> Event objects, dedup per lap
├── voice/
│   ├── wakeword.py          # openWakeWord listener thread ("hey engineer")
│   ├── stt.py                # faster-whisper (local) transcription
│   ├── phrasing.py           # Claude API: Event -> spoken line, or Question+State -> spoken answer
│   └── tts.py                # edge-tts playback
├── overlay.py                # small always-on-top window, shows last engineer line as text
└── config.py                 # thresholds, API keys, wake word phrase, ports
```

**Stack:** Python 3, on the game PC. Claude Code session on that same machine used to build/run it.

**Key libraries:** raw `socket` for UDP (or a maintained F1-24/25 telemetry parsing lib if the packet format matches — confirm at implementation time), `openWakeWord` (free, local wake-word), `faster-whisper` (free, local STT), `edge-tts` (free TTS), Claude API for phrasing/Q&A.

---

## Data Flow

1. Game → UDP packets (port 20777, telemetry broadcast enabled in game settings) → `listener.py` parses relevant packets (LapData, CarTelemetry, CarStatus) → `state.py` updates rolling State each tick.
2. `engine.py` runs on tick: checks thresholds against State → emits an Event on a threshold cross (deduped so the same event doesn't repeat within a lap).
3. Event → `phrasing.py` calls Claude with a small context (event type + relevant numbers) → returns one spoken line → `tts.py` plays it → same line written to `overlay.py`.
4. Parallel thread: `wakeword.py` always listening on mic → on "hey engineer" trigger, records until silence → `stt.py` transcribes → transcript + current State snapshot → `phrasing.py` (Q&A mode) → Claude answers → `tts.py` speaks it.

## Phase 1 Triggers (rule engine)

- **Lap/sector delta:** purple (overall best), green (personal best sector), yellow (slower) — compare live sector time to session best.
- **Tyre wear + fuel:** callout at wear thresholds (e.g. 30% / 15% / 5% remaining) and fuel-laps-remaining under 2.
- **Gap to car ahead/behind:** use game's own `deltaToCarInFront`/`deltaToCarInFront` fields from LapData packet directly (no manual calc needed) — callout when gap closes under ~1.0s.

---

## Error Handling

- No UDP packets received after N seconds while app expects them running → log "no telemetry" warning, keep running, don't crash.
- Claude API call fails/times out → fall back to a canned template line from the rule engine (event still gets voiced, just less natural phrasing).
- Mic/STT failure → fall back to text-only in the overlay window.
- Wake-word false trigger with no follow-up speech → short timeout, no-op.

---

## Testing

- Build `replay.py`: record one real session's raw UDP packets to a file, replay them on demand for offline dev — avoids needing to race every test cycle.
- Unit test `engine.py` threshold logic against synthetic State objects (no game needed).
- End-to-end manual test during an actual play session before calling Phase 1 done.

---

## Network/Deployment Note

Game and app both run on the same PC (the game PC), which also has its own Claude Code session — build and run happens there directly, not on this machine. No cross-machine audio streaming needed (that was considered and rejected for latency/complexity).

Game-side setup required before first run: enable UDP Telemetry broadcast in F1 25 settings (On, port 20777, target IP set to `127.0.0.1` or local broadcast since app runs on the same machine).
