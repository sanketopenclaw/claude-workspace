# Crypto Scan AI Ask Box Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-signal AI text box to the crypto scan page so the user can ask ad-hoc questions (re-entry timing, risk, etc.) about any scan pick.

**Architecture:** New `POST /api/crypto/ai/ask` route in `api.js` receives `{ symbol, question }`, loads the pick from `crypto-scan.json`, builds a prompt with full trade context, and calls `callAI`. `ScanFeedItem` in `crypto.jsx` gains 4 state vars + `handleAsk` + a text input rendered inside the existing `aiOpen` panel.

**Tech Stack:** Node.js (Express router), React (Babel/browser, no build-time types), existing `callAI` from `shared/ai.js`, `readJSON` from `shared/data.js`

---

### Task 1: Backend — add `POST /api/crypto/ai/ask` endpoint

**Files:**
- Modify: `tesseract-scan/dashboard/api.js` — insert after line 2561 (after `router.get('/crypto/ai/coach'` block)

- [ ] **Step 1: Add the route**

Open `tesseract-scan/dashboard/api.js`. After line 2561 (the closing `});` of `router.get('/crypto/ai/coach'`), insert:

```js
// ── Crypto AI: ad-hoc ask ─────────────────────────────────────────────────────
router.post('/crypto/ai/ask', async (req, res) => {
  try {
    const { symbol, question } = req.body || {};
    if (!symbol || !question) return res.status(400).json({ error: 'symbol and question required' });

    const sym  = symbol.toUpperCase();
    const q    = String(question).slice(0, 300);
    const scan = readJSON('crypto-scan.json', null);
    const pick = scan?.picks?.find(p => p.symbol === sym);
    if (!pick) return res.status(404).json({ error: `${sym} not in current scan` });

    const { callAI } = require('../shared/ai');
    const stopPct    = pick.entryHigh ? ((pick.entryHigh - pick.stop) / pick.entryHigh * 100).toFixed(1) : '?';
    const tgtPct     = pick.entryHigh ? ((pick.target2R - pick.entryHigh) / pick.entryHigh * 100).toFixed(1) : '?';
    const funding8h  = ((pick.funding || 0) * 100).toFixed(4);

    const sys  = 'You are a crypto futures trading assistant. Answer in 2-4 sentences. Be direct, specific, and actionable. No preamble.';
    const user = `Trade context:
Symbol: ${sym} | Strategy: ${pick.strategyName} | Timeframe: ${pick.tf || '4h'}
Entry: ${pick.entryHigh} | Stop: ${pick.stop} (-${stopPct}%) | 2R Target: ${pick.target2R} (+${tgtPct}%)
ATR: ${pick.atr} | Funding 8h: ${funding8h}% | ADX: ${pick.adx || 0} | ROC30: ${(pick.roc30 || 0).toFixed(1)}%
Regime: ${scan.regime || 'unknown'} | Leverage: ${pick.leverage || '?'}x | Risk: $${pick.riskUsd || '?'}

User question: ${q}`;

    const answer = await callAI(sys, user, { maxTokens: 300 });
    res.json({ symbol: sym, answer });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});
```

- [ ] **Step 2: Smoke-test the endpoint**

With the server running on port 3000, run in a separate terminal:

```bash
curl -s -X POST http://localhost:3000/api/crypto/ai/ask \
  -H "Content-Type: application/json" \
  -d "{}" | node -e "process.stdin.resume();process.stdin.on('data',d=>console.log(d.toString()))"
```

Expected: `{"error":"symbol and question required"}`

```bash
curl -s -X POST http://localhost:3000/api/crypto/ai/ask \
  -H "Content-Type: application/json" \
  -d "{\"symbol\":\"FAKECOIN\",\"question\":\"re-entry?\"}" | node -e "process.stdin.resume();process.stdin.on('data',d=>console.log(d.toString()))"
```

Expected: `{"error":"FAKECOIN not in current scan"}`

- [ ] **Step 3: Commit**

```bash
git -C C:/Claude/tesseract-scan add dashboard/api.js
git -C C:/Claude/tesseract-scan commit -m "feat: add POST /api/crypto/ai/ask endpoint"
```

---

### Task 2: Frontend — add state and handleAsk to ScanFeedItem

**Files:**
- Modify: `tesseract-scan/dashboard/public/crypto.jsx` lines 792–829

- [ ] **Step 1: Add 4 new state vars after existing state on line 801**

Find this block (lines 797–801):

```js
  const [aiOpen,    setAiOpen]    = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiThesis,  setAiThesis]  = useState(null);
  const [aiErr,     setAiErr]     = useState(null);
  const [copied,    setCopied]    = useState(null);
```

Replace with:

```js
  const [aiOpen,    setAiOpen]    = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiThesis,  setAiThesis]  = useState(null);
  const [aiErr,     setAiErr]     = useState(null);
  const [copied,    setCopied]    = useState(null);
  const [askQ,      setAskQ]      = useState('');
  const [askLoading,setAskLoading]= useState(false);
  const [askAnswer, setAskAnswer] = useState(null);
  const [askErr,    setAskErr]    = useState(null);
```

- [ ] **Step 2: Modify fetchThesis to reset ask state on panel close**

Find this block (lines 819–829):

```js
  const fetchThesis = async () => {
    if (aiThesis) { setAiOpen(v => !v); return; }
    setAiOpen(true); setAiLoading(true); setAiErr(null);
    try {
      const r = await fetch(`/api/crypto/ai/thesis/${pick.symbol}`);
      const d = await r.json();
      if (!r.ok) throw new Error(d.error);
      setAiThesis(d.thesis);
    } catch (e) { setAiErr(e.message); }
    finally { setAiLoading(false); }
  };
```

Replace with:

```js
  const fetchThesis = async () => {
    if (aiThesis) {
      setAiOpen(v => {
        if (v) { setAskQ(''); setAskAnswer(null); setAskErr(null); }
        return !v;
      });
      return;
    }
    setAiOpen(true); setAiLoading(true); setAiErr(null);
    try {
      const r = await fetch(`/api/crypto/ai/thesis/${pick.symbol}`);
      const d = await r.json();
      if (!r.ok) throw new Error(d.error);
      setAiThesis(d.thesis);
    } catch (e) { setAiErr(e.message); }
    finally { setAiLoading(false); }
  };

  const handleAsk = async () => {
    if (!askQ.trim() || askLoading) return;
    setAskLoading(true); setAskErr(null);
    try {
      const r = await fetch('/api/crypto/ai/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol: pick.symbol, question: askQ.trim() }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.error);
      setAskAnswer(d.answer);
      setAskQ('');
    } catch (e) { setAskErr(e.message); }
    finally { setAskLoading(false); }
  };
```

- [ ] **Step 3: Commit**

```bash
git -C C:/Claude/tesseract-scan add dashboard/public/crypto.jsx
git -C C:/Claude/tesseract-scan commit -m "feat: add ask state + handleAsk to ScanFeedItem"
```

---

### Task 3: Frontend — render ask input + answer in AI panel

**Files:**
- Modify: `tesseract-scan/dashboard/public/crypto.jsx` lines 1020–1038

- [ ] **Step 1: Replace the AI thesis panel block**

Find this block (lines 1020–1038):

```js
      {/* AI thesis panel */}
      {aiOpen && (
        <div style={{ marginTop: 10, borderTop: '1px solid #9b7be822', paddingTop: 10 }}>
          <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.14em', color: '#9b7be8', fontFamily: 'var(--font-mono)', marginBottom: 6, textTransform: 'uppercase' }}>
            ⚡ AI THESIS
          </div>
          {aiLoading && (
            <div style={{ fontSize: 10, color: 'var(--fg-3)', fontFamily: 'var(--font-mono)', fontStyle: 'italic' }}>Thinking…</div>
          )}
          {aiErr && (
            <div style={{ fontSize: 10, color: 'var(--bear)', fontFamily: 'var(--font-mono)' }}>{aiErr}</div>
          )}
          {aiThesis && (
            <div style={{ fontSize: 11, color: 'var(--fg-2)', lineHeight: 1.7, whiteSpace: 'pre-wrap', borderLeft: '2px solid #9b7be844', paddingLeft: 10 }}>
              {aiThesis}
            </div>
          )}
        </div>
      )}
```

Replace with:

```js
      {/* AI thesis + ask panel */}
      {aiOpen && (
        <div style={{ marginTop: 10, borderTop: '1px solid #9b7be822', paddingTop: 10 }}>
          <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.14em', color: '#9b7be8', fontFamily: 'var(--font-mono)', marginBottom: 6, textTransform: 'uppercase' }}>
            ⚡ AI THESIS
          </div>
          {aiLoading && (
            <div style={{ fontSize: 10, color: 'var(--fg-3)', fontFamily: 'var(--font-mono)', fontStyle: 'italic' }}>Thinking…</div>
          )}
          {aiErr && (
            <div style={{ fontSize: 10, color: 'var(--bear)', fontFamily: 'var(--font-mono)' }}>{aiErr}</div>
          )}
          {aiThesis && (
            <div style={{ fontSize: 11, color: 'var(--fg-2)', lineHeight: 1.7, whiteSpace: 'pre-wrap', borderLeft: '2px solid #9b7be844', paddingLeft: 10 }}>
              {aiThesis}
            </div>
          )}

          {/* Ask box */}
          <div style={{ marginTop: 10, display: 'flex', gap: 6, alignItems: 'center' }}>
            <input
              value={askQ}
              onChange={e => setAskQ(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleAsk(); } }}
              placeholder="Ask about re-entry, timing, risk…"
              disabled={askLoading}
              style={{
                flex: 1, fontSize: 10, fontFamily: 'var(--font-mono)',
                background: 'var(--bg-2)', border: '1px solid #9b7be844',
                borderRadius: 3, padding: '4px 8px', color: 'var(--fg-1)',
                outline: 'none', opacity: askLoading ? 0.5 : 1,
              }}
            />
            <button
              onClick={handleAsk}
              disabled={!askQ.trim() || askLoading}
              style={{
                fontSize: 11, padding: '4px 8px', borderRadius: 3, cursor: 'pointer',
                background: '#9b7be822', border: '1px solid #9b7be866', color: '#9b7be8',
                opacity: (!askQ.trim() || askLoading) ? 0.4 : 1,
              }}
            >▶</button>
          </div>
          {askLoading && (
            <div style={{ marginTop: 6, fontSize: 10, color: 'var(--fg-3)', fontFamily: 'var(--font-mono)', fontStyle: 'italic' }}>Thinking…</div>
          )}
          {askErr && (
            <div style={{ marginTop: 6, fontSize: 10, color: 'var(--bear)', fontFamily: 'var(--font-mono)' }}>{askErr}</div>
          )}
          {askAnswer && (
            <div style={{ marginTop: 6, fontSize: 11, color: 'var(--fg-2)', lineHeight: 1.7, whiteSpace: 'pre-wrap', borderLeft: '2px solid #9b7be844', paddingLeft: 10 }}>
              {askAnswer}
            </div>
          )}
        </div>
      )}
```

- [ ] **Step 2: Build the bundle**

```bash
node C:/Claude/tesseract-scan/dashboard/build.js
```

Expected output (last line): `✓ bundle.js — ...`

- [ ] **Step 3: Verify in browser**

1. Open the crypto scan page
2. Click **⚡ AI** on any signal row — thesis panel opens
3. Type `if I exited early what is the re-entry plan?` in the input, press Enter
4. Confirm "Thinking…" appears then an answer (2-4 sentences) replaces it
5. Ask a second question — confirm new answer replaces old
6. Click **⚡ AI** again to close — confirm panel collapses
7. Reopen — confirm input is blank and no answer shown

- [ ] **Step 4: Commit**

```bash
git -C C:/Claude/tesseract-scan add dashboard/public/crypto.jsx
git -C C:/Claude/tesseract-scan commit -m "feat: render AI ask input + answer in scan signal row"
```
