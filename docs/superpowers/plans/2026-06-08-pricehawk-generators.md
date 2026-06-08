# PriceHawk Generator Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite G1–G4 content generators to use rich `specifications` + `_features` product data, extract shared lib to eliminate duplication, and add a `push-page.js` utility for terminal-driven single-page generation.

**Architecture:** Three shared lib modules (`lib/wp.js`, `lib/content.js`, `lib/schema.js`) replace duplicated code across all generators. Each generator is rewritten to use the lib and produce product-specific prose grounded in real spec data. A new `push-page.js` utility accepts pre-written HTML and pushes it to WP as a draft.

**Tech Stack:** Node.js, axios, WordPress REST API, dotenv. No new dependencies required.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `scripts/lib/wp.js` | Create | WP REST helpers — findPage, upsertPage, makeAuth |
| `scripts/lib/content.js` | Create | HTML builders — specTable, featureHighlights, disclosure, methodology, loadProducts, resolveOffer |
| `scripts/lib/schema.js` | Create | schema.org JSON-LD builders — review, comparison, guide |
| `scripts/lib/__tests__/content.test.js` | Create | Unit tests for content.js functions |
| `scripts/push-page.js` | Create | CLI: read HTML file → upsert WP draft |
| `scripts/generate-reviews.js` | Rewrite | Use lib; spec-grounded intro, verdict, who-should-buy |
| `scripts/generate-comparisons.js` | Rewrite | Use lib; real spec comparison logic |
| `scripts/generate-buying-guides.js` | Rewrite | Use lib; price-sorted picks with real specs |
| `scripts/generate-phase1-content.js` | Modify | Use lib; real specs in product listings |

---

## Task 1: Create `scripts/lib/wp.js`

**Files:**
- Create: `scripts/lib/wp.js`

- [ ] **Step 1: Create the file**

```javascript
// scripts/lib/wp.js
require('dotenv').config()
const axios = require('axios')

function makeAuth(user, pass) {
  return {
    Authorization: `Basic ${Buffer.from(`${user}:${pass}`).toString('base64')}`,
    'Content-Type': 'application/json',
  }
}

async function wpFindPage(slug, { wp, auth }) {
  try {
    const r = await axios.get(
      `${wp}/wp-json/wp/v2/pages?slug=${slug}&per_page=1&status=draft,publish,private`,
      { headers: auth }
    )
    return r.data?.[0] || null
  } catch { return null }
}

async function wpUpsertPage({ title, slug, content }, { wp, auth, dryRun }) {
  if (dryRun) { console.log(`    [dry] ${slug}`); return null }
  const existing = await wpFindPage(slug, { wp, auth })
  const payload = { title, content, slug, status: 'draft', comment_status: 'closed' }
  try {
    if (existing) {
      const r = await axios.post(`${wp}/wp-json/wp/v2/pages/${existing.id}`, payload, { headers: auth })
      return { action: 'updated', id: r.data.id, link: r.data.link }
    } else {
      const r = await axios.post(`${wp}/wp-json/wp/v2/pages`, payload, { headers: auth })
      return { action: 'created', id: r.data.id, link: r.data.link }
    }
  } catch (e) {
    throw new Error(e.response?.data?.message || e.message)
  }
}

module.exports = { makeAuth, wpFindPage, wpUpsertPage }
```

- [ ] **Step 2: Commit**

```bash
git add scripts/lib/wp.js
git commit -m "feat(pricehawk): add shared WP REST lib"
```

---

## Task 2: Create `scripts/lib/content.js`

**Files:**
- Create: `scripts/lib/content.js`

- [ ] **Step 1: Create the file**

```javascript
// scripts/lib/content.js
const fs = require('fs')
const path = require('path')

function resolveOffer(product) {
  const o = product.offers
  return Array.isArray(o) ? o[0] : (o || {})
}

function specTable(specifications) {
  if (!specifications || typeof specifications !== 'object') return ''
  const rows = Object.entries(specifications)
    .filter(([k]) => !k.startsWith('_'))
    .filter(([, v]) => v && String(v).trim())
  if (!rows.length) return ''
  return `<table style="width:100%;border-collapse:collapse;font-size:14px;margin:16px 0;">
${rows.map(([k, v]) => `  <tr style="border-bottom:1px solid #e8e8e8;">
    <td style="padding:8px 12px;color:#666;width:40%;font-weight:600;">${k}</td>
    <td style="padding:8px 12px;">${String(v)}</td>
  </tr>`).join('\n')}
</table>`
}

function featureHighlights(features, max = 3) {
  if (!Array.isArray(features) || !features.length) return ''
  const items = features.slice(0, max)
  return `<ul style="font-size:15px;line-height:1.8;color:#333;margin:0;padding-left:20px;">
${items.map(f => `  <li>${f}</li>`).join('\n')}
</ul>`
}

function familySizeFromCapacity(capacityStr) {
  if (!capacityStr) return null
  const n = parseFloat(String(capacityStr).replace(/[^0-9.]/g, ''))
  if (isNaN(n)) return null
  if (n <= 2)   return '1–2 people'
  if (n <= 3)   return '2–3 people'
  if (n <= 4.5) return 'a family of 3–4'
  if (n <= 6)   return 'a family of 4–6'
  return 'large families or batch cooking'
}

// Pull first matching key from a specifications object
function getSpecVal(specs, ...keys) {
  for (const k of keys) {
    if (specs[k] && String(specs[k]).trim()) return String(specs[k]).trim()
  }
  return null
}

function asciDisclosure() {
  return `<div style="background:#fff8e1;border-left:4px solid #f9a825;padding:10px 16px;font-size:13px;line-height:1.5;margin-bottom:20px;">
<strong>Affiliate Disclosure:</strong> PriceHawk earns a commission on qualifying purchases made through links on this page. This never influences our editorial recommendations. As an Amazon Associate I earn from qualifying purchases.
</div>`
}

function methodologyBlock(contextSentence) {
  return `<div style="background:#f5f5f5;border:1px solid #e0e0e0;border-radius:6px;padding:14px 18px;margin:24px 0;font-size:13px;line-height:1.6;">
<strong>PriceHawk Methodology:</strong> ${contextSentence} PriceHawk has not independently lab-tested this unit. All opinions are based on documented specifications and aggregated public user feedback — not hands-on testing.
</div>`
}

function loadProducts(categories, prodsDir) {
  const index = {}
  for (const cat of categories) {
    const fp = path.join(prodsDir, `${cat}.json`)
    if (!fs.existsSync(fp)) continue
    const data = JSON.parse(fs.readFileSync(fp, 'utf8'))
    for (const p of (data.products || [])) {
      const offer = resolveOffer(p)
      const asin = offer?.external_id || p._legacy?.asin
      if (asin) index[asin] = { ...p, _catSlug: cat }
    }
  }
  return index
}

module.exports = {
  resolveOffer,
  specTable,
  featureHighlights,
  familySizeFromCapacity,
  getSpecVal,
  asciDisclosure,
  methodologyBlock,
  loadProducts,
}
```

- [ ] **Step 2: Commit**

```bash
git add scripts/lib/content.js
git commit -m "feat(pricehawk): add shared content builders lib"
```

---

## Task 3: Create `scripts/lib/__tests__/content.test.js` and run tests

**Files:**
- Create: `scripts/lib/__tests__/content.test.js`

- [ ] **Step 1: Create test file**

```javascript
// scripts/lib/__tests__/content.test.js
const { test } = require('node:test')
const assert = require('node:assert/strict')
const {
  resolveOffer, specTable, featureHighlights,
  familySizeFromCapacity, getSpecVal,
} = require('../content')

test('specTable renders rows from specifications', () => {
  const html = specTable({ 'Output Wattage': '1400 Watts', 'Capacity': '4.5 litres' })
  assert.ok(html.includes('<table'))
  assert.ok(html.includes('Output Wattage'))
  assert.ok(html.includes('1400 Watts'))
  assert.ok(html.includes('Capacity'))
})

test('specTable skips keys starting with _', () => {
  const html = specTable({ '_features': ['x'], 'Wattage': '1000W' })
  assert.ok(!html.includes('_features'))
  assert.ok(html.includes('Wattage'))
})

test('specTable returns empty string for empty or null specs', () => {
  assert.strictEqual(specTable({}), '')
  assert.strictEqual(specTable(null), '')
  assert.strictEqual(specTable(undefined), '')
})

test('featureHighlights renders first 3 items only', () => {
  const html = featureHighlights(['f1', 'f2', 'f3', 'f4', 'f5'])
  assert.ok(html.includes('f1'))
  assert.ok(html.includes('f3'))
  assert.ok(!html.includes('f4'))
})

test('featureHighlights returns empty string for empty/null', () => {
  assert.strictEqual(featureHighlights([]), '')
  assert.strictEqual(featureHighlights(null), '')
  assert.strictEqual(featureHighlights(undefined), '')
})

test('familySizeFromCapacity maps capacity to household size', () => {
  assert.strictEqual(familySizeFromCapacity('1.5 litres'), '1–2 people')
  assert.strictEqual(familySizeFromCapacity('2.5 litres'), '2–3 people')
  assert.strictEqual(familySizeFromCapacity('4.5 litres'), 'a family of 3–4')
  assert.strictEqual(familySizeFromCapacity('5 litres'), 'a family of 4–6')
  assert.strictEqual(familySizeFromCapacity('8L'), 'large families or batch cooking')
  assert.strictEqual(familySizeFromCapacity(null), null)
  assert.strictEqual(familySizeFromCapacity('no number'), null)
})

test('resolveOffer unwraps array offers', () => {
  const p = { offers: [{ external_id: 'B001' }] }
  assert.strictEqual(resolveOffer(p).external_id, 'B001')
})

test('resolveOffer handles object offers', () => {
  const p = { offers: { external_id: 'B002' } }
  assert.strictEqual(resolveOffer(p).external_id, 'B002')
})

test('resolveOffer returns empty object for missing offers', () => {
  assert.deepStrictEqual(resolveOffer({}), {})
})

test('getSpecVal returns first matching key', () => {
  const specs = { 'Output Wattage': '1400 Watts' }
  assert.strictEqual(getSpecVal(specs, 'Wattage', 'Output Wattage'), '1400 Watts')
})

test('getSpecVal returns null when no key matches', () => {
  assert.strictEqual(getSpecVal({ 'Capacity': '4L' }, 'Wattage', 'Output Wattage'), null)
})
```

- [ ] **Step 2: Run tests — expect all pass**

```bash
cd C:\Claude\pricehawk
node --test scripts/lib/__tests__/content.test.js
```

Expected: all 11 tests pass. If `node:test` not available (Node < 18), install: `npm install --save-dev tap` and adapt to `tap.test`.

- [ ] **Step 3: Commit**

```bash
git add scripts/lib/__tests__/content.test.js
git commit -m "test(pricehawk): unit tests for content lib"
```

---

## Task 4: Create `scripts/lib/schema.js`

**Files:**
- Create: `scripts/lib/schema.js`

- [ ] **Step 1: Create the file**

```javascript
// scripts/lib/schema.js

function slugify(s) {
  return (s || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
}

function reviewSchema({ name, brand, catLabel, catSlug, link, faqs, asinSlug }) {
  return {
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'Review',
        name: `${name} Review`,
        reviewBody: `${name} — ${catLabel} review for Indian buyers.`,
        author: { '@type': 'Organization', name: 'PriceHawk' },
        publisher: { '@type': 'Organization', name: 'PriceHawk', url: 'https://pricehawk.in' },
        datePublished: new Date().toISOString().split('T')[0],
        itemReviewed: {
          '@type': 'Product',
          name,
          brand: { '@type': 'Brand', name: brand },
          category: catLabel,
          offers: {
            '@type': 'Offer',
            url: link,
            priceCurrency: 'INR',
            availability: 'https://schema.org/InStock',
            seller: { '@type': 'Organization', name: 'Amazon India' },
          },
        },
      },
      {
        '@type': 'BreadcrumbList',
        itemListElement: [
          { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://pricehawk.in/' },
          { '@type': 'ListItem', position: 2, name: `Best ${catLabel}s in India`, item: `https://pricehawk.in/best-${catSlug}/` },
          { '@type': 'ListItem', position: 3, name: `${name} Review`, item: `https://pricehawk.in/${asinSlug}/` },
        ],
      },
      ...(faqs.length ? [{
        '@type': 'FAQPage',
        mainEntity: faqs.map(([q, a]) => ({
          '@type': 'Question', name: q,
          acceptedAnswer: { '@type': 'Answer', text: a },
        })),
      }] : []),
    ],
  }
}

function comparisonSchema({ name1, name2, catLabel, catSlug, link1, link2, faqs, slug }) {
  return {
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'ItemList',
        name: `${name1} vs ${name2} — ${catLabel} Comparison`,
        description: `Detailed specification comparison of ${name1} and ${name2} for Indian buyers.`,
        numberOfItems: 2,
        itemListElement: [
          { '@type': 'ListItem', position: 1, name: name1, url: link1 },
          { '@type': 'ListItem', position: 2, name: name2, url: link2 },
        ],
      },
      {
        '@type': 'BreadcrumbList',
        itemListElement: [
          { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://pricehawk.in/' },
          { '@type': 'ListItem', position: 2, name: `Best ${catLabel}s in India`, item: `https://pricehawk.in/best-${catSlug}/` },
          { '@type': 'ListItem', position: 3, name: `${name1} vs ${name2}`, item: `https://pricehawk.in/${slug}/` },
        ],
      },
      ...(faqs.length ? [{
        '@type': 'FAQPage',
        mainEntity: faqs.map(([q, a]) => ({
          '@type': 'Question', name: q,
          acceptedAnswer: { '@type': 'Answer', text: a },
        })),
      }] : []),
    ],
  }
}

function guideSchema({ catLabel, catSlug, slug, products }) {
  return {
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'ItemList',
        name: `Best ${catLabel} in India`,
        numberOfItems: products.length,
        itemListElement: products.map((p, i) => ({
          '@type': 'ListItem', position: i + 1, name: p.name, url: p.link,
        })),
      },
      {
        '@type': 'BreadcrumbList',
        itemListElement: [
          { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://pricehawk.in/' },
          { '@type': 'ListItem', position: 2, name: `Best ${catLabel} in India`, item: `https://pricehawk.in/${slug}/` },
        ],
      },
    ],
  }
}

module.exports = { reviewSchema, comparisonSchema, guideSchema, slugify }
```

- [ ] **Step 2: Commit**

```bash
git add scripts/lib/schema.js
git commit -m "feat(pricehawk): add schema.org builders lib"
```

---

## Task 5: Rewrite `scripts/generate-reviews.js`

**Files:**
- Modify: `scripts/generate-reviews.js`

Replace the entire file. Key changes: use lib modules, read `specifications` for spec table, read `_features[]` for key features section, build spec-grounded intro and verdict.

- [ ] **Step 1: Replace `generate-reviews.js`**

```javascript
// scripts/generate-reviews.js
require('dotenv').config()
const fs   = require('fs')
const path = require('path')

const { makeAuth, wpUpsertPage } = require('./lib/wp')
const {
  resolveOffer, specTable, featureHighlights,
  familySizeFromCapacity, getSpecVal, asciDisclosure,
  methodologyBlock, loadProducts,
} = require('./lib/content')
const { reviewSchema, slugify } = require('./lib/schema')

const WP   = (process.env.WORDPRESS_URL || '').replace(/\/$/, '')
const USER = process.env.WORDPRESS_USERNAME
const PASS = process.env.WORDPRESS_APP_PASSWORD
const TAG  = process.env.AMAZON_AFFILIATE_TAG || 'pricehawkin-21'
const AUTH = makeAuth(USER, PASS)

const PRODS_DIR  = path.join(__dirname, '../data/products')
const QUEUE_FILE = path.join(__dirname, '../data/content/phase1_queue.json')
const YEAR = new Date().getFullYear()

const KITCHEN = ['air-fryers','mixer-grinders','coffee-machines','induction-cooktops',
                 'electric-kettles','food-processors','hand-blenders','sandwich-makers','rice-cookers']

const CAT_LABELS = {
  'air-fryers':'Air Fryer','mixer-grinders':'Mixer Grinder','coffee-machines':'Coffee Machine',
  'induction-cooktops':'Induction Cooktop','electric-kettles':'Electric Kettle',
  'food-processors':'Food Processor','hand-blenders':'Hand Blender',
  'sandwich-makers':'Sandwich Maker','rice-cookers':'Rice Cooker',
}

// Segment copy — appended after spec-grounded context, not used alone
const SEGMENT_COPY = {
  budget:      'A cost-effective entry point for households new to this category.',
  'mid-range': 'A well-specified option for regular everyday use.',
  premium:     'A premium build with more precise controls — suited for frequent, heavy use.',
  flagship:    'Top-tier specification. Best for large families or daily intensive cooking.',
}

const CAT_FAQS = {
  'air-fryers': [
    ['Is this air fryer good for Indian cooking?', 'Air fryers work well for Indian snacks like samosas, pakoras, and tandoori items. Most models reaching 200°C handle these well. Check the capacity to ensure it fits the quantities you cook.'],
    ['How much electricity does an air fryer use?', 'Most home air fryers (1200–1800W) cost approximately ₹4–8 per hour at standard Indian electricity rates. They are generally more energy-efficient than conventional ovens for small quantities.'],
    ['Does the capacity on the box match real usable space?', 'Marketed capacity includes the full basket volume. Usable cooking space is typically 60–70% of stated capacity. A "4.5L" air fryer realistically holds 2–3 servings at once.'],
    ['Can I use the air fryer without oil?', 'Yes — that is the primary use case. A light spray of oil on some foods helps browning, but many foods (chips, frozen snacks, reheating) need none at all.'],
  ],
  'mixer-grinders': [
    ['What wattage is enough for Indian cooking?', '500–750W handles most household grinding. 750W+ suits families grinding large batches of wet batter frequently.'],
    ['Are stainless steel jars better than polycarbonate?', 'Stainless steel is more durable, does not stain from turmeric, and is easier to clean. Polycarbonate allows you to see contents but can scratch and retain odours.'],
    ['What warranty should I look for?', 'Minimum 2 years on the motor. Indian brands like Preethi and Butterfly typically offer 5-year motor warranties on premium models.'],
    ['Can a mixer grinder make nut butters?', 'Most standard mixer grinders are not designed for nut butters — they require prolonged high-torque operation.'],
  ],
  'coffee-machines': [
    ['Which type suits Indian tastes?', 'For South Indian filter coffee: stainless drip filters. For café-style espresso: pump machines (9+ bar). Capsule machines offer convenience but have ongoing pod costs.'],
    ['How often does a coffee machine need cleaning?', 'Daily rinse after each use. Monthly descaling is essential in India given hard water in most cities.'],
    ['Are pod machines worth it in India?', 'Capsule cost in India is ₹40–80 per cup versus ₹15–25 for ground coffee. Convenience is the main trade-off.'],
    ['What is bar pressure?', 'Bar measures brewing pressure. True espresso requires 9 bar minimum. Lower-rated machines produce strong coffee but not technically espresso.'],
  ],
  'induction-cooktops': [
    ['What cookware works on induction?', 'Only ferromagnetic cookware — cast iron and most stainless steel. Test with a fridge magnet: if it sticks to the bottom, it works.'],
    ['How much electricity does induction use vs gas?', 'Induction is 85–90% efficient versus 40–55% for gas. Typically costs ₹5–8 per hour, lower than LPG per equivalent heat output.'],
    ['Is induction safe for children?', 'The surface does not get directly hot — only the cookware heats. Most models auto-shut off when cookware is removed.'],
    ['Can I cook at full speed like a gas stove?', 'High-wattage induction (1800–2000W) heats faster than most domestic gas burners and offers instant power adjustment.'],
  ],
  'electric-kettles': [
    ['How long does boiling take?', 'A 1500W kettle boils 1 litre in ~3–4 minutes. 1800–2200W cuts this to ~2.5 minutes.'],
    ['Stainless steel or plastic kettle?', 'Stainless steel interior is recommended — no plastic taste, more hygienic, longer-lasting. Check the interior material specifically.'],
    ['What capacity should I choose?', '1–1.2L suits 1–2 people. 1.5–1.7L is standard for 3–4 people. 2L+ for larger households.'],
    ['Do I need temperature control?', 'Only if you brew green tea (70–80°C) or pour-over coffee. For chai and instant coffee, single-boil at 100°C is sufficient.'],
  ],
  'food-processors': [
    ['Food processor vs mixer grinder?', 'A mixer grinder handles wet grinding (batter, chutneys). A food processor handles solid prep (chopping, slicing, dough). Most households benefit from both.'],
    ['How many watts do I need?', '600W handles most household tasks. 800–1000W suits heavy continuous use.'],
    ['Are attachments easy to clean?', 'Most modern food processors have dishwasher-safe parts. Wide-mouth bowls with few crevices clean significantly faster.'],
    ['Can it replace a mixer grinder?', 'Partially. Food processors handle some wet grinding but most lack sustained power for idli/dosa batter.'],
  ],
  'hand-blenders': [
    ['Better than a mixer grinder for soups?', 'For blending soups directly in the pot: yes. Eliminates the transfer step and risk of hot liquid spills.'],
    ['What power is sufficient?', '250–400W covers smoothies, soups, and baby food. 600–800W is better for tougher tasks or extended blending.'],
    ['Do attachments make a difference?', 'A chopper attachment effectively adds a mini food processor. A whisk handles cream and egg whites. Buying with attachments can replace two or three separate appliances.'],
    ['How do I avoid splatter?', 'Submerge the blade head fully before switching on. Start at low speed and increase gradually.'],
  ],
  'sandwich-makers': [
    ['Sandwich maker vs grill?', 'Basic sandwich makers seal and toast. Grill plates add grill marks and work for paninis and vegetables. Multi-use models offer removable plates for both.'],
    ['How do I prevent sticking?', 'Light cooking spray or brushing with oil before each use. Quality non-stick coatings significantly reduce sticking without any addition.'],
    ['What wattage is needed?', '750–900W is standard and adequate. Higher wattage preheats faster and maintains temperature better for multiple sandwiches.'],
    ['Are removable plates worth it?', 'For cleaning ease: yes. For basic daily sandwiches, fixed plates are simpler and equally effective.'],
  ],
  'rice-cookers': [
    ['What capacity do I need?', '1L for 1–2 people. 1.8L for 3–4 people — the most common Indian household size. 2.8L+ for larger families.'],
    ['More efficient than a pressure cooker?', 'Different tools. Rice cookers deliver consistent results without monitoring. Pressure cookers are faster and more versatile. Many households use both.'],
    ['Can I cook dal or khichdi?', 'Yes — most rice cookers handle simple dal and khichdi. A multi-cook setting works better for heavily spiced dishes.'],
    ['How important is non-stick?', 'Significant for cleaning ease. Quality coatings last 3–5 years with gentle utensils. Metal utensils will damage the coating.'],
  ],
}

function titleCase(s) {
  return (s || '').replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function buildIntro(name, specs, catLabel, seg) {
  const wattage  = getSpecVal(specs, 'Output Wattage', 'Wattage', 'Wattage Rating')
  const capacity = getSpecVal(specs, 'Capacity', 'Volume', 'Bowl Capacity', 'Jug Capacity')
  const ctrl     = getSpecVal(specs, 'Controller Type', 'Control Method', 'Controls')
  const minT     = getSpecVal(specs, 'Min Temperature Setting', 'Minimum Temperature')
  const maxT     = getSpecVal(specs, 'Max Temperature Setting', 'Maximum Temperature')
  const material = getSpecVal(specs, 'Material Type', 'Inner Material', 'Material')

  const parts = []
  if (capacity && wattage) parts.push(`a ${capacity}, ${wattage} ${catLabel.toLowerCase()}`)
  else if (capacity) parts.push(`a ${capacity} ${catLabel.toLowerCase()}`)
  else if (wattage)  parts.push(`a ${wattage} ${catLabel.toLowerCase()}`)
  else parts.push(`a ${catLabel.toLowerCase()}`)

  if (ctrl) parts.push(`with ${ctrl.toLowerCase()} controls`)
  if (minT && maxT) parts.push(`operating between ${minT.replace(' Degrees Celsius','°C')} and ${maxT.replace(' Degrees Celsius','°C')}`)
  if (material && !parts.join(' ').includes(material.toLowerCase())) parts.push(`${material.toLowerCase()} construction`)

  const familySize = capacity ? familySizeFromCapacity(capacity) : null
  const familyNote = familySize ? ` Suited for ${familySize}.` : ''

  const segCopy = SEGMENT_COPY[seg] || SEGMENT_COPY['mid-range']
  return `${name} is ${parts.join(', ')}. ${segCopy}${familyNote}`
}

function buildWhoShouldBuy(specs, catLabel, features) {
  const capacity = getSpecVal(specs, 'Capacity', 'Volume', 'Bowl Capacity')
  const ctrl     = getSpecVal(specs, 'Controller Type', 'Control Method')
  const wattage  = getSpecVal(specs, 'Output Wattage', 'Wattage')
  const wAttr    = getSpecVal(specs, 'Special Features', 'Included Components')

  const bullets = []
  if (capacity) {
    const fs = familySizeFromCapacity(capacity)
    if (fs) bullets.push(`Households cooking for ${fs}`)
  }
  if (ctrl && /touch|digital/i.test(ctrl)) {
    bullets.push('Users who prefer digital preset controls over manual dials')
  } else if (ctrl && /manual|knob|analog/i.test(ctrl)) {
    bullets.push('Users who prefer simple manual controls')
  }
  if (wattage) {
    const w = parseFloat(wattage.replace(/[^0-9.]/g, ''))
    if (!isNaN(w) && w >= 1800) bullets.push(`High-power cooking: faster preheat and better performance for larger batches`)
  }
  const hasKeepWarm = features.some(f => /keep.?warm/i.test(f))
  if (hasKeepWarm) bullets.push('Households that need food to stay warm after cooking')
  const hasAutoShut = features.some(f => /auto.?shut|overheat/i.test(f))
  if (hasAutoShut) bullets.push('Safety-conscious buyers — auto shut-off and overheat protection included')

  if (!bullets.length) {
    bullets.push(`Buyers looking for a reliable everyday ${catLabel.toLowerCase()}`)
    bullets.push('Households comparing multiple options in this price segment')
  }

  return `<ul style="font-size:15px;line-height:1.8;color:#333;margin:0;padding-left:20px;">
${bullets.map(b => `  <li>${b}</li>`).join('\n')}
</ul>`
}

function buildReviewHTML(product, catSlug) {
  const name     = product.product_name || product._legacy?.name || 'Product'
  const brand    = titleCase(product.brand_id || '')
  const catLabel = CAT_LABELS[catSlug] || titleCase(catSlug)
  const offer    = resolveOffer(product)
  const asin     = offer.external_id || product._legacy?.asin || ''
  const link     = offer.affiliate_url || `https://www.amazon.in/dp/${asin}?tag=${TAG}`
  const seg      = product.price_segment || product._legacy?.price_segment || 'mid-range'
  const specs    = product.specifications || {}
  const features = specs._features || []
  const faqs     = CAT_FAQS[catSlug] || []

  const intro         = buildIntro(name, specs, catLabel, seg)
  const specsHTML     = specTable(specs)
  const featuresHTML  = featureHighlights(features)
  const whoHTML       = buildWhoShouldBuy(specs, catLabel, features)
  const asinSlug      = `review-${slugify(brand)}-${asin.toLowerCase()}`

  const schema = reviewSchema({ name, brand, catLabel, catSlug, link, faqs, asinSlug })

  const methodCtx = `This assessment is based on published specifications for the ${name}, aggregated user feedback, competitive positioning against comparable models, and PriceHawk's tracked price history.`

  return `${asciDisclosure()}

<nav style="font-size:13px;color:#888;margin-bottom:20px;">
<a href="/" style="color:#666;">Home</a> › <a href="/best-${catSlug}/" style="color:#666;">Best ${catLabel}s in India ${YEAR}</a> › ${name.substring(0, 50)}… Review
</nav>

<p style="font-size:16px;line-height:1.7;color:#333;">${intro}</p>

<div style="background:#f9f9f9;border:1px solid #e0e0e0;border-radius:6px;padding:16px 20px;margin:20px 0;">
  <p style="font-size:12px;color:#888;font-weight:700;text-transform:uppercase;margin:0 0 4px;">${brand}</p>
  <h2 style="font-size:17px;font-weight:700;margin:0 0 12px;line-height:1.4;">${name}</h2>
  <a href="${link}" target="_blank" rel="nofollow sponsored noopener"
     style="display:inline-block;background:#ff9900;color:#111;text-decoration:none;font-size:14px;font-weight:700;padding:9px 20px;border-radius:4px;">
    Check price on Amazon →
  </a>
</div>

<h2 style="font-size:20px;font-weight:700;margin:28px 0 10px;">Full Specifications</h2>
${specsHTML || '<p style="color:#666;font-size:14px;">Refer to the Amazon product page for full specifications.</p>'}

${featuresHTML ? `<h2 style="font-size:20px;font-weight:700;margin:28px 0 10px;">What Makes This Stand Out</h2>\n${featuresHTML}` : ''}

<h2 style="font-size:20px;font-weight:700;margin:28px 0 10px;">Who Should Buy This?</h2>
${whoHTML}

${methodologyBlock(methodCtx)}

<div style="background:#fff3e0;border:1px solid #ffe0b2;border-radius:6px;padding:16px 20px;margin:24px 0;">
  <p style="margin:0 0 10px;font-weight:700;font-size:15px;">Ready to buy or want to check the latest price?</p>
  <a href="${link}" target="_blank" rel="nofollow sponsored noopener"
     style="display:inline-block;background:#ff9900;color:#111;text-decoration:none;font-size:14px;font-weight:700;padding:9px 20px;border-radius:4px;">
    Check price on Amazon India →
  </a>
  <p style="margin:10px 0 0;font-size:12px;color:#999;">Amazon prices change frequently. Click to see the current price.</p>
</div>

${faqs.length ? `<h2 style="font-size:20px;font-weight:700;margin:32px 0 12px;">Frequently Asked Questions</h2>
${faqs.map(([q, a]) => `<details style="border:1px solid #e0e0e0;border-radius:4px;margin-bottom:8px;">
  <summary style="padding:12px 16px;cursor:pointer;font-weight:600;font-size:14px;background:#fafafa;">${q}</summary>
  <div style="padding:12px 16px;font-size:14px;line-height:1.7;color:#333;">${a}</div>
</details>`).join('\n')}` : ''}

<hr style="margin:32px 0;border:none;border-top:1px solid #e0e0e0;">
<p style="font-size:13px;color:#888;">
  <a href="/best-${catSlug}/" style="color:#e65100;font-weight:600;">← Compare all ${catLabel}s in India ${YEAR}</a>
</p>

<script type="application/ld+json">
${JSON.stringify(schema, null, 2)}
</script>`
}

async function main() {
  const args      = process.argv.slice(2)
  const dryRun    = args.includes('--dry-run')
  const catFilter = args.includes('--cat') ? args[args.indexOf('--cat') + 1] : null
  const limit     = args.includes('--limit') ? parseInt(args[args.indexOf('--limit') + 1]) || 9999 : 9999

  if (!WP || !USER || !PASS) { console.error('Missing WP credentials in .env'); process.exit(1) }
  if (!fs.existsSync(QUEUE_FILE)) { console.error('Run content-opportunity-engine.js first'); process.exit(1) }

  const productIndex = loadProducts(KITCHEN, PRODS_DIR)

  const queue = JSON.parse(fs.readFileSync(QUEUE_FILE, 'utf8'))
    .filter(o => o.type === 'review')
    .filter(o => !catFilter || o.category === catFilter)
    .slice(0, limit)

  console.log(`Review queue: ${queue.length} items`)
  const stats = { created: 0, updated: 0, skipped: 0, errors: 0 }

  for (const op of queue) {
    const product = productIndex[op.asin]
    if (!product) { console.log(`  skip ${op.asin} — not in product index`); stats.skipped++; continue }

    const name    = product.product_name || product._legacy?.name || ''
    const brand   = product.brand_id || 'product'
    const asin    = op.asin
    const catSlug = op.category
    const offer   = resolveOffer(product)
    const slug    = `review-${slugify(brand)}-${asin.toLowerCase()}`
    const rawName = name.replace(/\s*[\\|,].*$/, '').trim()
    const short   = rawName.length > 55 ? rawName.substring(0, 52) + '…' : rawName
    const title   = `${short} Review — Worth Buying in India ${YEAR}?`

    try {
      const html   = buildReviewHTML(product, catSlug)
      const result = await wpUpsertPage({ title, slug, content: html }, { wp: WP, auth: AUTH, dryRun })
      if (result) {
        console.log(`  ✓ [${result.action}] ${catSlug} | ${short.substring(0, 45)}`)
        result.action === 'created' ? stats.created++ : stats.updated++
      }
    } catch (e) {
      console.error(`  ✗ ${asin}: ${e.message}`)
      stats.errors++
    }

    await new Promise(r => setTimeout(r, 300))
  }

  console.log(`\n── DONE ────────────────────────`)
  console.log(`Created: ${stats.created} | Updated: ${stats.updated} | Skipped: ${stats.skipped} | Errors: ${stats.errors}`)
  if (dryRun) console.log('(dry run — no WP changes)')
}

main().catch(e => { console.error(e.message); process.exit(1) })
```

- [ ] **Step 2: Dry-run test**

```bash
cd C:\Claude\pricehawk
node scripts/generate-reviews.js --dry-run --cat air-fryers --limit 3
```

Expected: 3 lines like `[dry] review-agaro-b0cbblbdrk` with no errors.

- [ ] **Step 3: Commit**

```bash
git add scripts/generate-reviews.js
git commit -m "feat(pricehawk): rewrite G2 reviews to use rich spec data"
```

---

## Task 6: Rewrite `scripts/generate-comparisons.js`

**Files:**
- Modify: `scripts/generate-comparisons.js`

Key change: "Which Should You Buy?" now does real spec comparison instead of `specs.slice(0,2)`.

- [ ] **Step 1: Add comparison reasoning helper (at top of new file)**

```javascript
// scripts/generate-comparisons.js
require('dotenv').config()
const fs   = require('fs')
const path = require('path')

const { makeAuth, wpUpsertPage } = require('./lib/wp')
const {
  resolveOffer, specTable, asciDisclosure,
  methodologyBlock, loadProducts, getSpecVal,
} = require('./lib/content')
const { comparisonSchema, slugify } = require('./lib/schema')

const WP   = (process.env.WORDPRESS_URL || '').replace(/\/$/, '')
const USER = process.env.WORDPRESS_USERNAME
const PASS = process.env.WORDPRESS_APP_PASSWORD
const TAG  = process.env.AMAZON_AFFILIATE_TAG || 'pricehawkin-21'
const AUTH = makeAuth(USER, PASS)

const PRODS_DIR  = path.join(__dirname, '../data/products')
const QUEUE_FILE = path.join(__dirname, '../data/content/phase1_queue.json')
const YEAR = new Date().getFullYear()

const KITCHEN = ['air-fryers','mixer-grinders','coffee-machines','induction-cooktops',
                 'electric-kettles','food-processors','hand-blenders','sandwich-makers','rice-cookers']

const CAT_LABELS = {
  'air-fryers':'Air Fryer','mixer-grinders':'Mixer Grinder','coffee-machines':'Coffee Machine',
  'induction-cooktops':'Induction Cooktop','electric-kettles':'Electric Kettle',
  'food-processors':'Food Processor','hand-blenders':'Hand Blender',
  'sandwich-makers':'Sandwich Maker','rice-cookers':'Rice Cooker',
}

// Reuse same CAT_FAQS as generate-reviews.js — two comparison-specific FAQs per cat
const CAT_FAQS = {
  'air-fryers': [
    ['Should I choose larger or smaller capacity?', 'For 1–2 people, a 2–3L basket is adequate and heats up faster. For a family of 4, a 4–6L model is the practical choice. Larger does not always mean better — oversized baskets can distribute heat unevenly for small portions.'],
    ['Do all air fryers perform equally at the same wattage?', 'No. Wattage determines maximum heat output, but heating element design, fan placement, and basket construction affect actual cooking performance.'],
  ],
  'mixer-grinders': [
    ['Is there a performance difference between models at similar wattage?', 'Yes. Motor quality, jar shape, and blade design vary significantly even at the same wattage. Indian brands engineered for wet grinding differ even at identical wattages.'],
    ['How long do mixer grinders typically last?', 'With normal use (1–2 sessions daily), a quality mixer grinder should last 5–8 years. Motor overheating from continuous long-duration use is the primary cause of premature failure.'],
  ],
  'coffee-machines': [
    ['Is quality difference noticeable between models?', 'For basic drip coffee, differences are minor. For espresso, pressure and temperature stability matter — higher-end models extract better crema.'],
    ['What ongoing costs should I factor in?', 'Pod costs (₹40–80 each) add up versus ground coffee (₹15–25 per cup). Descaling tablets (₹150–300) are needed every 1–3 months.'],
  ],
  'induction-cooktops': [
    ['Does wattage matter for induction?', '1200–1500W suits smaller vessels. 1800–2000W brings larger vessels to boil faster. The gap is noticeable for large-batch cooking.'],
    ['Which brand has better after-sales service in India?', 'Philips, Havells, and Bajaj have broad service networks. For tier-2/3 cities, established Indian brands often have faster turnaround.'],
  ],
  'electric-kettles': [
    ['Real difference between ₹600 and ₹1,500 kettle?', 'Yes — primarily interior material (stainless vs plastic), keep-warm function, and build longevity. The stainless interior is worth the difference for daily use.'],
    ['How often to descale?', 'Monthly in hard water cities (Delhi, Bengaluru, Mumbai). Limestone build-up reduces heating efficiency and affects taste.'],
  ],
  'food-processors': [
    ['Can one replace the other — food processor vs mixer grinder?', 'Partially. A food processor handles solid prep better. A mixer grinder handles wet grinding better. Both have distinct roles in Indian kitchens.'],
    ['Most useful attachments for Indian cooking?', 'Slicing and chopping discs for vegetables. A dough blade for roti dough. Fine grater for coconut.'],
  ],
  'hand-blenders': [
    ['Can I use a hand blender for hot soups?', 'Yes — submerge the head fully, use a tall container to prevent splatter, and start at low speed.'],
    ['Is higher-wattage noticeably better?', 'For smoothies and soups, 300–400W is adequate. For crushing ice or extended use, 600W+ makes a real difference.'],
  ],
  'sandwich-makers': [
    ['Are removable plates worth the higher cost?', 'For cleaning ease: yes, significantly. For versatility (grill + waffle): yes if you use both. For basic daily sandwiches: fixed plates are equally effective.'],
    ['How to extend the life of a sandwich maker?', 'Wipe plates while still warm — residue is much easier to remove at this stage. Avoid metal utensils on non-stick surfaces.'],
  ],
  'rice-cookers': [
    ['Is a rice cooker worth buying with a pressure cooker?', 'Different use cases. A rice cooker delivers perfectly consistent results without monitoring. A pressure cooker is faster for combined dal+rice cooking.'],
    ['What capacity is right?', '1–1.5L for 1–2 people. 1.8L for 3–4 people. 2.8L+ for families of 5–6.'],
  ],
}

function titleCase(s) {
  return (s || '').replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function shortName(name, maxLen = 50) {
  const clean = (name || '').replace(/\s*[\\|,].*$/, '').trim()
  return clean.length > maxLen ? clean.substring(0, maxLen - 1) + '…' : clean
}

// Build "Choose A if... / Choose B if..." copy from actual spec comparison
function buildPickDecisions(p1, p2, specs1, specs2) {
  const seg1 = p1.price_segment || p1._legacy?.price_segment || 'mid-range'
  const seg2 = p2.price_segment || p2._legacy?.price_segment || 'mid-range'
  const reasons1 = []
  const reasons2 = []

  // Wattage
  const w1 = parseFloat((getSpecVal(specs1, 'Output Wattage', 'Wattage', 'Wattage Rating') || '').replace(/[^0-9.]/g, ''))
  const w2 = parseFloat((getSpecVal(specs2, 'Output Wattage', 'Wattage', 'Wattage Rating') || '').replace(/[^0-9.]/g, ''))
  if (!isNaN(w1) && !isNaN(w2) && w1 !== w2) {
    const wHigh = w1 > w2 ? reasons1 : reasons2
    const wHighVal = w1 > w2 ? getSpecVal(specs1, 'Output Wattage', 'Wattage') : getSpecVal(specs2, 'Output Wattage', 'Wattage')
    wHigh.push(`higher power (${wHighVal}) — faster preheat, better performance for larger batches`)
  }

  // Capacity
  const c1 = parseFloat((getSpecVal(specs1, 'Capacity', 'Volume', 'Bowl Capacity') || '').replace(/[^0-9.]/g, ''))
  const c2 = parseFloat((getSpecVal(specs2, 'Capacity', 'Volume', 'Bowl Capacity') || '').replace(/[^0-9.]/g, ''))
  if (!isNaN(c1) && !isNaN(c2) && c1 !== c2) {
    const cHigh = c1 > c2 ? reasons1 : reasons2
    const cHighVal = c1 > c2 ? getSpecVal(specs1, 'Capacity', 'Volume') : getSpecVal(specs2, 'Capacity', 'Volume')
    cHigh.push(`larger capacity (${cHighVal}) — better for bigger families`)
    const cLow = c1 < c2 ? reasons1 : reasons2
    cLow.push('more compact — quicker to heat for smaller portions')
  }

  // Price segment
  const segOrder = ['budget', 'mid-range', 'premium', 'flagship']
  const si1 = segOrder.indexOf(seg1)
  const si2 = segOrder.indexOf(seg2)
  if (si1 !== si2) {
    if (si1 < si2) { reasons1.push('more budget-friendly'); reasons2.push('more premium build and features') }
    else { reasons2.push('more budget-friendly'); reasons1.push('more premium build and features') }
  }

  // Fallback
  if (!reasons1.length) reasons1.push('its specific combination of specifications matches your primary requirement')
  if (!reasons2.length) reasons2.push('its specific combination of specifications matches your primary requirement')

  return { reasons1, reasons2 }
}

function buildComparisonHTML(p1, p2, catSlug) {
  const name1  = p1.product_name || p1._legacy?.name || 'Product 1'
  const name2  = p2.product_name || p2._legacy?.name || 'Product 2'
  const brand1 = titleCase(p1.brand_id || '')
  const brand2 = titleCase(p2.brand_id || '')
  const short1 = shortName(name1)
  const short2 = shortName(name2)
  const offer1 = resolveOffer(p1)
  const offer2 = resolveOffer(p2)
  const link1  = offer1.affiliate_url || `https://www.amazon.in/dp/${offer1.external_id || p1._legacy?.asin}?tag=${TAG}`
  const link2  = offer2.affiliate_url || `https://www.amazon.in/dp/${offer2.external_id || p2._legacy?.asin}?tag=${TAG}`
  const asin1  = offer1.external_id || p1._legacy?.asin || ''
  const asin2  = offer2.external_id || p2._legacy?.asin || ''
  const catLabel = CAT_LABELS[catSlug] || titleCase(catSlug)
  const faqs   = CAT_FAQS[catSlug] || []
  const specs1 = p1.specifications || {}
  const specs2 = p2.specifications || {}

  // Merged spec table — union of both products' specifications
  const allKeys = [...new Set([
    ...Object.keys(specs1).filter(k => !k.startsWith('_')),
    ...Object.keys(specs2).filter(k => !k.startsWith('_')),
  ])]

  const specRowsHTML = allKeys.length
    ? allKeys.map(k => `  <tr style="border-bottom:1px solid #e8e8e8;">
    <td style="padding:8px 12px;color:#666;font-weight:600;font-size:13px;width:25%;">${k}</td>
    <td style="padding:8px 12px;font-size:13px;width:37.5%;${specs1[k] ? '' : 'color:#bbb;'}">${specs1[k] || '—'}</td>
    <td style="padding:8px 12px;font-size:13px;width:37.5%;${specs2[k] ? '' : 'color:#bbb;'}">${specs2[k] || '—'}</td>
  </tr>`).join('\n')
    : `  <tr><td colspan="3" style="padding:12px;color:#999;font-size:13px;">Refer to Amazon product pages for full specifications.</td></tr>`

  const { reasons1, reasons2 } = buildPickDecisions(p1, p2, specs1, specs2)
  const slug = `compare-${slugify(brand1)}-${asin1.toLowerCase()}-vs-${slugify(brand2)}-${asin2.toLowerCase()}`
  const schema = comparisonSchema({ name1: short1, name2: short2, catLabel, catSlug, link1, link2, faqs, slug })

  const methodCtx = `This comparison is based on published specifications for the ${short1} and ${short2}, competitive positioning within each product's price segment, and aggregated user experience from public reviews.`

  return `${asciDisclosure()}

<nav style="font-size:13px;color:#888;margin-bottom:20px;">
<a href="/" style="color:#666;">Home</a> › <a href="/best-${catSlug}/" style="color:#666;">Best ${catLabel}s in India ${YEAR}</a> › Comparison
</nav>

<p style="font-size:16px;line-height:1.7;color:#333;">
Choosing between the <strong>${short1}</strong> and the <strong>${short2}</strong>?
This comparison breaks down the key specification differences to help you decide which is the better fit.
</p>

<div style="display:flex;gap:16px;margin:24px 0;flex-wrap:wrap;">
  <div style="flex:1;min-width:220px;border:1px solid #e0e0e0;border-radius:6px;padding:16px;">
    <p style="font-size:12px;color:#888;font-weight:700;text-transform:uppercase;margin:0 0 6px;">${brand1}</p>
    <p style="font-size:15px;font-weight:700;margin:0 0 14px;line-height:1.4;">${short1}</p>
    <a href="${link1}" target="_blank" rel="nofollow sponsored noopener"
       style="display:inline-block;background:#ff9900;color:#111;text-decoration:none;font-size:13px;font-weight:700;padding:8px 16px;border-radius:4px;">
      Check price on Amazon →
    </a>
  </div>
  <div style="flex:1;min-width:220px;border:1px solid #e0e0e0;border-radius:6px;padding:16px;">
    <p style="font-size:12px;color:#888;font-weight:700;text-transform:uppercase;margin:0 0 6px;">${brand2}</p>
    <p style="font-size:15px;font-weight:700;margin:0 0 14px;line-height:1.4;">${short2}</p>
    <a href="${link2}" target="_blank" rel="nofollow sponsored noopener"
       style="display:inline-block;background:#ff9900;color:#111;text-decoration:none;font-size:13px;font-weight:700;padding:8px 16px;border-radius:4px;">
      Check price on Amazon →
    </a>
  </div>
</div>

<h2 style="font-size:20px;font-weight:700;margin:28px 0 10px;">Specification Comparison</h2>
<div style="overflow-x:auto;">
<table style="width:100%;border-collapse:collapse;font-size:14px;">
  <thead>
    <tr style="background:#f5f5f5;">
      <th style="padding:10px 12px;text-align:left;font-weight:700;font-size:13px;color:#444;width:25%;">Specification</th>
      <th style="padding:10px 12px;text-align:left;font-weight:700;font-size:13px;color:#444;width:37.5%;">${short1.substring(0,35)}${short1.length>35?'…':''}</th>
      <th style="padding:10px 12px;text-align:left;font-weight:700;font-size:13px;color:#444;width:37.5%;">${short2.substring(0,35)}${short2.length>35?'…':''}</th>
    </tr>
  </thead>
  <tbody>
${specRowsHTML}
  </tbody>
</table>
</div>

<h2 style="font-size:20px;font-weight:700;margin:32px 0 12px;">Which One Should You Buy?</h2>

<div style="background:#e8f5e9;border-left:4px solid #4caf50;padding:14px 18px;border-radius:0 6px 6px 0;margin-bottom:12px;">
  <p style="margin:0;font-size:14px;line-height:1.6;">
    <strong>Choose ${short1.substring(0,40)}${short1.length>40?'…':''}</strong> if you want:
    <ul style="margin:8px 0 0;padding-left:18px;">
      ${reasons1.map(r => `<li>${r}</li>`).join('\n      ')}
    </ul>
  </p>
</div>

<div style="background:#e3f2fd;border-left:4px solid #2196f3;padding:14px 18px;border-radius:0 6px 6px 0;margin-bottom:24px;">
  <p style="margin:0;font-size:14px;line-height:1.6;">
    <strong>Choose ${short2.substring(0,40)}${short2.length>40?'…':''}</strong> if you want:
    <ul style="margin:8px 0 0;padding-left:18px;">
      ${reasons2.map(r => `<li>${r}</li>`).join('\n      ')}
    </ul>
  </p>
</div>

${methodologyBlock(methodCtx)}

<div style="background:#fff3e0;border:1px solid #ffe0b2;border-radius:6px;padding:16px 20px;margin:24px 0;">
  <p style="margin:0 0 10px;font-weight:700;font-size:15px;">Check current prices on Amazon India:</p>
  <div style="display:flex;gap:12px;flex-wrap:wrap;">
    <a href="${link1}" target="_blank" rel="nofollow sponsored noopener"
       style="display:inline-block;background:#ff9900;color:#111;text-decoration:none;font-size:13px;font-weight:700;padding:8px 16px;border-radius:4px;">
      ${short1.substring(0,30)}${short1.length>30?'…':''} →
    </a>
    <a href="${link2}" target="_blank" rel="nofollow sponsored noopener"
       style="display:inline-block;background:#ff9900;color:#111;text-decoration:none;font-size:13px;font-weight:700;padding:8px 16px;border-radius:4px;">
      ${short2.substring(0,30)}${short2.length>30?'…':''} →
    </a>
  </div>
  <p style="margin:10px 0 0;font-size:12px;color:#999;">Amazon prices change frequently. Click to see current prices.</p>
</div>

${faqs.length ? `<h2 style="font-size:20px;font-weight:700;margin:32px 0 12px;">Frequently Asked Questions</h2>
${faqs.map(([q, a]) => `<details style="border:1px solid #e0e0e0;border-radius:4px;margin-bottom:8px;">
  <summary style="padding:12px 16px;cursor:pointer;font-weight:600;font-size:14px;background:#fafafa;">${q}</summary>
  <div style="padding:12px 16px;font-size:14px;line-height:1.7;color:#333;">${a}</div>
</details>`).join('\n')}` : ''}

<hr style="margin:32px 0;border:none;border-top:1px solid #e0e0e0;">
<p style="font-size:13px;color:#888;">
  <a href="/best-${catSlug}/" style="color:#e65100;font-weight:600;">← See all ${catLabel}s compared in India ${YEAR}</a>
</p>

<script type="application/ld+json">
${JSON.stringify(schema, null, 2)}
</script>`
}

async function main() {
  const args      = process.argv.slice(2)
  const dryRun    = args.includes('--dry-run')
  const catFilter = args.includes('--cat') ? args[args.indexOf('--cat') + 1] : null
  const limit     = args.includes('--limit') ? parseInt(args[args.indexOf('--limit') + 1]) || 9999 : 9999

  if (!WP || !USER || !PASS) { console.error('Missing WP credentials in .env'); process.exit(1) }
  if (!fs.existsSync(QUEUE_FILE)) { console.error('Run content-opportunity-engine.js first'); process.exit(1) }

  const productIndex = loadProducts(KITCHEN, PRODS_DIR)
  const queue = JSON.parse(fs.readFileSync(QUEUE_FILE, 'utf8'))
    .filter(o => o.type === 'comparison')
    .filter(o => !catFilter || o.category === catFilter)
    .slice(0, limit)

  console.log(`Comparison queue: ${queue.length} items`)
  const stats = { created: 0, updated: 0, skipped: 0, errors: 0 }

  for (const op of queue) {
    const [asin1, asin2] = op.asins || []
    if (!asin1 || !asin2) { stats.skipped++; continue }
    const p1 = productIndex[asin1]
    const p2 = productIndex[asin2]
    if (!p1 || !p2) {
      console.log(`  skip ${asin1}+${asin2} — one or both not in product index`)
      stats.skipped++; continue
    }

    const brand1  = slugify(p1.brand_id || 'product')
    const brand2  = slugify(p2.brand_id || 'product')
    const catSlug = op.category
    const slug    = `compare-${brand1}-${asin1.toLowerCase()}-vs-${brand2}-${asin2.toLowerCase()}`
    const name1   = shortName(p1.product_name || p1._legacy?.name || '', 40)
    const name2   = shortName(p2.product_name || p2._legacy?.name || '', 40)
    const title   = `${name1} vs ${name2} — Which Is Better for Indian Homes?`

    try {
      const html   = buildComparisonHTML(p1, p2, catSlug)
      const result = await wpUpsertPage({ title, slug, content: html }, { wp: WP, auth: AUTH, dryRun })
      if (result) {
        console.log(`  ✓ [${result.action}] ${catSlug} | ${name1.substring(0,30)} vs ${name2.substring(0,30)}`)
        result.action === 'created' ? stats.created++ : stats.updated++
      }
    } catch (e) {
      console.error(`  ✗ ${asin1}+${asin2}: ${e.message}`)
      stats.errors++
    }
    await new Promise(r => setTimeout(r, 300))
  }

  console.log(`\n── DONE ────────────────────────`)
  console.log(`Created: ${stats.created} | Updated: ${stats.updated} | Skipped: ${stats.skipped} | Errors: ${stats.errors}`)
  if (dryRun) console.log('(dry run — no WP changes)')
}

main().catch(e => { console.error(e.message); process.exit(1) })
```

- [ ] **Step 2: Dry-run test**

```bash
node scripts/generate-comparisons.js --dry-run --cat air-fryers --limit 3
```

Expected: 3 `[dry]` lines, no errors.

- [ ] **Step 3: Commit**

```bash
git add scripts/generate-comparisons.js
git commit -m "feat(pricehawk): rewrite G3 comparisons with real spec reasoning"
```

---

## Task 7: Rewrite `scripts/generate-buying-guides.js`

**Files:**
- Modify: `scripts/generate-buying-guides.js`

Key change: product picks sorted by actual `last_price`, spec highlights from `specifications`, one `_features[0]` differentiator per product.

- [ ] **Step 1: Replace the `buildGuideHTML` function with price-sorted, spec-grounded version**

Replace the entire file with the following:

```javascript
// scripts/generate-buying-guides.js
require('dotenv').config()
const fs   = require('fs')
const path = require('path')

const { makeAuth, wpUpsertPage } = require('./lib/wp')
const {
  resolveOffer, specTable, featureHighlights,
  asciDisclosure, methodologyBlock, loadProducts, getSpecVal,
} = require('./lib/content')
const { guideSchema, slugify } = require('./lib/schema')

const WP   = (process.env.WORDPRESS_URL || '').replace(/\/$/, '')
const USER = process.env.WORDPRESS_USERNAME
const PASS = process.env.WORDPRESS_APP_PASSWORD
const TAG  = process.env.AMAZON_AFFILIATE_TAG || 'pricehawkin-21'
const AUTH = makeAuth(USER, PASS)

const PRODS_DIR  = path.join(__dirname, '../data/products')
const QUEUE_FILE = path.join(__dirname, '../data/content/phase1_queue.json')
const YEAR = new Date().getFullYear()

const KITCHEN = ['air-fryers','mixer-grinders','coffee-machines','induction-cooktops',
                 'electric-kettles','food-processors','hand-blenders','sandwich-makers','rice-cookers']

const CAT_LABELS = {
  'air-fryers':'Air Fryers','mixer-grinders':'Mixer Grinders','coffee-machines':'Coffee Machines',
  'induction-cooktops':'Induction Cooktops','electric-kettles':'Electric Kettles',
  'food-processors':'Food Processors','hand-blenders':'Hand Blenders',
  'sandwich-makers':'Sandwich Makers','rice-cookers':'Rice Cookers',
}
const CAT_LABEL_SINGULAR = {
  'air-fryers':'air fryer','mixer-grinders':'mixer grinder','coffee-machines':'coffee machine',
  'induction-cooktops':'induction cooktop','electric-kettles':'electric kettle',
  'food-processors':'food processor','hand-blenders':'hand blender',
  'sandwich-makers':'sandwich maker','rice-cookers':'rice cooker',
}

const CAT_INTROS = {
  'air-fryers': 'Air fryers are now India\'s fastest-growing kitchen appliance — delivering crispy results with significantly less oil than traditional frying. Whether you\'re making samosas, pakoras, or grilled chicken, the right air fryer transforms everyday cooking.',
  'mixer-grinders': 'A good mixer grinder is the backbone of an Indian kitchen. From idli batter to evening chutneys, the right one saves time and lasts years.',
  'coffee-machines': 'India\'s coffee culture has outgrown instant powder. A coffee machine delivers café-quality results at home and pays for itself within months compared to daily coffee shop visits.',
  'induction-cooktops': 'Induction cooktops offer precise temperature control, energy efficiency, and safety — no open flame, no gas leak risk. Ideal for Indian cooking styles.',
  'electric-kettles': 'Electric kettles boil water faster than any stovetop with lower energy consumption. Modern models with temperature control unlock pour-over coffee and green tea at their intended temperatures.',
  'food-processors': 'Food processors cut prep time dramatically — from grating coconut to kneading dough. A good processor handles tasks that would take 30 minutes by hand in under 5.',
  'hand-blenders': 'Hand blenders are the space-saving workhorse of the modern kitchen. Blend soups directly in the pot, make smoothies in the glass — minimal cleanup.',
  'sandwich-makers': 'Sandwich makers and grills go beyond sandwiches. The right one handles grilled cheese to paninis and Indian-style toast with even browning.',
  'rice-cookers': 'Electric rice cookers deliver perfectly cooked rice every time — no watching, no overflow, no burning. Set it, forget it, eat it.',
}

const CAT_BUYING_FACTORS = {
  'air-fryers': [
    { factor: 'Capacity', tip: 'A 2–3L basket suits 1–2 people. For a family of 4, choose 4–6L. Larger baskets take longer to heat.' },
    { factor: 'Wattage', tip: 'Higher wattage (1500W+) preheats faster and maintains temperature better during use.' },
    { factor: 'Preset Programs', tip: 'Presets are convenient for beginners. Experienced cooks often prefer manual control.' },
    { factor: 'Controls', tip: 'Digital touchscreen offers precision. Analog dials are simpler and often more durable.' },
  ],
  'mixer-grinders': [
    { factor: 'Wattage', tip: '500W handles light daily use. 750W suits families grinding idli/dosa batter regularly.' },
    { factor: 'Number of Jars', tip: '3 jars (dry, wet, chutney) covers most Indian cooking needs.' },
    { factor: 'Motor Warranty', tip: 'Look for minimum 2-year motor warranty. Indian brands often offer 5-year warranties.' },
    { factor: 'Jar Material', tip: 'Stainless steel jars are more durable and do not stain.' },
  ],
  'coffee-machines': [
    { factor: 'Coffee Type', tip: 'Drip: bulk coffee. Espresso: café-style shots. Capsule: convenience at higher per-cup cost.' },
    { factor: 'Bar Pressure', tip: 'True espresso requires 9 bar minimum.' },
    { factor: 'Milk Frother', tip: 'Required for cappuccinos and lattes. Budget machines typically omit this.' },
    { factor: 'Descaling', tip: 'In hard-water cities, descale monthly. Choose models with descaling indicators.' },
  ],
  'induction-cooktops': [
    { factor: 'Wattage', tip: '1200W handles everyday cooking. 1800–2000W boils water faster.' },
    { factor: 'Cookware', tip: 'Only ferromagnetic cookware works — cast iron and most stainless steel.' },
    { factor: 'Presets', tip: 'Temperature presets for dal, milk, chai save effort for daily use.' },
    { factor: 'Safety', tip: 'Look for auto-shutoff, child lock, and overheating protection.' },
  ],
  'electric-kettles': [
    { factor: 'Capacity', tip: '1L for 2–3 cups. 1.5–1.7L suits most households. 2L+ for larger families.' },
    { factor: 'Material', tip: 'Stainless steel interior is essential — no plastic taste, more hygienic.' },
    { factor: 'Wattage', tip: '1500W boils 1 litre in ~3.5 minutes. 2200W cuts this to ~2 minutes.' },
    { factor: 'Temperature Control', tip: 'Variable temperature needed for green tea or specialty coffee only.' },
  ],
  'food-processors': [
    { factor: 'Wattage', tip: '600W handles most household tasks. 800–1000W for heavy continuous use.' },
    { factor: 'Bowl Capacity', tip: '1.5–2L suits 2–4 people. 3L+ for large families.' },
    { factor: 'Attachments', tip: 'Slicing disc, shredding disc, and chopping blade cover 90% of use cases.' },
    { factor: 'Cleaning', tip: 'Wide-mouth bowls with dishwasher-safe parts save significant time.' },
  ],
  'hand-blenders': [
    { factor: 'Wattage', tip: '250–400W handles smoothies, soups, and baby food. 600W+ for tough ingredients.' },
    { factor: 'Speed Settings', tip: 'Variable speed gives better control for different textures.' },
    { factor: 'Shaft Material', tip: 'Stainless steel shafts last significantly longer than plastic.' },
    { factor: 'Attachments', tip: 'Chopper bowl and whisk attachments expand functionality significantly.' },
  ],
  'sandwich-makers': [
    { factor: 'Plate Type', tip: 'Fixed triangular: basic sandwich only. Flat grill: paninis. Removable: swap between modes.' },
    { factor: 'Wattage', tip: '750–900W standard. Higher wattage preheats faster for multiple sandwiches.' },
    { factor: 'Non-Stick', tip: 'Quality coating reduces need for butter and makes cleaning easier.' },
    { factor: 'Indicator', tip: 'Ready indicator shows when maker has reached cooking temperature.' },
  ],
  'rice-cookers': [
    { factor: 'Capacity', tip: '1L for 1–2 people. 1.8L is the standard Indian household size. 2.8L+ for larger families.' },
    { factor: 'Inner Pot', tip: 'Non-stick coating prevents sticking. Thicker pots provide even heat distribution.' },
    { factor: 'Keep-Warm', tip: 'Auto keep-warm function essential for Indian households with staggered mealtimes.' },
    { factor: 'Multi-Cook', tip: 'Multi-cook handles rice, dal, khichdi, and steam — worth it for daily use.' },
  ],
}

function titleCase(s) { return (s||'').replace(/-/g,' ').replace(/\b\w/g,c=>c.toUpperCase()) }
function shortName(name, max=50) {
  const c=(name||'').replace(/\s*[\\|,].*$/,'').trim()
  return c.length>max ? c.substring(0,max-1)+'…' : c
}

// Get top N products for a category, sorted by price ascending (for budget guides)
function getProductsForCat(catSlug, productIndex, n=5) {
  return Object.values(productIndex)
    .filter(p => p._catSlug === catSlug)
    .map(p => {
      const offer = resolveOffer(p)
      return { ...p, _price: offer.last_price || p._legacy?.current_price || 0 }
    })
    .sort((a, b) => a._price - b._price)
    .slice(0, n)
}

function buildProductCard(product, catSlug, position) {
  const name    = product.product_name || product._legacy?.name || 'Product'
  const brand   = titleCase(product.brand_id || '')
  const offer   = resolveOffer(product)
  const asin    = offer.external_id || product._legacy?.asin || ''
  const link    = offer.affiliate_url || `https://www.amazon.in/dp/${asin}?tag=${TAG}`
  const specs   = product.specifications || {}
  const features = specs._features || []

  const wattage  = getSpecVal(specs, 'Output Wattage', 'Wattage')
  const capacity = getSpecVal(specs, 'Capacity', 'Volume', 'Bowl Capacity')
  const ctrl     = getSpecVal(specs, 'Controller Type', 'Control Method')
  const specBits = [wattage, capacity, ctrl].filter(Boolean)

  const topFeature = features[0] || null

  return `<div style="border:1px solid #e0e0e0;border-radius:6px;padding:16px 20px;margin-bottom:16px;">
  <p style="font-size:12px;color:#888;font-weight:700;text-transform:uppercase;margin:0 0 4px;">#${position} · ${brand}</p>
  <h3 style="font-size:16px;font-weight:700;margin:0 0 8px;line-height:1.4;">${shortName(name, 70)}</h3>
  ${specBits.length ? `<p style="font-size:13px;color:#555;margin:0 0 8px;">${specBits.join(' · ')}</p>` : ''}
  ${topFeature ? `<p style="font-size:13px;color:#333;margin:0 0 12px;font-style:italic;">"${topFeature}"</p>` : ''}
  <a href="${link}" target="_blank" rel="nofollow sponsored noopener"
     style="display:inline-block;background:#ff9900;color:#111;text-decoration:none;font-size:13px;font-weight:700;padding:8px 16px;border-radius:4px;">
    Check price on Amazon →
  </a>
</div>`
}

function buildGuideHTML(products, catSlug, subtype, useCase) {
  const catLabel   = CAT_LABELS[catSlug] || titleCase(catSlug)
  const catSingular = CAT_LABEL_SINGULAR[catSlug] || catLabel.toLowerCase()
  const intro      = CAT_INTROS[catSlug] || `Find the best ${catSingular} for Indian homes.`
  const factors    = CAT_BUYING_FACTORS[catSlug] || []
  const guideSlug  = `best-${catSlug}${useCase ? '-' + slugify(useCase) : ''}${subtype === 'budget' ? '-budget' : ''}`

  const title = subtype === 'budget'
    ? `Best Budget ${catLabel} in India ${YEAR}`
    : useCase
      ? `Best ${catLabel} for ${useCase} in India ${YEAR}`
      : `Best ${catLabel} in India ${YEAR}`

  const productList = products.map((p, i) => ({
    name: shortName(p.product_name || p._legacy?.name || '', 60),
    link: (() => { const o = resolveOffer(p); return o.affiliate_url || `https://www.amazon.in/dp/${o.external_id || p._legacy?.asin}?tag=${TAG}` })()
  }))

  const schema = guideSchema({ catLabel, catSlug, slug: guideSlug, products: productList })

  const cardsHTML = products.map((p, i) => buildProductCard(p, catSlug, i + 1)).join('\n')

  const factorsHTML = factors.length ? `
<h2 style="font-size:20px;font-weight:700;margin:32px 0 12px;">What to Look For</h2>
${factors.map(({ factor, tip }) => `<div style="margin-bottom:12px;">
  <p style="font-size:15px;font-weight:700;margin:0 0 4px;">${factor}</p>
  <p style="font-size:14px;color:#444;margin:0;line-height:1.6;">${tip}</p>
</div>`).join('\n')}` : ''

  const methodCtx = `This guide covers ${catLabel} available on Amazon India. Selections are based on published specifications, price-to-feature value across segments, and analysis of user review patterns.`

  return `${asciDisclosure()}

<nav style="font-size:13px;color:#888;margin-bottom:20px;">
<a href="/" style="color:#666;">Home</a> › ${title}
</nav>

<p style="font-size:16px;line-height:1.7;color:#333;">${intro}</p>

<h2 style="font-size:20px;font-weight:700;margin:28px 0 16px;">Top Picks</h2>
${cardsHTML}

${factorsHTML}

${methodologyBlock(methodCtx)}

<hr style="margin:32px 0;border:none;border-top:1px solid #e0e0e0;">
<p style="font-size:13px;color:#888;">
  <a href="/best-${catSlug}/" style="color:#e65100;font-weight:600;">← See all ${catLabel} options in India ${YEAR}</a>
</p>

<script type="application/ld+json">
${JSON.stringify(schema, null, 2)}
</script>`
}

async function main() {
  const args       = process.argv.slice(2)
  const dryRun     = args.includes('--dry-run')
  const catFilter  = args.includes('--cat') ? args[args.indexOf('--cat') + 1] : null
  const subtype    = args.includes('--subtype') ? args[args.indexOf('--subtype') + 1] : null
  const limit      = args.includes('--limit') ? parseInt(args[args.indexOf('--limit') + 1]) || 9999 : 9999

  if (!WP || !USER || !PASS) { console.error('Missing WP credentials in .env'); process.exit(1) }
  if (!fs.existsSync(QUEUE_FILE)) { console.error('Run content-opportunity-engine.js first'); process.exit(1) }

  const productIndex = loadProducts(KITCHEN, PRODS_DIR)

  const queue = JSON.parse(fs.readFileSync(QUEUE_FILE, 'utf8'))
    .filter(o => o.type === 'buying_guide')
    .filter(o => !catFilter || o.category === catFilter)
    .filter(o => !subtype || o.subtype === subtype)
    .slice(0, limit)

  console.log(`Buying guide queue: ${queue.length} items`)
  const stats = { created: 0, updated: 0, skipped: 0, errors: 0 }

  for (const op of queue) {
    const catSlug  = op.category
    const useCase  = op.use_case || op.decision_type || null
    const sub      = op.subtype || 'general'
    const products = getProductsForCat(catSlug, productIndex)

    if (!products.length) { console.log(`  skip ${catSlug} — no products`); stats.skipped++; continue }

    const guideSlug = `best-${catSlug}${useCase ? '-' + slugify(useCase) : ''}${sub === 'budget' ? '-budget' : ''}`
    const catLabel  = CAT_LABELS[catSlug] || titleCase(catSlug)
    const title     = sub === 'budget'
      ? `Best Budget ${catLabel} in India ${YEAR}`
      : useCase
        ? `Best ${catLabel} for ${useCase} in India ${YEAR}`
        : `Best ${catLabel} in India ${YEAR}`

    try {
      const html   = buildGuideHTML(products, catSlug, sub, useCase)
      const result = await wpUpsertPage({ title, slug: guideSlug, content: html }, { wp: WP, auth: AUTH, dryRun })
      if (result) {
        console.log(`  ✓ [${result.action}] ${catSlug} | ${sub} | ${useCase || 'general'}`)
        result.action === 'created' ? stats.created++ : stats.updated++
      }
    } catch (e) {
      console.error(`  ✗ ${catSlug}: ${e.message}`)
      stats.errors++
    }
    await new Promise(r => setTimeout(r, 300))
  }

  console.log(`\n── DONE ────────────────────────`)
  console.log(`Created: ${stats.created} | Updated: ${stats.updated} | Skipped: ${stats.skipped} | Errors: ${stats.errors}`)
  if (dryRun) console.log('(dry run — no WP changes)')
}

main().catch(e => { console.error(e.message); process.exit(1) })
```

- [ ] **Step 2: Dry-run test**

```bash
node scripts/generate-buying-guides.js --dry-run --cat air-fryers --limit 3
```

Expected: 3 `[dry]` lines, no errors.

- [ ] **Step 3: Commit**

```bash
git add scripts/generate-buying-guides.js
git commit -m "feat(pricehawk): rewrite G4 buying guides with price-sorted picks"
```

---

## Task 8: Update `scripts/generate-phase1-content.js` to use lib

**Files:**
- Modify: `scripts/generate-phase1-content.js`

Only change the WP helpers and duplicated spec logic. Keep category hub HTML structure intact.

- [ ] **Step 1: Replace WP helpers and add lib imports at top of file**

Find the block starting with `const WP = ` and ending with the last credential line, plus the two WP helper functions (`wpFindPage`, `wpUpsertPage`), and replace with lib imports:

```javascript
// AT TOP — replace existing credential block and wpFindPage/wpUpsertPage functions with:
require('dotenv').config()
const fs   = require('fs')
const path = require('path')
const { makeAuth, wpUpsertPage } = require('./lib/wp')
const { asciDisclosure, methodologyBlock } = require('./lib/content')

const WP   = (process.env.WORDPRESS_URL || '').replace(/\/$/, '')
const USER = process.env.WORDPRESS_USERNAME
const PASS = process.env.WORDPRESS_APP_PASSWORD
const AUTH = makeAuth(USER, PASS)
const TAG  = process.env.AMAZON_AFFILIATE_TAG || 'pricehawkin-21'
```

- [ ] **Step 2: Remove the duplicate `ASCI_DISCLOSURE` constant and `methodologyBlock` function**

These are now provided by `lib/content.js`. Delete the local definitions:
- Delete: `const ASCI_DISCLOSURE = \`<div style=...`
- Delete: `function methodologyBlock(catLabel, productCount) { ... }`

Update any calls from `ASCI_DISCLOSURE` to `asciDisclosure()` and `methodologyBlock(catLabel, productCount)` to `methodologyBlock(\`This page covers ${productCount} ${catLabel} models...\`)`.

- [ ] **Step 3: Update `wpUpsertPage` calls to pass context object**

Find all calls like:
```javascript
await wpUpsertPage({ title, slug, content }, dryRun)
```
Replace with:
```javascript
await wpUpsertPage({ title, slug, content }, { wp: WP, auth: AUTH, dryRun })
```

- [ ] **Step 4: Dry-run test**

```bash
node scripts/generate-phase1-content.js --dry-run --cat air-fryers
```

Expected: dry-run output for category hub + top brand pages, no errors.

- [ ] **Step 5: Commit**

```bash
git add scripts/generate-phase1-content.js
git commit -m "feat(pricehawk): wire G1 phase1-content to shared lib"
```

---

## Task 9: Create `scripts/push-page.js`

**Files:**
- Create: `scripts/push-page.js`

Terminal-driven single-page push utility. Used after Claude generates a page draft in this session.

- [ ] **Step 1: Create the file**

```javascript
// scripts/push-page.js
// Usage: node scripts/push-page.js --slug <slug> --title "<title>" --file tmp/draft.html
require('dotenv').config()
const fs = require('fs')
const { makeAuth, wpUpsertPage } = require('./lib/wp')

const WP   = (process.env.WORDPRESS_URL || '').replace(/\/$/, '')
const USER = process.env.WORDPRESS_USERNAME
const PASS = process.env.WORDPRESS_APP_PASSWORD
const AUTH = makeAuth(USER, PASS)

async function main() {
  const args  = process.argv.slice(2)
  const slug  = args.includes('--slug')  ? args[args.indexOf('--slug')  + 1] : null
  const title = args.includes('--title') ? args[args.indexOf('--title') + 1] : null
  const file  = args.includes('--file')  ? args[args.indexOf('--file')  + 1] : null

  if (!slug || !title || !file) {
    console.error('Usage: node scripts/push-page.js --slug <slug> --title "<title>" --file <html-file>')
    process.exit(1)
  }
  if (!fs.existsSync(file)) { console.error(`File not found: ${file}`); process.exit(1) }
  if (!WP || !USER || !PASS) { console.error('Missing WP credentials in .env'); process.exit(1) }

  const content = fs.readFileSync(file, 'utf8')
  const result  = await wpUpsertPage({ title, slug, content }, { wp: WP, auth: AUTH, dryRun: false })
  if (result) {
    console.log(`✓ [${result.action}] ID ${result.id}`)
    console.log(`  Draft: ${result.link}`)
  }
}

main().catch(e => { console.error(e.message); process.exit(1) })
```

- [ ] **Step 2: Test with a dry-run equivalent (no --file yet, just verify it errors correctly)**

```bash
node scripts/push-page.js
```

Expected error output: `Usage: node scripts/push-page.js --slug <slug> --title "<title>" --file <html-file>`

- [ ] **Step 3: Ensure tmp/ directory exists**

```bash
mkdir -p C:\Claude\pricehawk\tmp
```

Add `tmp/` to `.gitignore` if not already present. Check:

```bash
grep -n "tmp" C:\Claude\pricehawk\.gitignore
```

If missing, add:
```
tmp/
```

- [ ] **Step 4: Commit**

```bash
git add scripts/push-page.js .gitignore
git commit -m "feat(pricehawk): add push-page.js for terminal-driven single page flow"
```

---

## Task 10: Integration smoke test — generate one review to WP

Verify the full pipeline works end-to-end on a single product.

- [ ] **Step 1: Run reviews generator for 1 product without dry-run**

```bash
node scripts/generate-reviews.js --cat air-fryers --limit 1
```

Expected output:
```
Review queue: 1 items
  ✓ [created] air-fryers | AGARO Galaxy Digital Air Fryer...
── DONE ────────────────────────
Created: 1 | Updated: 0 | Skipped: 0 | Errors: 0
```

- [ ] **Step 2: Verify WP draft exists and check content quality**

Log in to WordPress admin → Pages → Drafts. Find the new page. Open it. Verify:
- ASCI disclosure present at top
- Full spec table with real values (not just 2 rows from regex)
- "What Makes This Stand Out" section with Amazon bullet points
- "Who Should Buy" has spec-derived bullets (not generic 3-line template)
- Methodology block present
- Amazon CTA button present
- No price numbers visible in content (compliance)
- Schema JSON-LD present at bottom

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat(pricehawk): generator redesign complete — rich spec data, shared lib, push-page utility"
```
