# F1 Race Engineer — Feature Backlog

Phase 1 (core telemetry + voice callouts + dashboard shell) is done — see
`docs/superpowers/plans/2026-07-05-f1-race-engineer-phase1.md`. Phase 2 groups
1-6 below are also built (design: `docs/superpowers/specs/2026-07-05-f1-race-engineer-phase2-design.md`,
full history in `.superpowers/sdd/progress.md`). Status noted inline; anything
not marked done is still just an idea.

## Strategy / pit

- [x] Undercut/overcut pit-window calculator — uses the game's own
  `pit_stop_window_ideal_lap`/`latest_lap` (Session packet) rather than
  reinventing strategy simulation
- [x] ERS deploy/harvest mode advice (`check_ers`)
- [x] Fuel mix suggestions (`fuel_mix_advice`, fires alongside a fuel deficit)
- [x] **Live fuel-per-lap recalculation** (`check_fuel_strategy` — rolling
  3-lap burn-rate average, replaces the fixed threshold)
- [ ] "What if I box now" voice-triggered scenario sim — not built

## Safety / awareness

- [x] Track-limit/corner-cutting live warning (`check_penalty`, PENA event)
- [x] Yellow/red/VSC/safety-car callouts (`check_flag`, `check_safety_car`)
- [x] Weather forecast callout (`check_weather_forecast`)
- [x] **Damage-triggered reactive callout** (`check_damage_delta` — compares
  CarDamageData components tick-over-tick)
- [x] **Incident/contact warnings** (`check_collision`, player-involvement filtered)
- [ ] **Overtake/defend spotter calls** ("car alongside," "clear to move") —
  not built; `check_overtake` covers the after-the-fact "you passed/were
  passed" case from the OVTK event, not live wheel-to-wheel proximity calls
  (would need Motion-based relative-position tracking between cars, not just
  the player)

## Coaching

- [x] Braking-point/racing-line coaching vs personal-best ghost
  (`check_coaching` — **simplified**: compares player speed at 100m lap-distance
  buckets against the session-best lap's speed at the same buckets, not a full
  spatial trajectory replay with braking points/racing line)
- [x] Post-session debrief report (`check_debrief` — **simplified**: one spoken
  summary line at session end, not a full dashboard report page)
- [x] Speed-trap callouts (`check_speed_trap` — personal/overall best from the
  SPTP event; **not built**: a full sortable sector leaderboard vs field best)

## Setup (Phase 3)

- [ ] Driving-style profiler + track-aware setup recommender
- [ ] Multi-track setup library (save/reuse good setups per track)

## Race awareness

- [x] Rival behavior notes — **simplified to retirements only**
  (`check_retirement`); teammate-pit detection and DRS-train detection not
  built (would need m_myTeam cross-referencing and historical position
  tracking respectively)
- [x] Qualy gap-to-pole live countdown (`check_lap_completion`'s
  `gap_to_leader`/`provisional_pole`, gated to qualifying session types)
- [x] **Relative/leaderboard widget** — dashboard panel, position-sorted,
  driver names via Participants packet

## Voice UX

- [ ] Custom "hey engineer" wake-word — **infra supports swapping
  `config.WAKE_WORD_NAME`, but a real custom wake-word needs recorded audio
  samples run through openWakeWord's training notebook to produce a `.onnx`
  model. Can't be fabricated without that data/training pass** — still on
  `hey_jarvis` (one of openWakeWord's pretrained models)
- [x] Radio-static audio effect (`voice/tts.py` — synthesized white-noise
  burst via numpy, no external asset needed)
- [x] Voice personality picker (calm vs intense — affects both the LLM prompt
  tone and the TTS voice used)
- [x] **Q&A prompt examples** — real driver query vocabulary added to
  `answer_question`'s prompt
- [ ] Multi-language voice support — not built (would need translated canned
  lines for every event kind plus non-English STT/TTS voice selection; too
  large to build speculatively without a specific language requirement)

## Dashboard

- [x] Session history DB — `session_history.jsonl` + `/history` page
  (**simplified**: JSON-lines file, not a real database - fine at this scale)
- [x] **Halo HUD overlay style** — `/hud` page (**simplified**: a browser page
  meant to sit in a small window, not a true OS-level always-on-top overlay)

---

Explicitly skipped: shift-light/LED/button-box hardware output (SimHub feature) — not applicable, this project is screen/voice only, no hardware I/O.

Prior art referenced: Crew Chief (free, open-source voice race engineer — closest existing analog to this whole project) and SimHub (dashboard/overlay tool) — both surfaced via research, not copied code, just feature-parity ideas.
