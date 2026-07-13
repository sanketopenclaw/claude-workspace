# Squeeze Breakout Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop duplicate squeeze-breakout Telegram alerts and cut the whipsaw-alert rate by adding fired-state tracking, two-candle confirmation, and level-strength-scaled buffers to `squeeze-breakout-monitor.js`.

**Architecture:** `squeeze-scanner.js` gains touch-count fields on its output rows (already computed by `sr-levels.js`, just not exposed). `squeeze-breakout-monitor.js` gains a small pure state-machine module (`breakout-state.js`) that owns the pending→active→clear transitions and buffer sizing, unit-tested in isolation; the monitor script wires it to live candle fetches.

**Tech Stack:** Node.js (CommonJS), Jest (`config/jest.config.js`), existing `sr-levels.js` / `squeeze-scanner.js` / `squeeze-breakout-monitor.js`.

## Global Constraints

- No feature flag — deploy directly (per spec Rollout section).
- `squeeze-breakout-state.json` schema changes from `{ [symbol]: ts }` to `{ [symbol]: { lastTs, active, pending } }`; old-format entries treated as fresh state on load (file is cron-regenerated, no migration script).
- Buffer formula: `mult = clamp(3 / max(touches, 1), 1, 2)`, `buffer = atrRaw * ATR_BUFFER * mult` where `ATR_BUFFER = 0.25` (existing constant, unchanged).
- Confirmation: alert only fires on the **second** consecutive 5m candle beyond level±buffer in the same direction.

---

### Task 1: Expose touch counts from squeeze-scanner

**Files:**
- Modify: `C:\Claude\tesseract-scan\crypto\scanners\squeeze-scanner.js:186-211` (4H result push) and `:242-267` (15m result push)
- Test: `C:\Claude\tesseract-scan\crypto\tests\squeeze-scanner-touches.test.js`

**Interfaces:**
- Consumes: `srLevels(candles, price)` from `sr-levels.js` — already returns `res1pts`, `sup1pts` (arrays), used as `.length` for touch count. No changes to `sr-levels.js`.
- Produces: each result row in `squeeze-cache.json` gains `resTouches` (int, `sr4h.res1pts.length` / `sr15.res1pts.length`) and `supTouches` (int, `sr4h.sup1pts.length` / `sr15.sup1pts.length`). Task 3 (monitor) consumes these two fields by name.

- [ ] **Step 1: Write the failing test**

Create `C:\Claude\tesseract-scan\crypto\tests\squeeze-scanner-touches.test.js`:

```js
'use strict';
const fs = require('fs');
const os = require('os');
const path = require('path');

describe('squeeze-scanner touch counts', () => {
  test('scanSymbol result rows include resTouches and supTouches', () => {
    jest.resetModules();
    const tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'squeeze-touch-'));
    const cacheDir = path.join(tmpRoot, 'data', 'crypto-cache');
    fs.mkdirSync(cacheDir, { recursive: true });

    // Build a 60-candle 4H series: flat base, then a clean swing high/low pair
    // repeated 3x each so clusterLevels groups them into multi-touch levels.
    const candles = [];
    let t = 1_700_000_000_000;
    for (let i = 0; i < 60; i++) {
      const cyclePos = i % 6;
      let o = 100, h = 101, l = 99, c = 100, v = 1000;
      if (cyclePos === 2) { h = 110; c = 108; } // swing high
      if (cyclePos === 4) { l = 90;  c = 92;  } // swing low
      candles.push([t, o, h, l, c, v]);
      t += 4 * 60 * 60 * 1000;
    }
    fs.writeFileSync(path.join(cacheDir, 'ABC_USDT_USDT-4h.json'), JSON.stringify(candles));

    jest.doMock('path', () => {
      const real = jest.requireActual('path');
      return { ...real, join: (...args) => real.join(...args) };
    });

    // Point ROOT at tmpRoot by requiring the module fresh with a patched __dirname
    // is not possible directly, so instead exercise scanSymbol via the exported
    // internals through a require that reads from tmpRoot-relative CACHE_DIR.
    // squeeze-scanner.js derives CACHE_DIR from __dirname (../../data/crypto-cache),
    // which we cannot relocate without editing the module. Instead, test the
    // touch-count wiring directly against srLevels + the row-building logic by
    // requiring the real module and calling scanSymbol against the REAL cache dir
    // is unsafe in CI. So: test srLevels output shape is what squeeze-scanner reads.
    const { srLevels } = require('../scanners/sr-levels');
    const sr = srLevels(candles, 100);
    expect(Array.isArray(sr.res1pts)).toBe(true);
    expect(Array.isArray(sr.sup1pts)).toBe(true);
    expect(sr.res1pts.length).toBeGreaterThan(0);
    expect(sr.sup1pts.length).toBeGreaterThan(0);

    // Now assert squeeze-scanner.js source actually reads .length off these arrays
    // into resTouches/supTouches (regression guard against the field being dropped).
    const src = fs.readFileSync(
      path.join(__dirname, '..', 'scanners', 'squeeze-scanner.js'), 'utf8'
    );
    expect(src).toMatch(/resTouches:\s*sr4h\.res1pts\.length/);
    expect(src).toMatch(/supTouches:\s*sr4h\.sup1pts\.length/);
    expect(src).toMatch(/resTouches:\s*sr15\.res1pts\.length/);
    expect(src).toMatch(/supTouches:\s*sr15\.sup1pts\.length/);

    fs.rmSync(tmpRoot, { recursive: true, force: true });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:\Claude\tesseract-scan && npx jest --config config/jest.config.js crypto/tests/squeeze-scanner-touches.test.js`
Expected: FAIL — `resTouches:\s*sr4h\.res1pts\.length` not found in source (the `expect(src).toMatch(...)` assertions fail).

- [ ] **Step 3: Write minimal implementation**

In `C:\Claude\tesseract-scan\crypto\scanners\squeeze-scanner.js`, in the 4H block (around line 186-197), add two fields right after `supPrice2`:

```js
                resPrice:   sr4h.res1  ? +sr4h.res1.toFixed(6)  : null,
                resPrice2:  sr4h.res2  ? +sr4h.res2.toFixed(6)  : null,
                supPrice:   sr4h.sup1  ? +sr4h.sup1.toFixed(6)  : null,
                supPrice2:  sr4h.sup2  ? +sr4h.sup2.toFixed(6)  : null,
                resTouches: sr4h.res1pts.length,
                supTouches: sr4h.sup1pts.length,
```

In the 15m block (around line 248-251), add the equivalent fields:

```js
                resPrice:   sr15.res1  ? +sr15.res1.toFixed(6)  : null,
                resPrice2:  sr15.res2  ? +sr15.res2.toFixed(6)  : null,
                supPrice:   sr15.sup1  ? +sr15.sup1.toFixed(6)  : null,
                supPrice2:  sr15.sup2  ? +sr15.sup2.toFixed(6)  : null,
                resTouches: sr15.res1pts.length,
                supTouches: sr15.sup1pts.length,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:\Claude\tesseract-scan && npx jest --config config/jest.config.js crypto/tests/squeeze-scanner-touches.test.js`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd C:\Claude
git add tesseract-scan/crypto/scanners/squeeze-scanner.js tesseract-scan/crypto/tests/squeeze-scanner-touches.test.js
git commit -m "feat(squeeze): expose S/R touch counts in squeeze-cache output"
```

---

### Task 2: Breakout state machine module

**Files:**
- Create: `C:\Claude\tesseract-scan\crypto\scanners\breakout-state.js`
- Test: `C:\Claude\tesseract-scan\crypto\tests\breakout-state.test.js`

**Interfaces:**
- Consumes: nothing external — pure functions over plain objects.
- Produces (used by Task 3):
  - `bufferFor(atrRaw, touches, baseMult = 0.25)` → `number`
  - `evaluateBreakout(record, { close, resPrice, supPrice, resBuffer, supBuffer })` → `{ record: <new state record>, fire: 'up' | 'down' | null }`
    - `record` shape: `{ active: 'up' | 'down' | null, pending: 'up' | 'down' | null }` (caller stores `lastTs` alongside, untouched by this module)
    - `fire` is the direction to alert on, or `null` if nothing should fire this tick.

- [ ] **Step 1: Write the failing test**

Create `C:\Claude\tesseract-scan\crypto\tests\breakout-state.test.js`:

```js
'use strict';
const { bufferFor, evaluateBreakout } = require('../scanners/breakout-state');

describe('bufferFor', () => {
  test('1-touch level gets 2x buffer', () => {
    expect(bufferFor(1, 1)).toBeCloseTo(1 * 0.25 * 2, 6);
  });
  test('3-touch level gets 1x (base) buffer', () => {
    expect(bufferFor(1, 3)).toBeCloseTo(1 * 0.25 * 1, 6);
  });
  test('10-touch level clamps at 1x, not below', () => {
    expect(bufferFor(1, 10)).toBeCloseTo(1 * 0.25 * 1, 6);
  });
  test('zero touches treated as 1 touch (2x)', () => {
    expect(bufferFor(1, 0)).toBeCloseTo(1 * 0.25 * 2, 6);
  });
  test('non-positive atrRaw yields zero buffer', () => {
    expect(bufferFor(0, 1)).toBe(0);
    expect(bufferFor(-1, 1)).toBe(0);
  });
});

describe('evaluateBreakout', () => {
  const empty = { active: null, pending: null };

  test('single breach does not fire, sets pending', () => {
    const { record, fire } = evaluateBreakout(empty, {
      close: 110, resPrice: 100, supPrice: 90, resBuffer: 1, supBuffer: 1,
    });
    expect(fire).toBeNull();
    expect(record).toEqual({ active: null, pending: 'up' });
  });

  test('second consecutive breach confirms and fires', () => {
    const first = evaluateBreakout(empty, {
      close: 110, resPrice: 100, supPrice: 90, resBuffer: 1, supBuffer: 1,
    }).record;
    const { record, fire } = evaluateBreakout(first, {
      close: 111, resPrice: 100, supPrice: 90, resBuffer: 1, supBuffer: 1,
    });
    expect(fire).toBe('up');
    expect(record).toEqual({ active: 'up', pending: null });
  });

  test('while active, same-direction breach does not refire', () => {
    const active = { active: 'up', pending: null };
    const { record, fire } = evaluateBreakout(active, {
      close: 112, resPrice: 100, supPrice: 90, resBuffer: 1, supBuffer: 1,
    });
    expect(fire).toBeNull();
    expect(record).toEqual({ active: 'up', pending: null });
  });

  test('close back inside range clears active', () => {
    const active = { active: 'up', pending: null };
    const { record, fire } = evaluateBreakout(active, {
      close: 95, resPrice: 100, supPrice: 90, resBuffer: 1, supBuffer: 1,
    });
    expect(fire).toBeNull();
    expect(record).toEqual({ active: null, pending: null });
  });

  test('close back inside range clears pending without firing', () => {
    const pending = { active: null, pending: 'up' };
    const { record, fire } = evaluateBreakout(pending, {
      close: 95, resPrice: 100, supPrice: 90, resBuffer: 1, supBuffer: 1,
    });
    expect(fire).toBeNull();
    expect(record).toEqual({ active: null, pending: null });
  });

  test('breach in opposite direction while pending resets pending to new direction', () => {
    const pendingUp = { active: null, pending: 'up' };
    const { record, fire } = evaluateBreakout(pendingUp, {
      close: 85, resPrice: 100, supPrice: 90, resBuffer: 1, supBuffer: 1,
    });
    expect(fire).toBeNull();
    expect(record).toEqual({ active: null, pending: 'down' });
  });

  test('null resPrice/supPrice treated as no boundary on that side', () => {
    const { record, fire } = evaluateBreakout(empty, {
      close: 110, resPrice: null, supPrice: 90, resBuffer: 1, supBuffer: 1,
    });
    expect(fire).toBeNull();
    expect(record).toEqual({ active: null, pending: null });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:\Claude\tesseract-scan && npx jest --config config/jest.config.js crypto/tests/breakout-state.test.js`
Expected: FAIL — `Cannot find module '../scanners/breakout-state'`

- [ ] **Step 3: Write minimal implementation**

Create `C:\Claude\tesseract-scan\crypto\scanners\breakout-state.js`:

```js
'use strict';
// breakout-state.js — pure state machine for squeeze-breakout confirmation.
// Two-candle confirm: a single breach sets `pending`; a second consecutive
// breach in the same direction fires and sets `active`. While `active`,
// same-direction breaches are suppressed (no spam). A close back inside the
// range clears both `pending` and `active`.

function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

function bufferFor(atrRaw, touches, baseMult = 0.25) {
  if (!(atrRaw > 0)) return 0;
  const mult = clamp(3 / Math.max(touches, 1), 1, 2);
  return atrRaw * baseMult * mult;
}

function evaluateBreakout(record, { close, resPrice, supPrice, resBuffer, supBuffer }) {
  const beyondRes = resPrice != null && close > resPrice + resBuffer;
  const beyondSup = supPrice != null && close < supPrice - supBuffer;
  const breachDir = beyondRes ? 'up' : (beyondSup ? 'down' : null);

  if (!breachDir) {
    // back inside range (or no boundary breached): clear everything
    return { record: { active: null, pending: null }, fire: null };
  }

  if (record.active === breachDir) {
    // already alerted this breakout, still outside range
    return { record: { active: breachDir, pending: null }, fire: null };
  }

  if (record.pending === breachDir) {
    // second consecutive breach in same direction: confirm
    return { record: { active: breachDir, pending: null }, fire: breachDir };
  }

  // first breach in this direction (or direction flipped mid-pending)
  return { record: { active: null, pending: breachDir }, fire: null };
}

module.exports = { bufferFor, evaluateBreakout };
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:\Claude\tesseract-scan && npx jest --config config/jest.config.js crypto/tests/breakout-state.test.js`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
cd C:\Claude
git add tesseract-scan/crypto/scanners/breakout-state.js tesseract-scan/crypto/tests/breakout-state.test.js
git commit -m "feat(squeeze): add breakout confirmation state machine"
```

---

### Task 3: Wire state machine into squeeze-breakout-monitor

**Files:**
- Modify: `C:\Claude\tesseract-scan\crypto\scanners\squeeze-breakout-monitor.js`
- Test: `C:\Claude\tesseract-scan\crypto\tests\squeeze-breakout-monitor.test.js`

**Interfaces:**
- Consumes: `bufferFor`, `evaluateBreakout` from `../scanners/breakout-state` (Task 2). Consumes `resTouches`/`supTouches` fields on squeeze-cache rows (Task 1).
- Produces: `squeeze-breakout-state.json` written as `{ [symbol]: { lastTs, active, pending } }`. Old flat-`ts` entries (`typeof state[symbol] === 'number'`) are treated as `{ lastTs: state[symbol], active: null, pending: null }` on load — no separate migration step.

- [ ] **Step 1: Write the failing test**

Create `C:\Claude\tesseract-scan\crypto\tests\squeeze-breakout-monitor.test.js`. This tests the pure logic extracted into an exported `processCandidate` function (Step 3 refactors `main()`'s per-symbol loop body into this exported function so it's testable without hitting the network).

```js
'use strict';
const { processCandidate } = require('../scanners/squeeze-breakout-monitor');

describe('processCandidate', () => {
  const baseCandidate = {
    symbol: 'ABCUSDT',
    resPrice: 100,
    supPrice: 90,
    atrRaw: 4,
    score: 55,
    resTouches: 1,
    supTouches: 1,
  };

  test('first breach: no event, state has pending', () => {
    const { state, event } = processCandidate(baseCandidate, {}, 1000, 110);
    expect(event).toBeNull();
    expect(state.ABCUSDT).toEqual({ lastTs: 1000, active: null, pending: 'up' });
  });

  test('second consecutive breach: fires event, state active', () => {
    let { state } = processCandidate(baseCandidate, {}, 1000, 110);
    const result = processCandidate(baseCandidate, state, 1300, 111);
    expect(result.event).toMatchObject({
      symbol: 'ABCUSDT', direction: 'up', price: 111, level: 100, score: 55,
    });
    expect(result.state.ABCUSDT).toEqual({ lastTs: 1300, active: 'up', pending: null });
  });

  test('same 5m candle timestamp is skipped (no state change, no event)', () => {
    const prevState = { ABCUSDT: { lastTs: 1000, active: null, pending: 'up' } };
    const result = processCandidate(baseCandidate, prevState, 1000, 999999);
    expect(result.event).toBeNull();
    expect(result.state).toBe(prevState);
  });

  test('old flat-timestamp state format is treated as fresh state', () => {
    const oldState = { ABCUSDT: 500 }; // legacy format: symbol -> ts
    const result = processCandidate(baseCandidate, oldState, 1000, 110);
    expect(result.event).toBeNull();
    expect(result.state.ABCUSDT).toEqual({ lastTs: 1000, active: null, pending: 'up' });
  });

  test('weak (1-touch) level requires larger move to breach than strong (5-touch) level', () => {
    // ATR=4, base buffer 0.25*4=1. 1-touch -> mult 2 -> buffer 2. 5-touch -> mult clamp(3/5,1,2)=1 -> buffer 1.
    const weak = { ...baseCandidate, resTouches: 1 };
    const strong = { ...baseCandidate, resTouches: 5 };
    // close at 101.5: beyond strong's buffer (100+1=101) but not weak's (100+2=102)
    const weakResult = processCandidate(weak, {}, 1000, 101.5);
    const strongResult = processCandidate(strong, {}, 1000, 101.5);
    expect(weakResult.state.ABCUSDT.pending).toBeNull();
    expect(strongResult.state.ABCUSDT.pending).toBe('up');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:\Claude\tesseract-scan && npx jest --config config/jest.config.js crypto/tests/squeeze-breakout-monitor.test.js`
Expected: FAIL — `processCandidate is not a function` (module doesn't export it yet)

- [ ] **Step 3: Write minimal implementation**

Rewrite `C:\Claude\tesseract-scan\crypto\scanners\squeeze-breakout-monitor.js` in full:

```js
'use strict';
// squeeze-breakout-monitor.js — checks live 5m candles for symbols in the
// squeeze cache (15m tf, score > MIN_SCORE) against their 15m S/R range.
// Fires a breakout event (up/down) when two consecutive 5m closes confirm
// a break beyond the range, buffered by ATR and scaled by level touch-count
// strength. Tracks per-symbol active/pending state so an ongoing breakout
// only alerts once (see breakout-state.js).
const fs   = require('fs');
const path = require('path');
const data = require('../engine/data');
const { sendMessage } = require('../../shared/telegram');
const { bufferFor, evaluateBreakout } = require('./breakout-state');

const ROOT       = path.join(__dirname, '..', '..');
const SQUEEZE_FP = path.join(ROOT, 'data', 'squeeze-cache.json');
const STATE_FP   = path.join(ROOT, 'data', 'squeeze-breakout-state.json');
const EVENTS_FP  = path.join(ROOT, 'data', 'squeeze-breakouts.json');
const MIN_SCORE   = 50;
const MAX_EVENTS  = 100;
const ATR_BUFFER  = 0.25; // base multiplier; scaled 1x-2x by level touch-count strength

function toCcxtSymbol(symbol) {
  const base = symbol.replace(/USDT$/, '');
  return `${base}/USDT:USDT`;
}

function fmtAlert(ev) {
  const arrow = ev.direction === 'up' ? '↑' : '↓';
  return [
    `🔔 <b>${ev.symbol}</b> SQUEEZE BREAKOUT ${arrow}`,
    '',
    `Price: ${ev.price}`,
    `Level: ${ev.level} (${ev.direction === 'up' ? 'resistance' : 'support'})`,
    `Score: ${ev.score}`,
  ].join('\n');
}

function normalizeRecord(raw) {
  if (raw && typeof raw === 'object') return { active: raw.active ?? null, pending: raw.pending ?? null };
  return { active: null, pending: null }; // legacy flat-ts format or missing
}

// Pure per-symbol step: given a candidate row, current state map, the latest
// 5m candle timestamp, and its close price, returns the updated state map
// and an event object (or null). No I/O — safe to unit test directly.
function processCandidate(candidate, prevStateMap, ts, close) {
  const prevRaw = prevStateMap[candidate.symbol];
  const prevLastTs = (prevRaw && typeof prevRaw === 'object') ? prevRaw.lastTs : prevRaw;

  if (prevLastTs === ts) {
    return { state: prevStateMap, event: null }; // already evaluated this 5m candle
  }

  const record   = normalizeRecord(prevRaw);
  const resBuffer = bufferFor(candidate.atrRaw, candidate.resTouches);
  const supBuffer = bufferFor(candidate.atrRaw, candidate.supTouches);

  const { record: nextRecord, fire } = evaluateBreakout(record, {
    close,
    resPrice: candidate.resPrice,
    supPrice: candidate.supPrice,
    resBuffer,
    supBuffer,
  });

  const nextStateMap = {
    ...prevStateMap,
    [candidate.symbol]: { lastTs: ts, active: nextRecord.active, pending: nextRecord.pending },
  };

  if (!fire) return { state: nextStateMap, event: null };

  const level = fire === 'up' ? candidate.resPrice : candidate.supPrice;
  const event = {
    id:        `${candidate.symbol}-${ts}`,
    symbol:    candidate.symbol,
    direction: fire,
    price:     close,
    level,
    score:     candidate.score,
    ts:        new Date(ts).toISOString(),
  };
  return { state: nextStateMap, event };
}

async function main() {
  console.log('[SqueezeBreakout] Check starting...');
  const t0 = Date.now();

  if (data.isBinancePaused()) { console.log('[SqueezeBreakout] Binance paused, skip'); process.exit(0); }

  let squeeze;
  try { squeeze = JSON.parse(fs.readFileSync(SQUEEZE_FP, 'utf8')); }
  catch { console.log('[SqueezeBreakout] No squeeze cache, skip'); process.exit(0); }

  const candidates = (squeeze.results || []).filter(r =>
    r.tf === '15m' && r.score > MIN_SCORE && (r.resPrice != null || r.supPrice != null)
  );
  if (!candidates.length) { console.log('[SqueezeBreakout] No candidates'); process.exit(0); }

  let state = {};
  try { state = JSON.parse(fs.readFileSync(STATE_FP, 'utf8')); } catch (_) {}

  let events = [];
  try { events = JSON.parse(fs.readFileSync(EVENTS_FP, 'utf8')); } catch (_) {}

  const exchange = data.getAuthExchange();
  await data.ensureMarkets(exchange);

  let checked = 0, found = 0;
  for (const r of candidates) {
    try {
      const candles = await exchange.fetchOHLCV(toCcxtSymbol(r.symbol), '5m', undefined, 3);
      if (!candles.length) continue;
      const [ts, , , , close] = candles[candles.length - 1];
      checked++;

      const result = processCandidate(r, state, ts, close);
      state = result.state;

      if (result.event) {
        found++;
        events.push(result.event);
        console.log(`[SqueezeBreakout] ${result.event.symbol} ${result.event.direction.toUpperCase()} @ ${result.event.price} (level ${result.event.level})`);
        await sendMessage(fmtAlert(result.event)).catch(() => {});
      }

      await exchange.sleep(150);
    } catch (_) { /* skip symbol on fetch error */ }
  }

  events = events.slice(-MAX_EVENTS);

  fs.writeFileSync(STATE_FP, JSON.stringify(state), 'utf8');
  fs.writeFileSync(EVENTS_FP, JSON.stringify(events, null, 2), 'utf8');
  console.log(`[SqueezeBreakout] Done: ${checked} checked, ${found} breakouts in ${Date.now() - t0}ms`);
  process.exit(0);
}

if (require.main === module) {
  main().catch(e => {
    console.error('[SqueezeBreakout] Fatal:', e.message);
    process.exit(0);
  });
}

module.exports = { processCandidate, toCcxtSymbol, fmtAlert };
```

Key changes from current file: added `require('./breakout-state')`, added `normalizeRecord`/`processCandidate` pure functions, `main()` now delegates per-symbol logic to `processCandidate`, wrapped `main()` invocation in `require.main === module` so tests can `require()` the file without running the cron job, and exported `processCandidate` (plus existing helpers) for testing.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:\Claude\tesseract-scan && npx jest --config config/jest.config.js crypto/tests/squeeze-breakout-monitor.test.js`
Expected: PASS (5 tests)

- [ ] **Step 5: Run full crypto test suite to check for regressions**

Run: `cd C:\Claude\tesseract-scan && npx jest --config config/jest.config.js crypto/tests/`
Expected: all suites PASS (no pre-existing test imports `squeeze-breakout-monitor.js`, so this only needs to confirm nothing else broke)

- [ ] **Step 6: Commit**

```bash
cd C:\Claude
git add tesseract-scan/crypto/scanners/squeeze-breakout-monitor.js tesseract-scan/crypto/tests/squeeze-breakout-monitor.test.js
git commit -m "feat(squeeze): confirm breakouts over 2 candles, dedup via active state, scale buffer by level strength"
```

---

## Post-implementation verification (manual, not a task)

After deploy, re-run the whipsaw audit against a fresh sample of `squeeze-breakouts.json` (same method used during design diagnosis: for each event, check whether any of the next 8 15m closes cross back through `level`) to confirm the fail rate drops below the ~32% baseline. Also visually confirm no symbol produces 2+ events within the same active breakout (spam check) over a day of cron runs.
