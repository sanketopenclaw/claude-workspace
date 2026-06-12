# Crypto EOD Auto-Log Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove per-scan auto-logging of crypto picks and replace with a single daily cron at 8 PM IST that logs all picks from the latest scan to the forward test.

**Architecture:** Two surgical edits — strip the `addPosition` call from `crypto-scanner.js` (scanner becomes display-only), then add `runCryptoEodLog()` + cron to `server.js`. No new files, no schema changes.

**Tech Stack:** Node.js, node-cron, `crypto/engine/paper.js` (addPosition)

---

## File Map

| File | Change |
|------|--------|
| `tesseract-scan/crypto/scripts/crypto-scanner.js` | Remove `addPosition` require + auto-log block |
| `tesseract-scan/dashboard/server.js` | Add `runCryptoEodLog()` function + cron at 8 PM IST |

---

### Task 1: Remove auto-log from crypto-scanner.js

**Files:**
- Modify: `tesseract-scan/crypto/scripts/crypto-scanner.js:1-10` (remove require)
- Modify: `tesseract-scan/crypto/scripts/crypto-scanner.js:90-110` (remove auto-log block)

- [ ] **Step 1: Remove the `addPosition` require on line 5**

Current line 5:
```js
const { addPosition } = require('../engine/paper');
```
Delete this line entirely. The scanner no longer touches the forward test.

- [ ] **Step 2: Remove the auto-log block inside the picks loop**

Current block at lines 90–108 (inside `.then(async result => {`):
```js
    // Entry alerts + auto-log to forward-test journal
    if (result.picks?.length) {
      const regime = {
        state: result.regime,
        breadth: result.breadth,
        btcUp: result.breadthDetail?.btcUp ?? null,
      };
      for (const pick of result.picks) {
        await sendMessage(fmtEntry(pick, regime)).catch(() => {});
        try {
          addPosition(pick);
          console.log(`[crypto-scanner] Auto-logged ${pick.symbol} to forward test`);
        } catch (e) {
          // "Already have open position" is expected for repeating signals — skip silently
          if (!e.message.includes('Already have open')) {
            console.warn(`[crypto-scanner] Auto-log ${pick.symbol} failed:`, e.message);
          }
        }
      }
    }
```

Replace with (keep Telegram alerts, remove `addPosition` calls):
```js
    // Entry alerts
    if (result.picks?.length) {
      const regime = {
        state: result.regime,
        breadth: result.breadth,
        btcUp: result.breadthDetail?.btcUp ?? null,
      };
      for (const pick of result.picks) {
        await sendMessage(fmtEntry(pick, regime)).catch(() => {});
      }
    }
```

- [ ] **Step 3: Verify no remaining references to `addPosition` in the file**

Run:
```bash
grep -n "addPosition" tesseract-scan/crypto/scripts/crypto-scanner.js
```
Expected: no output (zero matches).

- [ ] **Step 4: Run existing crypto paper tests to confirm nothing broke**

```bash
cd tesseract-scan && npx jest crypto/tests/crypto-paper.test.js --no-coverage
```
Expected: all tests PASS (these tests cover `addPosition` in isolation — unaffected by scanner change).

- [ ] **Step 5: Commit**

```bash
cd tesseract-scan
git add crypto/scripts/crypto-scanner.js
git commit -m "refactor(crypto): remove per-scan auto-log — EOD cron takes over"
```

---

### Task 2: Add EOD cron to server.js

**Files:**
- Modify: `tesseract-scan/dashboard/server.js` — add function + cron after line 543

- [ ] **Step 1: Add `runCryptoEodLog` function and cron after the crypto scan cron block**

Find this block (around line 543):
```js
cron.schedule('0 */4 * * *', runCryptoScan);
```

Insert immediately after it:
```js

// ── Crypto EOD auto-log — 8 PM IST daily ─────────────────────────────────────
const CRYPTO_SCAN_FP = path.join(__dirname, '..', 'data', 'crypto-scan.json');
function runCryptoEodLog() {
  let scan;
  try {
    scan = JSON.parse(fs.readFileSync(CRYPTO_SCAN_FP, 'utf8'));
  } catch {
    console.log('[CRYPTO-EOD] No scan data — skipping');
    return;
  }
  if (!scan?.picks?.length) {
    console.log('[CRYPTO-EOD] No picks in latest scan — skipping');
    return;
  }
  const { addPosition } = require('../crypto/engine/paper');
  let added = 0, skipped = 0;
  for (const pick of scan.picks) {
    try {
      addPosition(pick);
      added++;
    } catch {
      skipped++;
    }
  }
  console.log(`[CRYPTO-EOD] ${added} picks logged to forward test, ${skipped} skipped (already open)`);
}
cron.schedule('0 20 * * *', runCryptoEodLog, { timezone: 'Asia/Kolkata' });
```

- [ ] **Step 2: Update the scheduled tasks log line**

Find (around line 545):
```js
console.log('  Scheduled: daily scan 4:15PM+8AM IST, live scan 9:15-15:30 5min, trail 3:35PM, exit-guidance 3:40PM, post-mortem 3:45PM, weekly Friday 3:35PM, cache sync every 1h, crypto scan every 4h');
```

Replace with:
```js
console.log('  Scheduled: daily scan 4:15PM+8AM IST, live scan 9:15-15:30 5min, trail 3:35PM, exit-guidance 3:40PM, post-mortem 3:45PM, weekly Friday 3:35PM, cache sync every 1h, crypto scan every 4h, crypto EOD log 8PM IST');
```

- [ ] **Step 3: Smoke-test the server starts without error**

```bash
cd tesseract-scan && node dashboard/server.js &
sleep 3 && curl -s http://localhost:3000/api/crypto/scan | head -c 100
```
Expected: server starts, returns JSON (or `{"status":"no_data"...}` if no scan file). Kill with `kill %1` after check.

> Note: If server is already running via pm2, skip the manual start — just check pm2 logs after restarting: `pm2 restart tesseract`

- [ ] **Step 4: Commit**

```bash
cd tesseract-scan
git add dashboard/server.js
git commit -m "feat(crypto): add 8PM IST cron to auto-log EOD scan picks to forward test"
```
