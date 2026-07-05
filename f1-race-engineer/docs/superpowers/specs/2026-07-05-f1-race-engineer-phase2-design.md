# F1 Race Engineer — Phase 2 Design

Status: approved for autonomous overnight execution (user going offline, explicitly
authorized building all groups without further check-ins). Design decisions for
Group 1 were made interactively; Groups 2-7 are scoped here and refined with
engineering judgment during implementation, documented in commit messages and
the SDD ledger (`.superpowers/sdd/progress.md`) as they're built.

## Scope and ordering

Phase 2 backlog (`FEATURE_BACKLOG.md`) decomposed into 7 groups, each its own
brainstorm→implement→test→commit cycle:

1. **UDP infra expansion** — parse Session, Event, Motion packets. Foundation
   for groups 2-5.
2. **Safety/awareness** — flag/safety-car/VSC callouts, weather forecast
   callout, track-limit/penalty warning.
3. **Strategy** — live fuel-per-lap recalculation, pit-window calculator,
   ERS/fuel-mix advice.
4. **Race awareness** — relative/leaderboard widget, rival behavior notes,
   qualy gap-to-pole countdown.
5. **Coaching** — wire Motion packet (deferred from group 1), braking/line
   coaching vs personal best, debrief report, sector leaderboard.
6. **Voice UX polish** — wake-word rename, personality picker, radio-static
   audio fx, Q&A phrasing examples. Independent of telemetry groups.
7. **Dashboard extras** — session history DB, halo HUD overlay mode, wire
   remaining placeholders (pit/weather panels) to real data from groups 2-4.

Damage-triggered reactive callout and overtake/defend spotter calls (from the
backlog's Safety/awareness and Race awareness sections) are folded into groups
2 and 4 respectively, using CarDamage-delta detection and the Motion/Event
data those groups already depend on.

## Group 1 — UDP infra expansion (approved design)

**Parser helper** (`telemetry/packets.py`): a field-spec-list helper replaces
hand-written `struct` format strings for the three new packets, to avoid the
class of bug just fixed in `CAR_STATUS_FORMAT` (format string silently
drifting from the field-name list):

```python
def _spec_format(spec):
    return "<" + "".join(t for _, t in spec)

def _unpack_spec(spec, data, offset):
    values = struct.unpack_from(_spec_format(spec), data, offset)
    return dict(zip((name for name, _ in spec), values))
```

Each struct (including nested ones — `MarshalZone`, `WeatherForecastSample`,
`ActiveAeroZone`, `DRSZone`, `CarMotionData`) gets one `_SPEC` list of
`(name, struct_type_char)` pairs copied from the official EA spec
(`P403n1x87/f1-packets` `data/spec.h`, "F1 25: 2026 Season Pack").

**New parsing functions** (full struct parse):
- `parse_session_packet(data)` → dict of all top-level fields + nested lists
  (`marshal_zones`, `weather_forecast_samples` sliced to
  `m_numWeatherForecastSamples`, `active_aero_zones_full/partial`,
  `drs_zones`, `weekend_structure`)
- `parse_event_packet(data)` → `(event_code: str, details: dict | None)`,
  routing the 4-char code to the right union variant (21 codes total: 7 with
  no payload — SSTA/SEND/DRSE/CHQF/STLG/LGOT/RDFL — and 14 with a payload
  struct — FTLP/RTMT/DRSD/TMPT/RCWN/PENA/SPTP/DTSV/SGSV/FLBK/BUTN/OVTK/SCAR/COLL)
- `parse_motion_packet(data)` → list of 24 per-car dicts (position/velocity/
  direction/g-force/yaw-pitch-roll) — **parser only**, not wired into
  listener/state until a later group consumes it (per-tick copy of 24 cars ×
  18 fields for nothing would be waste)

**StateTracker wiring** (Session + Event only — matches the existing
precedent where `LapData` parses all cars fully but `State` only keeps
derived `gap_ahead`/`gap_behind`):

- `update_session(session)` promotes: `weather`, `track_temperature`,
  `air_temperature`, `safety_car_status`, `weather_forecast` (trimmed list of
  `{time_offset, weather, rain_percentage}`). Everything else parsed but
  discarded — nothing uses it yet.
- `update_event(event_code, details)` promotes to typed fields only for
  backlog-relevant codes: `last_penalty` (PENA), `safety_car_event` (SCAR),
  `last_collision` (COLL), `last_overtake` (OVTK), `last_retirement` (RTMT).
  Other codes parsed correctly (full parse honored) but not stored yet.

**Testing**: mirrors `test_packets.py`'s existing style — synthetic packets
built from the same `_SPEC` lists, one test per struct/event-variant, plus
extending `test_dry_run_e2e.py`'s pipeline with a Session and a couple of
Event packets.

## Groups 2-7

Scoped at the level above; concrete rule-engine checks, phrasing templates,
and dashboard surfaces get designed just-in-time per group during
implementation, following the same TDD/verification discipline as Phase 1.
Each group's real design decisions (what exactly got built, what was
simplified or deferred, and why) are recorded in that group's commit
message(s) and the SDD ledger rather than re-litigated here.
