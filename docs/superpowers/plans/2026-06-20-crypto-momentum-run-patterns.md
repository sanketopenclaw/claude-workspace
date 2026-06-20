# Crypto Momentum Run Patterns — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Patterns tab (Flag/Pole, M Top, W Bottom) with a 15m Momentum Run scanner showing bull/bear candle run cards sorted by strength score.

**Architecture:** Delete 5 old detector functions + `/api/crypto/patterns` from api.js. Add `detectMomentumRun()` + `/api/crypto/momentum-runs` endpoint. Rewrite `CryptoPatternView` in crypto.jsx with `MiniSparkline` + `RunCard` sub-components. Rebuild bundle.

**Tech Stack:** Node.js/Express (api.js), React 18 via CDN (crypto.jsx JSX bundle via build.js), inline SVG (sparklines)

## Global Constraints

- All JSX in `dashboard/public/crypto.jsx` — single file, React loaded via CDN (no import statements)
- After any .jsx edit: run `node dashboard/build.js` to rebuild `dashboard/public/bundle.js`
- Pattern cache TTL: 15 minutes (`15 * 60 * 1000` ms)
- 15m candle files: `crypto/data/cache/*-15m.json` — array of `{ open, high, low, close, volume, time }` objects
- Binance futures links: `https://www.binance.com/en/futures/SYMBOL` where SYMBOL already includes USDT (e.g. `BTCUSDT`)
- Working directory for all commands: `C:\Claude\tesseract-scan`

---

### Task 1: Delete old pattern detection from api.js

**Files:**
- Modify: `dashboard/api.js`

**Interfaces:**
- Produces: `GET /api/crypto/patterns` no longer exists
- Produces: clean api.js without detectFlagPole, detectMTop, detectMTopForming, detectWBottom, detectWBottomForming, TF_CONFIG, pattern cache vars

- [ ] **Step 1: Find and delete pattern cache variables**

```bash
grep -n "patternCache\|patternTs\|patternsCache\|patternsTs\|_patternR" dashboard/api.js
```

Delete any `let _patternCache`, `let _patternTs`, or similar cache variables that belong to the old patterns endpoint.

- [ ] **Step 2: Delete detectFlagPole**

Find `function detectFlagPole(` in `dashboard/api.js` (~line 2926). Delete the entire function from its opening line to the closing `}`.

- [ ] **Step 3: Delete detectMTop**

Find `function detectMTop(` (~line 2992). Delete entirely.

- [ ] **Step 4: Delete detectWBottom**

Find `function detectWBottom(` (~line 3077). Delete entirely.

- [ ] **Step 5: Delete detectMTopForming**

Find `function detectMTopForming(` (~line 3163). Delete entirely.

- [ ] **Step 6: Delete detectWBottomForming**

Find `function detectWBottomForming(` (~line 3208). Delete entirely.

- [ ] **Step 7: Delete TF_CONFIG**

Find `const TF_CONFIG = {` (~line 3271). Delete the entire object literal.

- [ ] **Step 8: Delete /api/crypto/patterns route**

Find `app.get('/api/crypto/patterns'` (~line 3282). Delete the entire route handler block.

- [ ] **Step 9: Check and delete pattern-only helpers**

```bash
grep -n "atr14\|localPeaks\|localTroughs\|ema50Slope\|avgVol" dashboard/api.js
```

For each function found: if the only remaining callers are now-deleted functions, delete it too. If used elsewhere, keep it.

- [ ] **Step 10: Check for pattern tests**

```bash
grep -rn "crypto/patterns\|detectFlagPole\|detectMTop\|detectWBottom" . --include="*.test.js" --include="*.spec.js" -l
```

Delete any test files or describe/it blocks that exclusively test the removed functions/endpoint.

- [ ] **Step 11: Verify server parses cleanly**

```bash
node -e "try { require('./dashboard/api.js'); } catch(e) { console.error(e.message); }" 2>&1 | head -5
```

Expected: no output (or server starts and you Ctrl+C it). Zero syntax errors.

- [ ] **Step 12: Commit**

```bash
git add dashboard/api.js
git commit -m "chore: delete Flag/Pole M-Top W-Bottom pattern detection + /api/crypto/patterns endpoint"
```

---

### Task 2: Add detectMomentumRun + /api/crypto/momentum-runs endpoint

**Files:**
- Modify: `dashboard/api.js`

**Interfaces:**
- Produces: `function detectMomentumRun(candles)` → `{ direction, score, greenCount, redCount, totalBars, pctMove, volRatio } | null`
- Produces: `GET /api/crypto/momentum-runs?refresh=1` → `{ success, cached, scannedAt, results: RunResult[] }`

RunResult shape:
```js
{
  symbol: string,           // e.g. "BTCUSDT"
  direction: 'bull'|'bear',
  score: number,            // 0–100
  greenCount: number,
  redCount: number,
  totalBars: 15,
  pctMove: number,          // e.g. 3.8 (bull) or -2.1 (bear)
  volRatio: number,
  volUsd24h: number,
  currentPrice: number,
  candles: Array<{open,high,low,close}>,  // last 15 bars for sparkline
}
```

- [ ] **Step 1: Add cache variables**

Near existing cache variable declarations in `dashboard/api.js`, add:

```javascript
let _momentumRunsCache = null;
let _momentumRunsTs = 0;
const MOMENTUM_RUNS_TTL = 15 * 60 * 1000;
```

- [ ] **Step 2: Add detectMomentumRun function**

Add this function in `dashboard/api.js` where the old pattern detectors were:

```javascript
function detectMomentumRun(candles) {
  if (!candles || candles.length < 35) return null;

  const last15  = candles.slice(-15);
  const prior20 = candles.slice(-35, -15);

  const greenCount = last15.filter(c => c.close > c.open).length;
  const redCount   = last15.filter(c => c.close < c.open).length;

  const checkRun = (direction) => {
    const domCandles     = last15.filter(c => direction === 'bull' ? c.close > c.open : c.close < c.open);
    const counterCandles = last15.filter(c => direction === 'bull' ? c.close < c.open : c.close > c.open);
    if (domCandles.length < 8 || counterCandles.length > 2) return null;

    const avgDomBody = domCandles.reduce((s, c) => s + Math.abs(c.close - c.open), 0) / domCandles.length;
    if (counterCandles.length > 0) {
      const maxCounterBody = Math.max(...counterCandles.map(c => Math.abs(c.close - c.open)));
      if (maxCounterBody > avgDomBody * 0.4) return null;
    }

    const avgRunVol   = last15.reduce((s, c) => s + c.volume, 0) / last15.length;
    const avgPriorVol = prior20.reduce((s, c) => s + c.volume, 0) / prior20.length;
    const volRatio    = avgPriorVol > 0 ? avgRunVol / avgPriorVol : 1;
    if (volRatio < 1.5) return null;

    const pctMove = ((last15[14].close - last15[0].open) / last15[0].open) * 100;
    if (direction === 'bull' && pctMove < 1.5)  return null;
    if (direction === 'bear' && pctMove > -1.5) return null;

    const score = Math.round(
      (domCandles.length / 10) * 40 +
      Math.min(volRatio / 3, 1) * 30 +
      Math.min(Math.abs(pctMove) / 5, 1) * 30
    );

    return { direction, score, greenCount, redCount, totalBars: 15,
             pctMove: +pctMove.toFixed(2), volRatio: +volRatio.toFixed(2) };
  };

  if (greenCount >= 8 && redCount <= 2) return checkRun('bull');
  if (redCount >= 8 && greenCount <= 2) return checkRun('bear');
  return null;
}
```

- [ ] **Step 3: Verify fs and path are already imported**

```bash
grep -n "require('fs')\|require('path')" dashboard/api.js | head -4
```

Expected: both present. If either is missing, add at top of file:
```javascript
const fs   = require('fs');
const path = require('path');
```

- [ ] **Step 4: Add /api/crypto/momentum-runs endpoint**

Add in `dashboard/api.js` where the old `/api/crypto/patterns` route was:

```javascript
app.get('/api/crypto/momentum-runs', async (req, res) => {
  const refresh = req.query.refresh === '1';
  const now = Date.now();

  if (!refresh && _momentumRunsCache && (now - _momentumRunsTs) < MOMENTUM_RUNS_TTL) {
    return res.json({ success: true, cached: true, scannedAt: new Date(_momentumRunsTs).toISOString(), results: _momentumRunsCache });
  }

  try {
    const cacheDir = path.join(__dirname, '../crypto/data/cache');
    const files = fs.readdirSync(cacheDir).filter(f => f.endsWith('-15m.json'));
    const results = [];

    for (const file of files) {
      const symbol = file.replace('-15m.json', '');
      try {
        const candles = JSON.parse(fs.readFileSync(path.join(cacheDir, file), 'utf8'));
        const run = detectMomentumRun(candles);
        if (!run) continue;

        const last96    = candles.slice(-96);
        const volUsd24h = Math.round(last96.reduce((s, c) => s + (c.volume * c.close), 0));

        results.push({
          symbol,
          ...run,
          currentPrice: candles[candles.length - 1].close,
          volUsd24h,
          candles: candles.slice(-15).map(c => ({ open: c.open, high: c.high, low: c.low, close: c.close })),
        });
      } catch (_) { /* skip corrupt file */ }
    }

    results.sort((a, b) => b.score - a.score);
    _momentumRunsCache = results;
    _momentumRunsTs    = now;

    res.json({ success: true, cached: false, scannedAt: new Date(now).toISOString(), results });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});
```

- [ ] **Step 5: Restart server and test endpoint**

Restart the Tesseract server (via pm2 or however it's managed), then:

```bash
curl -s "http://localhost:3000/api/crypto/momentum-runs" | node -e "const d=require('fs').readFileSync(0,'utf8'); const j=JSON.parse(d); console.log('success:', j.success, 'count:', j.results && j.results.length, 'sample:', JSON.stringify(j.results && j.results[0]));"
```

Expected: `success: true count: <number>`. If count is 0 it may mean no 15m files have enough data — that's acceptable, just confirm no errors.

- [ ] **Step 6: Commit**

```bash
git add dashboard/api.js
git commit -m "feat: add detectMomentumRun + /api/crypto/momentum-runs endpoint (15m bull/bear run scanner)"
```

---

### Task 3: Delete old patterns UI from crypto.jsx

**Files:**
- Modify: `dashboard/public/crypto.jsx`

**Interfaces:**
- Produces: crypto.jsx without `CryptoPatternView` (old), `PatternBadge`, `PATTERN_META`
- Produces: `ConfBar` and `CompletionBar` retained only if used outside the deleted component

- [ ] **Step 1: Check ConfBar and CompletionBar usage**

```bash
grep -n "ConfBar\|CompletionBar" dashboard/public/crypto.jsx
```

Note all line numbers. If these names appear only inside the old `CryptoPatternView` block (lines ~4690–5032), they are safe to delete. If they appear elsewhere, keep them.

- [ ] **Step 2: Delete PATTERN_META constant**

Find `const PATTERN_META = {` in `dashboard/public/crypto.jsx` (~line 4627). Delete the entire const declaration (3–5 lines).

- [ ] **Step 3: Delete PatternBadge component**

Find `function PatternBadge(` and delete the entire component.

- [ ] **Step 4: Delete old CryptoPatternView component**

Find `function CryptoPatternView(` (~line 4690) and delete the entire component. It ends just before `function CryptoMomentumView(` (~line 5034). Delete everything between those two function definitions.

- [ ] **Step 5: Delete ConfBar and CompletionBar if pattern-only**

If Step 1 showed they're only inside the now-deleted block, also find and delete `function ConfBar(` and `function CompletionBar(`.

- [ ] **Step 6: Rebuild and verify no errors**

```bash
node dashboard/build.js 2>&1
```

Expected: exits cleanly, `bundle.js` timestamp updates. Zero errors.

- [ ] **Step 7: Commit**

```bash
git add dashboard/public/crypto.jsx dashboard/public/bundle.js
git commit -m "chore: delete old CryptoPatternView, PatternBadge, PATTERN_META from crypto.jsx"
```

---

### Task 4: Add MiniSparkline, RunCard, and new CryptoPatternView

**Files:**
- Modify: `dashboard/public/crypto.jsx`

**Interfaces:**
- Consumes: `GET /api/crypto/momentum-runs` — RunResult shape defined in Task 2
- Consumes: `r.candles` — `Array<{open,high,low,close}>`, 15 elements
- Produces: `function MiniSparkline({ candles })` — inline SVG bar chart
- Produces: `function RunCard({ r })` — single result card
- Produces: `function CryptoPatternView()` — main patterns tab (same name as deleted version, wired to existing tab routing)

- [ ] **Step 1: Ensure fmtVol exists at module scope**

```bash
grep -n "function fmtVol\|const fmtVol" dashboard/public/crypto.jsx
```

If not present at module scope (outside any component), add this near the top of the file after other utility functions:

```javascript
const fmtVol = v => {
  if (!v) return '—';
  if (v >= 1e9) return '$' + (v / 1e9).toFixed(1) + 'B';
  if (v >= 1e6) return '$' + (v / 1e6).toFixed(1) + 'M';
  if (v >= 1e3) return '$' + (v / 1e3).toFixed(0) + 'K';
  return '$' + v;
};
```

If `fmtVol` already exists at module scope, skip this step.

- [ ] **Step 2: Add MiniSparkline component**

Add in `dashboard/public/crypto.jsx` near where PatternBadge was (before CryptoPatternView):

```jsx
function MiniSparkline({ candles }) {
  if (!candles || candles.length === 0) return null;
  const W = 200, H = 36, barW = Math.max(1, Math.floor(W / candles.length) - 1);
  const maxBody = Math.max(...candles.map(c => Math.abs(c.close - c.open)), 1);
  return (
    <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ display: 'block' }}>
      {candles.map((c, i) => {
        const isGreen = c.close >= c.open;
        const bodyH   = Math.max(2, Math.round((Math.abs(c.close - c.open) / maxBody) * (H - 6)));
        const x = i * (barW + 1);
        const y = isGreen ? H - bodyH - 3 : 3;
        return <rect key={i} x={x} y={y} width={barW} height={bodyH} fill={isGreen ? '#00c853' : '#f44336'} opacity={0.85} rx={1} />;
      })}
    </svg>
  );
}
```

- [ ] **Step 3: Add RunCard component**

Add immediately after MiniSparkline:

```jsx
function RunCard({ r }) {
  const isBull = r.direction === 'bull';
  const color  = isBull ? '#00c853' : '#f44336';
  return (
    <div style={{
      border: `1px solid ${color}44`, borderRadius: 6,
      background: isBull ? '#00c85308' : '#f4433608',
      padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 8, position: 'relative',
    }}>
      {/* score bar */}
      <div style={{ position: 'absolute', top: 0, left: 0, height: 3, width: `${r.score}%`, background: color, borderRadius: '6px 0 0 0' }} />
      {/* header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginTop: 4 }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 16, color: 'var(--fg)' }}>
          {r.symbol.replace('USDT', '')}
        </span>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700, color,
          background: color + '22', border: `1px solid ${color}44`, borderRadius: 3, padding: '2px 7px' }}>
          {isBull ? '🟢 BULL RUN' : '🔴 BEAR RUN'}
        </span>
      </div>
      {/* price + pct */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 14, color: 'var(--fg-3)' }}>${r.currentPrice}</span>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 14, fontWeight: 700, color }}>
          {isBull ? '+' : ''}{r.pctMove}%
        </span>
      </div>
      {/* sparkline */}
      <MiniSparkline candles={r.candles} />
      {/* stats row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fg-4)' }}>
          {r.greenCount}G · {r.redCount}R · {fmtVol(r.volUsd24h)}
        </span>
        <a href={`https://www.binance.com/en/futures/${r.symbol}`}
          target="_blank" rel="noopener noreferrer"
          style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700, color: '#f0b90b',
            textDecoration: 'none', background: 'var(--bg-2)', border: '1px solid var(--line)',
            borderRadius: 3, padding: '3px 10px' }}>↗</a>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Add new CryptoPatternView component**

Add immediately after RunCard:

```jsx
function CryptoPatternView() {
  const [results, setResults]     = React.useState(null);
  const [loading, setLoading]     = React.useState(false);
  const [scannedAt, setScannedAt] = React.useState(null);
  const [filter, setFilter]       = React.useState('ALL');
  const [minVol, setMinVol]       = React.useState(0);
  const [countdown, setCountdown] = React.useState(15 * 60);

  const VOL_OPTIONS = [
    { label: 'All Vol', value: 0 },
    { label: '>$500K',  value: 500_000 },
    { label: '>$1M',    value: 1_000_000 },
    { label: '>$5M',    value: 5_000_000 },
    { label: '>$10M',   value: 10_000_000 },
  ];

  const runScan = React.useCallback((refresh = false) => {
    setLoading(true);
    fetch(`/api/crypto/momentum-runs${refresh ? '?refresh=1' : ''}`)
      .then(r => r.json())
      .then(d => {
        if (d.success) { setResults(d.results); setScannedAt(d.scannedAt); }
        setLoading(false);
        setCountdown(15 * 60);
      })
      .catch(() => setLoading(false));
  }, []);

  React.useEffect(() => { runScan(false); }, [runScan]);

  React.useEffect(() => {
    const iv = setInterval(() => {
      setCountdown(c => {
        if (c <= 1) { runScan(true); return 15 * 60; }
        return c - 1;
      });
    }, 1000);
    return () => clearInterval(iv);
  }, [runScan]);

  const fmtCD = s => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;

  const bullCount = (results || []).filter(r => r.direction === 'bull').length;
  const bearCount = (results || []).filter(r => r.direction === 'bear').length;

  const displayed = React.useMemo(() => (results || []).filter(r =>
    (filter === 'ALL' || r.direction === filter.toLowerCase()) &&
    (r.volUsd24h || 0) >= minVol
  ), [results, filter, minVol]);

  return (
    <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden', background: 'var(--bg)' }}>
      {/* controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 16px', flexShrink: 0, flexWrap: 'wrap', borderBottom: '1px solid var(--line)' }}>
        <button onClick={() => runScan(true)} disabled={loading} style={{
          fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700, letterSpacing: '0.1em',
          padding: '8px 18px', borderRadius: 4, cursor: loading ? 'default' : 'pointer',
          background: loading ? 'var(--bg-2)' : 'var(--gold)', color: loading ? 'var(--fg-4)' : '#0A0B0D',
          border: 'none', opacity: loading ? 0.6 : 1, flexShrink: 0,
        }}>{loading ? '◌ SCANNING…' : '▶ SCAN RUNS'}</button>

        {[['ALL', `ALL (${(results||[]).length})`], ['BULL', `🟢 BULL (${bullCount})`], ['BEAR', `🔴 BEAR (${bearCount})`]].map(([val, lbl]) => {
          const active = filter === val;
          const color  = val === 'BULL' ? '#00c853' : val === 'BEAR' ? '#f44336' : 'var(--gold)';
          return (
            <button key={val} onClick={() => setFilter(val)} style={{
              fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: active ? 700 : 500,
              padding: '6px 13px', borderRadius: 3, cursor: 'pointer',
              background: active ? color + '22' : 'var(--bg-2)',
              color: active ? color : 'var(--fg-4)',
              border: `1px solid ${active ? color + '66' : 'var(--line)'}`,
            }}>{lbl}</button>
          );
        })}

        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--fg-4)' }}>VOL≥</span>
          <select value={minVol} onChange={e => setMinVol(+e.target.value)} style={{
            background: 'var(--bg-2)', border: '1px solid var(--line)', color: minVol > 0 ? 'var(--gold)' : 'var(--fg-4)',
            fontFamily: 'var(--font-mono)', fontSize: 12, padding: '5px 8px', borderRadius: 3, cursor: 'pointer',
          }}>
            {VOL_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>

        <div style={{ marginLeft: 'auto', fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--fg-4)' }}>
          auto: {fmtCD(countdown)} ↻
          {scannedAt && <span style={{ marginLeft: 10 }}>cached {new Date(scannedAt).toLocaleTimeString()}</span>}
        </div>
      </div>

      {loading && !results && (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--fg-4)', fontFamily: 'var(--font-mono)', fontSize: 13 }}>
          Scanning 15m charts…
        </div>
      )}
      {!loading && results && displayed.length === 0 && (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--fg-4)' }}>No momentum runs found</div>
          <div style={{ fontSize: 11, color: '#444' }}>Try lowering the vol filter</div>
        </div>
      )}
      {!results && !loading && (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#333', fontFamily: 'var(--font-mono)', fontSize: 13 }}>
          Loading…
        </div>
      )}

      {results && displayed.length > 0 && (
        <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
            {displayed.map((r, i) => <RunCard key={i} r={r} />)}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Rebuild bundle**

```bash
node dashboard/build.js 2>&1
```

Expected: exits cleanly, no errors.

- [ ] **Step 6: Verify in browser**

Open `http://localhost:3000` → Crypto tab → Patterns tab. Verify all of:
- Controls bar: SCAN RUNS button, ALL/🟢BULL/🔴BEAR filter pills, VOL≥ dropdown, countdown timer
- Auto-scan fires immediately on load (loading spinner → cards appear)
- Cards: correct color borders (green=bull, red=bear), symbol name, price, pct, sparkline bars, G·R·Vol stats, ↗ Binance link
- Filter pills: clicking BULL shows only green cards, BEAR shows only red cards
- VOL≥ dropdown filters out low-vol results
- Manual SCAN RUNS button triggers new scan and resets countdown to 15:00
- Clicking ↗ opens correct Binance futures URL in new tab

- [ ] **Step 7: Commit**

```bash
git add dashboard/public/crypto.jsx dashboard/public/bundle.js
git commit -m "feat: add MiniSparkline + RunCard + new CryptoPatternView (15m momentum run scanner)"
```
