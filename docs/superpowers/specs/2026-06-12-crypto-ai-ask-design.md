# Crypto Scan — Per-Signal AI Ask Box

**Date:** 2026-06-12  
**Status:** Approved

## Overview

Add a text input to each crypto scan signal row that lets the user ask ad-hoc AI questions about that specific pick. Primary use case: re-entry timing after an early exit, but open-ended for any trade question.

## User Flow

1. User clicks **⚡ AI** on a signal row → AI thesis loads (existing behavior)
2. Below the thesis, a text input appears with placeholder "Ask about re-entry, timing, risk…"
3. User types question, presses **Enter** or clicks **▶** submit button
4. "Thinking…" spinner replaces previous answer
5. AI answer appears below input (2–4 sentences, direct)
6. User can ask another question — new answer replaces old one
7. AI panel collapse (clicking ⚡ AI again) clears both thesis and answer

## Architecture

### Frontend (`dashboard/public/crypto.jsx`)

`ScanFeedItem` component gains three new state variables:

```js
const [askQ,       setAskQ]       = useState('');
const [askLoading, setAskLoading] = useState(false);
const [askAnswer,  setAskAnswer]  = useState(null);
const [askErr,     setAskErr]     = useState(null);
```

New `handleAsk` async function:
- Guards: skip if `askQ.trim()` is empty or `askLoading` is true
- Sets `askLoading = true`, clears `askErr`
- `POST /api/crypto/ai/ask` with `{ symbol: pick.symbol, question: askQ.trim() }`
- On success: sets `askAnswer`, clears `askQ`
- On error: sets `askErr`
- Always: `askLoading = false`

Input rendered inside the `aiOpen` div, after the thesis block:

```
─────────────────────────────
⚡ AI THESIS
• bullet 1
• bullet 2

[ Ask about re-entry, timing… ] [▶]

Re-entry: wait for a pullback to 145–146...
─────────────────────────────
```

Input styles: match existing mono font, bg-2 background, border consistent with row accent color.  
Submit button: small `▶` icon, accent color, disabled while `askLoading`.  
`onKeyDown`: submit on `Enter` (not `Shift+Enter`).

When `aiOpen` toggles to false (user collapses panel), `askAnswer` and `askQ` reset to null/empty.

### Backend (`dashboard/api.js`)

New route: `POST /api/crypto/ai/ask`

```
Body: { symbol: string, question: string }
Response: { answer: string }
```

Logic:
1. Validate `symbol` and `question` present — 400 if missing
2. Sanitize: `question` max 300 chars (slice, not reject)
3. Read `crypto-scan.json` via existing `readJSON` helper
4. Find pick by `symbol.toUpperCase()` — 404 if not found
5. Build system prompt + user prompt (see below)
6. `callAI(sys, user, { maxTokens: 300 })` — no cache
7. Return `{ answer }`

**System prompt:**
```
You are a crypto futures trading assistant. Answer in 2-4 sentences. Be direct, specific, and actionable. No preamble.
```

**User prompt template:**
```
Trade context:
Symbol: {symbol} | Strategy: {strategyName} | Timeframe: {tf}
Entry: {entryHigh} | Stop: {stop} (-{stopPct}%) | 2R Target: {target2R} (+{tgtPct}%)
ATR: {atr} | Funding 8h: {funding}% | ADX: {adx} | ROC30: {roc30}%
Regime: {regime} | Leverage: {leverage}x | Risk: ${riskUsd}

User question: {question}
```

Fields derived from the pick object already present in `crypto-scan.json`. `regime` pulled from `scan.regime` (top-level field).

## Error Handling

| Scenario | Behavior |
|---|---|
| Empty question | No request sent (button disabled, Enter no-op) |
| Symbol not in scan | 404 → show "Symbol not in current scan" in red |
| AI provider fails | Show error message inline in red, input stays editable |
| Network timeout | Show "Request timed out" inline |

## What This Does Not Do

- No conversation history / multi-turn threading — each ask is independent
- No caching — ad-hoc questions should always be fresh
- Does not require thesis to be loaded first — Q&A works even if thesis is still loading
- Does not add suggested questions / prompt chips (scope creep)
