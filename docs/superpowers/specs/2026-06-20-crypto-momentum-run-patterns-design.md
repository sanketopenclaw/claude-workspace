# Crypto Momentum Run Patterns — Design Spec

**Date:** 2026-06-20  
**Branch:** crypto-live-risk  
**Scope:** Full replacement of the Patterns tab (Flag/Pole, M Top, W Bottom) with a new 15m Momentum Run scanner.

---

## Overview

Replace all existing pattern detection (Flag & Pole, M Top, W Bottom) and the Patterns tab UI with a single-purpose 15m momentum run scanner. Two pattern types: Bull Run (sustained green candle sequence) and Bear Run (sustained red candle sequence). Results displayed as a color-coded card grid sorted by strength score.

---

## 1. Pattern Detection

### Remove
- `detectFlagPole()` — api.js
- `detectMTop()` — api.js
- `detectMTopForming()` — api.js
- `detectWBottom()` — api.js
- `detectWBottomForming()` — api.js
- `TF_CONFIG` object (patterns-specific TF config) — api.js
- `GET /api/crypto/patterns` endpoint — api.js
- All in-memory pattern cache logic

### Add: `detectMomentumRun(candles)`

Operates on the last 15 candles of 15m OHLCV data per symbol.

**Bull Run qualifies when ALL of:**
- Green candle count ≥ 8 in the last 12–15 bars (candle is green if close > open)
- Red candles in that window ≤ 2
- Each red candle body size < 40% of the average green candle body size in the window (small pullbacks only)
- Average volume of run candles ≥ 1.5× the average volume of the prior 20 bars (vol confirmation)
- Net % move from run start (open of first green candle in sequence) to current close ≥ 1.5%

**Bear Run qualifies when ALL of (mirror):**
- Red candle count ≥ 8 in the last 12–15 bars (candle is red if close < open)
- Green candles in window ≤ 2
- Each green candle body size < 40% of the average red candle body size (small bounces only)
- Average volume of run candles ≥ 1.5× prior 20-bar avg volume
- Net % move down from run start to current close ≥ 1.5%

**Score (0–100):**
```
score = (greenCount / 10) * 40        // candle dominance, max 40
      + Math.min(volRatio / 3, 1) * 30 // vol ratio capped at 3×, max 30
      + Math.min(Math.abs(pctMove) / 5, 1) * 30 // % move capped at 5%, max 30
```

**Return shape per symbol:**
```json
{
  "symbol": "SOLUSDT",
  "direction": "bull" | "bear",
  "score": 78,
  "greenCount": 9,
  "redCount": 1,
  "totalBars": 10,
  "pctMove": 3.8,
  "volRatio": 2.1,
  "volUsd24h": 12100000,
  "currentPrice": 142.50,
  "candles": [...last 15 candle objects for sparkline render...],
  "scannedAt": "2026-06-20T10:30:00Z"
}
```

### Add: `GET /api/crypto/momentum-runs`

- Loads all 15m cached OHLCV files from `crypto/data/cache/*-15m.json`
- Calls `detectMomentumRun()` per symbol
- Returns all qualifying results (both bull and bear) sorted by score desc
- 15-minute in-memory cache (TTL matches auto-refresh interval)
- Query param: `refresh=1` forces cache bust
- Response: `{ success, scannedAt, cached, results: [...] }`

---

## 2. UI — CryptoPatternView (full rewrite)

### Remove from crypto.jsx
- All old `CryptoPatternView` code
- `PatternBadge` component
- `PATTERN_META` constant
- `ConfBar` component (if only used in patterns — check first)
- `CompletionBar` component (if only used in patterns — check first)

### Controls Bar
```
[▶ SCAN RUNS]  [ALL (24)]  [🟢 BULL (15)]  [🔴 BEAR (9)]  VOL≥[dropdown]  auto: 14:32 ↻
```

- **SCAN RUNS** button: triggers manual refresh (`refresh=1`)
- **Filter tabs:** ALL / BULL / BEAR — pill buttons, active state highlighted
- **VOL≥ dropdown:** All Vol / >$500K / >$1M / >$5M / >$10M
- **Auto countdown:** "auto: MM:SS ↻" counts down to next 15-min auto-refresh, updates every second

### Card Grid

4 cards per row (responsive). Sorted by score descending within each direction group (or globally if ALL selected).

**Bull card:**
```
┌──────────────────────────────┐
│ SOLUSDT        🟢 BULL RUN  │  ← symbol bold 16px, badge top-right
│ $142.50          +3.8%      │  ← price + pct move green
│ ▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇            │  ← SVG mini candle bars (15 bars)
│ 9G · 1R · Vol $12.1M   [↗] │  ← stats row + Binance link
└──────────────────────────────┘
```
- Card border: `#00c853` (green), background: `#00c85308`
- Score bar at top of card: thin green line, width = score%

**Bear card (mirror):**
- Border: `#f44336` (red), background: `#f4433608`
- Badge: `🔴 BEAR RUN`
- pctMove shown as negative, red color
- Score bar: red

### Mini Sparkline (SVG)

Inline SVG, 15 candle bars, each bar colored green (close > open) or red (close < open). Bar height proportional to body size relative to max body in window. Width: full card, height: 36px. No axes. Renders client-side from `candles` array in result.

### Binance Link

Every card: `[↗]` button links to `https://www.binance.com/en/futures/SYMBOLUSDT` (futures page). Opens in new tab.

### Empty / Loading States

- Loading: centered spinner text "Scanning 15m charts…"
- No results: "No momentum runs found — try lowering vol filter"
- Pre-scan (first load auto-triggers): skeleton cards or spinner

### Auto-Refresh

- Fires every 15 minutes automatically
- Countdown timer in controls bar counts down seconds
- Manual SCAN RUNS button overrides and resets countdown

---

## 3. File Changes

| File | Change |
|------|--------|
| `dashboard/api.js` | Delete 5 old detectors + `/api/crypto/patterns` endpoint + TF_CONFIG. Add `detectMomentumRun()` + `/api/crypto/momentum-runs` endpoint. |
| `dashboard/public/crypto.jsx` | Delete old `CryptoPatternView`, `PatternBadge`, `PATTERN_META`. Add new `CryptoPatternView` (momentum runs), `MiniSparkline` SVG component, `RunCard` card component. |
| `dashboard/build.js` | No change needed (bundle rebuild after jsx edit). |

---

## 4. Out of Scope

- No multi-TF confirmation (15m only)
- No chart overlay integration for these patterns
- No stop/target/RR calculation
- No pattern age tracking
- No persistence of results to disk
