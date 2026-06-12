# Crypto AI Ask Box — Journal, Forward Test, Live Trades Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the per-pick AI ask box (already live on the Scan tab) to Journal, Forward Test (open + closed), and Live Trades tabs.

**Architecture:** New `POST /api/crypto/ai/ask-position` generic endpoint in `api.js` receives `{ context, question }` pre-built by the frontend. Each component gains 4 dict-keyed state vars (`askQ/askLoading/askAnswer/askErr`) and a `handleAsk` function. Forward Test also adds `askOpen` dict to track which open rows are expanded. UI is identical across all tabs: purple `#9b7be8` accent, mono font, `▶` submit button, Enter key support.

**Tech Stack:** Node.js (Express router), React (Babel/browser, no build step), `callAI` from `shared/ai.js`. File to rebuild after edits: `node C:/Claude/tesseract-scan/dashboard/build.js`.

---

## File Map

| File | Change |
|---|---|
| `tesseract-scan/dashboard/api.js` | Add `POST /crypto/ai/ask-position` after line 2594 |
| `tesseract-scan/dashboard/public/crypto.jsx` | 4 component changes (Journal, FwdTest state+closed, FwdTest open, LiveTrades) |
| `tesseract-scan/dashboard/public/bundle.js` | Rebuilt by `build.js` — not hand-edited |

---

### Task 1: Backend — add `POST /api/crypto/ai/ask-position` endpoint

**Files:**
- Modify: `tesseract-scan/dashboard/api.js` after line 2594

- [ ] **Step 1: Insert the route**

Open `tesseract-scan/dashboard/api.js`. Find the closing `});` of the existing `/crypto/ai/ask` route at line 2594. Insert the new route immediately after:

```js
// ── Crypto AI: generic position ask ──────────────────────────────────────────
router.post('/crypto/ai/ask-position', async (req, res) => {
  try {
    const { context, question } = req.body || {};
    if (!context || !question) return res.status(400).json({ error: 'context and question required' });
    const ctx  = String(context).slice(0, 600);
    const q    = String(question).slice(0, 300);
    const { callAI } = require('../shared/ai');
    const sys  = 'You are a crypto futures trading assistant. Answer in 2-4 sentences. Be direct, specific, and actionable. No preamble.';
    const user = `${ctx}\n\nUser question: ${q}`;
    const answer = await callAI(sys, user, { maxTokens: 300 });
    res.json({ answer });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});
```

- [ ] **Step 2: Smoke-test the endpoint**

Server is running on port 3000. In a PowerShell terminal:

```powershell
Invoke-RestMethod -Method POST -Uri http://localhost:3000/api/crypto/ai/ask-position -ContentType "application/json" -Body '{}'
```

Expected: `{"error":"context and question required"}`

```powershell
Invoke-RestMethod -Method POST -Uri http://localhost:3000/api/crypto/ai/ask-position -ContentType "application/json" -Body '{"context":"Symbol: BTCUSDT | Strategy: MTF | Entry: 100000","question":"is 5x leverage safe here?"}'
```

Expected: JSON with `answer` field (a 2–4 sentence AI response).

- [ ] **Step 3: Commit**

```bash
git -C C:/Claude/tesseract-scan add dashboard/api.js
git -C C:/Claude/tesseract-scan commit -m "feat: add POST /api/crypto/ai/ask-position endpoint"
```

---

### Task 2: Journal — ask box in expanded card

**Files:**
- Modify: `tesseract-scan/dashboard/public/crypto.jsx` — `CryptoJournalView` (lines 1786–2134)

- [ ] **Step 1: Add 4 ask state dicts**

In `CryptoJournalView`, find the state block ending with `coachOpen` at line 1796:

```js
  const [coachOpen,       setCoachOpen]       = useState(false);
```

Replace that line with:

```js
  const [coachOpen,       setCoachOpen]       = useState(false);
  const [askQ,            setAskQ]            = useState({});
  const [askLoading,      setAskLoading]      = useState({});
  const [askAnswer,       setAskAnswer]       = useState({});
  const [askErr,          setAskErr]          = useState({});
```

- [ ] **Step 2: Add handleAsk function**

Find the closing `};` of the `runCoach` function (around line 1827). Insert immediately after:

```js
  const handleAsk = async (id, context) => {
    if (!askQ[id]?.trim() || askLoading[id]) return;
    setAskLoading(p => ({ ...p, [id]: true }));
    setAskErr(p => ({ ...p, [id]: null }));
    setAskAnswer(p => ({ ...p, [id]: null }));
    try {
      const r = await fetch('/api/crypto/ai/ask-position', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ context, question: askQ[id].trim() }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.error);
      setAskAnswer(p => ({ ...p, [id]: d.answer }));
      setAskQ(p => ({ ...p, [id]: '' }));
    } catch (e) {
      setAskErr(p => ({ ...p, [id]: e.message }));
    } finally {
      setAskLoading(p => ({ ...p, [id]: false }));
    }
  };
```

- [ ] **Step 3: Add askCtx variable in the closed.map callback**

In the `closed.map(pos => {` callback, find this block (around line 2054–2059):

```js
            const pnl  = pnlOf(pos);
            const rM   = pos.riskUsd > 0 ? pnl / pos.riskUsd : null;
            const meta = STRAT_META[pos.strategyId];
            const isEx = expanded[pos.id];
            const draft = notesDraft[pos.id] ?? (pos.notes || '');
            const win  = pnl >= 0;
```

Replace with:

```js
            const pnl  = pnlOf(pos);
            const rM   = pos.riskUsd > 0 ? pnl / pos.riskUsd : null;
            const meta = STRAT_META[pos.strategyId];
            const isEx = expanded[pos.id];
            const draft = notesDraft[pos.id] ?? (pos.notes || '');
            const win  = pnl >= 0;
            const askCtx = `Symbol: ${pos.symbol} | Strategy: ${pos.strategyName}\nEntry: ${cFmt(pos.entryPrice)} | Exit: ${cFmt(pos.closePrice)} | Qty: ${pos.qty?.toFixed(4)}\nP&L: ${(pnl >= 0 ? '+' : '') + usd(pnl)} (${rM != null ? (rM >= 0 ? '+' : '') + rM.toFixed(2) + 'R' : '—'}) | Close reason: ${pos.closeReason}\nOpened: ${pos.entryTime?.slice(0, 10)} | Closed: ${pos.closeTime?.slice(0, 10)}`;
```

- [ ] **Step 4: Insert ask UI after AI Debrief block**

In the `{isEx && (` expanded section, find the closing `</div>` of the AI Debrief block — it's the last `</div>` before the `</div>` that closes the entire `isEx` padding wrapper (around line 2124). Insert after the AI Debrief's closing `</div>` and before the padding wrapper's closing `</div>`:

```jsx
                    {/* Ask AI */}
                    <div style={{ marginTop: 12, borderTop: '1px solid #9b7be822', paddingTop: 10 }}>
                      <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.14em', color: '#9b7be8', fontFamily: 'var(--font-mono)', marginBottom: 6, textTransform: 'uppercase' }}>
                        ASK AI
                      </div>
                      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                        <input
                          value={askQ[pos.id] || ''}
                          onChange={e => setAskQ(p => ({ ...p, [pos.id]: e.target.value }))}
                          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleAsk(pos.id, askCtx); } }}
                          placeholder="Ask about this trade, strategy, or lessons learned…"
                          disabled={!!askLoading[pos.id]}
                          style={{ flex: 1, fontSize: 10, fontFamily: 'var(--font-mono)', background: 'var(--bg-2)', border: '1px solid #9b7be844', borderRadius: 3, padding: '4px 8px', color: 'var(--fg-1)', outline: 'none', opacity: askLoading[pos.id] ? 0.5 : 1 }}
                        />
                        <button
                          onClick={() => handleAsk(pos.id, askCtx)}
                          disabled={!askQ[pos.id]?.trim() || !!askLoading[pos.id]}
                          style={{ fontSize: 11, padding: '4px 8px', borderRadius: 3, cursor: (!askQ[pos.id]?.trim() || askLoading[pos.id]) ? 'not-allowed' : 'pointer', background: '#9b7be822', border: '1px solid #9b7be866', color: '#9b7be8', opacity: (!askQ[pos.id]?.trim() || askLoading[pos.id]) ? 0.4 : 1 }}
                        >▶</button>
                      </div>
                      {askLoading[pos.id] && <div style={{ marginTop: 6, fontSize: 10, color: 'var(--fg-3)', fontFamily: 'var(--font-mono)', fontStyle: 'italic' }}>Thinking…</div>}
                      {askErr[pos.id] && <div style={{ marginTop: 6, fontSize: 10, color: 'var(--bear)', fontFamily: 'var(--font-mono)' }}>{askErr[pos.id]}</div>}
                      {askAnswer[pos.id] && (
                        <div style={{ marginTop: 6, fontSize: 11, color: 'var(--fg-2)', lineHeight: 1.7, whiteSpace: 'pre-wrap', borderLeft: '2px solid #9b7be844', paddingLeft: 10 }}>
                          {askAnswer[pos.id]}
                        </div>
                      )}
                    </div>
```

To find the exact insertion point, look for the `{isEx && (` block in `CryptoJournalView`. The AI Debrief block ends with a `</div>` that closes `<div style={{ marginTop: 14, borderTop: '1px solid var(--line)', paddingTop: 12 }}>`. Insert the ask UI div immediately after that closing `</div>`, before the padding wrapper's `</div>` (which closes `<div style={{ padding: '12px 14px', background: 'var(--bg-1)', borderTop: '1px solid var(--line)' }}`).

- [ ] **Step 5: Build bundle and verify**

```bash
node C:/Claude/tesseract-scan/dashboard/build.js
```

Expected last line: `✓ bundle.js — ...`

Open browser → `http://localhost:3000` → Crypto → Journal tab. Click any closed trade to expand. Confirm "ASK AI" section appears below "AI Debrief". Type a question, press Enter. Confirm answer appears. Collapse the card and re-expand — confirm ask state is preserved (state lives in parent component dict, persists while component mounted).

- [ ] **Step 6: Commit**

```bash
git -C C:/Claude/tesseract-scan add dashboard/public/crypto.jsx dashboard/public/bundle.js
git -C C:/Claude/tesseract-scan commit -m "feat: add AI ask box to Journal tab"
```

---

### Task 3: Forward Test — ask box in closed + open positions

**Files:**
- Modify: `tesseract-scan/dashboard/public/crypto.jsx` — `CryptoForwardTestView` (lines 1402–1783)

#### Part A: Shared state + handleAsk + closed positions ask UI

- [ ] **Step 1: Add 5 ask state dicts**

In `CryptoForwardTestView`, find the state block ending with `runningEG` at line 1417:

```js
  const [runningEG,    setRunningEG]    = useState(false);
```

Replace with:

```js
  const [runningEG,    setRunningEG]    = useState(false);
  const [askQ,         setAskQ]         = useState({});
  const [askLoading,   setAskLoading]   = useState({});
  const [askAnswer,    setAskAnswer]    = useState({});
  const [askErr,       setAskErr]       = useState({});
  const [askOpen,      setAskOpen]      = useState({});
```

- [ ] **Step 2: Add handleAsk and toggleAskOpen functions**

Find the closing `};` of `saveNotes` function (around line 1468). Insert immediately after:

```js
  const handleAsk = async (id, context) => {
    if (!askQ[id]?.trim() || askLoading[id]) return;
    setAskLoading(p => ({ ...p, [id]: true }));
    setAskErr(p => ({ ...p, [id]: null }));
    setAskAnswer(p => ({ ...p, [id]: null }));
    try {
      const r = await fetch('/api/crypto/ai/ask-position', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ context, question: askQ[id].trim() }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.error);
      setAskAnswer(p => ({ ...p, [id]: d.answer }));
      setAskQ(p => ({ ...p, [id]: '' }));
    } catch (e) {
      setAskErr(p => ({ ...p, [id]: e.message }));
    } finally {
      setAskLoading(p => ({ ...p, [id]: false }));
    }
  };

  const toggleAskOpen = (id) => {
    setAskOpen(p => {
      if (p[id]) {
        setAskQ(q => { const n = {...q}; delete n[id]; return n; });
        setAskAnswer(a => { const n = {...a}; delete n[id]; return n; });
        setAskErr(e => { const n = {...e}; delete n[id]; return n; });
      }
      return { ...p, [id]: !p[id] };
    });
  };
```

- [ ] **Step 3: Add askCtx and ask UI in closed positions expansion**

In the `sortedClosed.map(pos => {` callback, find where `isExp` and `draft` are computed (around line 1727–1728):

```js
                  const isExp = expanded[pos.id];
                  const draft = notesDraft[pos.id] ?? (pos.notes || '');
```

Replace with:

```js
                  const isExp = expanded[pos.id];
                  const draft = notesDraft[pos.id] ?? (pos.notes || '');
                  const askCtx = `Symbol: ${pos.symbol} | Strategy: ${pos.strategyName}\nEntry: ${cFmt(pos.entryPrice)} | Exit: ${cFmt(pos.closePrice)} | Qty: ${pos.qty?.toFixed(4)}\nP&L: ${(pnl >= 0 ? '+' : '') + usd(pnl)} (${rM != null ? (rM >= 0 ? '+' : '') + rM.toFixed(2) + 'R' : '—'}) | Close reason: ${pos.closeReason}\nStatus: CLOSED`;
```

Then find the SAVE button inside the `{isExp && (` expansion (around line 1767–1769):

```jsx
                            <button onClick={() => saveNotes(pos.id)} disabled={savingNotes[pos.id]} style={{ marginTop: 6, background: TEAL, color: '#000', border: 'none', borderRadius: 3, padding: '4px 12px', fontSize: 9, fontFamily: 'var(--font-mono)', fontWeight: 700, cursor: 'pointer', letterSpacing: '0.08em' }}>
                              {savingNotes[pos.id] ? '…' : 'SAVE'}
                            </button>
```

Insert the ask UI immediately after that `</button>` and before the closing `</td>`:

```jsx
                            {/* Ask AI */}
                            <div style={{ marginTop: 12, borderTop: '1px solid #9b7be822', paddingTop: 10 }}>
                              <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.14em', color: '#9b7be8', fontFamily: 'var(--font-mono)', marginBottom: 6, textTransform: 'uppercase' }}>
                                ASK AI
                              </div>
                              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                                <input
                                  value={askQ[pos.id] || ''}
                                  onChange={e => setAskQ(p => ({ ...p, [pos.id]: e.target.value }))}
                                  onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleAsk(pos.id, askCtx); } }}
                                  placeholder="Ask about this trade…"
                                  disabled={!!askLoading[pos.id]}
                                  style={{ flex: 1, fontSize: 10, fontFamily: 'var(--font-mono)', background: 'var(--bg-2)', border: '1px solid #9b7be844', borderRadius: 3, padding: '4px 8px', color: 'var(--fg-1)', outline: 'none', opacity: askLoading[pos.id] ? 0.5 : 1 }}
                                />
                                <button
                                  onClick={() => handleAsk(pos.id, askCtx)}
                                  disabled={!askQ[pos.id]?.trim() || !!askLoading[pos.id]}
                                  style={{ fontSize: 11, padding: '4px 8px', borderRadius: 3, cursor: (!askQ[pos.id]?.trim() || askLoading[pos.id]) ? 'not-allowed' : 'pointer', background: '#9b7be822', border: '1px solid #9b7be866', color: '#9b7be8', opacity: (!askQ[pos.id]?.trim() || askLoading[pos.id]) ? 0.4 : 1 }}
                                >▶</button>
                              </div>
                              {askLoading[pos.id] && <div style={{ marginTop: 6, fontSize: 10, color: 'var(--fg-3)', fontFamily: 'var(--font-mono)', fontStyle: 'italic' }}>Thinking…</div>}
                              {askErr[pos.id] && <div style={{ marginTop: 6, fontSize: 10, color: 'var(--bear)', fontFamily: 'var(--font-mono)' }}>{askErr[pos.id]}</div>}
                              {askAnswer[pos.id] && (
                                <div style={{ marginTop: 6, fontSize: 11, color: 'var(--fg-2)', lineHeight: 1.7, whiteSpace: 'pre-wrap', borderLeft: '2px solid #9b7be844', paddingLeft: 10 }}>
                                  {askAnswer[pos.id]}
                                </div>
                              )}
                            </div>
```

#### Part B: Open positions — React.Fragment + new ASK AI column

- [ ] **Step 4: Add ASK AI to the open positions column headers**

Find this line (around line 1622):

```js
                {['SYMBOL · STRATEGY', 'ENTRY', 'CURRENT', 'UNREAL R', 'STOP', 'TRAIL SL', 'ADDED', ''].map(h => <th key={h} style={TH}>{h}</th>)}
```

Replace with:

```js
                {['SYMBOL · STRATEGY', 'ENTRY', 'CURRENT', 'UNREAL R', 'STOP', 'TRAIL SL', 'ADDED', '', 'ASK AI'].map(h => <th key={h} style={TH}>{h}</th>)}
```

- [ ] **Step 5: Wrap open rows in React.Fragment + add ASK AI column + sub-row**

In `open.map(pos => {`, find the closing `const win` or equivalent variables before `return (`. The map callback returns a `<tr key={pos.id}>` at around line 1634. Add `askCtx` before `return (`:

Find (around line 1633, right before `return (`):

```js
                  return (
                    <tr key={pos.id}>
```

Replace with:

```js
                  const askCtxOpen = `Symbol: ${pos.symbol} | Strategy: ${pos.strategyName}\nEntry: ${cFmt(pos.entryPrice)} | Current: ${cur != null ? cFmt(cur) : 'unknown'} | Stop: ${cFmt(pos.stop)} | Trail SL: ${cFmt(pos.currentStop)}\nUnrealized R: ${uR != null ? (uR >= 0 ? '+' : '') + uR.toFixed(2) + 'R' : '—'} | Added: ${pos.entryTime?.slice(0, 10)}\nStatus: OPEN`;
                  return (
                    <React.Fragment key={pos.id}>
                    <tr>
```

Then find the closing `</tr>` of the open position row (around line 1674-1675). It comes right after the close button `</td>`. Add the new ASK AI column cell AND the `</tr>` replacement AND the sub-row AND `</React.Fragment>`:

Find this block (the close button td + closing tr, around lines 1669–1675):

```jsx
                      <td style={TD}>
                        <button onClick={() => handleClose(pos)} disabled={closing === pos.id} style={{ background: 'transparent', border: '1px solid var(--bear)', color: 'var(--bear)', padding: '3px 9px', fontSize: 8, fontFamily: 'var(--font-mono)', borderRadius: 3, cursor: closing === pos.id ? 'default' : 'pointer', letterSpacing: '0.06em', fontWeight: 600 }}>
                          {closing === pos.id ? '…' : 'CLOSE'}
                        </button>
                      </td>
                    </tr>
```

Replace with:

```jsx
                      <td style={TD}>
                        <button onClick={() => handleClose(pos)} disabled={closing === pos.id} style={{ background: 'transparent', border: '1px solid var(--bear)', color: 'var(--bear)', padding: '3px 9px', fontSize: 8, fontFamily: 'var(--font-mono)', borderRadius: 3, cursor: closing === pos.id ? 'default' : 'pointer', letterSpacing: '0.06em', fontWeight: 600 }}>
                          {closing === pos.id ? '…' : 'CLOSE'}
                        </button>
                      </td>
                      <td style={TD}>
                        <button
                          onClick={() => toggleAskOpen(pos.id)}
                          style={{ background: askOpen[pos.id] ? '#9b7be822' : 'transparent', border: `1px solid ${askOpen[pos.id] ? '#9b7be866' : 'var(--line)'}`, color: askOpen[pos.id] ? '#9b7be8' : 'var(--fg-3)', padding: '2px 8px', borderRadius: 3, fontSize: 9, fontFamily: 'var(--font-mono)', cursor: 'pointer', letterSpacing: '0.04em' }}
                        >
                          {askOpen[pos.id] ? '▲ ASK' : '⚡ ASK'}
                        </button>
                      </td>
                    </tr>
                    {askOpen[pos.id] && (
                      <tr>
                        <td colSpan={9} style={{ padding: '12px 14px', background: 'var(--bg)', borderBottom: '1px solid var(--line)' }}>
                          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                            <input
                              value={askQ[pos.id] || ''}
                              onChange={e => setAskQ(p => ({ ...p, [pos.id]: e.target.value }))}
                              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleAsk(pos.id, askCtxOpen); } }}
                              placeholder="Ask about this open position…"
                              disabled={!!askLoading[pos.id]}
                              style={{ flex: 1, fontSize: 10, fontFamily: 'var(--font-mono)', background: 'var(--bg-2)', border: '1px solid #9b7be844', borderRadius: 3, padding: '4px 8px', color: 'var(--fg-1)', outline: 'none', opacity: askLoading[pos.id] ? 0.5 : 1 }}
                            />
                            <button
                              onClick={() => handleAsk(pos.id, askCtxOpen)}
                              disabled={!askQ[pos.id]?.trim() || !!askLoading[pos.id]}
                              style={{ fontSize: 11, padding: '4px 8px', borderRadius: 3, cursor: (!askQ[pos.id]?.trim() || askLoading[pos.id]) ? 'not-allowed' : 'pointer', background: '#9b7be822', border: '1px solid #9b7be866', color: '#9b7be8', opacity: (!askQ[pos.id]?.trim() || askLoading[pos.id]) ? 0.4 : 1 }}
                            >▶</button>
                          </div>
                          {askLoading[pos.id] && <div style={{ marginTop: 6, fontSize: 10, color: 'var(--fg-3)', fontFamily: 'var(--font-mono)', fontStyle: 'italic' }}>Thinking…</div>}
                          {askErr[pos.id] && <div style={{ marginTop: 6, fontSize: 10, color: 'var(--bear)', fontFamily: 'var(--font-mono)' }}>{askErr[pos.id]}</div>}
                          {askAnswer[pos.id] && (
                            <div style={{ marginTop: 6, fontSize: 11, color: 'var(--fg-2)', lineHeight: 1.7, whiteSpace: 'pre-wrap', borderLeft: '2px solid #9b7be844', paddingLeft: 10 }}>
                              {askAnswer[pos.id]}
                            </div>
                          )}
                        </td>
                      </tr>
                    )}
                    </React.Fragment>
```

- [ ] **Step 6: Build bundle and verify**

```bash
node C:/Claude/tesseract-scan/dashboard/build.js
```

Expected last line: `✓ bundle.js — ...`

Open browser → Crypto → Forward Test tab.

*Closed positions:* Click any closed trade row to expand it. Confirm "ASK AI" section appears below SAVE button. Type a question and press Enter. Confirm answer.

*Open positions:* Confirm table header shows "ASK AI" as last column. Click "⚡ ASK" button on any open position row. Confirm sub-row expands below with input. Type a question and submit. Click "▲ ASK" to collapse — confirm input cleared on re-open.

- [ ] **Step 7: Commit**

```bash
git -C C:/Claude/tesseract-scan add dashboard/public/crypto.jsx dashboard/public/bundle.js
git -C C:/Claude/tesseract-scan commit -m "feat: add AI ask box to Forward Test open + closed positions"
```

---

### Task 4: Live Trades — ask box in Binance AI sub-row

**Files:**
- Modify: `tesseract-scan/dashboard/public/crypto.jsx` — `CryptoLiveTradesView` (lines 2137–2420)

- [ ] **Step 1: Add 4 ask state dicts**

In `CryptoLiveTradesView`, find the state ending with `liveAnalLoading` at line 2146:

```js
  const [liveAnalLoading, setLiveAnalLoading] = useState({});
```

Replace with:

```js
  const [liveAnalLoading, setLiveAnalLoading] = useState({});
  const [askQ,            setAskQ]            = useState({});
  const [askLoading,      setAskLoading]      = useState({});
  const [askAnswer,       setAskAnswer]       = useState({});
  const [askErr,          setAskErr]          = useState({});
```

- [ ] **Step 2: Add handleAskLive function**

Find the closing `};` of `runLiveAnalysis` function (around line 2179). Insert immediately after:

```js
  const handleAskLive = async (rowKey, context) => {
    if (!askQ[rowKey]?.trim() || askLoading[rowKey]) return;
    setAskLoading(p => ({ ...p, [rowKey]: true }));
    setAskErr(p => ({ ...p, [rowKey]: null }));
    setAskAnswer(p => ({ ...p, [rowKey]: null }));
    try {
      const r = await fetch('/api/crypto/ai/ask-position', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ context, question: askQ[rowKey].trim() }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.error);
      setAskAnswer(p => ({ ...p, [rowKey]: d.answer }));
      setAskQ(p => ({ ...p, [rowKey]: '' }));
    } catch (e) {
      setAskErr(p => ({ ...p, [rowKey]: e.message }));
    } finally {
      setAskLoading(p => ({ ...p, [rowKey]: false }));
    }
  };
```

- [ ] **Step 3: Add liveAskCtx variable in the positions.map callback**

In `positions.map((p, i) => {`, find the block where `rowKey` and `aiOpen` are defined (around lines 2276–2280):

```js
                const rowKey   = `live-${i}`;
                const aiOpen   = !!aiExpanded[rowKey];
                const anal     = liveAnalysis[rowKey];
                const analLoad = liveAnalLoading[rowKey];
                const actionColor = { HOLD: TEAL, TRAIL: 'var(--warn)', EXIT: 'var(--bear)' };
```

Replace with:

```js
                const rowKey   = `live-${i}`;
                const aiOpen   = !!aiExpanded[rowKey];
                const anal     = liveAnalysis[rowKey];
                const analLoad = liveAnalLoading[rowKey];
                const actionColor = { HOLD: TEAL, TRAIL: 'var(--warn)', EXIT: 'var(--bear)' };
                const liqDistStr  = liqDist != null ? liqDist.toFixed(1) + '%' : 'unknown';
                const liveAskCtx  = `Symbol: ${sym} | Side: ${(p.side || '').toUpperCase()} | Leverage: ${p.leverage ?? '?'}x\nEntry: ${(p.entryPrice ?? 0).toFixed(4)} | Mark: ${(p.markPrice ?? 0).toFixed(4)} | Unrealized PnL: ${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}\nLiquidation: ${(p.liquidationPrice ?? 0).toFixed(2)} (${liqDistStr} away) | Margin: $${(p.marginUsed ?? 0).toFixed(2)}`;
```

- [ ] **Step 4: Modify AI toggle button to reset ask state on collapse**

Find the AI toggle button's onClick (around line 2312):

```js
                        <button onClick={() => { setAiExpanded(s => ({ ...s, [rowKey]: !s[rowKey] })); if (!aiOpen && !anal) runLiveAnalysis(rowKey, p); }}
```

Replace with:

```js
                        <button onClick={() => {
                          const opening = !aiExpanded[rowKey];
                          setAiExpanded(s => ({ ...s, [rowKey]: !s[rowKey] }));
                          if (!opening) {
                            setAskQ(q => { const n = {...q}; delete n[rowKey]; return n; });
                            setAskAnswer(a => { const n = {...a}; delete n[rowKey]; return n; });
                            setAskErr(e => { const n = {...e}; delete n[rowKey]; return n; });
                          }
                          if (opening && !anal) runLiveAnalysis(rowKey, p);
                        }}
```

- [ ] **Step 5: Insert ask UI at end of the aiOpen sub-row**

Find the closing `)}` of the `{analLoad ? ... : anal ? ... : ...}` ternary (around line 2348). It looks like:

```jsx
                          )}
                        </td>
```

Insert the ask UI between those two lines:

```jsx
                          {/* Ask AI */}
                          <div style={{ marginTop: 10, borderTop: '1px solid #9b7be822', paddingTop: 10 }}>
                            <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.14em', color: '#9b7be8', fontFamily: 'var(--font-mono)', marginBottom: 6, textTransform: 'uppercase' }}>ASK AI</div>
                            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                              <input
                                value={askQ[rowKey] || ''}
                                onChange={e => setAskQ(q => ({ ...q, [rowKey]: e.target.value }))}
                                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleAskLive(rowKey, liveAskCtx); } }}
                                placeholder="Ask about this position…"
                                disabled={!!askLoading[rowKey]}
                                style={{ flex: 1, fontSize: 10, fontFamily: 'var(--font-mono)', background: 'var(--bg-2)', border: '1px solid #9b7be844', borderRadius: 3, padding: '4px 8px', color: 'var(--fg-1)', outline: 'none', opacity: askLoading[rowKey] ? 0.5 : 1 }}
                              />
                              <button
                                onClick={() => handleAskLive(rowKey, liveAskCtx)}
                                disabled={!askQ[rowKey]?.trim() || !!askLoading[rowKey]}
                                style={{ fontSize: 11, padding: '4px 8px', borderRadius: 3, cursor: (!askQ[rowKey]?.trim() || askLoading[rowKey]) ? 'not-allowed' : 'pointer', background: '#9b7be822', border: '1px solid #9b7be866', color: '#9b7be8', opacity: (!askQ[rowKey]?.trim() || askLoading[rowKey]) ? 0.4 : 1 }}
                              >▶</button>
                            </div>
                            {askLoading[rowKey] && <div style={{ marginTop: 6, fontSize: 10, color: 'var(--fg-3)', fontFamily: 'var(--font-mono)', fontStyle: 'italic' }}>Thinking…</div>}
                            {askErr[rowKey] && <div style={{ marginTop: 6, fontSize: 10, color: 'var(--bear)', fontFamily: 'var(--font-mono)' }}>{askErr[rowKey]}</div>}
                            {askAnswer[rowKey] && (
                              <div style={{ marginTop: 6, fontSize: 11, color: 'var(--fg-2)', lineHeight: 1.7, whiteSpace: 'pre-wrap', borderLeft: '2px solid #9b7be844', paddingLeft: 10 }}>
                                {askAnswer[rowKey]}
                              </div>
                            )}
                          </div>
```

- [ ] **Step 6: Build bundle and verify**

```bash
node C:/Claude/tesseract-scan/dashboard/build.js
```

Expected last line: `✓ bundle.js — ...`

Open browser → Crypto → Live Trades tab. Click "▼ AI" on any Binance position row. Confirm AI analysis loads AND an "ASK AI" section appears below (with input + ▶ button). Type a question and press Enter. Confirm answer. Click "▲" to collapse — re-open and confirm input is blank.

- [ ] **Step 7: Commit**

```bash
git -C C:/Claude/tesseract-scan add dashboard/public/crypto.jsx dashboard/public/bundle.js
git -C C:/Claude/tesseract-scan commit -m "feat: add AI ask box to Live Trades tab"
```

---

### Task 5: Push to remote

- [ ] **Step 1: Verify all tests still pass**

```bash
cd C:/Claude/tesseract-scan && npm test -- --testPathPattern="crypto" 2>&1 | tail -20
```

Expected: no new failures beyond the pre-existing `ms-strategies.test.js:110` (strategy count mismatch — that test was failing before this feature).

- [ ] **Step 2: Push**

```bash
git -C C:/Claude/tesseract-scan push
```

Expected: `master -> master` (or `main -> main`).
