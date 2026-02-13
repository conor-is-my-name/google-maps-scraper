import json
import asyncio
import re
import random
import logging
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from urllib.parse import urlencode

# Import the extraction functions from our helper module
from . import extractor

# --- Logging Configuration ---
logger = logging.getLogger(__name__)

# --- Constants ---
BASE_URL = "https://www.google.com/maps/search/"
DEFAULT_TIMEOUT = 30000  # 30 seconds for navigation and selectors
SCROLL_PAUSE_TIME = 1.5  # Pause between scrolls
MAX_SCROLL_ATTEMPTS_WITHOUT_NEW_LINKS = 5 # Stop scrolling if no new links found after this many scrolls

# User agent rotation for anti-detection
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]

def random_delay(min_sec=1.0, max_sec=2.0):
    """Returns random delay for anti-detection"""
    return random.uniform(min_sec, max_sec)

# --- Helper Functions ---
def create_search_url(query, lang="en", geo_coordinates=None, zoom=None):
    """Creates a Google Maps search URL."""
    params = {'q': query, 'hl': lang}
    # Note: geo_coordinates and zoom might require different URL structure (/maps/@lat,lng,zoom)
    # For simplicity, starting with basic query search
    return BASE_URL + "?" + urlencode(params)

async def scrape_place_details(context, link, semaphore):
    """
    Scrapes details for a single place using a new page from the browser context.
    Uses a semaphore to limit concurrency.
    """
    async with semaphore:
        page = await context.new_page()
        try:
            logger.info(f"Processing link: {link}")
            await page.goto(link, wait_until='domcontentloaded')
            
            # Wait a bit for dynamic content if needed
            # await page.wait_for_load_state('networkidle', timeout=10000)

            html_content = await page.content()
            place_data = extractor.extract_place_data(html_content)

            if place_data:
                place_data['link'] = link
                return place_data
            else:
                logger.warning(f"Failed to extract data for: {link}")
                # Optionally save the HTML for debugging
                # with open(f"error_page_{hash(link)}.html", "w", encoding="utf-8") as f:
                #     f.write(html_content)
                return None

        except PlaywrightTimeoutError:
            logger.warning(f"Timeout navigating to or processing: {link}")
            return None
        except Exception as e:
            logger.error(f"Error processing {link}: {e}")
            return None
        finally:
            await page.close()

# --- Main Scraping Logic ---
async def scrape_google_maps(query, max_places=None, lang="en", headless=True, concurrency=5):
    """
    Scrapes Google Maps for places based on a query.

    Args:
        query (str): The search query (e.g., "restaurants in New York").
        max_places (int, optional): Maximum number of places to scrape. Defaults to None (scrape all found).
        lang (str, optional): Language code for Google Maps (e.g., 'en', 'es'). Defaults to "en".
        headless (bool, optional): Whether to run the browser in headless mode. Defaults to True.
        concurrency (int, optional): Number of concurrent tabs for scraping details. Defaults to 5.

    Returns:
        list: A list of dictionaries, each containing details for a scraped place.
              Returns an empty list if no places are found or an error occurs.
    """
    results = []
    place_links = set()
    scroll_attempts_no_new = 0
    browser = None

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(
                headless=headless,
                args=[
                    '--disable-dev-shm-usage',  # Use /tmp instead of /dev/shm for shared memory
                    '--no-sandbox',  # Required for running in Docker
                    '--disable-setuid-sandbox',
                ]
            )
            context = await browser.new_context(
                user_agent=random.choice(USER_AGENTS),  # Random user agent for anti-detection
                java_script_enabled=True,
                accept_downloads=False,
                locale=lang,
            )
            
            # --- Step 1: Search and Scroll to collect links ---
            page = await context.new_page()
            if not page:
                await browser.close()
                raise Exception("Failed to create a new browser page (context.new_page() returned None).")

            search_url = create_search_url(query, lang)
            logger.info(f"Navigating to search URL: {search_url}")
            await page.goto(search_url, wait_until='domcontentloaded')
            await asyncio.sleep(2)

            # --- Handle potential consent forms ---
            try:
                # Expanded consent xpath to include Spanish and input elements (from PR #7)
                consent_xpath = "//button[.//span[contains(text(), 'Accept all') or contains(text(), 'Reject all') or contains(text(), 'Aceptar todo') or contains(text(), 'Rechazar todo') or contains(text(), 'Accept')]] | //input[@type='submit' and (@value='Accept all' or @value='Reject all' or @value='Aceptar todo' or @value='Rechazar todo')]"

                # Wait briefly for the button to potentially appear
                await page.wait_for_selector(consent_xpath, state='visible', timeout=5000)

                # Prioritize "Accept all" / "Aceptar todo"
                accept_button = await page.query_selector("//button[.//span[contains(text(), 'Accept all') or contains(text(), 'Aceptar todo')]] | //input[@type='submit' and (@value='Accept all' or @value='Aceptar todo')]")
                if accept_button:
                    logger.info("Accepting consent form...")
                    await accept_button.click()
                else:
                    # Fallback
                    logger.info("Clicking available consent button...")
                    await page.locator(consent_xpath).first.click()

                # Wait for navigation/popup closure
                await page.wait_for_load_state('networkidle', timeout=5000)
            except PlaywrightTimeoutError:
                logger.debug("No consent form detected or timed out waiting.")
            except Exception as e:
                logger.warning(f"Error handling consent form: {e}")


            # --- Scrolling and Link Extraction ---
            logger.info("Scrolling to load places...")
            feed_selector = '[role="feed"]'
            found_feed = False

            # Attempt to find feed with fallbacks (from PR #7)
            try:
                await page.wait_for_selector(feed_selector, state='visible', timeout=10000)
                found_feed = True
            except PlaywrightTimeoutError:
                logger.info(f"Primary feed selector '{feed_selector}' not found. Checking fallbacks...")

            if not found_feed:
                # Check if it's a single result page (maps/place/)
                if "/maps/place/" in page.url:
                    logger.info("Detected single place page.")
                    place_links.add(page.url)
                else:
                    # Try to find place links directly (PR #7 fallback)
                    links = await page.locator('a[href*="/maps/place/"]').evaluate_all('elements => elements.map(a => a.href)')
                    if links:
                        logger.info(f"Found {len(links)} place links directly without feed selector.")
                        place_links.update(links)
                        # We won't be able to scroll effectively, but we have visible links
                    else:
                        logger.error(f"Error: Feed element not found. Page content may be unexpected.")
                        await browser.close()
                        return []

            if found_feed and await page.locator(feed_selector).count() > 0:
                last_height = await page.evaluate(f'document.querySelector(\'{feed_selector}\').scrollHeight')
                while True:
                    # Scroll down
                    await page.evaluate(f'document.querySelector(\'{feed_selector}\').scrollTop = document.querySelector(\'{feed_selector}\').scrollHeight')
                    await asyncio.sleep(random_delay(1.0, 2.0))  # Random delay for anti-detection

                    # Extract links after scroll
                    current_links_list = await page.locator(f'{feed_selector} a[href*="/maps/place/"]').evaluate_all('elements => elements.map(a => a.href)')
                    current_links = set(current_links_list)
                    new_links_found = len(current_links - place_links) > 0
                    place_links.update(current_links)
                    logger.info(f"Found {len(place_links)} unique place links so far...")

                    if max_places is not None and len(place_links) >= max_places:
                        logger.info(f"Reached max_places limit ({max_places}).")
                        place_links = set(list(place_links)[:max_places]) # Trim excess links
                        break

                    # Check if scroll height has changed
                    new_height = await page.evaluate(f'document.querySelector(\'{feed_selector}\').scrollHeight')
                    if new_height == last_height:
                        # Check for the "end of results" marker
                        # Check for end marker in multiple languages (PR #7)
                        end_marker_xpath = "//span[contains(text(), \"You've reached the end of the list.\") or contains(text(), \"Has llegado al final de la lista\")]"
                        if await page.locator(end_marker_xpath).count() > 0:
                            logger.info("Reached the end of the results list.")
                            break
                        else:
                            # If height didn't change but end marker isn't there, maybe loading issue?
                            if not new_links_found:
                                scroll_attempts_no_new += 1
                                logger.debug(f"Scroll height unchanged and no new links. Attempt {scroll_attempts_no_new}/{MAX_SCROLL_ATTEMPTS_WITHOUT_NEW_LINKS}")
                                if scroll_attempts_no_new >= MAX_SCROLL_ATTEMPTS_WITHOUT_NEW_LINKS:
                                    logger.info("Stopping scroll due to lack of new links.")
                                    break
                            else:
                                scroll_attempts_no_new = 0 # Reset if new links were found this cycle
                    else:
                        last_height = new_height
                        scroll_attempts_no_new = 0 # Reset if scroll height changed

            # Close the search page as we have the links now
            await page.close()

            # --- Step 2: Scraping Individual Places in Parallel ---
            logger.info(f"Scraping details for {len(place_links)} places with concurrency {concurrency}...")
            
            semaphore = asyncio.Semaphore(concurrency)
            tasks = [scrape_place_details(context, link, semaphore) for link in place_links]
            
            # Run tasks and gather results
            scraped_results = await asyncio.gather(*tasks)
            
            # Filter out None results (failed scrapes)
            results = [r for r in scraped_results if r is not None]

            await browser.close()

        except PlaywrightTimeoutError:
            logger.error(f"Timeout error during scraping process.")
        except Exception as e:
            logger.error(f"An error occurred during scraping: {e}", exc_info=True)
        finally:
            # Ensure browser is closed if an error occurred mid-process
            if browser and browser.is_connected():
                await browser.close()

    logger.info(f"Scraping finished. Found details for {len(results)} places.")
    return results