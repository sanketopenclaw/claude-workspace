# Trading MCP Integrations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bolt TV Screener pre-filtering and Firecrawl news enrichment onto the existing NSE scanner with zero changes to existing behavior on failure.

**Architecture:** Two new modules (`tvScreenerFilter.js`, `firecrawlNews.js`) called from existing entry points in `dashboard/server.js` and `nse/engine/ai-features.js`. Both are try/catch wrapped — failure returns null and callers fall back to existing behavior unchanged.

**Tech Stack:** Node.js (no new npm deps), Jest 29, TV Screener REST API (unauthenticated), Firecrawl REST API (`FIRECRAWL_API_KEY` env var).

---

## File Map

| File | Status | Change |
|------|--------|--------|
| `nse/engine/tvScreenerFilter.js` | Create | TV Screener REST call, returns symbol array or null |
| `nse/engine/firecrawlNews.js` | Create | Firecrawl search call, returns headline array or null |
| `nse/engine/multi-scanner.js` | Modify | Accept `symbolOverride` in options, filter symbols if provided |
| `nse/engine/ai-features.js` | Modify | Merge Firecrawl headlines into `enrichSignals` news array |
| `dashboard/server.js` | Modify | Call `tvScreenerFilter` before line-58 `runScan`; wire `firecrawlNews` module |
| `nse/tests/tvScreenerFilter.test.js` | Create | Unit tests for filter |
| `nse/tests/firecrawlNews.test.js` | Create | Unit tests for news fetcher |

Tests run from `tesseract-scan/` root with `npm test`.

---

## Task 1: `tvScreenerFilter.js` — TV Screener pre-filter module

**Files:**
- Create: `nse/engine/tvScreenerFilter.js`
- Create: `nse/tests/tvScreenerFilter.test.js`

- [ ] **Step 1: Write the failing test**

Create `nse/tests/tvScreenerFilter.test.js`:

```javascript
'use strict';
const https = require('https');

jest.mock('https');

const { tvScreenerFilter } = require('../engine/tvScreenerFilter');

describe('tvScreenerFilter', () => {
  afterEach(() => jest.clearAllMocks());

  test('returns stripped symbol array on success', async () => {
    const mockRes = {
      on: jest.fn((event, cb) => {
        if (event === 'data') cb(JSON.stringify({ data: [
          { s: 'NSE:DIXON', d: [] },
          { s: 'NSE:KPITTECH', d: [] },
        ]}));
        if (event === 'end') cb();
        return mockRes;
      }),
      statusCode: 200,
    };
    const mockReq = { on: jest.fn().mockReturnThis(), setTimeout: jest.fn().mockReturnThis(), write: jest.fn(), end: jest.fn() };
    https.request.mockImplementation((_, cb) => { cb(mockRes); return mockReq; });

    const result = await tvScreenerFilter();
    expect(result).toEqual(['DIXON', 'KPITTECH']);
  });

  test('returns null on network error', async () => {
    const mockReq = {
      on: jest.fn((event, cb) => { if (event === 'error') cb(new Error('network')); return mockReq; }),
      setTimeout: jest.fn().mockReturnThis(),
      write: jest.fn(),
      end: jest.fn(),
    };
    https.request.mockReturnValue(mockReq);

    const result = await tvScreenerFilter();
    expect(result).toBeNull();
  });

  test('returns null when response data is empty', async () => {
    const mockRes = {
      on: jest.fn((event, cb) => {
        if (event === 'data') cb(JSON.stringify({ data: [] }));
        if (event === 'end') cb();
        return mockRes;
      }),
    };
    const mockReq = { on: jest.fn().mockReturnThis(), setTimeout: jest.fn().mockReturnThis(), write: jest.fn(), end: jest.fn() };
    https.request.mockImplementation((_, cb) => { cb(mockRes); return mockReq; });

    const result = await tvScreenerFilter();
    expect(result).toBeNull();
  });

  test('strips exchange prefix from symbol names', async () => {
    const mockRes = {
      on: jest.fn((event, cb) => {
        if (event === 'data') cb(JSON.stringify({ data: [{ s: 'BSE:RELIANCE', d: [] }] }));
        if (event === 'end') cb();
        return mockRes;
      }),
    };
    const mockReq = { on: jest.fn().mockReturnThis(), setTimeout: jest.fn().mockReturnThis(), write: jest.fn(), end: jest.fn() };
    https.request.mockImplementation((_, cb) => { cb(mockRes); return mockReq; });

    const result = await tvScreenerFilter();
    expect(result).toEqual(['RELIANCE']);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd C:/Claude/tesseract-scan
npm test -- --testPathPattern=tvScreenerFilter --forceExit
```

Expected: `FAIL` — `Cannot find module '../engine/tvScreenerFilter'`

- [ ] **Step 3: Create `nse/engine/tvScreenerFilter.js`**

```javascript
'use strict';
const https = require('https');

const TV_FILTER_PAYLOAD = {
  filter: [
    { left: 'close', operation: 'above', right: 'SMA200' },
    { left: 'relative_volume_10d_calc', operation: 'greater', right: 1.5 },
    { left: 'RSI', operation: 'in_range', right: [40, 75] },
  ],
  columns: ['name'],
  range: [0, 150],
  sort: { sortBy: 'relative_volume_10d_calc', sortOrder: 'desc' },
};

function postJSON(hostname, path, payload) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify(payload);
    const req = https.request(
      {
        hostname,
        path,
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(body),
        },
      },
      res => {
        let raw = '';
        res.on('data', c => (raw += c));
        res.on('end', () => resolve(raw));
      }
    );
    req.on('error', reject);
    req.setTimeout(10000, () => req.destroy(new Error('timeout')));
    req.write(body);
    req.end();
  });
}

async function tvScreenerFilter() {
  try {
    const raw = await postJSON('scanner.tradingview.com', '/india/scan', TV_FILTER_PAYLOAD);
    const parsed = JSON.parse(raw);
    if (!parsed.data || !Array.isArray(parsed.data) || parsed.data.length === 0) return null;
    return parsed.data.map(item => item.s.replace(/^[A-Z]+:/, ''));
  } catch (e) {
    console.warn('[TV_SCREENER] Filter failed:', e.message);
    return null;
  }
}

module.exports = { tvScreenerFilter };
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd C:/Claude/tesseract-scan
npm test -- --testPathPattern=tvScreenerFilter --forceExit
```

Expected: `PASS nse/tests/tvScreenerFilter.test.js` (4 tests)

- [ ] **Step 5: Commit**

```bash
git add nse/engine/tvScreenerFilter.js nse/tests/tvScreenerFilter.test.js
git commit -m "feat: add TV Screener pre-filter module"
```

---

## Task 2: Wire `tvScreenerFilter` into the daily scan

**Files:**
- Modify: `nse/engine/multi-scanner.js` (line 669)
- Modify: `dashboard/server.js` (line 58)

- [ ] **Step 1: Add `symbolOverride` to `multi-scanner.js:runScan` options**

In `nse/engine/multi-scanner.js`, find line 670:
```javascript
  const { livePriceOverrides = null, isPreview = false } = options;
```
Replace with:
```javascript
  const { livePriceOverrides = null, isPreview = false, symbolOverride = null } = options;
```

Then find lines 674–680 (the symbol loading block):
```javascript
  let symbols;
  try {
    symbols = JSON.parse(fs.readFileSync(N500_FP, 'utf8'));
  } catch {
    onProgress(0, 'ERROR: nifty500-approx.json not found. Run seed script first.');
    throw new Error('N500 symbol list missing');
  }
  onProgress(5, `${symbols.length} symbols loaded. Computing RS rankings...`);
```
Replace with:
```javascript
  let symbols;
  try {
    symbols = JSON.parse(fs.readFileSync(N500_FP, 'utf8'));
  } catch {
    onProgress(0, 'ERROR: nifty500-approx.json not found. Run seed script first.');
    throw new Error('N500 symbol list missing');
  }
  if (symbolOverride && symbolOverride.length > 0) {
    const overrideSet = new Set(symbolOverride);
    symbols = symbols.filter(s => overrideSet.has(s));
    onProgress(4, `TV Screener pre-filtered: ${symbols.length}/${symbolOverride.length} symbols`);
  }
  onProgress(5, `${symbols.length} symbols loaded. Computing RS rankings...`);
```

- [ ] **Step 2: Wire `tvScreenerFilter` into `dashboard/server.js` daily scan only**

At the top of `dashboard/server.js`, after the existing `require` block (around line 19):
```javascript
const { tvScreenerFilter } = require('../nse/engine/tvScreenerFilter');
```

Find the daily scan at line 56–60:
```javascript
    // 2. Run the multi-strategy scan
    console.log('[AUTO-SCAN] Running strategy scan...');
    const result = await runScan((pct, msg) => {
      if (pct % 20 === 0) console.log(`[AUTO-SCAN] ${pct}% — ${msg}`);
    });
```
Replace with:
```javascript
    // 2. Run the multi-strategy scan (TV Screener pre-filter applied if available)
    console.log('[AUTO-SCAN] Running strategy scan...');
    const tvSymbols = await tvScreenerFilter().catch(() => null);
    if (tvSymbols) console.log(`[AUTO-SCAN] TV Screener pre-filter: ${tvSymbols.length} symbols`);
    const result = await runScan((pct, msg) => {
      if (pct % 20 === 0) console.log(`[AUTO-SCAN] ${pct}% — ${msg}`);
    }, { symbolOverride: tvSymbols });
```

Note: preview scan at line 263 is intentionally NOT modified — it needs full N500 for live price injection.

- [ ] **Step 3: Verify server still starts**

```bash
cd C:/Claude/tesseract-scan
node -e "require('./dashboard/server')" 2>&1 | head -5
```

Expected: No `SyntaxError` or `Cannot find module` errors.

- [ ] **Step 4: Run full test suite**

```bash
cd C:/Claude/tesseract-scan
npm test -- --forceExit
```

Expected: All existing tests still pass. Count should be same as before (≥417).

- [ ] **Step 5: Commit**

```bash
git add nse/engine/multi-scanner.js dashboard/server.js
git commit -m "feat: wire TV Screener pre-filter into daily scan"
```

---

## Task 3: `firecrawlNews.js` — Firecrawl news enrichment module

**Files:**
- Create: `nse/engine/firecrawlNews.js`
- Create: `nse/tests/firecrawlNews.test.js`

- [ ] **Step 1: Write the failing test**

Create `nse/tests/firecrawlNews.test.js`:

```javascript
'use strict';
const https = require('https');

jest.mock('https');

describe('fetchFirecrawlNews', () => {
  const OLD_ENV = process.env;

  beforeEach(() => {
    jest.resetModules();
    process.env = { ...OLD_ENV, FIRECRAWL_API_KEY: 'test-key' };
  });

  afterEach(() => {
    process.env = OLD_ENV;
    jest.clearAllMocks();
  });

  function mockHttps(responseBody) {
    const mockRes = {
      on: jest.fn((event, cb) => {
        if (event === 'data') cb(responseBody);
        if (event === 'end') cb();
        return mockRes;
      }),
    };
    const mockReq = {
      on: jest.fn().mockReturnThis(),
      setTimeout: jest.fn().mockReturnThis(),
      write: jest.fn(),
      end: jest.fn(),
    };
    https.request.mockImplementation((_, cb) => { cb(mockRes); return mockReq; });
  }

  test('returns title array on success', async () => {
    const { fetchFirecrawlNews } = require('../engine/firecrawlNews');
    mockHttps(JSON.stringify({
      success: true,
      data: [
        { title: 'Dixon Q4 earnings beat', description: 'Revenue up 40%' },
        { title: 'Dixon wins Apple contract', description: '' },
      ],
    }));

    const result = await fetchFirecrawlNews('DIXON');
    expect(result).toEqual(['Dixon Q4 earnings beat', 'Dixon wins Apple contract']);
  });

  test('returns null when FIRECRAWL_API_KEY not set', async () => {
    delete process.env.FIRECRAWL_API_KEY;
    const { fetchFirecrawlNews } = require('../engine/firecrawlNews');

    const result = await fetchFirecrawlNews('DIXON');
    expect(result).toBeNull();
    expect(https.request).not.toHaveBeenCalled();
  });

  test('returns null on network error', async () => {
    const { fetchFirecrawlNews } = require('../engine/firecrawlNews');
    const mockReq = {
      on: jest.fn((event, cb) => { if (event === 'error') cb(new Error('ECONNREFUSED')); return mockReq; }),
      setTimeout: jest.fn().mockReturnThis(),
      write: jest.fn(),
      end: jest.fn(),
    };
    https.request.mockReturnValue(mockReq);

    const result = await fetchFirecrawlNews('DIXON');
    expect(result).toBeNull();
  });

  test('returns null when API returns success:false', async () => {
    const { fetchFirecrawlNews } = require('../engine/firecrawlNews');
    mockHttps(JSON.stringify({ success: false, error: 'Rate limit exceeded' }));

    const result = await fetchFirecrawlNews('DIXON');
    expect(result).toBeNull();
  });

  test('falls back to description when title missing', async () => {
    const { fetchFirecrawlNews } = require('../engine/firecrawlNews');
    mockHttps(JSON.stringify({
      success: true,
      data: [{ title: '', description: 'Dixon files patent for EMS tech' }],
    }));

    const result = await fetchFirecrawlNews('DIXON');
    expect(result).toEqual(['Dixon files patent for EMS tech']);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd C:/Claude/tesseract-scan
npm test -- --testPathPattern=firecrawlNews --forceExit
```

Expected: `FAIL` — `Cannot find module '../engine/firecrawlNews'`

- [ ] **Step 3: Create `nse/engine/firecrawlNews.js`**

```javascript
'use strict';
const https = require('https');

async function fetchFirecrawlNews(symbol, count = 3) {
  const apiKey = process.env.FIRECRAWL_API_KEY;
  if (!apiKey) return null;

  const body = JSON.stringify({
    query: `"${symbol}" NSE stock news India`,
    limit: count,
  });

  return new Promise(resolve => {
    const req = https.request(
      {
        hostname: 'api.firecrawl.dev',
        path: '/v1/search',
        method: 'POST',
        headers: {
          Authorization: `Bearer ${apiKey}`,
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(body),
        },
      },
      res => {
        let raw = '';
        res.on('data', c => (raw += c));
        res.on('end', () => {
          try {
            const parsed = JSON.parse(raw);
            if (!parsed.success || !Array.isArray(parsed.data)) return resolve(null);
            const titles = parsed.data
              .map(item => item.title || item.description)
              .filter(Boolean);
            resolve(titles.length ? titles : null);
          } catch {
            resolve(null);
          }
        });
      }
    );
    req.on('error', () => resolve(null));
    req.setTimeout(8000, () => { req.destroy(); resolve(null); });
    req.write(body);
    req.end();
  });
}

module.exports = { fetchFirecrawlNews };
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd C:/Claude/tesseract-scan
npm test -- --testPathPattern=firecrawlNews --forceExit
```

Expected: `PASS nse/tests/firecrawlNews.test.js` (5 tests)

- [ ] **Step 5: Commit**

```bash
git add nse/engine/firecrawlNews.js nse/tests/firecrawlNews.test.js
git commit -m "feat: add Firecrawl news enrichment module"
```

---

## Task 4: Wire Firecrawl news into `enrichSignals`

**Files:**
- Modify: `nse/engine/ai-features.js` (lines 297–320)

- [ ] **Step 1: Add Firecrawl import and merge headlines in `enrichSignals`**

In `nse/engine/ai-features.js`, find line 298 inside `enrichSignals`:
```javascript
  const { fetchNewsHeadlines } = require('./news-fetcher');
```
Add after it:
```javascript
  const { fetchFirecrawlNews } = require('./firecrawlNews');
```

Find line 307:
```javascript
      const headlines = await fetchNewsHeadlines(stock.symbol, 5);
```
Replace with:
```javascript
      const [googleResult, firecrawlResult] = await Promise.allSettled([
        fetchNewsHeadlines(stock.symbol, 5),
        fetchFirecrawlNews(stock.symbol, 3),
      ]);
      const headlines = [
        ...(googleResult.status === 'fulfilled' ? googleResult.value || [] : []),
        ...(firecrawlResult.status === 'fulfilled' ? firecrawlResult.value || [] : []),
      ];
```

- [ ] **Step 2: Run full test suite**

```bash
cd C:/Claude/tesseract-scan
npm test -- --forceExit
```

Expected: All tests pass (count same or higher). No regressions.

- [ ] **Step 3: Verify `enrichSignals` module requires no other change**

The `headlines` array is already passed to `scorePickConviction(stock, headlines, regimeLabel)` at line 308 (now 311 after the addition). The function accepts an array of strings — no interface change needed.

- [ ] **Step 4: Add `FIRECRAWL_API_KEY` to `.env`**

Open `C:/Claude/tesseract-scan/.env` and append:
```
# Firecrawl — optional; news enrichment degrades to Google News if not set
FIRECRAWL_API_KEY=
```

Fill in the API key value (found in Firecrawl dashboard).

- [ ] **Step 5: Commit**

```bash
git add nse/engine/ai-features.js .env
git commit -m "feat: merge Firecrawl headlines into conviction scorer enrichSignals"
```

---

## Verification

After all 4 tasks:

```bash
cd C:/Claude/tesseract-scan
npm test -- --forceExit
```

Expected output includes:
- `PASS nse/tests/tvScreenerFilter.test.js`
- `PASS nse/tests/firecrawlNews.test.js`
- All pre-existing tests still passing
- Zero test regressions
