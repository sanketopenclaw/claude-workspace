# MCP Integrations Design
**Date:** 2026-06-06  
**Scope:** Additive MCP bolt-ons for Trading (Tesseract) and Job Auto-Apply  
**Approach:** Phase 1 = signal enhancement, Phase 2 = automation closers. Zero existing code breakage.

---

## Cross-Cutting Rules

- Every Firecrawl MCP call wrapped in try/catch
- On failure: log `FIRECRAWL_CREDIT_EXHAUSTED` or `FIRECRAWL_ERROR`, return null
- Caller always degrades gracefully to existing behavior
- Firecrawl is never on the critical path

---

## Track A: Trading (Tesseract)

### Phase 1A — TV Screener Pre-filter

**File:** `nse/tvScreenerFilter.js`  
**MCP:** `tradingview-screener` → `custom_query`

**What it does:**  
Queries TV Screener with base criteria common to all 5 strategies. Returns filtered symbol list. Scanner uses this list instead of full N500, reducing candle-fetch overhead.

**Criteria:**
- `close > SMA(200)`
- `volume > Avg(volume, 30) * 1.5`
- `RSI(14) between 40 and 75`
- Max 150 results

**Integration point:**  
Scanner entry point receives optional `symbolList` override. If `tvScreenerFilter` returns results, pass them in. If MCP call fails → pass undefined → existing full-N500 behavior unchanged.

```js
// nse/scanner.js (only change)
const filtered = await tvScreenerFilter().catch(() => undefined);
await runScan({ symbolOverride: filtered });
```

**Failure behavior:** MCP error → undefined → full N500 scan proceeds normally.

---

### Phase 1B — Firecrawl News Enrichment

**File:** `shared/firecrawlNews.js`  
**MCP:** `firecrawl` → `firecrawl_search`

**What it does:**  
Fetches richer news articles for a given ticker. Called from existing conviction scorer alongside (not replacing) current Google News fetch. Merges results before scoring.

**Query:** `"{TICKER} NSE stock news"`, top 3 results  
**No caching** — news is time-sensitive  

**Integration point:**  
Conviction scorer's news fetch section:
```js
const [googleNews, firecrawlNews] = await Promise.allSettled([
  fetchGoogleNews(ticker),
  fetchFirecrawlNews(ticker)   // new
]);
const articles = [...(googleNews.value ?? []), ...(firecrawlNews.value ?? [])];
```

**Failure behavior:** `firecrawlNews` returns null → scorer uses Google News only, no change to scoring logic.

---

## Track B: Job Auto-Apply

### Phase 1 — Firecrawl Job Monitor

**File:** `job-autoapply/firecrawlMonitor.js`  
**MCP:** `firecrawl` → `firecrawl_monitor_create`, `firecrawl_monitor_check`

**What it does:**  
Creates persistent monitors on international job boards. When new postings detected, parses structured data and inserts into existing jobs DB using the same schema existing scrapers produce.

**Job boards monitored:**
- LinkedIn Jobs
- Indeed
- Seek (AU)
- WorkInAustralia

**No Indian portals** (Naukri, Shine, etc.)

**Extracted schema:**
```js
{ title, company, location, url, description, posted_date, source: 'firecrawl' }
```

**Polling mechanism:** `firecrawl_monitor_create` sets up the monitor. A new cron (every 2h) calls `firecrawl_monitor_check` per monitor ID, diffs against last-seen job URLs stored in local JSON file, inserts new records into DB.

**Integration point:**  
New standalone service. Writes to existing `jobs` DB table. Existing scrapers continue running on their own cron unmodified.

**Failure behavior:** Monitor fails → logs error → existing scrapers continue unchanged.

---

### Phase 2A — Gmail Job Tracking

**File:** `job-autoapply/gmailTracker.js`  
**MCP:** `claude_ai_Gmail` → `create_draft`, `search_threads`, `label_thread`, `create_label`

**What it does:**  
Two functions:

1. **On apply:** Creates Gmail draft with formatted cover letter email. Labels it `JOB/APPLIED`.
2. **Reply poller (cron, every 4h):** Searches threads from domains: `linkedin.com`, `greenhouse.io`, `lever.co`, `myworkdayjobs.com`, `seek.com.au`, `indeed.com`, `workInAustralia.com.au`. Detects interview invites (subject contains "interview", "call", "invite") or rejections ("unfortunately", "not moving forward"). Updates job status in DB. Labels thread accordingly.

**Labels created on first run:**
- `JOB/APPLIED`
- `JOB/REPLIED`
- `JOB/INTERVIEW`
- `JOB/REJECTED`

**Integration point:**  
Existing apply button handler calls `gmailTracker.onApply(job, coverLetter)` after existing apply logic completes. Non-blocking (fire-and-forget with error swallow).

**Failure behavior:** Gmail MCP error → logged, apply flow unaffected.

---

### Phase 2B — Playwright ATS Submitter

**File:** `job-autoapply/atsSubmitter.js`  
**MCP:** `plugin:playwright` → `browser_navigate`, `browser_fill_form`, `browser_click`, `browser_file_upload`, `browser_snapshot`

**What it does:**  
"Auto-Submit" button in existing job apply modal. Navigates to ATS URL, detects platform, fills standard fields, uploads resume PDF, submits application.

**Supported ATS platforms:**
- Workday (`myworkdayjobs.com`)
- Greenhouse (`boards.greenhouse.io`)
- Lever (`jobs.lever.co`)

**Standard fields filled:**
- First name, last name, email, phone
- Resume PDF upload
- Cover letter text field (if present)
- LinkedIn URL (if present)

**Return states:**
- `SUBMITTED` → marks job in DB, shows success
- `UNSUPPORTED` → modal shows "Submit manually" with ATS URL
- `ERROR` → logs, modal shows error, falls back to manual

**Integration point:**  
New "Auto-Submit" button in existing job apply modal. Calls `atsSubmitter.submit(job, resumePath, coverLetter)`. Existing "Copy Cover Letter" / manual flow unchanged.

**Failure behavior:** Any Playwright error → returns `ERROR` state → user submits manually.

---

## File Map

```
nse/
  tvScreenerFilter.js          ← new

shared/
  firecrawlNews.js             ← new

job-autoapply/
  firecrawlMonitor.js          ← new
  gmailTracker.js              ← new
  atsSubmitter.js              ← new
```

**Existing files touched (minimal):**
- `nse/scanner.js` — 3-line change to accept symbolOverride
- `nse/convictionScorer.js` — merge firecrawlNews into news array
- `job-autoapply/applyHandler.js` — fire-and-forget gmailTracker.onApply call
- `job-autoapply/applyModal.jsx` — add Auto-Submit button

---

## Out of Scope

- Replacing existing scrapers (additive only)
- Gmail daily digest (dropped by user)
- Indian job portals
- Any Notion/Google Drive/Meta Ads integration
- Auto-sending emails (drafts only)
