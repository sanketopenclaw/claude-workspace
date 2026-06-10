# Crypto Microstructure Strategy Backtest — Design Spec

**Date:** 2026-06-10  
**Project:** Tesseract — Crypto Module  
**Capital:** $1,000  
**Scope:** 7 new strategy plugins + Excel comparison report

---

## 1. Goals

Backtest 7 new crypto strategies based on market microstructure and momentum edges not yet tested in the existing 50-strategy suite. Output a rich Excel workbook for comparison and decision-making on which to add to production scanner.

---

## 2. The 7 Strategies

### S1: CVD Divergence
**Hypothesis:** When price makes a higher high but cumulative volume delta (buy vol minus sell vol) makes a lower high, the move is fake — reversal incoming.

**Signal (long):** Price makes 20-bar high, CVD does NOT make 20-bar high (divergence). Enter long on reversal candle close above prior bar.  
**Signal (short):** Inverse.  
**CVD approximation:** `buyVol = volume × (close - low) / (high - low)`. CVD = running sum of (buyVol - sellVol).  
**Timeframe:** 4H  

---

### S2: OI Squeeze
**Hypothesis:** Open interest rising while price falls = trapped longs. When OI spikes >15% in 4 bars but price is flat/down, short. When OI spikes and price is up, confirms breakout — long.

**Data needed:** Binance `/futures/data/openInterestHist?symbol=BTCUSDT&period=4h&limit=500`  
**Signal:** OI 4-bar change > 15% AND price 4-bar change < 1% → short. OI 4-bar change > 15% AND price 4-bar change > 3% → long.  
**Timeframe:** 4H  

---

### S3: Funding Rate Fade
**Hypothesis:** When perpetual funding rate is extreme (>0.1%), market is over-leveraged long. Fade the crowd.

**Data:** Already fetched in engine (Binance + Bybit combined).  
**Signal (short):** Funding > 0.08% AND price below EMA21. Entry at next bar open.  
**Signal (long):** Funding < -0.05% AND price above EMA21.  
**Timeframe:** 4H  

---

### S4: Cross-Sectional Momentum (Simplified)
**Hypothesis:** Top performers keep outperforming. Simplified: symbols with 14-day ROC > 20% AND price above EMA200 are in "momentum regime" — enter on any pullback to EMA21.

**Signal:** ROC(14) > 20% AND close > EMA200 AND close < EMA21 × 1.02 (near EMA, not extended).  
**Timeframe:** 1D  
**Note:** True cross-sectional ranking requires multi-symbol pass — simplified to absolute threshold filter as proxy.

---

### S5: Perpetual Basis Signal
**Hypothesis:** When perp trades at unusual premium/discount vs spot, it signals crowding. Large positive basis (perp >> spot) = overcrowded longs = fade.

**Data needed:** Binance spot OHLCV for same symbols (separate cache, endpoint: `GET /api/v3/klines`).  
**Basis:** `(perpClose - spotClose) / spotClose × 100`  
**Signal (short):** Basis > 0.3% AND below EMA55.  
**Signal (long):** Basis < -0.2% AND above EMA55.  
**Timeframe:** 4H  

---

### S6: VWAP Deviation Reversion
**Hypothesis:** Price stretched >3% from daily VWAP snaps back. Mean reversion play.

**VWAP:** Compute per day from intraday bars: `VWAP = Σ(typical_price × volume) / Σ(volume)` where typical = (H+L+C)/3. Reset each UTC day.  
**Signal (long):** Close < VWAP × 0.97 AND RSI(14) < 40 AND close > EMA200.  
**Signal (short):** Close > VWAP × 1.03 AND RSI(14) > 60 AND close < EMA200.  
**Timeframe:** 4H (VWAP computed on 4H bars, reset daily)  

---

### S7: Volatility Squeeze Breakout
**Hypothesis:** After prolonged low volatility (Bollinger Bands narrow), a big move is imminent. Trade the breakout direction.

**Squeeze detection:** BB width = (upper - lower) / middle. Squeeze = BB width < 20-bar lowest width.  
**Signal (long):** Squeeze just ended (width now > prior bar width after 3+ bars of squeeze) AND close > BB upper AND close > EMA200.  
**Signal (short):** Squeeze ends AND close < BB lower AND close < EMA200.  
**Timeframe:** 4H  

---

## 3. Data Architecture

### Existing (no changes needed)
- OHLCV cache: `data/crypto-cache/*.json` — 1D and 4H candles
- Funding cache: combined Binance + Bybit in engine

### New fetchers required
| Fetcher | File | Binance Endpoint |
|---|---|---|
| OI history | `crypto/scripts/fetch-oi-cache.js` | `/futures/data/openInterestHist` |
| Spot OHLCV | `crypto/scripts/fetch-spot-cache.js` | `/api/v3/klines` (spot, no :USDT suffix) |

Both fetch same symbol universe as perp cache. Store in:
- `data/crypto-oi-cache/` — one file per symbol, 4H OI bars
- `data/crypto-spot-cache/` — one file per symbol, 4H spot candles

---

## 4. New Indicators (additions to `engine/indicators.js`)

```
cvd(candles)           → running CVD array
bollingerBands(closes, period, stdDev) → { upper, middle, lower, width }
bbWidth(closes, period, stdDev)        → width array
vwap(candles, resetDaily)              → VWAP array (4H bars, UTC day reset)
rsi(closes, period)                    → RSI array
oiChange(oiSeries, lookback)           → % change array
basis(perpCloses, spotCloses)          → basis % array
```

---

## 5. Strategy Plugin Interface

Each strategy in `crypto/strategies/microstructure/`:

```js
module.exports = {
  id: 'ms_cvd_divergence_4h',
  name: 'CVD Divergence 4H',
  timeframe: '4h',
  direction: 'both',      // 'long' | 'short' | 'both'
  requiresOI: false,      // true for S2
  requiresSpot: false,    // true for S5
  params: {},
  precompute(candles, p, aux) { ... },  // aux = { oiData, spotData, fundingData }
  signal(i, o, candles, p) { ... },    // returns 'long' | 'short' | null
  exit: { stopMult: 2, trailAfterR: 2, trailMult: 3, timeBars: 10 },
};
```

---

## 6. Backtest Runner

File: `crypto/scripts/run-microstructure-backtest.js`

1. Load all 7 strategy plugins
2. For each strategy: load required data (OHLCV + OI if needed + spot if needed + funding)
3. Run `backtest.runStrategy(strategy, symbols, params)` — existing engine, $1000 equity
4. Collect results object per strategy
5. Compute year-by-year breakdown (2022/2023/2024/2025)
6. Pass all results to Excel generator

---

## 7. Excel Report

File: `crypto/scripts/export-microstructure-xlsx.js`  
Library: `exceljs` (install as dev dep)

### Sheet structure

| Sheet | Content |
|---|---|
| `Summary` | All 7 strategies × all metrics, one row per strategy |
| `Comparison` | Same data ranked by CAGR, conditional formatting (green best → red worst per column) |
| `S1_CVD` through `S7_Squeeze` | Per-strategy: metrics block + year-by-year table + full trades log |

### Metrics captured per strategy
- Trades (total)
- Win Rate %
- Avg R
- Profit Factor
- SL% (trades stopped out / total)
- Max Drawdown %
- CAGR %
- Total PnL $
- Total PnL %
- Sharpe Ratio
- Final Equity ($1000 start)

### Year-by-year (per strategy sheet)
Columns: Year | Trades | Win Rate | PnL $ | PnL % | Max DD %  
Rows: 2022, 2023, 2024, 2025

### Trades log (per strategy sheet)
Columns: Date | Symbol | Direction | Entry $ | Exit $ | R | PnL $ | Exit Reason (SL/Trail/Time)

---

## 8. File Map

```
tesseract-scan/
  crypto/
    strategies/
      microstructure/
        ms_cvd_divergence_4h.js
        ms_oi_squeeze_4h.js
        ms_funding_fade_4h.js
        ms_cross_sectional_1d.js
        ms_perp_basis_4h.js
        ms_vwap_reversion_4h.js
        ms_volatility_squeeze_4h.js
        index.js
    scripts/
      fetch-oi-cache.js         (new)
      fetch-spot-cache.js       (new)
      run-microstructure-backtest.js  (new)
      export-microstructure-xlsx.js   (new)
    engine/
      indicators.js             (extend: cvd, bb, vwap, rsi, oiChange, basis)
  data/
    crypto-oi-cache/            (new dir)
    crypto-spot-cache/          (new dir)
```

---

## 9. Success Criteria

- All 7 strategies backtest without errors on full symbol universe
- Excel file opens cleanly with 9 sheets (Summary + Comparison + 7 strategy sheets)
- Year-by-year data present for each strategy
- CAGR, SL%, DD correctly computed
- Comparison sheet color-coded

---

## 10. Out of Scope

- Live trading integration (research phase only)
- Index options or BTC.D-based strategies
- Walk-forward testing (separate phase if a strategy shows edge)
- Hyperparameter optimization (separate sweep script if results warrant)
