# Token-saving process — design spec

Date: 2026-07-06
Scope: global (all Claude Code sessions/projects for this user), not specific to f1-race-engineer.

## Goal

Reduce per-session token/context consumption across all active projects, with the process enforced automatically at session start rather than relying on the model remembering to do it.

## Background

- No existing skill/plugin does this end-to-end. Evaluated and rejected: MemOS (wrong use case, needs hosted infra), savethetokens (7 stars, stale 5mo).
- Adopted: `codesight` (npm, installed globally) — generates AST-based context maps (`.codesight/`) + a `CLAUDE.md` claude-code profile per project, cutting first-touch exploration cost (~10k tokens saved per project in the f1-race-engineer trial run).
- Auto-compact is already native to Claude Code (`autoCompactEnabled`, default on, binary — no threshold tuning available). No action needed here; confirmed via research, not to be re-implemented.
- Caveman output mode already active and working (user confirmed) — no change needed.

## Components

### 1. Codesight auto-install (SessionStart hook)

New script `codesight-session-init.js`, added as an **additional** SessionStart hook entry in `C:\Users\sanks\.claude\settings.json` (alongside the existing `caveman-activate.js`, not replacing it).

Logic:
1. From cwd, walk upward to the nearest `.git` directory (project root). If none found within a few levels, exit silently (0 output) — don't touch non-project dirs.
2. If `<root>/.codesight/CODESIGHT.md` already exists, skip install (already done).
3. If none of `package.json`, `requirements.txt`, `pyproject.toml` exist at root, skip (not a recognizable project — avoid running in random folders).
4. Otherwise run, best-effort, swallowing failures (must never block session start):
   - `npx codesight --profile claude-code` (writes `.codesight/` + `CLAUDE.md`)
   - `claude mcp add codesight -- npx codesight --mcp` (project-scoped MCP registration; skip if already registered)
5. Emit a short line noting install happened, so the user sees it once per project.

Rollout is **lazy**: the first session opened in each project triggers install for that project. No separate batch backfill script — consistent with the "auto" decision already made, and avoids touching every project's files in one sweep before the user's seen it work once.

### 2. Habits reminder (same hook, always runs)

Regardless of install state, the hook also emits a short standing checklist as additional context every session:
- Use codesight MCP tools / `.codesight/` maps over full-file reads when available.
- Cap `Grep`/`Read` output (`head_limit`, targeted offsets) — don't pull whole files when a section will do.
- Delegate large/multi-step/multi-file searches to the `Agent` tool (Explore or general-purpose) instead of doing them inline — keeps main context small.
- Avoid re-reading files already visible in context.

### 3. claude-md-improver pass after first install

The already-installed `claude-md-management` plugin's `claude-md-improver` skill audits/trims a CLAUDE.md for staleness and duplication. Hooks can't invoke skills directly, so: when the SessionStart hook reports a fresh codesight install for a project, I (Claude) invoke `claude-md-improver` on that project's new `CLAUDE.md` once, in that same session, to trim it before it settles in as the project's baseline context.

### 4. Haiku tier for mechanical Agent calls

Behavioral rule, not a hook: when dispatching `Agent` for a lookup that requires no judgment — a single-fact grep-style question, a "does X exist" check, a doc/README fetch-and-summarize — pass `model: "haiku"`. Reserve default/inherited model for anything requiring synthesis, judgment calls, or code changes. Saved as a feedback memory so it persists across sessions.

### 5. Statusline context-usage indicator

Extend the existing (currently unconfigured) `caveman-statusline.ps1` to also read the statusline JSON stdin payload and append `context_window.used_percentage`, e.g. `[CAVEMAN] ctx:42%`. Requires:
- Wiring `statusLine` in `settings.json` (currently absent — was flagged once before, never done).
- Parsing the JSON stdin the same way the script currently reads the caveman flag file (need to add JSON stdin read; script currently doesn't consume stdin at all).

This gives a passive, always-visible signal for both user and me to judge when to proactively `/compact` rather than waiting for the automatic threshold.

### 6. Proactive compact-at-boundary habit

Behavioral rule: at natural task-phase boundaries (feature done, bug fixed and verified, before starting an unrelated task), if the statusline shows meaningfully-elevated context usage, suggest `/compact` rather than waiting for the automatic near-limit trigger — compacting fresh, coherent context loses less than compacting near the ceiling.

## Persistence

Save a **feedback** memory (`feedback-token-saving-process.md`) documenting:
- The rule: auto-install codesight per-project via SessionStart hook; apply the habits checklist; haiku-tier trivial Agent calls; proactive compact suggestions.
- Why: user flagged rising token usage; no prebuilt skill existed; this is the adopted process.
- How to apply: which hook file, what it touches, what's manual (claude-md-improver pass, haiku tier judgment, compact suggestions) vs automatic (install, reminder, statusline).

Linked from `MEMORY.md`.

## Testing / rollout verification

- Open a session in a project without `.codesight/` (e.g. crypto or nse-equity) → confirm the hook installs it, registers the MCP server, and the habits reminder appears.
- Open a session in a project that already has `.codesight/` (f1-race-engineer, post this work) → confirm the hook skips install but still emits the habits reminder.
- Confirm statusline renders `ctx:NN%` alongside the existing `[CAVEMAN]` tag once wired.
- Confirm hook failures (e.g. `npx` not on PATH, no network) don't block or delay session start — errors swallowed, session proceeds normally.

## Explicitly out of scope

- Tuning the auto-compact threshold — not exposed by Claude Code, nothing to build.
- Changing caveman-mode enforcement — already working, confirmed by user.
- One-time batch backfill across all known projects — rollout is lazy/on-touch instead.
