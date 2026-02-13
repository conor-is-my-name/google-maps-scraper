# Google Maps Data Extraction Analysis

## Executive Summary

After comprehensive analysis of Google Maps' current structure (as of Feb 2026), **JSON extraction is no longer viable for most fields**. However, HTML extraction can be made MUCH MORE ROBUST by prioritizing semantic selectors over obfuscated CSS classes.

## Current JSON Data Availability

### window.APP_INITIALIZATION_STATE
**Location:** `data[5][3][2]`
**Contains:** Only 4 fields (very sparse)
- `cid` (Internal ID for reviews - e.g., "0x87527d47d656515b:0xd2911edc0feb4a84")
- `name` (e.g., "Starbucks Coffee Company")
- `coordinates` (lat/lng)
- `place_id` (e.g., "ChIJW1FW1kd9UocRhErrD9wekdI")

**Missing:** Address, phone, website, rating, reviews count, categories, hours, thumbnail

### window.APP_OPTIONS
**Size:** ~76KB
**Contains:** Application configuration, NOT place-specific data

### Conclusion
❌ JSON sources do NOT contain comprehensive place data anymore
✅ JSON is only useful for: place_id, cid, name, coordinates (4 fields)

---

## HTML Data Availability & Stability

### 🟢 HIGHLY STABLE (Recommended for extraction)

These use **semantic/accessibility attributes** that Google is unlikely to change:

| Field | Method | Example Pattern | Status |
|-------|--------|----------------|--------|
| **Address** | `aria-label` | `aria-label="Address: 1960 E 9400 S, Sandy, UT 84093"` | ✅ Found |
| **Address** | `data-item-id` | `data-item-id="address"` | ✅ Found |
| **Phone** | `aria-label` | `aria-label="Phone: (801) 576-0668"` | ✅ Found |
| **Phone** | `tel:` href | `href="tel:+18015760668"` | ✅ Found |
| **Website** | `aria-label` | `aria-label="Website: starbucks.com"` | ✅ Found |
| **Website** | `data-item-id` | `data-item-id="authority" href="..."` | ✅ Found |
| **Rating** | `aria-label` | `aria-label="4.1 stars"` | ✅ Found (9 occurrences) |
| **Hours** | `aria-label` | `aria-label="Friday, 5 AM to 8 PM"` | ✅ Found |
| **Name** | `<title>` tag | `<title>Starbucks Coffee Company - Google Maps</title>` | ✅ Found |

### 🟡 MODERATELY STABLE

| Field | Method | Stability Risk |
|-------|--------|---------------|
| **Categories** | Button text in category buttons | Moderate - HTML structure might change |
| **Reviews Count** | Regex: `(\d+) reviews?` | Moderate - text format might change |

### 🔴 FRAGILE (Current implementation uses these - HIGH RISK)

| Field | Method | Why It's Fragile |
|-------|--------|-----------------|
| **Name** | CSS class `DUwDvf` | Obfuscated class name - changes frequently |
| **Thumbnail** | CSS class `kSOdnb` | Obfuscated class name |
| **Categories** | `jsaction="pane.wfvdle20.category"` | Obfuscated identifier - will break on updates |
| **Thumbnail** | `jsaction="pane.wfvdle18.heroHeaderImage"` | Obfuscated identifier |

---

## Recommendations

### Priority 1: Refactor Extractor to Use Stable Selectors

Replace fragile patterns with stable ones:

```python
# CURRENT (Fragile):
name = extract_from_html(html, r'<h1[^>]*class="[^"]*DUwDvf[^"]*"[^>]*>.*?<span[^>]*></span>([^<]+)<', 1)

# RECOMMENDED (Stable):
name = extract_from_html(html, r'<title>([^-]+?)\s*-\s*Google Maps</title>', 1)

# CURRENT (Fragile):
category = extract_from_html(html, r'jsaction="pane\.wfvdle20\.category">([^<]+)</button>', 1)

# RECOMMENDED (More Stable):
# Use button text without relying on jsaction identifier
```

### Priority 2: Extraction Strategy

1. **Always try JSON first** for: `place_id`, `cid`, `name`, `coordinates`
   - Pros: Most reliable when available
   - Cons: Only covers 4 fields

2. **Use aria-labels as primary HTML method** for all other fields
   - Pros: Semantic, accessibility-required, very stable
   - Cons: None identified

3. **Use data-item-id as secondary fallback**
   - Pros: Semantic identifiers, stable
   - Cons: Limited coverage

4. **Use generic patterns as tertiary fallback**
   - Pros: Works when semantic attributes aren't found
   - Cons: Moderate stability risk

5. **AVOID obfuscated CSS classes/jsaction identifiers**
   - Only use as last resort
   - Add monitoring/alerts for extraction failures

### Priority 3: Make Current Code More Robust

Current code already uses some fallback patterns, but should:

1. **Reorder extraction attempts**: Put aria-labels FIRST
2. **Remove dependence on obfuscated identifiers** where possible
3. **Add extraction success logging** to detect when patterns start failing
4. **Add field-level monitoring** to alert when extraction rate drops

---

## Field-by-Field Extraction Plan

### Can Extract from JSON ✅
- `place_id` → `data[5][3][2][18]`
- `cid` → `data[5][3][2][0]`
- `name` → `data[5][3][2][1]`
- `coordinates` → `data[5][3][2][7]` (as `[null, null, lat, lng]`)

### Must Extract from HTML (Stable Methods Available) ✅
- `address` → `aria-label="Address: ..."` or `data-item-id="address"`
- `phone` → `aria-label="Phone: ..."` or `href="tel:..."`
- `website` → `aria-label="Website: ..."` or `data-item-id="authority"`
- `rating` → `aria-label="X.X stars"`
- `hours` → `aria-label="Monday, X AM to Y PM"`

### Must Extract from HTML (Moderately Stable) ⚠️
- `reviews_count` → Pattern: `(\d+) reviews?`
- `categories` → Category button text (avoid jsaction selectors)

### Challenging to Extract (No Stable Method Found) ❌
- `thumbnail` → Currently uses obfuscated CSS classes
  - May need to use img tags within specific sections
  - Consider using Open Graph meta tags if available

### Deprecated Fields ⚠️
- `reviews_url` → Google deprecated this endpoint (returns 404)
  - Field should be marked as deprecated in docs

---

## Bottom Line

**Good News:** You can extract all critical fields from HTML using stable selectors!

**The Change Needed:** Refactor extraction functions to prioritize:
1. Aria-labels (most stable)
2. Data-item-id attributes (very stable)
3. Structured patterns (moderate)
4. Obfuscated CSS classes (last resort only)

This will make your scraper **significantly more resilient** to Google Maps updates.
