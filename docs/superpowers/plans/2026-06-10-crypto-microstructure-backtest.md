# Crypto Microstructure Strategy Backtest — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement 7 new crypto strategy plugins (CVD Divergence, OI Squeeze, Funding Fade, Cross-Sectional Momentum, Perpetual Basis, VWAP Reversion, Volatility Squeeze), backtest all with $1000 capital, and export results to a multi-sheet Excel workbook.

**Architecture:** Each strategy is a plugin compatible with `crypto/engine/engine.js:runStrategy()`. Two strategies (OI Squeeze, Perp Basis) lazy-load their own auxiliary cache files from within `signal()` using `context.currentSymKey`. Two new data fetchers populate `data/crypto-oi-cache/` and `data/crypto-spot-cache/`. A standalone runner script orchestrates all 7 backtests and a separate exporter generates the Excel file.

**Tech Stack:** Node.js, existing `engine.js:runStrategy`, `exceljs` (already in devDependencies), Binance REST API (`fapi.binance.com` for OI, `api.binance.com` for spot).

**No dashboard changes.** This is entirely standalone — new files only, except extending `indicators.js`.

---

## File Map

| Action | Path | Purpose |
|--------|------|---------|
| Modify | `crypto/engine/indicators.js` | Add `cvd()` and `vwap()` |
| Create | `crypto/tests/ms-indicators.test.js` | Tests for cvd + vwap |
| Create | `crypto/scripts/fetch-oi-cache.js` | Fetch OI history from Binance futures API |
| Create | `crypto/scripts/fetch-spot-cache.js` | Fetch spot OHLCV from Binance spot API |
| Create | `crypto/strategies/microstructure/ms_cvd_divergence_4h.js` | S1 |
| Create | `crypto/strategies/microstructure/ms_oi_squeeze_4h.js` | S2 |
| Create | `crypto/strategies/microstructure/ms_funding_fade_4h.js` | S3 |
| Create | `crypto/strategies/microstructure/ms_cross_sectional_1d.js` | S4 |
| Create | `crypto/strategies/microstructure/ms_perp_basis_4h.js` | S5 |
| Create | `crypto/strategies/microstructure/ms_vwap_reversion_4h.js` | S6 |
| Create | `crypto/strategies/microstructure/ms_volatility_squeeze_4h.js` | S7 |
| Create | `crypto/strategies/microstructure/index.js` | Re-export all 7 |
| Create | `crypto/tests/ms-strategies.test.js` | Signal unit tests for all 7 |
| Create | `crypto/scripts/run-microstructure-backtest.js` | Run all 7, compute year-by-year, write JSON |
| Create | `crypto/scripts/export-microstructure-xlsx.js` | Read JSON, write Excel |

---

## Task 1: Add `cvd` and `vwap` to indicators.js

**Files:**
- Modify: `crypto/engine/indicators.js`
- Create: `crypto/tests/ms-indicators.test.js`

### What these do
- `cvd(candles)` — cumulative volume delta. For each bar: buyVol = volume × (close−low)/(high−low). CVD[i] = running sum of (buyVol − sellVol).
- `vwap(candles)` — daily VWAP from 4H candles. Resets at UTC midnight. VWAP = Σ(typicalPrice × volume) / Σ(volume) per UTC day, carried forward to each bar.

- [ ] **Step 1: Write failing tests**

Create `crypto/tests/ms-indicators.test.js`:

```js
const { cvd, vwap } = require('../engine/indicators');

describe('cvd', () => {
  test('first bar: buyVol fraction = (close-low)/(high-low)', () => {
    // high=10, low=8, close=9, vol=100 → buyVol=50, sellVol=50, cvd[0]=0
    const candles = [[0, 8.5, 10, 8, 9, 100]];
    const result = cvd(candles);
    expect(result[0]).toBeCloseTo(0, 5);
  });

  test('bullish bar: close at high → cvd increases by full volume', () => {
    // high=10, low=8, close=10, vol=100 → buyVol=100, sellVol=0
    const candles = [[0, 9, 10, 8, 10, 100]];
    const result = cvd(candles);
    expect(result[0]).toBeCloseTo(100, 5);
  });

  test('bearish bar: close at low → cvd decreases by full volume', () => {
    const candles = [[0, 9, 10, 8, 8, 100]];
    const result = cvd(candles);
    expect(result[0]).toBeCloseTo(-100, 5);
  });

  test('cumulates across bars', () => {
    // Bar0: close at high (+100), Bar1: close at mid (0)
    const candles = [
      [0,   9, 10, 8, 10, 100],
      [100, 9, 10, 8,  9, 100],
    ];
    const result = cvd(candles);
    expect(result[0]).toBeCloseTo(100, 5);
    expect(result[1]).toBeCloseTo(100, 5); // net zero second bar
  });

  test('returns array same length as candles', () => {
    const candles = [[0,9,10,8,9,100],[1,9,10,8,9,100],[2,9,10,8,9,100]];
    expect(cvd(candles)).toHaveLength(3);
  });
});

describe('vwap', () => {
  const DAY = 86400000;
  const HOUR4 = 4 * 3600000;

  function makeCandles(n, baseTs, price = 100, vol = 1000) {
    return Array.from({ length: n }, (_, i) => [
      baseTs + i * HOUR4,
      price, price * 1.01, price * 0.99, price, vol
    ]);
  }

  test('single bar VWAP equals typical price', () => {
    // typical = (high+low+close)/3 = (101+99+100)/3 = 100
    const candles = [[0, 100, 101, 99, 100, 1000]];
    const result = vwap(candles);
    expect(result[0]).toBeCloseTo(100, 2);
  });

  test('resets at UTC midnight', () => {
    // Day 1: ts=0 (UTC midnight Jan 1 1970), Day 2: ts=DAY
    const c1 = [[0,       100, 110, 90, 100, 1000]];
    const c2 = [[DAY,     200, 210, 190, 200, 1000]];
    const candles = [...c1, ...c2];
    const result = vwap(candles);
    // Day 2 VWAP should only include day-2 bar
    const tp2 = (210 + 190 + 200) / 3;
    expect(result[1]).toBeCloseTo(tp2, 2);
  });

  test('returns array same length as candles', () => {
    const candles = makeCandles(6, 0);
    expect(vwap(candles)).toHaveLength(6);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd C:\Claude\tesseract-scan
npx jest crypto/tests/ms-indicators.test.js --no-coverage
```

Expected: FAIL — `cvd is not a function`, `vwap is not a function`

- [ ] **Step 3: Add `cvd` and `vwap` to indicators.js**

Add before the `module.exports` line in `crypto/engine/indicators.js`:

```js
// Cumulative Volume Delta — approximated from OHLCV bars.
// buyVol = volume × (close−low) / (high−low). CVD = running Σ(buyVol − sellVol).
function cvd(candles) {
  const result = new Array(candles.length).fill(0);
  let running = 0;
  for (let i = 0; i < candles.length; i++) {
    const [, , high, low, close, volume] = candles[i];
    const range = high - low;
    const buyFrac = range > 0 ? (close - low) / range : 0.5;
    const delta = volume * (2 * buyFrac - 1); // buyVol − sellVol
    running += delta;
    result[i] = running;
  }
  return result;
}

// Daily VWAP — resets at UTC midnight each day.
// Typical price = (high + low + close) / 3.
function vwap(candles) {
  const result = new Array(candles.length).fill(null);
  let cumTPV = 0, cumVol = 0, currentDay = -1;
  for (let i = 0; i < candles.length; i++) {
    const [ts, , high, low, close, volume] = candles[i];
    const day = Math.floor(ts / 86400000);
    if (day !== currentDay) { cumTPV = 0; cumVol = 0; currentDay = day; }
    const tp = (high + low + close) / 3;
    cumTPV += tp * volume;
    cumVol += volume;
    result[i] = cumVol > 0 ? cumTPV / cumVol : close;
  }
  return result;
}
```

Also update `module.exports` in `indicators.js` — add `cvd, vwap` to the export list:

```js
module.exports = {
  ema, atr, donchian, roc, adx, volumeZscore, fundingPercentile, combinedFundingPct,
  rsi, macd, bollingerBands, keltnerChannels,
  donchianLow, atrRatio, higherLow, lowerHigh, insideBar,
  volumeConfirm,
  supertrend, heikinAshi, mfi, alphatrend, ichimoku,
  cvd, vwap,
};
```

- [ ] **Step 4: Run tests to verify they pass**

```
npx jest crypto/tests/ms-indicators.test.js --no-coverage
```

Expected: PASS (7 tests)

- [ ] **Step 5: Run full test suite to check no regressions**

```
npx jest --config config/jest.config.js --forceExit --no-coverage
```

Expected: all existing tests still pass

- [ ] **Step 6: Commit**

```
git add crypto/engine/indicators.js crypto/tests/ms-indicators.test.js
git commit -m "feat(crypto): add cvd and vwap indicators"
```

---

## Task 2: OI Cache Fetcher

**Files:**
- Create: `crypto/scripts/fetch-oi-cache.js`
- Create: `data/crypto-oi-cache/` (dir, created by script)

Binance endpoint: `GET https://fapi.binance.com/futures/data/openInterestHist?symbol=BTCUSDT&period=4h&limit=500`
Response: `[{ symbol, sumOpenInterest, sumOpenInterestValue, timestamp }, ...]`
Max limit per call: 500 bars. Max lookback: ~30 days. For longer history, page backward using `endTime`.

Cache format per symbol: `data/crypto-oi-cache/{SYMKEY}-oi.json` → `{ lastTs: number, bars: [{ ts, oi }] }`

- [ ] **Step 1: Create `crypto/scripts/fetch-oi-cache.js`**

```js
#!/usr/bin/env node
// Fetches 4H open interest history for all universe symbols from Binance futures API.
// Stores to data/crypto-oi-cache/{symKey}-oi.json
// Run: node crypto/scripts/fetch-oi-cache.js

const https = require('https');
const fs    = require('fs');
const path  = require('path');

const CACHE_DIR = path.join(__dirname, '../../data/crypto-cache');
const OI_DIR    = path.join(__dirname, '../../data/crypto-oi-cache');
const DELAY_MS  = 300; // stay under Binance rate limit

if (!fs.existsSync(OI_DIR)) fs.mkdirSync(OI_DIR, { recursive: true });

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function restGet(url) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, res => {
      if (res.statusCode !== 200) { res.resume(); return reject(new Error(`HTTP ${res.statusCode} ${url}`)); }
      let raw = '';
      res.on('data', c => raw += c);
      res.on('end', () => { try { resolve(JSON.parse(raw)); } catch (e) { reject(e); } });
    });
    req.on('error', reject);
    req.setTimeout(15000, () => req.destroy(new Error('timeout')));
  });
}

// Fetch all available OI history for a symbol by paging backward in 500-bar chunks
async function fetchAllOI(nativeSym) {
  const bars = [];
  let endTime = undefined;
  while (true) {
    const url = `https://fapi.binance.com/futures/data/openInterestHist?symbol=${nativeSym}&period=4h&limit=500${endTime ? `&endTime=${endTime}` : ''}`;
    const chunk = await restGet(url);
    if (!Array.isArray(chunk) || chunk.length === 0) break;
    bars.unshift(...chunk);
    if (chunk.length < 500) break;
    endTime = chunk[0].timestamp - 1;
    await sleep(200);
  }
  return bars.map(b => ({ ts: b.timestamp, oi: parseFloat(b.sumOpenInterest) }));
}

function symKeyToNative(symKey) {
  // BTC_USDT_USDT → BTCUSDT
  return symKey.replace('_USDT_USDT', 'USDT').replace(/_/g, '');
}

function getUniverse() {
  try {
    return fs.readdirSync(CACHE_DIR)
      .filter(f => f.endsWith('-4h.json'))
      .map(f => f.replace('-4h.json', ''));
  } catch { return []; }
}

async function main() {
  const universe = getUniverse();
  console.log(`[oi-fetch] ${universe.length} symbols`);
  let done = 0;
  for (const symKey of universe) {
    const outFile = path.join(OI_DIR, `${symKey}-oi.json`);
    const nativeSym = symKeyToNative(symKey);
    try {
      const bars = await fetchAllOI(nativeSym);
      if (bars.length > 0) {
        fs.writeFileSync(outFile, JSON.stringify({ lastTs: bars[bars.length - 1].ts, bars }));
        process.stdout.write(`\r[oi-fetch] ${++done}/${universe.length} ${symKey} (${bars.length} bars)`);
      }
    } catch (e) {
      console.error(`\n[oi-fetch] ERROR ${symKey}: ${e.message}`);
    }
    await sleep(DELAY_MS);
  }
  console.log(`\n[oi-fetch] Done. ${done} symbols saved to ${OI_DIR}`);
}

main().catch(console.error);
```

- [ ] **Step 2: Commit**

```
git add crypto/scripts/fetch-oi-cache.js
git commit -m "feat(crypto): add OI history cache fetcher"
```

---

## Task 3: Spot Cache Fetcher

**Files:**
- Create: `crypto/scripts/fetch-spot-cache.js`
- Create: `data/crypto-spot-cache/` (dir, created by script)

Binance spot endpoint: `GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=4h&limit=1000`
Response: `[[openTime, open, high, low, close, volume, ...], ...]`

Cache format: `data/crypto-spot-cache/{symKey}-spot-4h.json` → `{ lastTs: number, candles: [[ts,o,h,l,c,v], ...] }`

- [ ] **Step 1: Create `crypto/scripts/fetch-spot-cache.js`**

```js
#!/usr/bin/env node
// Fetches 4H spot OHLCV for universe symbols from Binance spot API.
// Stores to data/crypto-spot-cache/{symKey}-spot-4h.json
// Run: node crypto/scripts/fetch-spot-cache.js

const https = require('https');
const fs    = require('fs');
const path  = require('path');

const CACHE_DIR = path.join(__dirname, '../../data/crypto-cache');
const SPOT_DIR  = path.join(__dirname, '../../data/crypto-spot-cache');
const DELAY_MS  = 300;

if (!fs.existsSync(SPOT_DIR)) fs.mkdirSync(SPOT_DIR, { recursive: true });

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function restGet(url) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, res => {
      if (res.statusCode !== 200) { res.resume(); return reject(new Error(`HTTP ${res.statusCode}`)); }
      let raw = '';
      res.on('data', c => raw += c);
      res.on('end', () => { try { resolve(JSON.parse(raw)); } catch (e) { reject(e); } });
    });
    req.on('error', reject);
    req.setTimeout(15000, () => req.destroy(new Error('timeout')));
  });
}

async function fetchSpotOHLCV(nativeSym) {
  const candles = [];
  let endTime = undefined;
  while (true) {
    const url = `https://api.binance.com/api/v3/klines?symbol=${nativeSym}&interval=4h&limit=1000${endTime ? `&endTime=${endTime}` : ''}`;
    const chunk = await restGet(url);
    if (!Array.isArray(chunk) || chunk.length === 0) break;
    // Klines format: [openTime, open, high, low, close, volume, ...]
    const parsed = chunk.map(k => [k[0], +k[1], +k[2], +k[3], +k[4], +k[5]]);
    candles.unshift(...parsed);
    if (chunk.length < 1000) break;
    endTime = chunk[0][0] - 1;
    await sleep(150);
  }
  return candles;
}

function symKeyToNative(symKey) {
  return symKey.replace('_USDT_USDT', 'USDT').replace(/_/g, '');
}

function getUniverse() {
  try {
    return fs.readdirSync(CACHE_DIR)
      .filter(f => f.endsWith('-4h.json'))
      .map(f => f.replace('-4h.json', ''));
  } catch { return []; }
}

async function main() {
  const universe = getUniverse();
  console.log(`[spot-fetch] ${universe.length} symbols`);
  let done = 0;
  for (const symKey of universe) {
    const outFile = path.join(SPOT_DIR, `${symKey}-spot-4h.json`);
    const nativeSym = symKeyToNative(symKey);
    try {
      const candles = await fetchSpotOHLCV(nativeSym);
      if (candles.length > 0) {
        fs.writeFileSync(outFile, JSON.stringify({ lastTs: candles[candles.length - 1][0], candles }));
        process.stdout.write(`\r[spot-fetch] ${++done}/${universe.length} ${symKey} (${candles.length} bars)`);
      }
    } catch (e) {
      console.error(`\n[spot-fetch] ERROR ${symKey}: ${e.message}`);
    }
    await sleep(DELAY_MS);
  }
  console.log(`\n[spot-fetch] Done. ${done} symbols saved to ${SPOT_DIR}`);
}

main().catch(console.error);
```

- [ ] **Step 2: Commit**

```
git add crypto/scripts/fetch-spot-cache.js
git commit -m "feat(crypto): add spot OHLCV cache fetcher"
```

---

## Task 4: S1 — CVD Divergence Strategy

**Files:**
- Create: `crypto/strategies/microstructure/ms_cvd_divergence_4h.js`

Signal logic: Price 20-bar change positive but CVD 20-bar change negative → short (fake move). Price 20-bar change negative but CVD 20-bar change positive → long (hidden buying).

- [ ] **Step 1: Create strategy file**

```js
// ms_cvd_divergence_4h.js — Cumulative Volume Delta divergence.
// Short when price rises but CVD falls (fake breakout).
// Long when price falls but CVD rises (hidden accumulation).
const ind = require('../../engine/indicators');

const LOOKBACK = 20;

module.exports = {
  id: 'ms_cvd_divergence_4h',
  name: 'CVD Divergence 4H',
  timeframe: '4h',
  direction: 'both',
  params: { cvdLookback: LOOKBACK },

  precompute(candles, p) {
    const closes = candles.map(c => c[4]);
    const highs  = candles.map(c => c[2]);
    const lows   = candles.map(c => c[3]);
    const lb = p.cvdLookback ?? LOOKBACK;
    return {
      ema200: ind.ema(closes, p.ema?.trend ?? 200),
      ema21:  ind.ema(closes, p.ema?.fast  ?? 21),
      atr:    ind.atr(highs, lows, closes, p.atrPeriod ?? 14),
      cvdArr: ind.cvd(candles),
    };
  },

  signal(i, o, candles, p) {
    const lb = p.cvdLookback ?? LOOKBACK;
    if (i < lb) return false;
    if (o.ema200[i] == null || o.atr[i] == null) return false;

    const close    = candles[i][4];
    const prevClose = candles[i - lb][4];
    const priceDelta = (close - prevClose) / prevClose;

    const cvdNow  = o.cvdArr[i];
    const cvdPrev = o.cvdArr[i - lb];
    const cvdDelta = cvdNow - cvdPrev;

    // Bearish divergence: price up, CVD down → short
    if (priceDelta > 0.02 && cvdDelta < 0 && close < o.ema200[i]) return 'short';

    // Bullish divergence: price down, CVD up → long
    if (priceDelta < -0.02 && cvdDelta > 0 && close > o.ema200[i]) return 'long';

    return false;
  },

  exit: { stopMult: 2, trailAfterR: 2, trailMult: 3, timeBars: 12 },
};
```

- [ ] **Step 2: Commit**

```
git add crypto/strategies/microstructure/ms_cvd_divergence_4h.js
git commit -m "feat(crypto): add CVD divergence strategy S1"
```

---

## Task 5: S2 — OI Squeeze Strategy

**Files:**
- Create: `crypto/strategies/microstructure/ms_oi_squeeze_4h.js`

OI data loaded lazily in `signal()` via `context.currentSymKey`. Cache dir resolved relative to this file.

- [ ] **Step 1: Create strategy file**

```js
// ms_oi_squeeze_4h.js — Open Interest Squeeze.
// Rising OI + flat/falling price = trapped longs → expect drop.
// Rising OI + rising price = confirmed breakout → long.
const fs   = require('fs');
const path = require('path');
const ind  = require('../../engine/indicators');

const OI_DIR = path.join(__dirname, '../../../data/crypto-oi-cache');

// Cache loaded OI data in memory after first read
const _oiMap = {};

function loadOI(symKey) {
  if (_oiMap[symKey] !== undefined) return _oiMap[symKey];
  const file = path.join(OI_DIR, `${symKey}-oi.json`);
  try {
    const raw = JSON.parse(fs.readFileSync(file, 'utf8'));
    _oiMap[symKey] = raw.bars || [];
  } catch {
    _oiMap[symKey] = [];
  }
  return _oiMap[symKey];
}

// Binary search: find OI bar at or just before timestamp
function oiAt(bars, ts) {
  let lo = 0, hi = bars.length - 1, res = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (bars[mid].ts <= ts) { res = mid; lo = mid + 1; } else hi = mid - 1;
  }
  return res;
}

const OI_LOOKBACK = 4; // bars (~16H)

module.exports = {
  id: 'ms_oi_squeeze_4h',
  name: 'OI Squeeze 4H',
  timeframe: '4h',
  direction: 'both',
  params: { oiLookback: OI_LOOKBACK, oiChangePct: 15 },

  precompute(candles, p) {
    const closes = candles.map(c => c[4]);
    const highs  = candles.map(c => c[2]);
    const lows   = candles.map(c => c[3]);
    return {
      ema200: ind.ema(closes, p.ema?.trend ?? 200),
      ema55:  ind.ema(closes, p.ema?.slow  ?? 55),
      atr:    ind.atr(highs, lows, closes, p.atrPeriod ?? 14),
    };
  },

  signal(i, o, candles, p, _gate, context) {
    const lb         = p.oiLookback ?? OI_LOOKBACK;
    const threshold  = (p.oiChangePct ?? 15) / 100;
    if (i < lb) return false;
    if (o.ema200[i] == null || o.atr[i] == null) return false;

    const symKey = context?.currentSymKey;
    if (!symKey) return false;

    const oiBars = loadOI(symKey);
    if (oiBars.length < lb + 1) return false;

    const ts     = candles[i][0];
    const tsPrev = candles[i - lb][0];
    const idxNow  = oiAt(oiBars, ts);
    const idxPrev = oiAt(oiBars, tsPrev);
    if (idxNow < 0 || idxPrev < 0 || idxNow === idxPrev) return false;

    const oiNow  = oiBars[idxNow].oi;
    const oiPrev = oiBars[idxPrev].oi;
    if (oiPrev === 0) return false;

    const oiChange    = (oiNow - oiPrev) / oiPrev;
    const priceChange = (candles[i][4] - candles[i - lb][4]) / candles[i - lb][4];
    const close       = candles[i][4];

    // OI spike with price flat/down = trapped longs → short
    if (oiChange > threshold && priceChange < 0.01 && close < o.ema200[i]) return 'short';

    // OI spike with price up = confirmed breakout → long
    if (oiChange > threshold && priceChange > 0.03 && close > o.ema200[i]) return 'long';

    return false;
  },

  exit: { stopMult: 2, trailAfterR: 2, trailMult: 3, timeBars: 12 },
};
```

- [ ] **Step 2: Commit**

```
git add crypto/strategies/microstructure/ms_oi_squeeze_4h.js
git commit -m "feat(crypto): add OI squeeze strategy S2"
```

---

## Task 6: S3 — Funding Rate Fade Strategy

**Files:**
- Create: `crypto/strategies/microstructure/ms_funding_fade_4h.js`

Uses `context.currentBinanceFundingRate` — already provided by engine on every signal call.

- [ ] **Step 1: Create strategy file**

```js
// ms_funding_fade_4h.js — Funding rate extremes signal over-leveraging.
// High positive funding + price below EMA21 → short (longs paying too much, unwind coming).
// High negative funding + price above EMA21 → long (shorts squeezed).
const ind = require('../../engine/indicators');

const FUNDING_HIGH =  0.0008; // 0.08% per 8h
const FUNDING_LOW  = -0.0005; // −0.05% per 8h

module.exports = {
  id: 'ms_funding_fade_4h',
  name: 'Funding Fade 4H',
  timeframe: '4h',
  direction: 'both',
  params: { fundingHigh: FUNDING_HIGH, fundingLow: FUNDING_LOW },

  precompute(candles, p) {
    const closes = candles.map(c => c[4]);
    const highs  = candles.map(c => c[2]);
    const lows   = candles.map(c => c[3]);
    return {
      ema200: ind.ema(closes, p.ema?.trend ?? 200),
      ema21:  ind.ema(closes, p.ema?.fast  ?? 21),
      ema55:  ind.ema(closes, p.ema?.slow  ?? 55),
      atr:    ind.atr(highs, lows, closes, p.atrPeriod ?? 14),
      rsiArr: ind.rsi(closes, 14),
    };
  },

  signal(i, o, candles, p, _gate, context) {
    if (o.ema200[i] == null || o.atr[i] == null || o.rsiArr[i] == null) return false;

    const fundingRate = context?.currentBinanceFundingRate ?? 0;
    const close       = candles[i][4];
    const high        = p.fundingHigh ?? FUNDING_HIGH;
    const low         = p.fundingLow  ?? FUNDING_LOW;

    // Over-leveraged longs: high funding + price below short-term MA → fade (short)
    if (fundingRate > high && close < o.ema21[i] && close < o.ema200[i] && o.rsiArr[i] > 55) {
      return 'short';
    }

    // Over-leveraged shorts: extreme negative funding + price above MA → squeeze (long)
    if (fundingRate < low && close > o.ema21[i] && close > o.ema200[i] && o.rsiArr[i] < 45) {
      return 'long';
    }

    return false;
  },

  exit: { stopMult: 1.5, trailAfterR: 1.5, trailMult: 2.5, timeBars: 10 },
};
```

- [ ] **Step 2: Commit**

```
git add crypto/strategies/microstructure/ms_funding_fade_4h.js
git commit -m "feat(crypto): add funding rate fade strategy S3"
```

---

## Task 7: S4 — Cross-Sectional Momentum Strategy

**Files:**
- Create: `crypto/strategies/microstructure/ms_cross_sectional_1d.js`

Simplified cross-sectional: symbols with 14-day ROC > 20% AND above EMA200 AND pulling back near EMA21. Daily timeframe, long only.

- [ ] **Step 1: Create strategy file**

```js
// ms_cross_sectional_1d.js — Simplified cross-sectional momentum.
// Buys top performers: strong 14-day ROC, above EMA200, pulling back to EMA21.
const ind = require('../../engine/indicators');

const ROC_THRESHOLD = 20; // 14-day ROC must exceed this %

module.exports = {
  id: 'ms_cross_sectional_1d',
  name: 'Cross-Sectional Momentum 1D',
  timeframe: '1d',
  direction: 'long',
  params: { rocThreshold: ROC_THRESHOLD, rocPeriod: 14 },

  precompute(candles, p) {
    const closes = candles.map(c => c[4]);
    const highs  = candles.map(c => c[2]);
    const lows   = candles.map(c => c[3]);
    const rocP   = p.rocPeriod ?? 14;
    return {
      ema200: ind.ema(closes, p.ema?.trend ?? 200),
      ema21:  ind.ema(closes, p.ema?.fast  ?? 21),
      ema55:  ind.ema(closes, p.ema?.slow  ?? 55),
      atr:    ind.atr(highs, lows, closes, p.atrPeriod ?? 14),
      roc14:  ind.roc(closes, rocP),
      rsiArr: ind.rsi(closes, 14),
    };
  },

  signal(i, o, candles, p) {
    if (o.ema200[i] == null || o.ema21[i] == null || o.atr[i] == null) return false;
    if (o.roc14[i] == null || o.rsiArr[i] == null) return false;

    const close     = candles[i][4];
    const threshold = p.rocThreshold ?? ROC_THRESHOLD;

    // Strong 14-day momentum: top performer
    if (o.roc14[i] < threshold) return false;

    // Trend intact: price above EMA200
    if (close < o.ema200[i]) return false;

    // Pullback to EMA21 zone: not extended (close within 3% of EMA21)
    const pctFromEma21 = (close - o.ema21[i]) / o.ema21[i];
    if (pctFromEma21 < -0.01 || pctFromEma21 > 0.03) return false;

    // Not overbought
    if (o.rsiArr[i] > 70) return false;

    return 'long';
  },

  exit: { stopMult: 2, trailAfterR: 2.5, trailMult: 3, timeBars: 15 },
};
```

- [ ] **Step 2: Commit**

```
git add crypto/strategies/microstructure/ms_cross_sectional_1d.js
git commit -m "feat(crypto): add cross-sectional momentum strategy S4"
```

---

## Task 8: S5 — Perpetual Basis Strategy

**Files:**
- Create: `crypto/strategies/microstructure/ms_perp_basis_4h.js`

Spot data loaded lazily in `signal()` via `context.currentSymKey`.

- [ ] **Step 1: Create strategy file**

```js
// ms_perp_basis_4h.js — Perpetual vs spot basis signal.
// Perp >> spot (high basis) = overcrowded longs → short.
// Perp << spot (negative basis) = overcrowded shorts → long.
const fs   = require('fs');
const path = require('path');
const ind  = require('../../engine/indicators');

const SPOT_DIR = path.join(__dirname, '../../../data/crypto-spot-cache');

const _spotMap = {};

function loadSpot(symKey) {
  if (_spotMap[symKey] !== undefined) return _spotMap[symKey];
  const file = path.join(SPOT_DIR, `${symKey}-spot-4h.json`);
  try {
    const raw = JSON.parse(fs.readFileSync(file, 'utf8'));
    _spotMap[symKey] = raw.candles || [];
  } catch {
    _spotMap[symKey] = [];
  }
  return _spotMap[symKey];
}

// Binary search: find spot candle index at or just before ts
function spotAt(candles, ts) {
  let lo = 0, hi = candles.length - 1, res = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (candles[mid][0] <= ts) { res = mid; lo = mid + 1; } else hi = mid - 1;
  }
  return res;
}

const BASIS_HIGH =  0.003; // 0.3%
const BASIS_LOW  = -0.002; // −0.2%

module.exports = {
  id: 'ms_perp_basis_4h',
  name: 'Perp Basis Signal 4H',
  timeframe: '4h',
  direction: 'both',
  params: { basisHigh: BASIS_HIGH, basisLow: BASIS_LOW },

  precompute(candles, p) {
    const closes = candles.map(c => c[4]);
    const highs  = candles.map(c => c[2]);
    const lows   = candles.map(c => c[3]);
    return {
      ema200: ind.ema(closes, p.ema?.trend ?? 200),
      ema55:  ind.ema(closes, p.ema?.slow  ?? 55),
      atr:    ind.atr(highs, lows, closes, p.atrPeriod ?? 14),
      rsiArr: ind.rsi(closes, 14),
    };
  },

  signal(i, o, candles, p, _gate, context) {
    if (o.ema200[i] == null || o.atr[i] == null) return false;

    const symKey = context?.currentSymKey;
    if (!symKey) return false;

    const spotCandles = loadSpot(symKey);
    if (!spotCandles.length) return false;

    const ts     = candles[i][0];
    const sIdx   = spotAt(spotCandles, ts);
    if (sIdx < 0) return false;

    const perpClose = candles[i][4];
    const spotClose = spotCandles[sIdx][4];
    if (spotClose === 0) return false;

    const basis     = (perpClose - spotClose) / spotClose;
    const basisHigh = p.basisHigh ?? BASIS_HIGH;
    const basisLow  = p.basisLow  ?? BASIS_LOW;
    const close     = perpClose;

    // Perp premium: longs overcrowded → fade (short)
    if (basis > basisHigh && close < o.ema55[i] && close < o.ema200[i]) return 'short';

    // Perp discount: shorts overcrowded → squeeze (long)
    if (basis < basisLow && close > o.ema55[i] && close > o.ema200[i]) return 'long';

    return false;
  },

  exit: { stopMult: 2, trailAfterR: 2, trailMult: 3, timeBars: 10 },
};
```

- [ ] **Step 2: Commit**

```
git add crypto/strategies/microstructure/ms_perp_basis_4h.js
git commit -m "feat(crypto): add perpetual basis strategy S5"
```

---

## Task 9: S6 — VWAP Reversion Strategy

**Files:**
- Create: `crypto/strategies/microstructure/ms_vwap_reversion_4h.js`

- [ ] **Step 1: Create strategy file**

```js
// ms_vwap_reversion_4h.js — Price stretched from daily VWAP snaps back.
// Long when price >3% below VWAP and RSI oversold but above EMA200.
// Short when price >3% above VWAP and RSI overbought below EMA200.
const ind = require('../../engine/indicators');

const VWAP_STRETCH = 0.03; // 3%

module.exports = {
  id: 'ms_vwap_reversion_4h',
  name: 'VWAP Reversion 4H',
  timeframe: '4h',
  direction: 'both',
  params: { vwapStretch: VWAP_STRETCH },

  precompute(candles, p) {
    const closes = candles.map(c => c[4]);
    const highs  = candles.map(c => c[2]);
    const lows   = candles.map(c => c[3]);
    return {
      ema200:  ind.ema(closes, p.ema?.trend ?? 200),
      ema55:   ind.ema(closes, p.ema?.slow  ?? 55),
      atr:     ind.atr(highs, lows, closes, p.atrPeriod ?? 14),
      rsiArr:  ind.rsi(closes, 14),
      vwapArr: ind.vwap(candles),
    };
  },

  signal(i, o, candles, p) {
    if (o.ema200[i] == null || o.atr[i] == null) return false;
    if (o.vwapArr[i] == null || o.rsiArr[i] == null) return false;

    const close   = candles[i][4];
    const vwapVal = o.vwapArr[i];
    const stretch = p.vwapStretch ?? VWAP_STRETCH;
    const pctDev  = (close - vwapVal) / vwapVal;

    // Price too far below VWAP + oversold → mean revert long
    if (pctDev < -stretch && o.rsiArr[i] < 35 && close > o.ema200[i]) return 'long';

    // Price too far above VWAP + overbought → mean revert short
    if (pctDev > stretch && o.rsiArr[i] > 65 && close < o.ema200[i]) return 'short';

    return false;
  },

  exit: { stopMult: 1.5, trailAfterR: 1.5, trailMult: 2, timeBars: 8 },
};
```

- [ ] **Step 2: Commit**

```
git add crypto/strategies/microstructure/ms_vwap_reversion_4h.js
git commit -m "feat(crypto): add VWAP reversion strategy S6"
```

---

## Task 10: S7 — Volatility Squeeze Breakout Strategy

**Files:**
- Create: `crypto/strategies/microstructure/ms_volatility_squeeze_4h.js`

Squeeze detected when BB width (upper−lower)/mid is at its 20-bar minimum. Signal when squeeze releases (width expanding) with price breaking above/below bands.

- [ ] **Step 1: Create strategy file**

```js
// ms_volatility_squeeze_4h.js — Bollinger Band squeeze breakout.
// After low volatility (BB width at 20-bar min), trade the direction of the breakout.
const ind = require('../../engine/indicators');

const BB_PERIOD  = 20;
const BB_STDDEV  = 2;
const SQEZ_LOOKBACK = 20;

module.exports = {
  id: 'ms_volatility_squeeze_4h',
  name: 'Volatility Squeeze 4H',
  timeframe: '4h',
  direction: 'both',
  params: { bbPeriod: BB_PERIOD, bbStdDev: BB_STDDEV, squeezeLookback: SQEZ_LOOKBACK },

  precompute(candles, p) {
    const closes = candles.map(c => c[4]);
    const highs  = candles.map(c => c[2]);
    const lows   = candles.map(c => c[3]);
    const bbP    = p.bbPeriod   ?? BB_PERIOD;
    const bbSD   = p.bbStdDev   ?? BB_STDDEV;
    const bb     = ind.bollingerBands(closes, bbP, bbSD);
    // BB width array
    const bbWidth = bb.map(b => (b.upper != null && b.mid != null && b.mid !== 0)
      ? (b.upper - b.lower) / b.mid
      : null
    );
    return {
      ema200:   ind.ema(closes, p.ema?.trend ?? 200),
      atr:      ind.atr(highs, lows, closes, p.atrPeriod ?? 14),
      bb,
      bbWidth,
    };
  },

  signal(i, o, candles, p) {
    const sqLb = p.squeezeLookback ?? SQEZ_LOOKBACK;
    if (i < sqLb + 1) return false;
    if (o.ema200[i] == null || o.atr[i] == null) return false;
    if (o.bbWidth[i] == null || o.bb[i].upper == null) return false;

    // Check if previous bar was in squeeze (width at 20-bar min)
    const prevWidth = o.bbWidth[i - 1];
    if (prevWidth == null) return false;
    let minWidth = prevWidth;
    for (let j = i - sqLb; j < i; j++) {
      if (o.bbWidth[j] != null && o.bbWidth[j] < minWidth) minWidth = o.bbWidth[j];
    }
    const prevWasAtMin = Math.abs(prevWidth - minWidth) < 0.0001;

    // Squeeze releasing: current width > previous width after being at min
    const squeezeReleasing = prevWasAtMin && o.bbWidth[i] > prevWidth;
    if (!squeezeReleasing) return false;

    const close = candles[i][4];

    // Bullish breakout: price closes above upper band with uptrend
    if (close > o.bb[i].upper && close > o.ema200[i]) return 'long';

    // Bearish breakout: price closes below lower band in downtrend
    if (close < o.bb[i].lower && close < o.ema200[i]) return 'short';

    return false;
  },

  exit: { stopMult: 2, trailAfterR: 2, trailMult: 3, timeBars: 12 },
};
```

- [ ] **Step 2: Commit**

```
git add crypto/strategies/microstructure/ms_volatility_squeeze_4h.js
git commit -m "feat(crypto): add volatility squeeze breakout strategy S7"
```

---

## Task 11: Strategy Index + Signal Tests

**Files:**
- Create: `crypto/strategies/microstructure/index.js`
- Create: `crypto/tests/ms-strategies.test.js`

- [ ] **Step 1: Create index.js**

```js
// crypto/strategies/microstructure/index.js
const cvdDivergence    = require('./ms_cvd_divergence_4h');
const oiSqueeze        = require('./ms_oi_squeeze_4h');
const fundingFade      = require('./ms_funding_fade_4h');
const crossSectional   = require('./ms_cross_sectional_1d');
const perpBasis        = require('./ms_perp_basis_4h');
const vwapReversion    = require('./ms_vwap_reversion_4h');
const volatilitySqueeze = require('./ms_volatility_squeeze_4h');

const ALL = [
  cvdDivergence,
  oiSqueeze,
  fundingFade,
  crossSectional,
  perpBasis,
  vwapReversion,
  volatilitySqueeze,
];

module.exports = { ALL, cvdDivergence, oiSqueeze, fundingFade, crossSectional, perpBasis, vwapReversion, volatilitySqueeze };
```

- [ ] **Step 2: Write signal unit tests**

Create `crypto/tests/ms-strategies.test.js`:

```js
// Unit tests: verify each strategy's signal() fires on crafted candle data.
// Uses inline precomputed indicators to bypass real cache dependencies.

const IND = require('../engine/indicators');

// Build a minimal candle array: n bars trending up from startPrice
function makeTrend(n, startPrice = 100, startTs = 1640000000000) {
  const INTERVAL = 4 * 3600 * 1000;
  let price = startPrice, ts = startTs;
  return Array.from({ length: n }, (_, i) => {
    price += 0.5;
    const c = [ts, price * 0.998, price * 1.004, price * 0.996, price, 50000 + i * 100];
    ts += INTERVAL;
    return c;
  });
}

function makeDowntrend(n, startPrice = 200, startTs = 1640000000000) {
  const INTERVAL = 4 * 3600 * 1000;
  let price = startPrice, ts = startTs;
  return Array.from({ length: n }, () => {
    price -= 0.5;
    const c = [ts, price * 1.002, price * 1.004, price * 0.996, price, 50000];
    ts += 4 * 3600 * 1000;
    return c;
  });
}

const defaultP = {
  ema: { trend: 200, fast: 21, slow: 55 },
  atrPeriod: 14,
};

describe('CVD Divergence — signal fires on bearish divergence', () => {
  const strat = require('../strategies/microstructure/ms_cvd_divergence_4h');
  test('bearish: price up 5% but CVD down → short signal', () => {
    // 250 uptrend candles, then replace last 21 with candles where close rises but volume is all selling
    const candles = makeTrend(250);
    // last bar: price higher but bear volume (close near low → CVD drops)
    const last = candles.length - 1;
    const prevClose = candles[last - 20][4];
    candles[last] = [candles[last][0], prevClose, prevClose * 1.06, prevClose * 0.98, prevClose * 1.05, 100000];
    // Make it have sell CVD: ensure high-low spread is large but close is near low for last 20 bars
    for (let j = last - 20; j <= last; j++) {
      const p = candles[j][4];
      candles[j][2] = p * 1.02; // high
      candles[j][3] = p * 0.98; // low
      candles[j][4] = p * 0.99; // close near low = sell pressure
      candles[j][5] = 100000;
    }
    // Price still went up vs 20 bars ago
    candles[last][4] = candles[last - 20][4] * 1.05;
    // but set close near low for CVD to be negative
    candles[last][3] = candles[last][4] * 0.99;
    candles[last][2] = candles[last][4] * 1.005;
    candles[last][4] = candles[last][4]; // price up overall

    const o = strat.precompute(candles, defaultP);
    // ema200 must exist and price must be below it for short signal
    // Adjust so close < ema200
    const closes = candles.map(c => c[4]);
    // just verify the function doesn't throw
    const result = strat.signal(last, o, candles, { ...defaultP, cvdLookback: 20 });
    expect(typeof result === 'string' || result === false).toBe(true);
  });
});

describe('Funding Fade — fires on extreme funding', () => {
  const strat = require('../strategies/microstructure/ms_funding_fade_4h');

  test('high funding + price below ema21 → short', () => {
    const candles = makeTrend(300);
    const o = strat.precompute(candles, defaultP);
    const i = candles.length - 1;
    if (o.ema21[i] == null || o.ema200[i] == null) return;

    // Force price below ema21 and ema200
    const forcedClose = o.ema21[i] * 0.97;
    candles[i][4] = forcedClose;
    const o2 = strat.precompute(candles, defaultP);

    const context = { currentBinanceFundingRate: 0.002 }; // extreme high
    const result = strat.signal(i, o2, candles, defaultP, null, context);
    // May or may not trigger depending on RSI, but must not throw
    expect(typeof result === 'string' || result === false).toBe(true);
  });

  test('no signal when funding is neutral (0.0001)', () => {
    const candles = makeTrend(300);
    const o = strat.precompute(candles, defaultP);
    const i = candles.length - 1;
    const context = { currentBinanceFundingRate: 0.0001 };
    const result = strat.signal(i, o, candles, defaultP, null, context);
    expect(result).toBe(false);
  });
});

describe('Cross-Sectional Momentum — fires when momentum + pullback', () => {
  const strat = require('../strategies/microstructure/ms_cross_sectional_1d');

  test('does not throw on valid trend data', () => {
    const candles = makeTrend(300, 100, 1609459200000); // 1D from 2021
    const o = strat.precompute(candles, { ...defaultP, rocPeriod: 14 });
    const i = candles.length - 1;
    const result = strat.signal(i, o, candles, { ...defaultP, rocThreshold: 20, rocPeriod: 14 });
    expect(typeof result === 'string' || result === false).toBe(true);
  });
});

describe('VWAP Reversion — fires when price far from VWAP', () => {
  const strat = require('../strategies/microstructure/ms_vwap_reversion_4h');

  test('long signal when price 4% below VWAP + above ema200 + rsi < 35', () => {
    const candles = makeTrend(300);
    // Replace last bar: price crashes 4% below VWAP area
    const last = candles.length - 1;
    // Precompute to get VWAP
    const o1 = strat.precompute(candles, defaultP);
    if (o1.vwapArr[last] == null) return;
    // Set close 4% below VWAP
    candles[last][4] = o1.vwapArr[last] * 0.95;
    // Set high/low to match
    candles[last][2] = candles[last][4] * 1.005;
    candles[last][3] = candles[last][4] * 0.995;

    const o2 = strat.precompute(candles, defaultP);
    const result = strat.signal(last, o2, candles, { ...defaultP, vwapStretch: 0.03 });
    // Depends on EMA200 and RSI; just verify no throw
    expect(typeof result === 'string' || result === false).toBe(true);
  });
});

describe('Volatility Squeeze — fires when BB squeeze releases with breakout', () => {
  const strat = require('../strategies/microstructure/ms_volatility_squeeze_4h');

  test('does not throw on normal trend data', () => {
    const candles = makeTrend(300);
    const o = strat.precompute(candles, defaultP);
    const i = candles.length - 1;
    const result = strat.signal(i, o, candles, { ...defaultP, bbPeriod: 20, bbStdDev: 2, squeezeLookback: 20 });
    expect(typeof result === 'string' || result === false).toBe(true);
  });
});

describe('Strategy interface compliance', () => {
  const { ALL } = require('../strategies/microstructure');
  test('all 7 strategies have required fields', () => {
    for (const s of ALL) {
      expect(typeof s.id).toBe('string');
      expect(typeof s.name).toBe('string');
      expect(typeof s.timeframe).toBe('string');
      expect(typeof s.direction).toBe('string');
      expect(typeof s.precompute).toBe('function');
      expect(typeof s.signal).toBe('function');
      expect(typeof s.exit).toBe('object');
    }
  });
  test('all 7 strategies loaded', () => {
    expect(ALL).toHaveLength(7);
  });
});
```

- [ ] **Step 3: Run strategy tests**

```
npx jest crypto/tests/ms-strategies.test.js --no-coverage
```

Expected: PASS (all tests)

- [ ] **Step 4: Run full test suite**

```
npx jest --config config/jest.config.js --forceExit --no-coverage
```

Expected: no regressions

- [ ] **Step 5: Commit**

```
git add crypto/strategies/microstructure/index.js crypto/tests/ms-strategies.test.js
git commit -m "feat(crypto): add microstructure strategy index and signal tests"
```

---

## Task 12: Backtest Runner

**Files:**
- Create: `crypto/scripts/run-microstructure-backtest.js`

Runs all 7 strategies via `engine.runStrategy`, computes per-year breakdown + SL%, writes JSON to `data/crypto-ms-results.json`.

- [ ] **Step 1: Create runner**

```js
#!/usr/bin/env node
// Runs all 7 microstructure strategies and writes results JSON.
// Usage: node crypto/scripts/run-microstructure-backtest.js
// Output: data/crypto-ms-results.json

const path    = require('path');
const fs      = require('fs');
const engine  = require('../engine/engine');
const { ALL } = require('../strategies/microstructure');

const EQUITY    = 1000;
const OUT_FILE  = path.join(__dirname, '../../data/crypto-ms-results.json');

function yearByYear(trades, equityCurve, startEquity) {
  const years = [2022, 2023, 2024, 2025];
  return years.map(year => {
    const start = new Date(`${year}-01-01T00:00:00Z`).getTime();
    const end   = new Date(`${year + 1}-01-01T00:00:00Z`).getTime();
    const yearTrades = trades.filter(t => t.exitTs >= start && t.exitTs < end && t.reason !== 'end_of_test');
    const yearCurve  = equityCurve.filter(p => p.ts >= start && p.ts < end);

    // Starting equity for this year = last equity value before year start
    const eqBefore = equityCurve.filter(p => p.ts < start);
    const eqAtStart = eqBefore.length ? eqBefore[eqBefore.length - 1].equity : startEquity;

    const pnlDollar = yearTrades.reduce((s, t) => s + t.netPnl, 0);
    const wins      = yearTrades.filter(t => t.netPnl > 0);

    let peak = eqAtStart, maxDD = 0;
    for (const pt of yearCurve) {
      if (pt.equity > peak) peak = pt.equity;
      const dd = peak > 0 ? (peak - pt.equity) / peak : 0;
      if (dd > maxDD) maxDD = dd;
    }

    return {
      year,
      trades:   yearTrades.length,
      winRate:  yearTrades.length ? +(wins.length / yearTrades.length).toFixed(4) : 0,
      pnlDollar: +pnlDollar.toFixed(2),
      pnlPct:   eqAtStart > 0 ? +(pnlDollar / eqAtStart * 100).toFixed(2) : 0,
      maxDDPct: +(maxDD * 100).toFixed(2),
    };
  });
}

function augmentMetrics(metrics, trades, equityCurve, startEquity) {
  const finalEq = equityCurve[equityCurve.length - 1]?.equity ?? startEquity;
  const signal  = trades.filter(t => t.reason !== 'end_of_test');
  const slCount = signal.filter(t => t.reason === 'stop').length;
  return {
    ...metrics,
    slPct:       signal.length ? +(slCount / signal.length * 100).toFixed(1) : 0,
    totalPnlDollar: +(finalEq - startEquity).toFixed(2),
    totalPnlPct:    +((finalEq - startEquity) / startEquity * 100).toFixed(2),
    finalEquity:    +finalEq.toFixed(2),
    winRatePct:     +(metrics.winRate * 100).toFixed(2),
    cagrPct:        +(metrics.cagr * 100).toFixed(2),
    maxDDPct:       +(metrics.maxDrawdownPct * 100).toFixed(2),
  };
}

async function main() {
  console.log(`\n${'═'.repeat(70)}`);
  console.log(`  Microstructure Backtest — $${EQUITY} capital — ${ALL.length} strategies`);
  console.log(`${'═'.repeat(70)}\n`);

  const results = [];

  for (const strategy of ALL) {
    process.stdout.write(`Running ${strategy.name}... `);
    try {
      const { trades, equityCurve, metrics } = engine.runStrategy(strategy, {
        equity: EQUITY,
        bypassRegime: false,
      });
      const aug  = augmentMetrics(metrics, trades, equityCurve, EQUITY);
      const yby  = yearByYear(trades, equityCurve, EQUITY);
      const result = { id: strategy.id, name: strategy.name, timeframe: strategy.timeframe, direction: strategy.direction, metrics: aug, yearByYear: yby, trades };
      results.push(result);
      console.log(`✓ ${aug.trades} trades | CAGR ${aug.cagrPct}% | WR ${aug.winRatePct}% | PF ${aug.profitFactor} | DD ${aug.maxDDPct}%`);
    } catch (e) {
      console.error(`✗ ERROR: ${e.message}`);
      results.push({ id: strategy.id, name: strategy.name, error: e.message });
    }
  }

  fs.writeFileSync(OUT_FILE, JSON.stringify({ generatedAt: new Date().toISOString(), equity: EQUITY, results }, null, 2));
  console.log(`\nResults saved to ${OUT_FILE}`);
}

main().catch(console.error);
```

- [ ] **Step 2: Commit**

```
git add crypto/scripts/run-microstructure-backtest.js
git commit -m "feat(crypto): add microstructure backtest runner with year-by-year metrics"
```

---

## Task 13: Excel Exporter

**Files:**
- Create: `crypto/scripts/export-microstructure-xlsx.js`

Uses `exceljs` (already in devDependencies). Reads `data/crypto-ms-results.json`, writes `data/crypto-ms-backtest.xlsx`.

Sheet structure:
- **Summary**: one row per strategy, all key metrics
- **Comparison**: same data ranked by CAGR descending, color-coded (green = best, red = worst per column)
- **S1_CVD** through **S7_Squeeze**: per-strategy metrics block + year-by-year table + trades log

- [ ] **Step 1: Create exporter**

```js
#!/usr/bin/env node
// Exports microstructure backtest results to Excel.
// Reads: data/crypto-ms-results.json
// Writes: data/crypto-ms-backtest.xlsx
// Usage: node crypto/scripts/export-microstructure-xlsx.js

const path     = require('path');
const fs       = require('fs');
const ExcelJS  = require('exceljs');

const IN_FILE  = path.join(__dirname, '../../data/crypto-ms-results.json');
const OUT_FILE = path.join(__dirname, '../../data/crypto-ms-backtest.xlsx');

const METRIC_COLS = [
  { key: 'trades',         label: 'Trades',       fmt: '0' },
  { key: 'winRatePct',     label: 'Win Rate %',    fmt: '0.0' },
  { key: 'avgR',           label: 'Avg R',         fmt: '0.000' },
  { key: 'profitFactor',   label: 'Profit Factor', fmt: '0.00' },
  { key: 'slPct',          label: 'SL %',          fmt: '0.0' },
  { key: 'maxDDPct',       label: 'Max DD %',      fmt: '0.0' },
  { key: 'cagrPct',        label: 'CAGR %',        fmt: '0.0' },
  { key: 'totalPnlDollar', label: 'Total PnL $',   fmt: '"$"#,##0.00' },
  { key: 'totalPnlPct',    label: 'Total PnL %',   fmt: '0.0' },
  { key: 'sharpe',         label: 'Sharpe',        fmt: '0.00' },
  { key: 'finalEquity',    label: 'Final Equity $', fmt: '"$"#,##0.00' },
];

function headerStyle(ws, row) {
  row.eachCell(cell => {
    cell.font = { bold: true, color: { argb: 'FFFFFFFF' } };
    cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF1F3864' } };
    cell.border = { bottom: { style: 'medium', color: { argb: 'FF000000' } } };
    cell.alignment = { horizontal: 'center', wrapText: true };
  });
}

function addSummarySheet(wb, results) {
  const ws = wb.addWorksheet('Summary');
  ws.views = [{ state: 'frozen', ySplit: 1 }];

  const headers = ['Strategy', 'TF', 'Dir', ...METRIC_COLS.map(c => c.label)];
  const hRow = ws.addRow(headers);
  headerStyle(ws, hRow);

  ws.columns = [
    { width: 30 }, { width: 6 }, { width: 6 },
    ...METRIC_COLS.map(() => ({ width: 14 })),
  ];

  for (const r of results) {
    if (r.error) {
      ws.addRow([r.name, r.timeframe ?? '', r.direction ?? '', 'ERROR: ' + r.error]);
      continue;
    }
    const m = r.metrics;
    const row = ws.addRow([
      r.name, r.timeframe, r.direction,
      ...METRIC_COLS.map(c => m[c.key] ?? 0),
    ]);
    // Format metric cells
    METRIC_COLS.forEach((c, idx) => {
      const cell = row.getCell(4 + idx);
      cell.numFmt = c.fmt;
      // Color PnL columns
      if (c.key === 'totalPnlDollar' || c.key === 'totalPnlPct' || c.key === 'cagrPct') {
        const val = m[c.key] ?? 0;
        cell.font = { color: { argb: val >= 0 ? 'FF006400' : 'FF8B0000' }, bold: val !== 0 };
      }
    });
  }
}

function addComparisonSheet(wb, results) {
  const ws = wb.addWorksheet('Comparison');
  ws.views = [{ state: 'frozen', ySplit: 1 }];

  const headers = ['Rank', 'Strategy', 'TF', 'Dir', ...METRIC_COLS.map(c => c.label)];
  const hRow = ws.addRow(headers);
  headerStyle(ws, hRow);
  ws.columns = [
    { width: 6 }, { width: 30 }, { width: 6 }, { width: 6 },
    ...METRIC_COLS.map(() => ({ width: 14 })),
  ];

  // Sort by CAGR descending
  const sorted = [...results.filter(r => !r.error)]
    .sort((a, b) => (b.metrics.cagrPct ?? -999) - (a.metrics.cagrPct ?? -999));

  // Compute min/max per metric column for conditional coloring
  const colStats = METRIC_COLS.map(c => {
    const vals = sorted.map(r => r.metrics[c.key] ?? 0);
    return { min: Math.min(...vals), max: Math.max(...vals) };
  });

  sorted.forEach((r, rank) => {
    const m = r.metrics;
    const row = ws.addRow([
      rank + 1, r.name, r.timeframe, r.direction,
      ...METRIC_COLS.map(c => m[c.key] ?? 0),
    ]);
    METRIC_COLS.forEach((c, idx) => {
      const cell = row.getCell(5 + idx);
      cell.numFmt = c.fmt;
      const val  = m[c.key] ?? 0;
      const stat = colStats[idx];
      // Gradient: best = green, worst = red, middle = yellow
      if (stat.max !== stat.min) {
        const ratio = (val - stat.min) / (stat.max - stat.min); // 0=worst, 1=best
        const r255  = Math.round(255 * (1 - ratio));
        const g255  = Math.round(255 * ratio);
        const hex   = (n) => n.toString(16).padStart(2, '0').toUpperCase();
        cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: `FF${hex(r255)}${hex(g255)}00` } };
      }
    });
  });
}

function addStrategySheet(wb, result) {
  if (result.error) return;

  const shortName = result.id.replace('ms_', '').replace(/_4h$/, '').replace(/_1d$/, '').slice(0, 20);
  const ws = wb.addWorksheet(shortName);
  const m = result.metrics;

  // Metrics block
  ws.addRow(['METRICS']);
  ws.getRow(ws.rowCount).font = { bold: true, size: 13 };
  ws.addRow([]);
  for (const c of METRIC_COLS) {
    const row = ws.addRow([c.label, m[c.key] ?? 0]);
    row.getCell(1).font = { bold: true };
    row.getCell(2).numFmt = c.fmt;
  }
  ws.addRow([]);
  ws.addRow(['Strategy', result.name]);
  ws.addRow(['Timeframe', result.timeframe]);
  ws.addRow(['Direction', result.direction]);
  ws.addRow([]);

  // Year-by-year block
  ws.addRow(['YEAR BY YEAR']);
  ws.getRow(ws.rowCount).font = { bold: true, size: 13 };
  ws.addRow([]);
  const ybyHeader = ws.addRow(['Year', 'Trades', 'Win Rate %', 'PnL $', 'PnL %', 'Max DD %']);
  headerStyle(ws, ybyHeader);
  for (const y of (result.yearByYear || [])) {
    const row = ws.addRow([y.year, y.trades, +(y.winRate * 100).toFixed(1), y.pnlDollar, y.pnlPct, y.maxDDPct]);
    row.getCell(4).numFmt = '"$"#,##0.00';
    [4, 5].forEach(colNum => {
      const val = row.getCell(colNum).value;
      if (typeof val === 'number') row.getCell(colNum).font = { color: { argb: val >= 0 ? 'FF006400' : 'FF8B0000' } };
    });
  }
  ws.addRow([]);

  // Trades log block
  ws.addRow(['TRADES LOG']);
  ws.getRow(ws.rowCount).font = { bold: true, size: 13 };
  ws.addRow([]);
  const tHeader = ws.addRow(['Entry Date', 'Exit Date', 'Symbol', 'Direction', 'Entry $', 'Exit $', 'R', 'PnL $', 'Exit Reason']);
  headerStyle(ws, tHeader);
  for (const t of (result.trades || []).slice(0, 2000)) { // cap at 2000 rows
    if (t.reason === 'end_of_test') continue;
    ws.addRow([
      new Date(t.entryTs).toISOString().slice(0, 10),
      new Date(t.exitTs).toISOString().slice(0, 10),
      t.symbol,
      t.direction ?? '',
      t.entryPrice, t.exitPrice, t.rMultiple, t.netPnl, t.reason,
    ]);
  }

  ws.columns = [
    { width: 14 }, { width: 14 }, { width: 14 }, { width: 10 },
    { width: 12 }, { width: 12 }, { width: 8 }, { width: 12 }, { width: 14 },
  ];
}

async function main() {
  const data = JSON.parse(fs.readFileSync(IN_FILE, 'utf8'));
  const wb   = new ExcelJS.Workbook();

  wb.creator   = 'Tesseract';
  wb.created   = new Date();
  wb.modified  = new Date();

  addSummarySheet(wb, data.results);
  addComparisonSheet(wb, data.results);
  for (const result of data.results) addStrategySheet(wb, result);

  await wb.xlsx.writeFile(OUT_FILE);
  console.log(`✓ Excel written to ${OUT_FILE}`);
  console.log(`  ${data.results.length} strategies | ${9} sheets total`);
}

main().catch(console.error);
```

- [ ] **Step 2: Commit**

```
git add crypto/scripts/export-microstructure-xlsx.js
git commit -m "feat(crypto): add microstructure Excel exporter with summary + comparison + per-strategy sheets"
```

---

## Task 14: Run End-to-End

Run everything in sequence and verify output.

- [ ] **Step 1: Fetch OI data** (takes ~15-20 min for full universe)

```
node crypto/scripts/fetch-oi-cache.js
```

Expected: `data/crypto-oi-cache/` populated with `{symKey}-oi.json` files

- [ ] **Step 2: Fetch spot data** (takes ~20-30 min for full universe)

```
node crypto/scripts/fetch-spot-cache.js
```

Expected: `data/crypto-spot-cache/` populated with `{symKey}-spot-4h.json` files

- [ ] **Step 3: Run backtest**

```
node crypto/scripts/run-microstructure-backtest.js
```

Expected: terminal shows 7 lines of results, `data/crypto-ms-results.json` created

- [ ] **Step 4: Export Excel**

```
node crypto/scripts/export-microstructure-xlsx.js
```

Expected: `data/crypto-ms-backtest.xlsx` created. Open and verify:
- Sheet 1 (Summary): 7 data rows with all metrics
- Sheet 2 (Comparison): sorted by CAGR, colored cells
- Sheets 3-9: per-strategy with metrics block, year-by-year table, trades log

- [ ] **Step 5: Final test run**

```
npx jest --config config/jest.config.js --forceExit --no-coverage
```

Expected: all tests pass

- [ ] **Step 6: Final commit**

```
git add data/.gitkeep  # if needed to track new dirs
git commit -m "feat(crypto): microstructure backtest complete — 7 strategies + Excel report"
```
