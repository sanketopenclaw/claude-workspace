# PriceHawk Generator Redesign — Design Spec
**Date:** 2026-06-08  
**Scope:** G2 (reviews), G3 (comparisons), G4 (buying guides), G1 (category/brand hubs), shared lib, terminal-driven single-page flow

---

## Problem

692 WP drafts were deleted — content quality insufficient. Root cause: all generators ignore rich product data already scraped. Instead they use:

- Regex spec extraction from product name (misses most specs)
- Static pre-written verdicts keyed on `price_segment` — identical prose for every product in same segment
- Category-level FAQs — same 4 questions for every product review

Products already have:
- `specifications` object — full Amazon spec table (wattage, capacity, material, controller type, temp range, included components, dimensions, etc.)
- `_features[]` — Amazon bullet points = actual product differentiators per SKU

---

## Architecture

### Shared Library (new)

**`scripts/lib/wp.js`** — WP REST helpers  
- `wpFindPage(slug)` → existing page or null  
- `wpUpsertPage({ title, slug, content }, dryRun)` → create/update draft  
Currently duplicated across all 4 generators — extract once.

**`scripts/lib/content.js`** — content building blocks  
- `asciDisclosure()` → affiliate disclosure HTML  
- `methodologyBlock(context)` → methodology disclaimer HTML  
- `specTable(specifications)` → HTML table from `specifications` object  
- `featureHighlights(features, maxItems)` → HTML list from `_features[]`  
- `priceContext(lastPrice, priceSegment)` → price-anchored text fragment  
- `familySizeFromCapacity(capacityStr)` → "1–2 people" / "family of 4" etc.  
- `loadProducts(categories)` → ASIN → product map  
- `resolveOffer(product)` → normalised offer object (handles array vs object schema)  

**`scripts/lib/schema.js`** — schema.org JSON-LD builders  
- `reviewSchema(product, catSlug, link)` → Review + Product + FAQPage + BreadcrumbList  
- `comparisonSchema(p1, p2, catSlug)` → ItemList + FAQPage + BreadcrumbList  
- `guideSchema(catSlug, products)` → ItemList + FAQPage + BreadcrumbList  

---

## G2 — Review Generator (`generate-reviews.js`)

### Spec table
Read `product.specifications` directly. Skip internal keys (`_features`, keys starting with `_`). Render all present keys as rows. Fall back to name-regex extraction only if `specifications` is empty.

### Intro paragraph
```
[Name] is a [wattage]W, [capacity] [catLabel] with [controllerType] controls.
```
Assembled from spec fields. Reads `Output Wattage`, `Capacity`, `Controller Type` (or `Control Method`). No fabrication — only fields that exist.

### Key features section (new)
Read `_features[]` — render first 3 items verbatim as bulleted list under "What Makes This Stand Out". No transformation or filtering — use the text exactly as scraped. If `_features` empty or missing, omit section entirely.

### Verdict
Spec-grounded and segment-anchored (no price numbers — `display_price_publicly: false`):
```
[Name] is a [capacity], [wattage]W [catLabel] in the [segment] range.
[Segment copy]. [Top differentiator from _features[0] if present].
```
Segment copy (budget/mid-range/premium/flagship) kept but preceded by actual spec context, not used alone.

### Who Should Buy
Derived from specs, not static:
- Capacity → family size mapping  
- Wattage → use intensity  
- Presets → beginner vs. manual-cook preference  
- Keep-warm / auto-shutoff → safety/convenience flags  

### FAQs
Keep category-level (still valid, not product-specific). No change needed.

---

## G3 — Comparison Generator (`generate-comparisons.js`)

### Spec table
Build unified table from both `product.specifications` objects. Union of all keys. Show value or "—" per product.

### "Which One Should You Buy?" section
Actual reasoning logic:

1. **Price diff**: if `last_price` available for both, state the ₹ difference
2. **Capacity winner**: if capacity differs → route to family-size use case  
3. **Wattage winner**: if wattage differs → "faster preheat / larger batches"  
4. **Feature diff**: unique features in `_features[]` of each product  
5. **Segment match**: if same segment, recommend based on spec advantage; if different, frame as budget vs. premium  

"Choose A if..." copy is generated from actual spec comparison — not from `specs1.slice(0,2)`.

---

## G4 — Buying Guide Generator (`generate-buying-guides.js`)

### Product picks
Sort by `last_price` (ascending) for budget guides. For "best overall" use composite score: wattage + capacity + feature count from `_features[]`. Each pick includes:
- 2–3 spec highlights from `specifications`  
- Top `_features[0]` differentiator  
- Price segment label  

### Budget guide intro
Uses actual price floor/ceiling from products in category: `"Covers [catLabel]s from ₹[min] to ₹[max]"` — not static copy.

---

## G1 — Category Hub + Brand Pages (`generate-phase1-content.js`)

### Product listings
Each product listed with real specs from `specifications` (not name-parsed). Price shown as segment label only (`display_price_publicly: false` respected).

### Brand pages
List products for that brand with spec highlights. No changes to brand filtering logic (TRUSTED_BRAND_SLUGS stays).

---

## Part 2 — Terminal-Driven Single Page Flow

### New script: `scripts/push-page.js`
```
node scripts/push-page.js --slug review-philips-B0XXXX --title "..." --file tmp/draft.html
```
Reads HTML from `--file`, upserts WP draft. Exit 0 on success. No logic — pure push utility.

### Workflow
1. User requests: `"generate review for [ASIN or product name]"`  
2. Claude reads product from `data/products/[cat].json`  
3. Claude writes full page HTML in terminal response  
4. User reviews in terminal  
5. User approves → Claude writes to `tmp/draft.html`, runs `push-page.js`  
6. Claude confirms WP draft URL  

No LLM API costs. Uses Claude Code session (Max plan).

---

## File Changes Summary

| File | Change |
|------|--------|
| `scripts/lib/wp.js` | New — WP REST helpers |
| `scripts/lib/content.js` | New — shared HTML builders |
| `scripts/lib/schema.js` | New — schema.org builders |
| `scripts/push-page.js` | New — push single page to WP |
| `scripts/generate-reviews.js` | Rewrite HTML builder, use lib |
| `scripts/generate-comparisons.js` | Rewrite comparison logic, use lib |
| `scripts/generate-buying-guides.js` | Rewrite product picks, use lib |
| `scripts/generate-phase1-content.js` | Use lib, real specs in listings |

---

## Constraints

- `display_price_publicly: false` — never show price numbers in output HTML  
- `status: 'draft'` — all WP pushes remain drafts  
- No fabricated testing claims — only what `specifications` and `_features` contain  
- Methodology block on every page  
- ASCI disclosure above fold on every page  
- Affiliate links: `rel="nofollow sponsored noopener"` always  
