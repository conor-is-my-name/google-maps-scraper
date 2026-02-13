# Extractor Refactoring Summary

## Changes Made (2026-02-13)

### Objective
Refactor `extractor.py` to prioritize stable, semantic selectors over fragile obfuscated CSS classes and jsaction identifiers, making the scraper more resilient to Google Maps updates.

---

## Key Improvements

### 1. Stability-Prioritized Extraction

All extraction functions now attempt patterns in order of stability:

**🟢 Highest Priority (Most Stable):**
- `aria-label` attributes (accessibility-required)
- `data-item-id` attributes (semantic identifiers)
- Standard HTML tags (`<title>`, `<meta>`)
- Semantic URLs (`tel:`, `og:image`)

**🟡 Medium Priority (Moderately Stable):**
- Generic HTML structure patterns
- Common text patterns
- Standard button/link text

**🔴 Lowest Priority (Fragile - Last Resort):**
- Obfuscated CSS classes (e.g., `DUwDvf`, `kSOdnb`)
- Obfuscated jsaction identifiers (e.g., `pane.wfvdle20.category`)

### 2. Function-by-Function Changes

#### `get_main_name()`
- **Before:** Used obfuscated class `DUwDvf` first
- **After:** Uses `<title>` tag first, then generic `<h1>` structure, obfuscated class as last resort

#### `get_complete_address()`
- **Before:** aria-label first (already good), generic patterns second
- **After:** Added `data-item-id="address"` as secondary stable method, reordered by stability

#### `get_website()`
- **Before:** Basic patterns
- **After:** Prioritizes `data-item-id="authority"` and `aria-label`, adds URL normalization

#### `get_phone_number()`
- **Before:** Mixed priority
- **After:** `aria-label` and `tel:` hrefs first, data attributes second, reordered by stability

#### `get_rating()`
- **Before:** Already using stable aria-label
- **After:** Added stability comments for clarity

#### `get_reviews_count()`
- **Before:** Basic patterns
- **After:** Prioritizes aria-label context, added stability comments

#### `get_categories()`
- **Before:** Used obfuscated `jsaction="pane.wfvdle20.category"` first
- **After:**
  - Tries semantic selectors first
  - Obfuscated jsaction as last resort
  - **Improved filtering:** Excludes UI elements like "Learn more", "Show slider", etc.

#### `get_thumbnail()`
- **Before:** Used obfuscated classes and jsaction
- **After:**
  - Tries `og:image` meta tag first
  - Semantic alt text and Google CDN patterns
  - Obfuscated patterns as last resort
  - Added image URL validation

#### `get_hours()` ⭐ NEW
- **Added:** New function to extract business hours using aria-labels
- **Returns:** List of day-hour strings (e.g., `["Friday, 5 AM to 8 PM"]`)
- **Stability:** Highly stable (uses aria-label)

### 3. Documentation

- Added comprehensive module docstring explaining:
  - Extraction strategy (stability levels)
  - Data sources (JSON vs HTML)
  - Stability ratings for different selector types
- Added inline comments marking each pattern's stability level
- Updated last modified date

### 4. New Field

Added `hours` field to extracted data:
```python
place_details = {
    # ... existing fields ...
    "hours": get_hours(html_content),  # NEW
}
```

---

## Test Results

Tested with `before_reviews_click.html`:

```json
{
  "name": "Starbucks Coffee Company",
  "place_id": "ChIJW1FW1kd9UocRhErrD9wekdI",
  "address": "1960 E 9400 S, Sandy, UT 84093",
  "rating": 4.1,
  "reviews_url": "https://search.google.com/local/reviews?placeid=...",
  "categories": ["Coffee shop"],
  "website": "https://www.starbucks.com/store-locator/store/8522/",
  "phone": "8015760668",
  "thumbnail": "https://lh3.googleusercontent.com/...",
  "hours": ["Friday, 5 AM to 8 PM"]
}
```

**Field Coverage:**
- ✅ name
- ✅ place_id
- ✅ address
- ✅ rating
- ✅ categories (now clean, no UI elements)
- ✅ website
- ✅ phone
- ✅ hours (new!)
- ✅ thumbnail
- ⚠️ coordinates (depends on JSON availability)
- ⚠️ reviews_count (depends on page state)

---

## Benefits

### Increased Resilience
- **Before:** Scraper would break immediately when Google updates obfuscated class names
- **After:** Primary extraction methods use semantic attributes that are:
  - Required for accessibility compliance
  - Unlikely to change
  - More maintainable long-term

### Better Field Coverage
- Added `hours` extraction (previously not available)
- Improved `categories` filtering (removes UI noise)
- Better `website` normalization (adds https:// if missing)

### Improved Code Quality
- Clear documentation of stability levels
- Self-documenting code with stability comments
- Fallback patterns preserved for edge cases

---

## Backward Compatibility

✅ **Fully backward compatible**
- All existing fields maintained
- Same function signatures
- Same return types
- Additional `hours` field added (won't break existing code)

---

## Next Steps (Optional Future Improvements)

1. **Monitoring:** Add extraction success rate logging to detect when patterns start failing
2. **Alerting:** Set up notifications when field extraction rates drop below threshold
3. **Testing:** Create automated tests with multiple HTML samples from different locales
4. **Reviews:** Consider if individual review extraction is worth attempting (currently deprecated)

---

## Migration Guide

**No migration needed!** The refactored extractor is a drop-in replacement:

```python
# Same usage as before
from gmaps_scraper_server import extractor

place_data = extractor.extract_place_data(html_content)
# Now returns data with:
# - More stable extraction
# - New 'hours' field
# - Cleaner 'categories' (no UI elements)
```

---

## Files Modified

1. `gmaps_scraper_server/extractor.py`
   - Refactored all extraction functions
   - Added module docstring
   - Added `get_hours()` function
   - Improved `get_categories()` filtering

2. `DATA_EXTRACTION_ANALYSIS.md` (new)
   - Comprehensive analysis of data availability
   - Stability assessment
   - Recommendations

3. `REFACTORING_SUMMARY.md` (this file)
   - Summary of changes
   - Test results
   - Migration guide
