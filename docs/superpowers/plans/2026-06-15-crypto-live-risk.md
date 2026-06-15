# Crypto Live Risk Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge Binance live positions with the paper ledger so each open position shows unrealized R, stop distance, a rules-based action, and a portfolio risk summary — plus a `version.js` snapshot/restore tool whose "current" always points at the last verified-working build.

**Architecture:** A pure module `crypto/engine/live-risk.js` reconciles Binance positions against open paper trades (matched by base symbol), computing R, risk-at-stop, a deterministic action, and a portfolio summary. A new `GET /api/crypto/live-risk` endpoint wires data sources to the pure function. The `LiveTradesCrypto` component in `crypto.jsx` switches to this single endpoint and renders R badges, a stop→target bar, action badges, and a portfolio strip. A `dashboard/version.js` CLI snapshots tracked files into `_versions/` with a `lastKnownWorking` pointer.

**Tech Stack:** Node.js, Jest (`config/jest.config.js`), React (via `dashboard/build.js` JSX bundler), ccxt (Binance USDM).

**Working directory for all commands:** `C:\Claude\tesseract-scan` unless stated otherwise.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `crypto/engine/live-risk.js` | NEW — pure `computeLiveRisk(binancePositions, paperPositions, equity)` + helpers + rules engine |
| `crypto/tests/live-risk.test.js` | NEW — unit tests for matching, R, risk, rules, portfolio |
| `dashboard/api.js` | MODIFY — add `GET /crypto/live-risk` route |
| `dashboard/public/crypto.jsx` | MODIFY — `LiveTradesCrypto`: single data source + R badge + stop→target bar + action badge + portfolio strip |
| `dashboard/public/bundle.js` | REBUILD — `node dashboard/build.js` |
| `dashboard/version.js` | NEW — snapshot / promote / restore-working / list |
| `_versions/MANIFEST.json` | NEW — created by `version.js snapshot` |

---

## Task 1: Version tooling + baseline snapshot

Build the version tool first so the current working state is captured before any code changes.

**Files:**
- Create: `dashboard/version.js`

- [ ] **Step 1: Write `dashboard/version.js`**

```javascript
// Version history for the crypto dashboard.
// Snapshots tracked files into _versions/<ts>-<label>/, tracks a lastKnownWorking pointer.
// Usage:
//   node dashboard/version.js snapshot "label"   — archive current files (does NOT promote)
//   node dashboard/version.js promote            — mark newest snapshot as last known working
//   node dashboard/version.js restore-working    — restore lastKnownWorking files + rebuild
//   node dashboard/version.js list               — list snapshots, mark lastKnownWorking
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const DASH = __dirname;
const VERS = path.join(DASH, '_versions');
const MANIFEST = path.join(VERS, 'MANIFEST.json');

// Tracked files, relative to dashboard/
const TRACKED = [
  'public/crypto.jsx',
  'public/bundle.js',
  'api.js',
  '../crypto/engine/live-risk.js',
];

function readManifest() {
  try { return JSON.parse(fs.readFileSync(MANIFEST, 'utf8')); }
  catch { return { lastKnownWorking: null, snapshots: [] }; }
}
function writeManifest(m) {
  fs.mkdirSync(VERS, { recursive: true });
  fs.writeFileSync(MANIFEST, JSON.stringify(m, null, 2));
}
function ts() {
  const d = new Date();
  const p = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
}

function snapshot(label) {
  if (!label) { console.error('snapshot needs a label'); process.exit(1); }
  const id = `${ts()}-${label.replace(/[^a-z0-9]+/gi, '-')}`;
  const dir = path.join(VERS, id);
  fs.mkdirSync(dir, { recursive: true });
  const saved = [];
  for (const rel of TRACKED) {
    const src = path.join(DASH, rel);
    if (!fs.existsSync(src)) continue;
    const dest = path.join(dir, path.basename(rel));
    fs.copyFileSync(src, dest);
    saved.push(path.basename(rel));
  }
  const m = readManifest();
  m.snapshots.push({ id, label, ts: new Date().toISOString(), files: saved });
  writeManifest(m);
  console.log(`snapshot ${id} (${saved.join(', ')})`);
}

function promote() {
  const m = readManifest();
  if (!m.snapshots.length) { console.error('no snapshots to promote'); process.exit(1); }
  m.lastKnownWorking = m.snapshots[m.snapshots.length - 1].id;
  writeManifest(m);
  console.log(`lastKnownWorking = ${m.lastKnownWorking}`);
}

function restoreWorking() {
  const m = readManifest();
  if (!m.lastKnownWorking) { console.error('no lastKnownWorking set'); process.exit(1); }
  const dir = path.join(VERS, m.lastKnownWorking);
  for (const rel of TRACKED) {
    const snap = path.join(dir, path.basename(rel));
    if (!fs.existsSync(snap)) continue;
    fs.copyFileSync(snap, path.join(DASH, rel));
  }
  console.log(`restored ${m.lastKnownWorking}; rebuilding bundle…`);
  execSync('node build.js', { cwd: DASH, stdio: 'inherit' });
}

function list() {
  const m = readManifest();
  for (const s of m.snapshots) {
    const mark = s.id === m.lastKnownWorking ? ' *WORKING' : '';
    console.log(`${s.id}${mark}  [${s.files.join(', ')}]`);
  }
}

const [cmd, arg] = process.argv.slice(2);
if (cmd === 'snapshot') snapshot(arg);
else if (cmd === 'promote') promote();
else if (cmd === 'restore-working') restoreWorking();
else if (cmd === 'list') list();
else { console.error('commands: snapshot <label> | promote | restore-working | list'); process.exit(1); }
```

- [ ] **Step 2: Snapshot + promote the current working baseline**

Run (from `C:\Claude\tesseract-scan`):
```bash
node dashboard/version.js snapshot "baseline-pre-live-risk"
node dashboard/version.js promote
node dashboard/version.js list
```
Expected: `snapshot <id>` line, then `lastKnownWorking = <id>`, then `list` shows that id with `*WORKING`. (`live-risk.js` does not exist yet — it is silently skipped; that is fine.)

- [ ] **Step 3: Commit**

```bash
git add dashboard/version.js _versions/MANIFEST.json
git commit -m "feat(crypto): add version.js snapshot tool + baseline"
```

---

## Task 2: live-risk.js — matching, R, and risk-at-stop

**Files:**
- Create: `crypto/engine/live-risk.js`
- Test: `crypto/tests/live-risk.test.js`

- [ ] **Step 1: Write the failing test**

Create `crypto/tests/live-risk.test.js`:
```javascript
const { computeLiveRisk } = require('../engine/live-risk');

// Binance ccxt position shape (subset used by binance-live.js)
const longHype = {
  symbol: 'HYPE/USDT:USDT', side: 'long', contracts: 4.44,
  entryPrice: 57.37, markPrice: 65.77, unrealizedPnl: 37.3,
  liquidationPrice: 30.0, marginUsed: 29.2,
};
const untrackedH = {
  symbol: 'H/USDT:USDT', side: 'long', contracts: 822,
  entryPrice: 0.425, markPrice: 0.502, unrealizedPnl: 63.5,
  liquidationPrice: 0.064, marginUsed: 82.6,
};
const paperHype = {
  symbol: 'HYPEUSDT', status: 'open', entryPrice: 57.0,
  stop: 51.62, currentStop: 51.62, target2R: 70.0,
  strategyId: 'qarp', strategyName: 'QARP Momentum 1D',
};

test('matches Binance position to open paper trade by base symbol', () => {
  const { positions } = computeLiveRisk([longHype], [paperHype], 500);
  expect(positions[0].stopSource).toBe('tracked');
  expect(positions[0].strategyName).toBe('QARP Momentum 1D');
  expect(positions[0].stop).toBe(51.62);
});

test('computes long unrealized R from Binance entry/mark and paper stop', () => {
  const { positions } = computeLiveRisk([longHype], [paperHype], 500);
  // (65.77 - 57.37) / (57.37 - 51.62) = 8.4 / 5.75
  expect(positions[0].unrealR).toBeCloseTo(8.4 / 5.75, 4);
});

test('computes short unrealized R mirrored', () => {
  const shortPos = { symbol: 'XYZ/USDT:USDT', side: 'short', contracts: 10, entryPrice: 100, markPrice: 90 };
  const shortPaper = { symbol: 'XYZUSDT', status: 'open', stop: 110, currentStop: 110, target2R: 80 };
  const { positions } = computeLiveRisk([shortPos], [shortPaper], 500);
  // (100 - 90) / (110 - 100) = 1.0
  expect(positions[0].unrealR).toBeCloseTo(1.0, 4);
});

test('untracked position has no stop and zero risk', () => {
  const { positions } = computeLiveRisk([untrackedH], [paperHype], 500);
  expect(positions[0].stopSource).toBe('untracked');
  expect(positions[0].unrealR).toBeNull();
  expect(positions[0].riskAtStopUsd).toBe(0);
});

test('riskAtStopUsd is locked-profit-floored to zero when stop above mark (long, stop>mark impossible) — uses current stop', () => {
  // long, currentStop below mark: risk = qty*(mark-currentStop)
  const { positions } = computeLiveRisk([longHype], [paperHype], 500);
  // 4.44 * (65.77 - 51.62) = 62.826
  expect(positions[0].riskAtStopUsd).toBeCloseTo(4.44 * (65.77 - 51.62), 3);
});

test('riskAtStopUsd zero when stop already above mark (stop locked beyond price)', () => {
  const lockedPaper = { ...paperHype, currentStop: 70.0 }; // above mark 65.77
  const { positions } = computeLiveRisk([longHype], [lockedPaper], 500);
  expect(positions[0].riskAtStopUsd).toBe(0);
});

test('ignores closed paper trades when matching', () => {
  const closed = { ...paperHype, status: 'closed' };
  const { positions } = computeLiveRisk([longHype], [closed], 500);
  expect(positions[0].stopSource).toBe('untracked');
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx jest --config config/jest.config.js crypto/tests/live-risk.test.js`
Expected: FAIL — `Cannot find module '../engine/live-risk'`.

- [ ] **Step 3: Write minimal implementation**

Create `crypto/engine/live-risk.js`:
```javascript
// Pure reconciliation of Binance live positions against the open paper ledger.
// No I/O — all inputs passed in, so this is fully unit-testable.

function baseOf(ccxtSymbol) {
  // 'HYPE/USDT:USDT' -> 'HYPE'
  return (ccxtSymbol || '').split('/')[0];
}

function enrich(bp, paperByBase) {
  const base = baseOf(bp.symbol);
  const paper = paperByBase[base] || null;
  const qty = Math.abs(bp.contracts || 0);
  const isLong = bp.side === 'long';

  if (!paper) {
    return {
      ...bp, base, stopSource: 'untracked',
      unrealR: null, stop: null, currentStop: null, target2R: null,
      strategyId: null, strategyName: null, riskAtStopUsd: 0, action: 'UNTRACKED',
    };
  }

  const entry = bp.entryPrice;
  const mark = bp.markPrice;
  const stop = paper.stop;
  const currentStop = paper.currentStop != null ? paper.currentStop : paper.stop;

  const unrealR = isLong
    ? (mark - entry) / (entry - stop)
    : (entry - mark) / (stop - entry);
  const riskAtStopUsd = isLong
    ? Math.max(0, qty * (mark - currentStop))
    : Math.max(0, qty * (currentStop - mark));

  const enriched = {
    ...bp, base, stopSource: 'tracked', unrealR,
    stop, currentStop, target2R: paper.target2R,
    strategyId: paper.strategyId, strategyName: paper.strategyName,
    riskAtStopUsd,
  };
  enriched.action = decideAction(enriched, isLong, entry);
  return enriched;
}

function decideAction(p, isLong, entry) {
  const { unrealR, currentStop, markPrice } = p;
  const stopBreached = isLong ? markPrice <= currentStop : markPrice >= currentStop;
  if (stopBreached) return 'EXIT';
  const stopNotLocked = isLong ? currentStop < entry : currentStop > entry;
  if (unrealR >= 2 && stopNotLocked) return 'TRAIL';
  if (unrealR >= 1 && stopNotLocked) return 'MOVE_STOP_BE';
  if (unrealR <= -0.8) return 'WARN';
  return 'HOLD';
}

function summarize(positions, equity) {
  const tracked = positions.filter(p => p.stopSource === 'tracked');
  const totalRiskAtStopUsd = tracked.reduce((s, p) => s + p.riskAtStopUsd, 0);
  const eq = equity > 0 ? equity : 0;
  const worstCaseLiqUsd = positions
    .filter(p => p.liquidationPrice && p.markPrice &&
      Math.abs(p.markPrice - p.liquidationPrice) / p.markPrice < 0.15)
    .reduce((s, p) => s + (p.marginUsed || 0), 0);
  return {
    totalRiskAtStopUsd,
    pctEquityAtRisk: eq > 0 ? totalRiskAtStopUsd / eq : 0,
    worstCaseLiqUsd,
    trackedCount: tracked.length,
    untrackedCount: positions.length - tracked.length,
    totalUnrealizedPnlUsd: positions.reduce((s, p) => s + (p.unrealizedPnl || 0), 0),
  };
}

function computeLiveRisk(binancePositions, paperPositions, equity) {
  const openPaper = (paperPositions || []).filter(p => p.status === 'open');
  const paperByBase = {};
  for (const p of openPaper) {
    const base = (p.symbol || '').replace('USDT', '');
    if (!(base in paperByBase)) paperByBase[base] = p;
  }
  const positions = (binancePositions || []).map(bp => enrich(bp, paperByBase));
  return { positions, portfolio: summarize(positions, equity) };
}

module.exports = { computeLiveRisk, decideAction, baseOf };
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx jest --config config/jest.config.js crypto/tests/live-risk.test.js`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add crypto/engine/live-risk.js crypto/tests/live-risk.test.js
git commit -m "feat(crypto): live-risk module — matching, R, risk-at-stop"
```

---

## Task 3: Rules engine branches

The rules engine is already implemented in `decideAction` (Task 2). This task adds dedicated tests for every branch to lock behavior.

**Files:**
- Test: `crypto/tests/live-risk.test.js` (append)

- [ ] **Step 1: Append failing tests**

Append to `crypto/tests/live-risk.test.js`:
```javascript
function longCase(mark, currentStop, entry = 100, stop = 90) {
  const bp = { symbol: 'AAA/USDT:USDT', side: 'long', contracts: 1, entryPrice: entry, markPrice: mark };
  const paper = { symbol: 'AAAUSDT', status: 'open', stop, currentStop, target2R: 120 };
  return computeLiveRisk([bp], [paper], 500).positions[0];
}

test('action EXIT when mark at/below current stop', () => {
  expect(longCase(89, 90).action).toBe('EXIT');
});
test('action TRAIL at R>=2 with stop not yet locked', () => {
  // entry 100, stop 90 -> 1R = 10. mark 121 = 2.1R, currentStop 90 < entry
  expect(longCase(121, 90).action).toBe('TRAIL');
});
test('action MOVE_STOP_BE at 1<=R<2 with stop not locked', () => {
  // mark 115 = 1.5R, currentStop 90 < entry
  expect(longCase(115, 90).action).toBe('MOVE_STOP_BE');
});
test('action HOLD when stop already locked past entry', () => {
  // mark 121 = 2.1R but currentStop 105 >= entry 100 -> not eligible to move
  expect(longCase(121, 105).action).toBe('HOLD');
});
test('action WARN when R<=-0.8 and not breached', () => {
  // mark 91.5: R = (91.5-100)/(100-90) = -0.85, currentStop 90 (not breached, mark>stop)
  expect(longCase(91.5, 90).action).toBe('WARN');
});
test('action HOLD in normal positive zone below 1R', () => {
  // mark 105 = 0.5R
  expect(longCase(105, 90).action).toBe('HOLD');
});
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `npx jest --config config/jest.config.js crypto/tests/live-risk.test.js`
Expected: PASS (all 13 tests). If any FAIL, fix `decideAction` ordering in `live-risk.js` until green.

- [ ] **Step 3: Commit**

```bash
git add crypto/tests/live-risk.test.js
git commit -m "test(crypto): cover all live-risk action branches"
```

---

## Task 4: Portfolio summary tests

**Files:**
- Test: `crypto/tests/live-risk.test.js` (append)

- [ ] **Step 1: Append failing tests**

Append to `crypto/tests/live-risk.test.js`:
```javascript
test('portfolio aggregates tracked risk and pct of equity', () => {
  const bp = { symbol: 'AAA/USDT:USDT', side: 'long', contracts: 2, entryPrice: 100, markPrice: 110, marginUsed: 50, liquidationPrice: 50 };
  const paper = { symbol: 'AAAUSDT', status: 'open', stop: 90, currentStop: 95, target2R: 120 };
  const { portfolio } = computeLiveRisk([bp], [paper], 500);
  // risk = 2 * (110 - 95) = 30
  expect(portfolio.totalRiskAtStopUsd).toBeCloseTo(30, 4);
  expect(portfolio.pctEquityAtRisk).toBeCloseTo(30 / 500, 6);
  expect(portfolio.trackedCount).toBe(1);
  expect(portfolio.untrackedCount).toBe(0);
});

test('portfolio counts untracked separately and excludes from risk', () => {
  const tracked = { symbol: 'AAA/USDT:USDT', side: 'long', contracts: 2, entryPrice: 100, markPrice: 110, marginUsed: 50 };
  const paper = { symbol: 'AAAUSDT', status: 'open', stop: 90, currentStop: 95, target2R: 120 };
  const untracked = { symbol: 'H/USDT:USDT', side: 'long', contracts: 5, entryPrice: 1, markPrice: 1.2, marginUsed: 80 };
  const { portfolio } = computeLiveRisk([tracked, untracked], [paper], 500);
  expect(portfolio.trackedCount).toBe(1);
  expect(portfolio.untrackedCount).toBe(1);
  expect(portfolio.totalRiskAtStopUsd).toBeCloseTo(30, 4);
});

test('worstCaseLiqUsd sums margin only for positions within 15% of liq', () => {
  const near = { symbol: 'AAA/USDT:USDT', side: 'long', contracts: 1, entryPrice: 100, markPrice: 100, marginUsed: 40, liquidationPrice: 90 }; // 10% away
  const far = { symbol: 'BBB/USDT:USDT', side: 'long', contracts: 1, entryPrice: 100, markPrice: 100, marginUsed: 60, liquidationPrice: 50 }; // 50% away
  const { portfolio } = computeLiveRisk([near, far], [], 500);
  expect(portfolio.worstCaseLiqUsd).toBe(40);
});

test('pctEquityAtRisk is zero when equity is not positive', () => {
  const bp = { symbol: 'AAA/USDT:USDT', side: 'long', contracts: 1, entryPrice: 100, markPrice: 110, marginUsed: 50 };
  const paper = { symbol: 'AAAUSDT', status: 'open', stop: 90, currentStop: 95, target2R: 120 };
  const { portfolio } = computeLiveRisk([bp], [paper], 0);
  expect(portfolio.pctEquityAtRisk).toBe(0);
});
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `npx jest --config config/jest.config.js crypto/tests/live-risk.test.js`
Expected: PASS (all 17 tests). The portfolio logic from Task 2 should already satisfy these. If `worstCaseLiqUsd` fails, verify the `< 0.15` threshold in `summarize`.

- [ ] **Step 3: Commit**

```bash
git add crypto/tests/live-risk.test.js
git commit -m "test(crypto): cover live-risk portfolio aggregation"
```

---

## Task 5: API endpoint

**Files:**
- Modify: `dashboard/api.js` (insert after the existing `/crypto/binance-positions` route, ~line 2426)

- [ ] **Step 1: Add the route**

In `dashboard/api.js`, immediately after the `router.get('/crypto/binance-positions', …)` handler closes (the `});` near line 2426), insert:
```javascript
// Live risk: Binance positions enriched with paper-ledger stops + R + rules + portfolio
router.get('/crypto/live-risk', async (req, res) => {
  try {
    const { fetchBinancePositions } = require('../crypto/engine/binance-live');
    const { readPositions }         = require('../crypto/engine/paper');
    const { computeLiveRisk }       = require('../crypto/engine/live-risk');
    const config                    = require('../crypto/engine/config');
    const result = await fetchBinancePositions();
    if (result.error) {
      return res.json({ positions: [], portfolio: null, fetchedAt: result.fetchedAt, error: result.error });
    }
    const equity = Number(req.query.equity) > 0 ? Number(req.query.equity) : config.equity;
    const { positions, portfolio } = computeLiveRisk(result.positions, readPositions(), equity);
    res.json({ positions, portfolio, fetchedAt: result.fetchedAt, error: null });
  } catch (e) {
    res.status(500).json({ positions: [], portfolio: null, error: e.message });
  }
});
```

- [ ] **Step 2: Verify route loads (server smoke test)**

Run (from `C:\Claude\tesseract-scan`):
```bash
node -e "require('./crypto/engine/live-risk'); require('./crypto/engine/config'); require('./crypto/engine/paper'); console.log('requires ok')"
```
Expected: `requires ok` (confirms the modules the route depends on load without error).

- [ ] **Step 3: Commit**

```bash
git add dashboard/api.js
git commit -m "feat(crypto): GET /api/crypto/live-risk endpoint"
```

---

## Task 6: Frontend — switch data source + portfolio strip

**Files:**
- Modify: `dashboard/public/crypto.jsx` — `LiveTradesCrypto` component (`load` ~line 2332, summary strip ~line 2418-2427)

- [ ] **Step 1: Switch `load()` to the new endpoint**

In `LiveTradesCrypto`, replace the `load` function (currently fetching `/api/crypto/binance-positions` and `/api/crypto/paper` in `Promise.all`) with:
```javascript
  const load = async () => {
    setLoading(true);
    try {
      const account = Number(localStorage.getItem('tsrct-scan-account')) || 500;
      const live = await fetch(`/api/crypto/live-risk?equity=${account}`).then(r => r.json());
      setData(live);
    } catch (e) { console.error(e); }
    finally { setLoading(false); setCountdown(30); }
  };
```
Note: `positions` are now pre-enriched by the backend. Leave the `paperPos` state declaration and the `paperByBase` construction block (~line 2405-2407) IN PLACE for now — the row map still references `paperByBase`/`hasPaper`, so removing it here would break the render. With `setPaperPos` no longer called, `paperPos` stays `[]` and `paperByBase` is harmlessly empty. Task 7 removes both the usage and this dead block together.

- [ ] **Step 2: Add the portfolio risk strip**

Locate the existing summary strip (the `<div>` containing `statCell('Live Positions', …)` etc., ~line 2422-2427). Immediately AFTER that closing `</div>`, insert a second strip:
```javascript
      {/* Portfolio risk strip */}
      {data?.portfolio && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 1, border: '1px solid var(--line)', borderRadius: 6, overflow: 'hidden' }}>
          {statCell('% Equity at Risk', (data.portfolio.pctEquityAtRisk * 100).toFixed(1) + '%',
            data.portfolio.pctEquityAtRisk > 0.06 ? 'var(--bear)' : data.portfolio.pctEquityAtRisk > 0.03 ? 'var(--warn)' : undefined)}
          {statCell('Risk if All Stops Hit', '$' + data.portfolio.totalRiskAtStopUsd.toFixed(2))}
          {statCell('Worst Case if Liq', data.portfolio.worstCaseLiqUsd > 0 ? '$' + data.portfolio.worstCaseLiqUsd.toFixed(0) : '—',
            data.portfolio.worstCaseLiqUsd > 0 ? 'var(--bear)' : undefined)}
          {statCell('Tracked / Untracked', `${data.portfolio.trackedCount} / ${data.portfolio.untrackedCount}`)}
        </div>
      )}
```
(`statCell` is already defined in this component, ~line 2409.)

- [ ] **Step 3: Rebuild + browser verify**

Run (from `C:\Claude\tesseract-scan`):
```bash
node dashboard/build.js
```
Expected: `✓ bundle.js` line. Then hard-refresh the dashboard Live Trades tab (Ctrl+Shift+R). Confirm: positions still render, a second risk strip appears with sensible numbers, no console errors.

- [ ] **Step 4: Commit**

```bash
git add dashboard/public/crypto.jsx dashboard/public/bundle.js
git commit -m "feat(crypto): live-risk data source + portfolio strip"
```

---

## Task 7: Frontend — per-row R badge, stop→target bar, action badge

**Files:**
- Modify: `dashboard/public/crypto.jsx` — `LiveTradesCrypto` positions table row (`positions.map`, ~line 2473-2535)

- [ ] **Step 1a: Remove the now-dead paperByBase block + paperPos state**

Delete the dead cross-reference block left in place by Task 6 (~line 2405-2407):
```javascript
  // Map paper trades by base symbol for cross-reference
  const paperByBase  = {};
  for (const p of paperPos) paperByBase[(p.symbol || '').replace('USDT', '')] = p;
```
Also remove the now-unused `paperPos`/`setPaperPos` state declaration (the `useState` line for it).

- [ ] **Step 1b: Replace the derived `sym`/`base`/`hasPaper` lines**

In the `positions.map((p, i) => { … })` body (~line 2479-2481), the rows are now enriched. Replace:
```javascript
                const sym      = p.symbol?.split('/')[0] ?? p.symbol;
                const base     = sym?.replace('USDT','');
                const hasPaper = !!paperByBase[base];
```
with:
```javascript
                const sym      = (p.symbol || '').split(':')[0].replace('/', '') || p.symbol;
                const tracked  = p.stopSource === 'tracked';
                const ACTION_COLOR = { HOLD: TEAL, TRAIL: 'var(--warn)', MOVE_STOP_BE: 'var(--warn)', EXIT: 'var(--bear)', WARN: 'var(--bear)', UNTRACKED: 'var(--fg-3)' };
                const ACTION_LABEL = { HOLD: 'HOLD', TRAIL: 'TRAIL', MOVE_STOP_BE: 'STOP→BE', EXIT: 'EXIT', WARN: 'WARN', UNTRACKED: 'NO STOP' };
                // mark position between stop and target for the progress bar (0..1)
                const barPct = tracked && p.target2R != null && p.currentStop != null && p.target2R !== p.currentStop
                  ? Math.max(0, Math.min(1, (p.markPrice - p.currentStop) / (p.target2R - p.currentStop)))
                  : null;
```

- [ ] **Step 2: Enrich the Symbol cell with R badge, bar, strategy, action**

Replace the Symbol `<td>` block (~line 2493-2498, the cell containing `<span … >{sym}</span>` and the `hasPaper && … PAPER` badge) with:
```javascript
                      <td style={{ ...TD, textAlign: 'left' }}>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                            <span style={{ fontWeight: 700, fontSize: 13 }}>{sym}</span>
                            {tracked && p.unrealR != null && (
                              <span style={{ fontSize: 10, fontWeight: 700, fontFamily: 'var(--font-mono)', padding: '1px 6px', borderRadius: 2, background: (p.unrealR >= 0 ? 'var(--bull)' : 'var(--bear)') + '22', color: p.unrealR >= 0 ? 'var(--bull)' : 'var(--bear)' }}>
                                {(p.unrealR >= 0 ? '+' : '') + p.unrealR.toFixed(2)}R
                              </span>
                            )}
                            <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.06em', padding: '1px 6px', borderRadius: 2, background: (ACTION_COLOR[p.action] || 'var(--fg-3)') + '22', color: ACTION_COLOR[p.action] || 'var(--fg-3)', border: `1px solid ${(ACTION_COLOR[p.action] || 'var(--line)')}44` }}>
                              {ACTION_LABEL[p.action] || p.action}
                            </span>
                          </div>
                          {tracked ? (
                            <>
                              <div style={{ fontSize: 9, color: 'var(--fg-3)', fontFamily: 'var(--font-mono)' }}>
                                {p.strategyName || '—'} · stop {p.currentStop != null ? p.currentStop.toFixed(4) : '—'}
                              </div>
                              {barPct != null && (
                                <div style={{ position: 'relative', height: 4, background: 'var(--bg-2)', borderRadius: 2, width: 140 }}>
                                  <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: (barPct * 100) + '%', background: p.unrealR >= 0 ? 'var(--bull)' : 'var(--warn)', borderRadius: 2 }} />
                                </div>
                              )}
                            </>
                          ) : (
                            <div style={{ fontSize: 9, color: 'var(--fg-3)', fontFamily: 'var(--font-mono)', fontStyle: 'italic' }}>⚠ no stop tracked — add to forward test</div>
                          )}
                        </div>
                      </td>
```

- [ ] **Step 3: Rebuild + browser verify**

Run: `node dashboard/build.js`
Then hard-refresh Live Trades. Confirm for a tracked position (e.g. HYPE): R badge shows, action badge shows, strategy + stop line shows, thin progress bar renders. For an untracked position (e.g. H): "no stop tracked" line, action badge `NO STOP`. No console errors.

- [ ] **Step 4: Commit**

```bash
git add dashboard/public/crypto.jsx dashboard/public/bundle.js
git commit -m "feat(crypto): per-row R badge, stop->target bar, action badge"
```

---

## Task 8: Full test run + promote working version

**Files:** none (verification + version promote)

- [ ] **Step 1: Run the full crypto test suite**

Run (from `C:\Claude\tesseract-scan`):
```bash
npx jest --config config/jest.config.js crypto/tests/live-risk.test.js
```
Expected: PASS (17 tests). Optionally run the whole suite: `npm test` — expect no NEW failures introduced by this change.

- [ ] **Step 2: Snapshot + promote the verified build**

After confirming the Live Trades tab works in the browser:
```bash
node dashboard/version.js snapshot "live-risk-v1"
node dashboard/version.js promote
node dashboard/version.js list
```
Expected: new snapshot listed with `*WORKING`, including `live-risk.js` now present in the tracked file list.

- [ ] **Step 3: Commit**

```bash
git add _versions/MANIFEST.json
git commit -m "chore(crypto): promote live-risk-v1 as last known working"
```

---

## Self-Review Notes

- **Spec coverage:** R + stop distance (Task 2, 7), rules engine (Task 2, 3, 7), portfolio summary (Task 2, 4, 6), endpoint (Task 5), version.js (Task 1, 8), tests (Task 2-4). Correlation cluster intentionally absent (deferred to phase 2 per spec).
- **Untracked handling:** excluded from risk math (Task 2 `summarize` filters `stopSource==='tracked'`), flagged in UI (Task 7 Step 2).
- **Type consistency:** field names `unrealR`, `stopSource`, `riskAtStopUsd`, `currentStop`, `target2R`, `action`, `strategyName` used identically across module, tests, endpoint, and JSX.
- **Restore path:** `version.js restore-working` reverts tracked files to `lastKnownWorking` and rebuilds the bundle.
