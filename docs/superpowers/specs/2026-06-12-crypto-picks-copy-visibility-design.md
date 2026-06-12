# Crypto Picks — Copy-to-Clipboard + Visibility Design Spec

## Problem

1. Price values (stop, entry, 2R target) and symbol in pick cards cannot be copied — requires manual text selection.
2. Price values are too small to read at a glance (12px for values, 7px for percentage sub-labels).

## Goal

- Each data field (symbol, stop, entry, 2R) is independently clickable to copy its value to clipboard with a brief flash confirmation.
- Price values and symbol text are legible without straining.

## Scope

One file: `tesseract-scan/dashboard/public/crypto.jsx`

Two components affected:
- `ScanFeedItem` — feed/list pick rows (main scan view)
- `PickCard` — expanded card view (strategy column grid)

---

## Copy Behaviour

### Mechanism
- `navigator.clipboard.writeText(value)` on click
- Local `copied` state (string key, e.g. `'stop'|'entry'|'2r'|'symbol'`) per component instance
- Flash: the **label** text above the value swaps to `✓` for 900ms then reverts
- `cursor: 'copy'` on copyable elements; no tooltip needed

### Copyable fields and values written to clipboard

| Field | Value copied |
|-------|-------------|
| Symbol | `pick.symbol` (e.g. `SOLUSDT`) |
| Stop | raw number string, same as displayed (e.g. `174.8000`) |
| Entry | `pick.entryHigh` formatted same as displayed |
| 2R Target | `pick.target2R` formatted same as displayed |

---

## Size Changes

### `ScanFeedItem` — `priceBox` helper

| Property | Before | After |
|----------|--------|-------|
| Box padding | `4px 9px` | `6px 12px` |
| Label (STOP/ENTRY/2R) | `10px` | `10px` (unchanged) |
| Value text | `12px` | `16px` |
| Sub text (%-values) | `7px` | `9px` |
| Symbol | `20px` | `22px` |

### `PickCard` — `rowCell` helper

| Property | Before | After |
|----------|--------|-------|
| Label | `9px` | `10px` |
| Value text | `12px` | `15px` |
| Sub text | `9px` | `9px` (unchanged) |
| Symbol | `16px` | `19px` |

---

## Implementation Detail

### `ScanFeedItem`

Add state:
```js
const [copied, setCopied] = useState(null);
```

Add helper:
```js
const copyField = (key, val) => {
  navigator.clipboard.writeText(String(val));
  setCopied(key);
  setTimeout(() => setCopied(null), 900);
};
```

Update `priceBox` signature to accept `copyKey` and `rawVal`:
```js
const priceBox = (label, value, sub, color, copyKey, rawVal) => (
  <div
    onClick={() => copyField(copyKey, rawVal)}
    style={{ padding: '6px 12px', cursor: 'copy', ... }}
  >
    <div style={{ fontSize: 10, ... }}>{copied === copyKey ? '✓' : label}</div>
    <div style={{ fontSize: 16, fontWeight: 700, color, fontFamily: 'var(--font-mono)' }}>{value}</div>
    {sub && <div style={{ fontSize: 9, color: 'var(--fg-3)' }}>{sub}</div>}
  </div>
);
```

Update call sites:
```js
{priceBox('STOP',  fmt(pick.stop),     `-${stopPct}%`, 'var(--bear)', 'stop',  pick.stop)}
{priceBox('ENTRY', fmt(pick.entryHigh), 'next bar',    'var(--fg)',   'entry', pick.entryHigh)}
{priceBox('2R',    fmt(pick.target2R),  `+${tgtPct}%`, 'var(--bull)', '2r',   pick.target2R)}
```

Symbol span — wrap with onClick:
```js
<span
  onClick={() => copyField('sym', pick.symbol)}
  style={{ fontSize: 22, fontWeight: 700, color: meta.color, fontFamily: 'var(--font-mono)', cursor: 'copy', letterSpacing: '0.01em' }}
>
  {copied === 'sym' ? '✓' : pick.symbol}
</span>
```

### `PickCard`

Same pattern — add `const [copied, setCopied] = useState(null)` and `copyField` helper.

Update `rowCell` to accept `copyKey` + `rawVal`:
```js
const rowCell = (label, value, sub, color, last, copyKey, rawVal) => (
  <div
    onClick={copyKey ? () => copyField(copyKey, rawVal) : undefined}
    style={{ flex: 1, padding: '9px 12px', textAlign: 'center', cursor: copyKey ? 'copy' : 'default', borderRight: last ? 'none' : '1px solid var(--line)' }}
  >
    <div style={{ fontSize: 10, color: 'var(--fg-3)', ... }}>{copied === copyKey ? '✓' : label}</div>
    <div style={{ fontSize: 15, fontFamily: 'var(--font-mono)', color: color || 'var(--fg)', fontWeight: 700 }}>{value}</div>
    {sub && <div style={{ fontSize: 9, ... }}>{sub}</div>}
  </div>
);
```

Update call sites:
```js
{rowCell('STOP LOSS',  cFmt(pick.stop),     `−${stopPct}%`, 'var(--bear)', false, 'stop',  pick.stop)}
{rowCell('ENTRY ZONE', ...,                  'next bar open','var(--fg)',   false, 'entry', pick.entryHigh)}
{rowCell('TARGET 2R',  cFmt(pick.target2R),  `+${tgtPct}%`, 'var(--bull)', true,  '2r',   pick.target2R)}
```

Symbol span in PickCard header:
```js
<span
  onClick={() => copyField('sym', pick.symbol)}
  style={{ fontSize: 19, fontWeight: 700, color: TEAL, fontFamily: 'var(--font-mono)', cursor: 'copy', letterSpacing: '0.02em' }}
>
  {copied === 'sym' ? '✓' : pick.symbol}
</span>
```

---

## Build Step

After editing `crypto.jsx`, run:
```bash
cd tesseract-scan && node dashboard/build.js
```

`bundle.js` is what gets served — source edits have no effect until rebuilt.
