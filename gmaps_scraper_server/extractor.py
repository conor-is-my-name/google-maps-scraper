"""
Google Maps Data Extractor

This module extracts place data from Google Maps HTML pages using a stability-prioritized approach.

EXTRACTION STRATEGY (Prioritized by Stability):
==============================================

🟢 HIGHLY STABLE (Primary Methods):
   - aria-label attributes: Required for accessibility, rarely change
   - data-item-id attributes: Semantic identifiers, stable
   - <title> tags: Standard HTML, very stable
   - tel: and other semantic URLs: Standard protocols

🟡 MODERATELY STABLE (Secondary Fallbacks):
   - Generic HTML structure patterns
   - Common text patterns (e.g., "X reviews", "X stars")
   - Standard button/link text

🔴 FRAGILE (Last Resort Only):
   - Obfuscated CSS classes (e.g., "DUwDvf", "kSOdnb")
   - Obfuscated jsaction identifiers (e.g., "pane.wfvdle20.category")
   - These WILL break when Google updates their interface

DATA SOURCES:
============
1. JSON (window.APP_INITIALIZATION_STATE): Only 4 fields available
   - place_id, cid (internal ID), name, coordinates
2. HTML DOM: Required for all other fields
   - Extracted using stability-prioritized patterns

Last Updated: 2026-02-13
"""

import json
import re
import logging

# Configure logger for this module
logger = logging.getLogger(__name__)

def extract_initial_json(html_content):
    """
    Extracts the JSON string assigned to window.APP_INITIALIZATION_STATE from HTML content.
    Note: Google Maps has changed to load most data dynamically. This now extracts minimal metadata.
    """
    try:
        match = re.search(r';window\.APP_INITIALIZATION_STATE\s*=\s*(.*?);window\.APP_FLAGS', html_content, re.DOTALL)
        if match:
            json_str = match.group(1)
            if json_str.strip().startswith(('[', '{')):
                return json_str
            else:
                logger.warning("Extracted content doesn't look like valid JSON start.")
                return None
        else:
            logger.warning("APP_INITIALIZATION_STATE pattern not found.")
            return None
    except Exception as e:
        logger.error(f"Error extracting JSON string: {e}")
        return None

def parse_json_data(json_str):
    """
    Parses the extracted JSON string to get basic metadata.
    Returns a dict with basic info (place_id, cid, name, coordinates) from APP_INITIALIZATION_STATE.
    Most detailed data now comes from rendered HTML DOM.
    """
    if not json_str:
        return None
    try:
        initial_data = json.loads(json_str)

        # New structure: data is at [5][3][2] with sparse information
        if isinstance(initial_data, list) and len(initial_data) > 5:
            if isinstance(initial_data[5], list) and len(initial_data[5]) > 3:
                if isinstance(initial_data[5][3], list) and len(initial_data[5][3]) > 2:
                    data_blob = initial_data[5][3][2]
                    if isinstance(data_blob, list) and len(data_blob) >= 19:
                        # Extract minimal metadata from this sparse structure
                        metadata = {
                            'cid': data_blob[0] if len(data_blob) > 0 else None,  # Internal ID for reviews
                            'name': data_blob[1] if len(data_blob) > 1 else None,
                            'coordinates': None,
                            'place_id': data_blob[18] if len(data_blob) > 18 else None,
                        }

                        # Extract coordinates from index 7
                        if len(data_blob) > 7 and isinstance(data_blob[7], list) and len(data_blob[7]) >= 4:
                            lat = data_blob[7][2]
                            lon = data_blob[7][3]
                            if lat is not None and lon is not None:
                                metadata['coordinates'] = {"latitude": lat, "longitude": lon}

                        logger.debug(f"Extracted metadata from APP_INITIALIZATION_STATE: {metadata.get('name')}")
                        return metadata

        logger.warning("Could not find expected data structure at [5][3][2]")
        return None

    except json.JSONDecodeError as e:
        logger.error(f"Error decoding initial JSON: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error parsing JSON data: {e}")
        return None


# --- Field Extraction Functions (Extract from HTML DOM, not JSON) ---

def extract_from_html(html_content, pattern, group=1, default=None):
    """Helper function to extract data from HTML using regex."""
    try:
        match = re.search(pattern, html_content, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(group)
        return default
    except Exception as e:
        logger.debug(f"Error extracting with pattern: {e}")
        return default

def clean_html_text(text):
    """Remove HTML tags and clean up text."""
    if not text:
        return None
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Decode HTML entities
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"')
    # Clean whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text if text else None

def get_main_name(html_content, metadata):
    """Extracts the main name of the place from HTML or metadata."""
    # Try metadata first (from APP_INITIALIZATION_STATE)
    if metadata and metadata.get('name'):
        return metadata['name']

    # STABLE: Try title tag first (most reliable)
    name = extract_from_html(html_content, r'<title>([^-]+?)\s*-\s*Google Maps</title>', 1)
    if name:
        return clean_html_text(name)

    # STABLE: Try h1 tag without class dependency
    name = extract_from_html(html_content, r'<h1[^>]*>.*?<span[^>]*>([^<]+)</span>', 1)
    if name:
        return clean_html_text(name)

    # FRAGILE FALLBACK: Only use as last resort (obfuscated class)
    name = extract_from_html(html_content, r'<h1[^>]*class="[^"]*DUwDvf[^"]*"[^>]*>.*?<span[^>]*></span>([^<]+)<', 1)
    if name:
        return clean_html_text(name)

    return None

def get_place_id(html_content, metadata):
    """Extracts the Google Place ID."""
    # Use metadata from APP_INITIALIZATION_STATE
    if metadata and metadata.get('place_id'):
        return metadata['place_id']

    # Fall back to searching HTML for ChIJ pattern
    place_id = extract_from_html(html_content, r'(ChIJ[a-zA-Z0-9_-]{20,})', 1)
    return place_id

def get_place_id_cid(html_content, metadata):
    """Extracts the internal Google Place ID (CID) for reviews URL."""
    # Use metadata from APP_INITIALIZATION_STATE
    if metadata and metadata.get('cid'):
        return metadata['cid']

    # Fall back to searching HTML
    cid = extract_from_html(html_content, r'(0x[a-f0-9]+:0x[a-f0-9]+)', 1)
    return cid

def get_reviews_url(html_content, metadata):
    """
    Constructs the reviews URL using the internal Place ID (CID).

    DEPRECATED (2026): This URL format returns 404 errors. Google deprecated this endpoint.
    Additionally, Google now requires user authentication to view individual reviews.
    Review extraction is not supported without violating Terms of Service.
    This function is kept for backwards compatibility only.

    Format: https://search.google.com/local/reviews?placeid={cid}
    """
    cid = get_place_id_cid(html_content, metadata)
    if cid:
        return f"https://search.google.com/local/reviews?placeid={cid}"
    return None

def get_gps_coordinates(html_content, metadata):
    """Extracts latitude and longitude."""
    # Use metadata from APP_INITIALIZATION_STATE
    if metadata and metadata.get('coordinates'):
        return metadata['coordinates']

    # Fall back to searching HTML for coordinate patterns
    lat = extract_from_html(html_content, r'\"latitude\"\s*:\s*([-]?\d+\.\d+)', 1)
    lon = extract_from_html(html_content, r'\"longitude\"\s*:\s*([-]?\d+\.\d+)', 1)

    if lat and lon:
        try:
            return {"latitude": float(lat), "longitude": float(lon)}
        except ValueError:
            pass

    return None

def get_complete_address(html_content):
    """Extracts the complete address from HTML."""
    # STABLE: Try semantic selectors first (accessibility attributes)
    patterns = [
        r'aria-label="Address:\s*([^"]+)"',  # HIGHLY STABLE - accessibility required
        r'data-item-id="address"[^>]*aria-label="([^"]+)"',  # STABLE - semantic + aria-label
        r'button[^>]*data-item-id="address"[^>]*>([^<]+)<',  # STABLE - semantic selector
        r'"formatted_address"\s*:\s*"([^"]+)"',  # MODERATE - JSON-like pattern
        r'button[^>]*aria-label="[^"]*([0-9]+[^",]{15,80})"',  # MODERATE - generic pattern
    ]

    for pattern in patterns:
        address = extract_from_html(html_content, pattern, 1)
        if address:
            cleaned = clean_html_text(address)
            # Validate it looks like an address (has some numbers and letters)
            if cleaned and len(cleaned) > 10 and re.search(r'\d', cleaned):
                return cleaned

    return None

def get_rating(html_content):
    """Extracts the average star rating from HTML."""
    # HIGHLY STABLE: aria-label with stars (accessibility required)
    rating_str = extract_from_html(html_content, r'aria-label="([\d.]+)\s+stars?"', 1)
    if rating_str:
        try:
            rating = float(rating_str)
            if 1.0 <= rating <= 5.0:
                return rating
        except ValueError:
            pass

    # MODERATE: Try alternative text pattern
    rating_str = extract_from_html(html_content, r'(\d\.\d)\s+out of 5 stars', 1)
    if rating_str:
        try:
            return float(rating_str)
        except ValueError:
            pass

    return None

def get_reviews_count(html_content):
    """Extracts the total number of reviews from HTML."""
    # MODERATE STABILITY: Text patterns (format could change but unlikely)
    patterns = [
        r'aria-label="[\d.]+\s+stars.*?([\d,]+)\s+reviews?"',  # MODERATE - in aria-label
        r'([\d,]+)\s+reviews?',  # MODERATE - general pattern
        r'([0-9,]+)\s*Google reviews?',  # MODERATE - specific variant
    ]

    for pattern in patterns:
        count_str = extract_from_html(html_content, pattern, 1)
        if count_str:
            try:
                # Remove commas and convert to int
                count = int(count_str.replace(',', ''))
                # Sanity check - reviews count should be reasonable
                if 0 < count < 10000000:
                    return count
            except ValueError:
                pass

    return None

def get_website(html_content):
    """Extracts the primary website link from HTML."""
    # STABLE: Try semantic selectors first
    patterns = [
        r'data-item-id="authority"[^>]*href="([^"]+)"',  # HIGHLY STABLE - semantic ID
        r'aria-label="Website:\s*([^"]+)"',  # HIGHLY STABLE - accessibility attribute
        r'<a[^>]*aria-label="[^"]*[Ww]ebsite[^"]*"[^>]*href="([^"]+)"',  # STABLE - aria-label variant
        r'data-tooltip="Open website"[^>]*href="([^"]+)"',  # MODERATE - data attribute
    ]

    for pattern in patterns:
        website = extract_from_html(html_content, pattern, 1)
        if website:
            # Clean up the website URL
            website = clean_html_text(website)
            if website and ('http://' in website or 'https://' in website or '.' in website):
                # Ensure it has protocol
                if not website.startswith('http'):
                    website = 'https://' + website
                return website

    return None

def get_phone_number(html_content):
    """Extracts and standardizes the primary phone number from HTML."""
    # STABLE: Try semantic selectors first
    patterns = [
        r'aria-label="Phone:\s*([^"]+)"',  # HIGHLY STABLE - accessibility attribute
        r'href="tel:([^"]+)"',  # HIGHLY STABLE - standard tel: protocol
        r'data-item-id="phone[^"]*"[^>]*aria-label="[^"]*([^"]+)"',  # STABLE - semantic + aria
        r'data-tooltip="Call"[^>]*href="tel:([^"]+)"',  # MODERATE - data attribute
        r'button[^>]*aria-label="[^"]*(\+?1?\s*\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})[^"]*"',  # MODERATE - pattern in aria-label
    ]

    for pattern in patterns:
        phone = extract_from_html(html_content, pattern, 1)
        if phone:
            # Standardize phone number - remove all non-digits except leading +
            phone = clean_html_text(phone)
            standardized = re.sub(r'\D', '', phone)
            if len(standardized) >= 10:  # Valid phone should have at least 10 digits
                return standardized

    return None

def get_categories(html_content):
    """Extracts the list of categories/types from HTML."""
    # STABLE: Try semantic/aria-label patterns first
    patterns = [
        r'aria-label="Category:\s*([^"]+)"',  # STABLE - accessibility attribute
        r'data-item-id="category"[^>]*aria-label="([^"]+)"',  # STABLE - semantic + aria
        r'jsaction="pane\.[^"]*category[^>]*>([^<]+)</button>',  # FRAGILE FALLBACK - obfuscated jsaction
    ]

    all_categories = []

    # UI elements to exclude (not actual categories)
    excluded_terms = {
        'save', 'share', 'send', 'directions', 'website', 'call', 'menu', 'order',
        'reserve', 'learn more', 'show slider', 'photos', 'reviews', 'overview',
        'about', 'updates', 'show', 'hide', 'more', 'less', 'see', 'view', 'edit',
        'suggest', 'claim', 'add', 'report', 'nearby', 'similar', 'copy', 'close'
    }

    for pattern in patterns:
        # Use findall to get all matches
        matches = re.findall(pattern, html_content, re.DOTALL | re.IGNORECASE)
        for match in matches:
            cleaned = clean_html_text(match)
            # Validate it looks like a category
            if cleaned and 2 < len(cleaned) < 50:
                # Skip UI elements and common actions
                if cleaned.lower() in excluded_terms:
                    continue
                # Skip if it contains typical UI action words
                if any(word in cleaned.lower() for word in ['click', 'button', 'open', 'show', 'hide']):
                    continue
                # Split by common separators
                cats = [c.strip() for c in re.split(r'[,·•]', cleaned)]
                for cat in cats:
                    if cat and len(cat) > 2 and cat.lower() not in excluded_terms:
                        all_categories.append(cat)

    # Return unique categories
    if all_categories:
        unique_cats = []
        seen = set()
        for cat in all_categories:
            cat_lower = cat.lower()
            if cat_lower not in seen:
                unique_cats.append(cat)
                seen.add(cat_lower)
        return unique_cats if unique_cats else None

    return None

def get_thumbnail(html_content):
    """Extracts the main thumbnail image URL from HTML."""
    # STABLE: Try semantic patterns first
    patterns = [
        r'<meta\s+property="og:image"\s+content="([^"]+)"',  # STABLE - Open Graph meta tag
        r'<img[^>]*alt="[^"]*(?:Photo|Image)[^"]*"[^>]*src="([^"]+)"',  # MODERATE - semantic alt text
        r'<img[^>]*aria-label="[^"]*"[^>]*src="(https://[^"]+googleusercontent[^"]+)"',  # MODERATE - Google image CDN
        r'<img[^>]*src="(https://lh\d+\.googleusercontent\.com/[^"]+)"',  # MODERATE - Google CDN pattern
        r'jsaction="pane\.[^"]*[Hh]ero[^"]*[Ii]mage[^>]*<img[^>]+src="([^"]+)"',  # FRAGILE FALLBACK - obfuscated jsaction
        r'<img[^>]*class="[^"]*kSOdnb[^"]*"[^>]+src="([^"]+)"',  # FRAGILE FALLBACK - obfuscated class
    ]

    for pattern in patterns:
        thumbnail = extract_from_html(html_content, pattern, 1)
        if thumbnail and ('http://' in thumbnail or 'https://' in thumbnail):
            # Validate it's an actual image URL
            if any(ext in thumbnail.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp', 'googleusercontent']):
                return thumbnail

    return None

def get_hours(html_content):
    """Extracts business hours from HTML."""
    # HIGHLY STABLE: aria-labels contain hour information
    patterns = [
        r'aria-label="([A-Z][a-z]+day,\s+\d+(?::\d+)?\s+[AP]M\s+to\s+\d+(?::\d+)?\s+[AP]M)[^"]*"',  # Individual day hours
        r'aria-label="Hours:\s*([^"]+)"',  # Hours in aria-label
        r'aria-label="Show open hours[^"]*"',  # Marker that hours exist
    ]

    hours_list = []

    # Try to extract all day hours
    day_hours = re.findall(patterns[0], html_content, re.IGNORECASE)
    if day_hours:
        # Return as a list of day-hour strings
        return day_hours

    # Try general hours pattern
    for pattern in patterns[1:]:
        hours = extract_from_html(html_content, pattern, 1)
        if hours:
            cleaned = clean_html_text(hours)
            if cleaned and len(cleaned) > 5:
                return cleaned

    return None

def extract_place_data(html_content):
    """
    High-level function to orchestrate extraction from HTML content.
    Updated to extract from rendered HTML DOM instead of JSON (Google Maps changed structure).
    """
    # Extract minimal metadata from APP_INITIALIZATION_STATE JSON (place_id, coordinates, CID)
    json_str = extract_initial_json(html_content)
    metadata = None
    if json_str:
        metadata = parse_json_data(json_str)
        if not metadata:
            logger.debug("Could not extract metadata from APP_INITIALIZATION_STATE")
    else:
        logger.debug("APP_INITIALIZATION_STATE not found in HTML")

    # Extract all fields from HTML DOM (primary method) and metadata (fallback)
    place_details = {
        "name": get_main_name(html_content, metadata),
        "place_id": get_place_id(html_content, metadata),
        "coordinates": get_gps_coordinates(html_content, metadata),
        "address": get_complete_address(html_content),
        "rating": get_rating(html_content),
        "reviews_count": get_reviews_count(html_content),
        "reviews_url": get_reviews_url(html_content, metadata),
        "categories": get_categories(html_content),
        "website": get_website(html_content),
        "phone": get_phone_number(html_content),
        "thumbnail": get_thumbnail(html_content),
        "hours": get_hours(html_content),
        # Add other fields as needed
    }

    # Filter out None values
    place_details = {k: v for k, v in place_details.items() if v is not None}

    if not place_details or not place_details.get('name'):
        logger.warning("Failed to extract sufficient place data from HTML")
        return None

    logger.info(f"Successfully extracted data for: {place_details.get('name')}")
    return place_details

# Example usage (for testing):
if __name__ == '__main__':
    # Configure basic logging for standalone execution
    logging.basicConfig(level=logging.INFO)

    # Load sample HTML content from a file (replace 'sample_place.html' with your file)
    try:
        with open('sample_place.html', 'r', encoding='utf-8') as f:
            sample_html = f.read()

        extracted_info = extract_place_data(sample_html)

        if extracted_info:
            print("Extracted Place Data:")
            print(json.dumps(extracted_info, indent=2))
        else:
            logger.warning("Could not extract data from the sample HTML.")

    except FileNotFoundError:
        logger.warning("Sample HTML file 'sample_place.html' not found. Cannot run example.")
    except Exception as e:
        logger.error(f"An error occurred during example execution: {e}")