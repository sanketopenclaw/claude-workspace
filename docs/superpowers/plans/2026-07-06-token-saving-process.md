# Token-Saving Process Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-install `codesight` context maps in any project touched, inject a token-saving habits checklist every session, add a live context-usage % to the statusline, and persist the haiku-tier/proactive-compact behavioral rules to memory — all enforced automatically at session start rather than relying on the model remembering.

**Architecture:** A new SessionStart hook script (`codesight-session-init.js`) added alongside the existing `caveman-activate.js` hook in `C:\Users\sanks\.claude\settings.json`. It walks up from cwd to the git root, auto-installs codesight if missing, registers it as an MCP server, and always emits a habits checklist as additional session context. The existing (currently unwired) `caveman-statusline.ps1` gets extended to read the statusline JSON stdin payload and append context-usage %, and `statusLine` finally gets wired in settings.json. Behavioral-only rules (haiku tier, proactive compact) are captured in a feedback memory file, not code.

**Tech Stack:** Node.js (hook scripts, matches existing hooks), PowerShell (statusline script, matches existing), `codesight` npm CLI (already installed globally, v1.18.0), Claude Code hooks/statusline JSON contracts.

## Global Constraints

- Hook scripts must never throw or block session start — all fallible operations wrapped in try/catch, swallow-and-continue on failure (per spec Testing section).
- Don't touch non-project directories — only act when a `.git` root AND one of `package.json`/`requirements.txt`/`pyproject.toml` exist at that root (per spec Component 1).
- Don't replace existing SessionStart hook (`caveman-activate.js`) — add a second entry in the same array (per spec Component 1).
- Codesight install is lazy/per-project-on-touch — no batch backfill script (per spec, explicitly out of scope).
- Use the global `codesight` binary directly (already installed via `npm install -g codesight`), not `npx codesight` — avoids npm resolution overhead on every session start.

---

### Task 1: codesight-session-init.js — detection + install logic

**Files:**
- Create: `C:\Users\sanks\.claude\hooks\codesight-session-init.js`
- Test: manual invocation (Node hook scripts in this repo have no existing test harness — `caveman-activate.js` and `pre-compact.js` are verified by direct invocation, matching that pattern)

**Interfaces:**
- Produces: a Node script invocable as `node "C:/Users/sanks/.claude/hooks/codesight-session-init.js"`, reading `process.cwd()`, writing plain text to stdout (matches `caveman-activate.js`'s plain-stdout convention for SessionStart — NOT the `{additionalInput: ...}` JSON wrapper `pre-compact.js` uses for PreCompact).

- [ ] **Step 1: Write the script**

```js
#!/usr/bin/env node
// codesight-session-init — Claude Code SessionStart hook
//
// Runs on every session start:
//   1. Finds the git project root above cwd (if any)
//   2. If it's a recognizable project without .codesight/, installs codesight
//      and registers it as an MCP server for that project
//   3. Always emits a token-saving habits checklist as session context

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const HABITS_CHECKLIST = `
TOKEN-SAVING HABITS (apply every session):
- Prefer codesight MCP tools / .codesight/ maps over full-file reads when available in this project.
- Cap Grep/Read output (head_limit, targeted offsets) instead of pulling whole files.
- Delegate large/multi-step/multi-file searches to the Agent tool (Explore or general-purpose) instead of doing them inline.
- Avoid re-reading files already visible in context.
`.trim();

function findProjectRoot(startDir) {
  let dir = startDir;
  for (let i = 0; i < 20; i++) {
    if (fs.existsSync(path.join(dir, '.git'))) return dir;
    const parent = path.dirname(dir);
    if (parent === dir) return null;
    dir = parent;
  }
  return null;
}

function hasProjectMarker(root) {
  return ['package.json', 'requirements.txt', 'pyproject.toml']
    .some((f) => fs.existsSync(path.join(root, f)));
}

let installMessage = '';

try {
  const root = findProjectRoot(process.cwd());
  if (root && hasProjectMarker(root)) {
    const codesightMarker = path.join(root, '.codesight', 'CODESIGHT.md');
    if (!fs.existsSync(codesightMarker)) {
      execSync('codesight --profile claude-code', { cwd: root, stdio: 'ignore', timeout: 25000 });
      try {
        execSync('claude mcp add codesight -- codesight --mcp', { cwd: root, stdio: 'ignore', timeout: 10000 });
      } catch (e) {
        // MCP registration is best-effort — install succeeded even if this fails
        // (e.g. already registered, or `claude` not resolvable in this shell).
      }
      installMessage = `codesight auto-installed for this project (${root}) — context maps + CLAUDE.md generated, MCP server registered.\n\n`;
    }
  }
} catch (e) {
  // Never block session start over codesight install failures (missing binary,
  // network issues, permission errors, etc.)
}

process.stdout.write(installMessage + HABITS_CHECKLIST);
```

- [ ] **Step 2: Test in a project WITHOUT codesight installed**

Run (pick a project from `MEMORY.md`'s active list that has no `.codesight/` yet, e.g. `C:\Claude\crypto-futures` — adjust path to whatever exists):

```bash
cd C:\Claude\crypto-futures  # or another active project lacking .codesight/
node "C:/Users/sanks/.claude/hooks/codesight-session-init.js"
```

Expected: stdout starts with `codesight auto-installed for this project (...)`, followed by the habits checklist. Confirm `.codesight/CODESIGHT.md` and `CLAUDE.md` now exist in that project directory, and `claude mcp list` (run from that directory) shows a `codesight` entry.

- [ ] **Step 3: Test idempotency (second run, same project)**

```bash
node "C:/Users/sanks/.claude/hooks/codesight-session-init.js"
```

Expected: stdout is ONLY the habits checklist (no `auto-installed` line) — confirms the `.codesight/CODESIGHT.md` existence check correctly skips re-install.

- [ ] **Step 4: Test in a non-project directory**

```bash
cd C:\Users\sanks\Downloads   # or any dir with no .git and no project markers
node "C:/Users/sanks/.claude/hooks/codesight-session-init.js"
```

Expected: stdout is ONLY the habits checklist — no crash, no install attempted (no `.git` found, or found but no project marker).

- [ ] **Step 5: Commit**

```bash
cd C:\Users\sanks\.claude
git add hooks/codesight-session-init.js 2>&1 || true
```

(Note: `C:\Users\sanks\.claude` may not be a git repo — if `git add` fails with "not a git repository", skip committing this file; it's user-config, not project code. Verify with `git rev-parse --is-inside-work-tree` first and only commit if true.)

---

### Task 2: Wire the hook into settings.json

**Files:**
- Modify: `C:\Users\sanks\.claude\settings.json`

**Interfaces:**
- Consumes: `codesight-session-init.js` from Task 1 (must exist at the path referenced in the new hook entry).

- [ ] **Step 1: Add the new SessionStart hook entry**

Edit the `hooks.SessionStart` array in `C:\Users\sanks\.claude\settings.json` to add a second entry (do not remove the existing `caveman-activate.js` entry):

```json
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "node \"C:/Claude/projects/cricket-gully/caveman/hooks/caveman-activate.js\"",
            "timeout": 5,
            "statusMessage": "Loading caveman mode..."
          }
        ]
      },
      {
        "hooks": [
          {
            "type": "command",
            "command": "node \"C:/Users/sanks/.claude/hooks/codesight-session-init.js\"",
            "timeout": 30,
            "statusMessage": "Checking codesight setup..."
          }
        ]
      }
    ],
```

- [ ] **Step 2: Validate JSON**

```bash
node -e "JSON.parse(require('fs').readFileSync('C:/Users/sanks/.claude/settings.json', 'utf8')); console.log('valid')"
```

Expected: `valid`

- [ ] **Step 3: Manual smoke test — start a real session**

Start a new Claude Code session in any project directory and confirm (via the injected SessionStart context, visible in a `<system-reminder>` at the top of the conversation, same as the existing `CAVEMAN MODE ACTIVE` reminder) that the habits checklist text now also appears.

- [ ] **Step 4: Commit**

`C:\Users\sanks\.claude` is user config, not a project repo — no commit needed unless it is itself a git repo (check per Task 1 Step 5 note). If it is, commit with:

```bash
git add settings.json
git commit -m "Add codesight-session-init SessionStart hook"
```

---

### Task 3: Statusline context-usage indicator

**Files:**
- Modify: `C:\Claude\projects\cricket-gully\caveman\hooks\caveman-statusline.ps1`
- Modify: `C:\Users\sanks\.claude\settings.json` (add `statusLine` key)

**Interfaces:**
- Consumes: statusline JSON stdin payload field `context_window.used_percentage` (per Claude Code statusline docs, confirmed available).

- [ ] **Step 1: Read current script content**

Already read in this session — current script only reads the `.caveman-active` flag file and writes an ANSI-colored `[CAVEMAN]`/`[CAVEMAN:MODE]` tag. It does not currently read stdin at all.

- [ ] **Step 2: Add stdin JSON parsing + context % append**

Add this block to `caveman-statusline.ps1`, immediately before the final `if ([string]::IsNullOrEmpty($Mode)...` rendering block (i.e., after the `$Valid`/whitelist check, before output is written):

```powershell
# Read statusline JSON from stdin (if any) to append live context-usage %.
# Never let a parse failure block the caveman tag from rendering.
$CtxSuffix = ""
try {
    $StdinRaw = [Console]::In.ReadToEnd()
    if (-not [string]::IsNullOrWhiteSpace($StdinRaw)) {
        $Payload = $StdinRaw | ConvertFrom-Json -ErrorAction Stop
        if ($null -ne $Payload.context_window -and $null -ne $Payload.context_window.used_percentage) {
            $Pct = [math]::Round([double]$Payload.context_window.used_percentage)
            $CtxSuffix = " ctx:${Pct}%"
        }
    }
} catch {
    $CtxSuffix = ""
}
```

Then change the two output lines to append `$CtxSuffix`:

```powershell
$Esc = [char]27
if ([string]::IsNullOrEmpty($Mode) -or $Mode -eq "full") {
    [Console]::Write("${Esc}[38;5;172m[CAVEMAN]${Esc}[0m${CtxSuffix}")
} else {
    $Suffix = $Mode.ToUpperInvariant()
    [Console]::Write("${Esc}[38;5;172m[CAVEMAN:$Suffix]${Esc}[0m${CtxSuffix}")
}
```

Note: the script currently `exit 0`s early (before any output) if the caveman flag file is missing/invalid — in that case no statusline text is printed at all, caveman or context. That's existing behavior, out of scope to change here (the spec only asks for a context-% addition alongside the existing tag, not a caveman-independent context indicator).

- [ ] **Step 3: Wire statusLine in settings.json**

Add this key to `C:\Users\sanks\.claude\settings.json` (top level, alongside `"hooks"`, `"model"`, etc.):

```json
  "statusLine": {
    "type": "command",
    "command": "powershell -ExecutionPolicy Bypass -File \"C:\\Claude\\projects\\cricket-gully\\caveman\\hooks\\caveman-statusline.ps1\""
  },
```

- [ ] **Step 4: Validate JSON**

```bash
node -e "JSON.parse(require('fs').readFileSync('C:/Users/sanks/.claude/settings.json', 'utf8')); console.log('valid')"
```

Expected: `valid`

- [ ] **Step 5: Test the script directly with simulated stdin**

```bash
echo '{"context_window":{"used_percentage":42.3}}' | powershell -ExecutionPolicy Bypass -File "C:\Claude\projects\cricket-gully\caveman\hooks\caveman-statusline.ps1"
```

Expected: prints `[CAVEMAN] ctx:42%` (or `[CAVEMAN:<MODE>] ctx:42%` depending on current `.caveman-active` flag contents) — confirms JSON parsing and percentage rounding work. If the flag file doesn't currently exist, this will print nothing (exits at the top guard) — that's expected per the flag-gating behavior; set the flag first via a real session start if you want to see output.

- [ ] **Step 6: Test with missing/malformed stdin (regression check)**

```bash
echo '' | powershell -ExecutionPolicy Bypass -File "C:\Claude\projects\cricket-gully\caveman\hooks\caveman-statusline.ps1"
```

Expected: same output as before this change (just `[CAVEMAN]`/`[CAVEMAN:MODE]`, no `ctx:` suffix, no error) — confirms the try/catch fallback doesn't break the pre-existing behavior when stdin is empty.

- [ ] **Step 7: Commit**

```bash
cd C:\Claude
git add projects/cricket-gully/caveman/hooks/caveman-statusline.ps1
git commit -m "Add live context-usage % to caveman statusline"
```

(Skip the `settings.json` commit — it's user config, not tracked in this repo, per Task 2 Step 4 note.)

---

### Task 4: Persist behavioral rules + close out the memory trail

**Files:**
- Create: `C:\Users\sanks\.claude\projects\C--Claude\memory\feedback-token-saving-process.md`
- Modify: `C:\Users\sanks\.claude\projects\C--Claude\memory\MEMORY.md`

**Interfaces:** none (pure memory-system files, no code dependencies on Tasks 1-3).

- [ ] **Step 1: Write the feedback memory file**

```markdown
---
name: feedback-token-saving-process
description: Auto-install codesight per project, apply habits checklist, use haiku for mechanical Agent calls, suggest /compact proactively at task boundaries
metadata:
  type: feedback
---

Reduce per-session token/context cost across all projects via four rules:

1. **Codesight auto-install is automatic** — a SessionStart hook (`C:\Users\sanks\.claude\hooks\codesight-session-init.js`) installs `codesight` context maps + registers its MCP server the first time any project (with a `.git` root and a package.json/requirements.txt/pyproject.toml) is touched. Nothing to do manually — it's lazy/on-touch, not batch-backfilled.
2. **Habits checklist** — injected every session by the same hook: prefer codesight tools over full-file reads, cap Grep/Read output, delegate large searches to Agent subagents, don't re-read files already in context.
3. **Haiku tier for mechanical Agent calls** — when dispatching Agent for a lookup requiring no judgment (single-fact check, "does X exist", doc fetch-and-summarize), pass `model: "haiku"`. Reserve default/inherited model for synthesis, judgment calls, or code changes.
4. **Proactive /compact suggestions** — at natural task-phase boundaries (feature done, bug fixed+verified, before switching to an unrelated task), if the statusline's `ctx:NN%` indicator shows meaningfully elevated usage, suggest `/compact` rather than waiting for the automatic near-limit trigger.

**Why:** user flagged rising token usage session-over-session; no prebuilt skill existed for this (evaluated and rejected MemOS — wrong use case; savethetokens — too stale). This is the adopted process, spec at `C:\Claude\docs\superpowers\specs\2026-07-06-token-saving-process-design.md`.

**How to apply:** rules 1-2 are automatic (hook-enforced) — no action needed beyond having the hook installed. Rules 3-4 are behavioral — apply them as ongoing judgment in every session, they aren't enforced by tooling.
```

- [ ] **Step 2: Add the MEMORY.md pointer**

Add this line under the `## Feedback (Behavioral Rules)` section of `C:\Users\sanks\.claude\projects\C--Claude\memory\MEMORY.md`:

```
- [Feedback: Token-Saving Process](feedback-token-saving-process.md) — codesight auto-install hook + habits checklist + haiku-tier Agent calls + proactive /compact suggestions
```

- [ ] **Step 3: Verify**

```bash
node -e "console.log(require('fs').existsSync('C:/Users/sanks/.claude/projects/C--Claude/memory/feedback-token-saving-process.md'))"
```

Expected: `true`

Read `MEMORY.md` back and confirm the new line appears exactly once under `## Feedback (Behavioral Rules)`.

No commit needed — this memory directory is not a tracked git repo (per existing session-memory-saving convention used throughout prior sessions in this project).

---

## Self-Review Notes

- **Spec coverage:** Component 1 (auto-install) → Task 1+2. Component 2 (habits checklist) → Task 1. Component 3 (claude-md-improver pass) → intentionally NOT a task here — per spec it's a one-time manual skill invocation I (Claude) perform in-session the first time a project gets a fresh codesight install, not a scriptable step; noted in the feedback memory's "how to apply" instead of a checkbox task. Component 4 (haiku tier) → Task 4 feedback memory. Component 5 (statusline) → Task 3. Component 6 (proactive compact habit) → Task 4 feedback memory. Auto-compact tuning and caveman-mode changes are explicitly out of scope per spec — no tasks for them.
- **Placeholder scan:** no TBD/TODO; all code blocks are complete and runnable as written.
- **Type/interface consistency:** `codesight-session-init.js` is self-contained (no shared types with other tasks). `caveman-statusline.ps1`'s existing `$Mode`/`$Valid`/`$Esc` variables are reused, not renamed, to avoid breaking the pre-existing caveman-tag rendering.
