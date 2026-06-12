# Crypto AI Ask Box — Journal, Forward Test, Live Trades

**Date:** 2026-06-12  
**Status:** Approved  
**Related:** `2026-06-12-crypto-ai-ask-design.md` (scan tab implementation)

## Overview

Extend the per-pick AI ask box (already live on the Scan tab) to three more crypto tabs: Journal, Forward Test (open + closed positions), and Live Trades. Each tab surfaces different trade context to the AI, but the UX and backend pattern are consistent.

## Backend

### New endpoint: `POST /api/crypto/ai/ask-position`

```
Body: { context: string, question: string }
Response: { answer: string }
```

- `context`: pre-formatted trade context string built by the frontend (max 600 chars, sliced not rejected)
- `question`: user question (max 300 chars, sliced not rejected)
- Validates both fields present — 400 if missing
- System prompt: `"You are a crypto futures trading assistant. Answer in 2-4 sentences. Be direct, specific, and actionable. No preamble."`
- User prompt: `${context}\n\nUser question: ${question}`
- `callAI(sys, user, { maxTokens: 300 })` — no caching
- 500 on AI failure

This endpoint is intentionally generic — it does not read any server-side data files. All context is built client-side per tab.

---

## Frontend State Pattern

All three tabs use **dict-keyed state** (by `pos.id` or `rowKey`), not component-level state like `ScanFeedItem`. This is because these tabs render positions in loops inside a single parent component — there is no per-row component to hold local state.

Four new state dicts per tab (or shared where tabs are in the same component):

```js
const [askQ,       setAskQ]       = useState({});  // { [id]: string }
const [askLoading, setAskLoading] = useState({});  // { [id]: bool }
const [askAnswer,  setAskAnswer]  = useState({});  // { [id]: string|null }
const [askErr,     setAskErr]     = useState({});  // { [id]: string|null }
```

`handleAsk(id, context)` function per tab:
- Guard: skip if `!askQ[id]?.trim() || askLoading[id]`
- Sets `askLoading[id] = true`, clears `askErr[id]`, clears `askAnswer[id]`
- `POST /api/crypto/ai/ask-position` with `{ context, question: askQ[id].trim() }`
- On success: sets `askAnswer[id]`, clears `askQ[id]`
- On error: sets `askErr[id]`
- Finally: `askLoading[id] = false`

---

## Journal (`CryptoJournalView`)

### Where it appears
Inside the existing expanded card (`isEx` section), below the "AI Debrief" block (after line ~2125).

### Context string built client-side
```
Symbol: {pos.symbol} | Strategy: {pos.strategyName}
Entry: {pos.entryPrice} | Exit: {pos.closePrice} | Qty: {pos.qty}
P&L: {pnl} ({rM}R) | Close reason: {pos.closeReason}
Opened: {pos.entryTime?.slice(0,10)} | Closed: {pos.closeTime?.slice(0,10)}
```

### State
4 new dicts in `CryptoJournalView` (same scope as existing `debriefs`, `genDebrief`).

### UI
Placed after the AI Debrief block, separated by a `borderTop` divider:
```
─── ASK AI ───────────────────────────────
[Ask about this trade...            ] [▶]
Answer text appears here after submit
```
Same input/button/loading/error/answer pattern as scan tab. `#9b7be8` accent. Input placeholder: `"Ask about this trade, strategy, or lessons learned…"`

---

## Forward Test (`CryptoForwardTestView`)

### Open positions table

**New column header:** `"ASK AI"` (last column, after existing close button column)

**Row expansion pattern:** `React.Fragment` wrapper per row. New `askOpen` dict tracks which rows have the sub-row visible. Clicking "⚡" toggles `askOpen[pos.id]` and resets ask state for that row on close.

```jsx
<React.Fragment key={pos.id}>
  <tr>
    ...existing columns...
    <td>
      <button onClick={() => toggleAskOpen(pos.id)}>⚡</button>
    </td>
  </tr>
  {askOpen[pos.id] && (
    <tr>
      <td colSpan={9}>
        [ask input + answer]
      </td>
    </tr>
  )}
</React.Fragment>
```

`toggleAskOpen(id)`: if currently open, resets `askQ[id]`, `askAnswer[id]`, `askErr[id]` before closing.

**Context for open positions:**
```
Symbol: {pos.symbol} | Strategy: {pos.strategyName}
Entry: {pos.entryPrice} | Current: {cur ?? 'unknown'} | Stop: {pos.stop} | Trail SL: {pos.currentStop}
Unrealized R: {uR} | Added: {pos.entryTime?.slice(0,10)}
Status: OPEN
```

### Closed positions table

**Different pattern from open** — closed rows already use `React.Fragment` + `isExp` expansion (click row to expand, `colSpan={8}`). The expanded section already has "AI Post-Mortem" + notes textarea + save button. The ask box goes **inside the existing expanded section**, below the save button. No new column needed.

**Context for closed positions:**
```
Symbol: {pos.symbol} | Strategy: {pos.strategyName}
Entry: {pos.entryPrice} | Exit: {pos.closePrice} | Qty: {pos.qty}
P&L: {pnlOf(pos).toFixed(2)} ({rM}R) | Close reason: {pos.closeReason}
Status: CLOSED
```

**State added to `CryptoForwardTestView`:**
- 4 ask dicts (`askQ`, `askLoading`, `askAnswer`, `askErr`) — shared across open + closed (pos IDs are unique)
- 1 open-tracking dict: `askOpen` — only used by open positions table (closed uses existing `expanded` dict)

---

## Live Trades (`CryptoLiveTradesView`)

### Where it appears
Inside the existing `aiOpen` sub-row (`<td colSpan={12}>` block), below the live analysis content (after the ↻ Refresh button, before `</td>`).

### Context string
```
Symbol: {sym} | Side: {p.side?.toUpperCase()} | Leverage: {p.leverage}x
Entry: {p.entryPrice} | Mark: {p.markPrice} | Unrealized PnL: {pnl}
Liquidation: {p.liquidationPrice} ({liqDist}% away) | Margin: {p.marginUsed}
```

### State
4 new ask dicts in `CryptoLiveTradesView`. Key: `rowKey` (same key as `aiExpanded`/`liveAnalysis`).

When `aiExpanded[rowKey]` toggles to false (row collapses), reset `askQ[rowKey]`, `askAnswer[rowKey]`, `askErr[rowKey]`.

**Modification to existing toggle button** (line ~2312):
```js
onClick={() => {
  const opening = !aiExpanded[rowKey];
  setAiExpanded(s => ({ ...s, [rowKey]: !s[rowKey] }));
  if (!opening) {
    setAskQ(q => { const n={...q}; delete n[rowKey]; return n; });
    setAskAnswer(a => { const n={...a}; delete n[rowKey]; return n; });
    setAskErr(e => { const n={...e}; delete n[rowKey]; return n; });
  }
  if (opening && !anal) runLiveAnalysis(rowKey, p);
}}
```

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Empty question | No request (button disabled, Enter no-op) |
| AI provider fails | Inline error in `var(--bear)` red |
| Network timeout | Show error inline, input preserved |
| Row collapses mid-flight | Request completes but state cleaned up on reopen |

## What This Does Not Do

- No conversation history — each ask is independent
- No caching
- No suggested question chips
- Forward Test does NOT add ask to the Binance live positions sub-section (already handled by Live Trades tab)
