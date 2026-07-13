# Squeeze Breakout Reliability — Design

## Problem

Live-data audit of `data/squeeze-breakouts.json` (last 100 events) against the following
2h of 15m candles found:

1. **Spam re-fire.** `squeeze-breakout-monitor.js` dedups only by 5m candle timestamp
   (`state[symbol] === ts`), not by "already alerted this breakout." While price stays
   beyond a level, a new event fires every 5m tick. Confirmed on AAPLUSDT, TLMUSDT,
   METAUSDT, LABUSDT, BEUSDT, BZUSDT, CLUSDT — each fired 2-3 near-duplicate events for
   one underlying move.
2. **~32% whipsaw rate.** 32 of 98 measurable events reversed back through the trigger
   level within 2h. Failures cluster on marginal breaches (e.g. AAPL +0.04%, META
   +0.03% past level+buffer) — the flat `ATR_BUFFER = 0.25` multiplier is too loose for
   weak/noisy levels and doesn't account for how well-established the S/R level is.

## Goals

- Stop duplicate alerts for the same ongoing breakout.
- Reduce whipsaw-triggered alerts without materially delaying real breakouts.
- Weight buffer size by S/R level strength (touch count), which `sr-levels.js` already
  computes but the monitor currently discards.

## Non-goals

- Reworking `sr-levels.js` swing-detection/clustering algorithm itself.
- Changing the squeeze compression score (`squeezeScore()` in squeeze-scanner.js).
- Backtesting/optimizing exact buffer constants beyond a reasonable default — tune later
  from live data if still noisy.

## Design

### 1. Fired-state tracking (`squeeze-breakout-monitor.js`)

Replace `state[symbol] = ts` (candle-dedup only) with a richer per-symbol record:

```js
state[r.symbol] = {
  lastTs: ts,
  active: 'up' | 'down' | null,   // breakout currently alerted+unresolved
  pending: 'up' | 'down' | null,  // single-candle breach awaiting confirmation
}
```

- If `active` direction matches the current breach direction → skip (already alerted,
  still outside range).
- `active` clears when price closes back inside the range (`sup1 <= close <= resPrice`)
  — a genuine reversal-then-rebreak can alert again.
- Migrate old flat-`ts` state format transparently (treat as `{ lastTs: ts, active: null,
  pending: null }` on load).

### 2. Two-candle confirmation

On a breach (close beyond level ± buffer):
- If no `pending` in that direction yet → set `pending = direction`, do **not** alert.
- If `pending` already matches direction (i.e. breach persisted through the next 5m
  candle) → confirm: fire alert, set `active = direction`, clear `pending`.
- If price closes back inside range before confirmation → clear `pending`.

This adds ~5min latency to real breakouts in exchange for filtering single-candle spikes.

### 3. Strength-scaled buffer

`squeeze-scanner.js` already has `pts1`/`pts2` touch-count arrays from `srLevels()` but
doesn't propagate them. Add `resTouches` / `supTouches` (touch count of the level being
used, i.e. `res1pts.length` / `sup1pts.length`) to each result row in `squeeze-cache.json`.

In the monitor, compute buffer per-level instead of one flat constant:

```js
function bufferFor(atrRaw, touches) {
  const mult = clamp(3 / Math.max(touches, 1), 1, 2); // 1 touch → 2x, 3+ touches → 1x
  return atrRaw > 0 ? atrRaw * ATR_BUFFER * mult : 0;
}
```

Weak (1-touch) levels require a 2x buffer before confirming a breach; strong (3+ touch)
levels use the existing 0.25×ATR base.

## Data/schema changes

- `squeeze-cache.json` result rows: add `resTouches`, `supTouches` (int, from
  `sr1pts.length`/`sup1pts.length`).
- `squeeze-breakout-state.json`: schema changes from `{ [symbol]: ts }` to
  `{ [symbol]: { lastTs, active, pending } }`. Old-format entries treated as fresh state
  on first read (no migration script needed — file is regenerated every run).

## Testing

- Unit test `bufferFor()` clamp behavior (1 touch, 3 touch, 10 touch).
- Unit test state-machine transitions (breach → pending → confirm → active → clear on
  re-entry) with a small synthetic candle sequence, covering: single-spike no-confirm,
  two-candle confirm, spam suppression while active, re-entry clearing active.
- Re-run the same live-data whipsaw audit script used for diagnosis against a future
  `squeeze-breakouts.json` sample once deployed, to confirm the fail rate drops.

## Rollout

No feature flag — small scanner script, low blast radius, cron-driven (not user-facing
until Telegram alert fires). Deploy directly; monitor next few days of alerts for
spam/latency regressions.
