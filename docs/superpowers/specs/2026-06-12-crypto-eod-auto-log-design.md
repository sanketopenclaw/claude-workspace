# Crypto EOD Auto-Log — Design Spec

## Problem

Crypto scanner runs every 4h and currently auto-logs picks to the forward test on each run. This creates multiple log attempts per day per symbol (deduped by error), and couples scan execution to forward-test entry. User wants a single clean end-of-day snapshot.

## Goal

Move all picks from the latest crypto scan into the forward test once per day at 8 PM IST. Remove per-scan auto-logging.

## Changes

### 1. `crypto/scripts/crypto-scanner.js`

Remove the auto-log block (lines 99–108):

```js
// REMOVE THIS BLOCK:
try {
  addPosition(pick);
  console.log(`[crypto-scanner] Auto-logged ${pick.symbol} to forward test`);
} catch (e) {
  if (!e.message.includes('Already have open')) {
    console.warn(`[crypto-scanner] Auto-log ${pick.symbol} failed:`, e.message);
  }
}
```

Also remove the `addPosition` require at the top of the file if it becomes unused.

### 2. `dashboard/server.js`

Add after the existing crypto scan cron:

```js
// ── Crypto EOD auto-log — 8 PM IST daily ─────────────────────────────────────
async function runCryptoEodLog() {
  const scan = readJSON('crypto-scan.json', null);
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

Update the scheduled tasks console.log to include: `crypto EOD log 8PM IST`.

## Data Flow

```
crypto-scanner.js (every 4h)
  → writes crypto-scan.json (display only)

server.js cron 8PM IST
  → reads crypto-scan.json
  → calls addPosition(pick) for each pick
  → writes crypto-paper.json (forward test)
```

## Constraints

- `addPosition` deduplicates by open symbol — any already-open position is skipped silently
- No scan-age check; logs whatever is in crypto-scan.json at 8 PM
- `crypto-paper.json` schema unchanged
- Forward test UI unchanged

## Files Changed

| File | Change |
|------|--------|
| `crypto/scripts/crypto-scanner.js` | Remove `addPosition` auto-log block + unused require |
| `dashboard/server.js` | Add `runCryptoEodLog` function + cron at 8 PM IST |
