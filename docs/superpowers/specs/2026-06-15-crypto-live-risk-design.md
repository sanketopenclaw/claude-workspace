# Crypto Live Risk Reconciliation — Design Spec

**Date:** 2026-06-15
**Component:** tesseract-scan / crypto / dashboard Live Trades tab
**Goal:** Make live/forward tracking actionable — merge Binance live positions with the paper ledger so each open position shows risk in R, stop distance, a rules-based action, and a portfolio-level risk view.

## Problem

The Live Trades tab shows raw Binance exchange data per open position (entry, mark, $ PnL, %, leverage, liq price, margin) but **no strategy context**. The stop, target, trail level, strategy name, and R-multiple all live in the paper ledger (`data/crypto-paper.json`) and are never merged onto the live row. The trader eyeballs `$` and `%` instead of `R` and "distance to stop," and has no single portfolio risk number.

## Scope

In scope (user-selected):
1. Risk in R + stop distance per position (merge paper stop/target onto Binance row + progress bar).
2. Rules-based "when to act" signal per position (deterministic, complements existing AI).
3. Portfolio risk view (total $ at risk if all stops hit, % equity, worst-case-if-liq, tracked/untracked counts).

Out of scope:
- Fetching actual exchange stop/TP orders (`fetchOpenOrders`) — explicitly rejected.
- Correlation-cluster exposure — **deferred to phase 2** (needs per-symbol daily candles; breaks module purity, heavier I/O).
- Auto-execution / order placement — not this project.

## Architecture

### 1. `crypto/engine/live-risk.js` — pure reconciliation module

Single pure function, no I/O (all inputs passed in → easy to unit test):

```
computeLiveRisk(binancePositions, paperPositions, equity)
  → { positions: EnrichedPosition[], portfolio: PortfolioSummary }
```

**Matching:** Binance position → paper trade by base symbol. Binance ccxt symbol `HYPE/USDT:USDT` → base `HYPE`. Paper symbol `HYPEUSDT` → base `HYPE` (strip `USDT`). Match on base. Only paper trades with `status === "open"` are candidates. If multiple open paper trades share a base, match the first (single-position-per-symbol is the norm).

**EnrichedPosition fields** (Binance fields preserved, plus):
- `base` — e.g. `HYPE`
- `unrealR` — long: `(mark − entry) / (entry − stop)`; short: `(entry − mark) / (stop − entry)`. `null` if untracked.
- `stop`, `currentStop` (trail), `target2R`, `strategyId`, `strategyName` — from matched paper trade; `null` if untracked.
- `stopSource` — `"tracked"` | `"untracked"`
- `riskAtStopUsd` — loss from current mark to current stop if stopped now:
  - long: `max(0, qty · (mark − currentStop))`
  - short: `max(0, qty · (currentStop − mark))`
  - locked-profit (stop beyond entry in profit direction) ⇒ `0`. `qty` from `Math.abs(contracts)`.
- `action` — from rules engine below.

Entry price uses Binance `entryPrice` (real fill), not paper entry, so R reflects the actual position. Stop/target come from paper (the plan).

### 2. Rules engine (inside live-risk.js, deterministic)

Per position, evaluated top-down (first match wins):

| Condition | `action` | Meaning |
|-----------|----------|---------|
| untracked (no stop) | `UNTRACKED` | no plan logged — add to tracker |
| long: mark ≤ currentStop / short: mark ≥ currentStop | `EXIT` | stop breached, still open |
| `unrealR ≥ 2` and currentStop on wrong side of entry | `TRAIL` | tighten / chandelier |
| `unrealR ≥ 1` and currentStop on wrong side of entry | `MOVE_STOP_BE` | move stop to breakeven |
| `unrealR ≤ −0.8` | `WARN` | near stop |
| else | `HOLD` | within plan |

"currentStop on wrong side of entry" = stop has not yet been moved to lock profit (long: `currentStop < entry`; short: `currentStop > entry`). Qualitative only — no ATR I/O in v1, so the module stays pure. This complements (does not replace) the existing AI `live-analysis` HOLD/TRAIL/EXIT feature.

### 3. PortfolioSummary (returned by same function)

Computed over **tracked** positions only:
- `totalRiskAtStopUsd` = Σ `riskAtStopUsd`
- `pctEquityAtRisk` = `totalRiskAtStopUsd / equity` (guard `equity > 0`)
- `worstCaseLiqUsd` = Σ `marginUsed` for positions whose liq distance < 15%
- `trackedCount`, `untrackedCount`
- `totalUnrealizedPnlUsd` = Σ `unrealizedPnl` (all positions, mirrors existing summary)

### 4. Endpoint — `GET /api/crypto/live-risk?equity=<n>`

Handler in `dashboard/api.js`:
1. `fetchBinancePositions()` (existing, `crypto/engine/binance-live.js`).
2. Read open paper positions (existing `paper.js` `readPositions()` filtered to open).
3. `equity` from query param (frontend passes account size from `tsrct-scan-account` localStorage); default to `config.equity` if absent/invalid.
4. `computeLiveRisk(positions, paper, equity)` → return `{ positions, portfolio, fetchedAt, error }`.
5. On Binance error (no API key), pass through the existing error shape so the frontend "not configured" empty state still works.

### 5. Frontend — `crypto.jsx` Live Trades tab (`LiveTradesCrypto` component)

Switch the data source from `/api/crypto/binance-positions` + `/api/crypto/paper` to the single `/api/crypto/live-risk?equity=<account>` call (account read from existing localStorage key).

Per Binance row, add:
- **R badge** (`unrealR`, color by sign) next to symbol.
- **Entry → stop → target progress bar** (current mark position between stop and target2R).
- **Strategy chip** + **trail level** (currentStop) for tracked rows.
- **Action badge** color-coded: HOLD=teal, TRAIL/MOVE_STOP_BE=warn, EXIT/WARN=bear, UNTRACKED=muted.
- Untracked rows: muted "⚠ add to tracker" affordance (no R, no bar).

Add a **portfolio risk strip** above the positions table:
- `% equity at risk`, `$ at risk if all stops hit`, `worst-case if liq`, `tracked / untracked` counts.
- Sits alongside / above the existing Live Positions / Unrealized PnL / Margin / Exposure summary strip.

Existing per-row AI analysis (▼ AI) and Ask-AI are untouched.

### 6. Tests — `crypto/tests/live-risk.test.js`

Pure-function unit tests (no network):
- Long R and short R correctness.
- Tracked vs untracked matching (base symbol normalization, `HYPE/USDT:USDT` ↔ `HYPEUSDT`).
- Each rules branch: EXIT, TRAIL, MOVE_STOP_BE, WARN, HOLD, UNTRACKED.
- Locked-profit ⇒ `riskAtStopUsd === 0`.
- Portfolio aggregation: sum risk, % equity, worst-case-liq threshold (15%), tracked/untracked counts.
- `equity <= 0` guard.

## Version history (`version.js` + `_versions/`)

User requirement: keep a version history; the served/current version must always be the last known **working** version (a broken edit must never become "current").

### `dashboard/version.js` (Node CLI)
Tracked files: `public/crypto.jsx`, `public/bundle.js`, `api.js`, `../crypto/engine/live-risk.js`.

Commands:
- `node version.js snapshot "<label>"` — copy tracked files into `_versions/<YYYYMMDD_HHMMSS>-<label>/`; append entry to `_versions/MANIFEST.json` (`{ id, label, ts, files[] }`). Does **not** change `lastKnownWorking`.
- `node version.js promote` — set `MANIFEST.lastKnownWorking` to the most recent snapshot id. Run **only after** browser-verifying the change works.
- `node version.js restore-working` — copy files from the `lastKnownWorking` snapshot back over the live files, then rebuild bundle.
- `node version.js list` — print snapshots, mark `lastKnownWorking`.

`_versions/MANIFEST.json` shape:
```json
{
  "lastKnownWorking": "20260615_090000-baseline",
  "snapshots": [
    { "id": "20260615_090000-baseline", "label": "baseline", "ts": "2026-06-15T09:00:00Z", "files": ["crypto.jsx","bundle.js","api.js"] }
  ]
}
```

### Workflow
1. `snapshot "pre-live-risk baseline"` of current working state, then `promote` (current main = known good).
2. Implement feature.
3. `node dashboard/build.js` (rebuild bundle — required after any `.jsx` edit).
4. Browser-verify Live Trades tab.
5. `snapshot "live-risk v1"` → verify again → `promote`.
6. Git commit per promoted version = durable history; `_versions/` = fast local restore.

Git remains the durable backbone; `_versions/` is the fast, visible local restore layer the user wanted.

## File summary

| File | Change |
|------|--------|
| `crypto/engine/live-risk.js` | NEW — pure `computeLiveRisk` + rules engine |
| `crypto/tests/live-risk.test.js` | NEW — unit tests |
| `dashboard/api.js` | NEW route `GET /api/crypto/live-risk` |
| `dashboard/public/crypto.jsx` | `LiveTradesCrypto`: single data source, R badge, progress bar, action badge, portfolio strip |
| `dashboard/public/bundle.js` | rebuilt via `build.js` |
| `dashboard/version.js` | NEW — snapshot/promote/restore-working/list |
| `_versions/MANIFEST.json` | NEW — version manifest |

## Success criteria
- Each tracked live position shows unrealized R, stop distance bar, strategy, and a correct rules action.
- Untracked positions clearly flagged, excluded from risk math.
- Portfolio strip shows % equity at risk + $ at risk if all stops hit.
- `live-risk.test.js` passes (all rule branches + portfolio aggregation).
- `version.js restore-working` reverts to last promoted snapshot and rebuilds.
- Existing AI per-row analysis unaffected.
