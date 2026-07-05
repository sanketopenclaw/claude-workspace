# F1 Race Engineer — Feature Backlog

Not built yet. Phase 1 (core telemetry + voice callouts + dashboard shell) comes first — see `docs/superpowers/plans/2026-07-05-f1-race-engineer-phase1.md`. Each item below needs its own brainstorm → spec → plan before implementation, same as Phase 1 did.

## Strategy / pit

- Undercut/overcut pit-window calculator
- ERS deploy/harvest mode advice
- Fuel mix suggestions (rich/lean target per lap)
- **Live fuel-per-lap recalculation** — continuously re-estimate fuel needed based on actual burn rate this stint (not just a fixed threshold like Phase 1's `fuel_remaining_laps < 2`), tell exact fuel needed before next pit. (Crew Chief does this.)
- "What if I box now" voice-triggered scenario sim

## Safety / awareness

- Track-limit/corner-cutting live warning (PenaltyIssued event)
- Yellow/red/VSC/safety-car callouts
- Weather forecast callout ("rain in 3 min, box for inters") — needs Session-packet parsing
- **Damage-triggered reactive callout** — detect a contact/heavy kerb hit via telemetry delta and immediately report what broke, not just a standing damage % readout. (Crew Chief does this.)
- **Incident/contact warnings for nearby cars** — relevant in races with AI, not time trial.
- **Overtake/defend spotter calls** — "car alongside on your left," "clear to move" — wheel-to-wheel awareness, adapted from Crew Chief's oval-racing spotter concept for F1 road-racing context.

## Coaching

- Braking-point/racing-line coaching vs personal-best ghost (Motion packet)
- Post-session debrief report (lap consistency, sector compare, tyre wear curve)
- Speed-trap/sector leaderboard vs field best

## Setup (Phase 3)

- Driving-style profiler + track-aware setup recommender
- Multi-track setup library (save/reuse good setups per track)

## Race awareness

- Rival behavior notes (teammate pit, retirements, DRS trains)
- Qualy gap-to-pole live countdown
- **Relative/leaderboard widget** — dashboard strip showing nearby cars' names + live gaps in one view. (SimHub does this.)

## Voice UX

- Custom "hey engineer" wake-word (replace hey_jarvis)
- Radio-static audio effect for immersion
- Voice personality picker (calm vs intense)
- **Design Q&A prompt examples around common real phrasings** — "what position am I in," "gap to car number X," "how much fuel to the end" — Crew Chief's actual query vocabulary is a good reference for what drivers naturally ask.
- Multi-language voice support

## Dashboard

- Session history DB — browse past races in dashboard
- **Halo HUD overlay style** — minimal in-cockpit overlay option (numbers over the game view) as an alternative to the full second-screen dashboard, for setups without a spare monitor. (SimHub offers this as a display mode.)

---

Explicitly skipped: shift-light/LED/button-box hardware output (SimHub feature) — not applicable, this project is screen/voice only, no hardware I/O.

Prior art referenced: Crew Chief (free, open-source voice race engineer — closest existing analog to this whole project) and SimHub (dashboard/overlay tool) — both surfaced via research, not copied code, just feature-parity ideas.
