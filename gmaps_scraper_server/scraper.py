import json
import asyncio # Changed from time
import re
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError # Changed to async
from urllib.parse import urlencode

# Import the extraction functions from our helper module
from . import extractor

# --- Constants ---
BASE_URL = "https://www.google.com/maps/search/"
DEFAULT_TIMEOUT = 30000  # 30 seconds for navigation and selectors
SCROLL_PAUSE_TIME = 1.5  # Pause between scrolls
MAX_SCROLL_ATTEMPTS_WITHOUT_NEW_LINKS = 5 # Stop scrolling if no new links found after this many scrolls

# --- Helper Functions ---
def create_search_url(query, lang="en", geo_coordinates=None, zoom=None):
    """Creates a Google Maps search URL."""
    params = {'q': query, 'hl': lang}
    # Note: geo_coordinates and zoom might require different URL structure (/maps/@lat,lng,zoom)
    # For simplicity, starting with basic query search
    return BASE_URL + "?" + urlencode(params)

# --- Main Scraping Logic ---
async def scrape_google_maps(query, max_places=None, lang="en", headless=True): # Added async
    """
    Scrapes Google Maps for places based on a query.

    Args:
        query (str): The search query (e.g., "restaurants in New York").
        max_places (int, optional): Maximum number of places to scrape. Defaults to None (scrape all found).
        lang (str, optional): Language code for Google Maps (e.g., 'en', 'es'). Defaults to "en".
        headless (bool, optional): Whether to run the browser in headless mode. Defaults to True.

    Returns:
        list: A list of dictionaries, each containing details for a scraped place.
              Returns an empty list if no places are found or an error occurs.
    """
    results = []
    place_links = set()
    scroll_attempts_no_new = 0
    browser = None

    async with async_playwright() as p: # Changed to async
        try:
            browser = await p.chromium.launch(
                headless=headless,
                args=[
                    '--disable-dev-shm-usage',  # Use /tmp instead of /dev/shm for shared memory
                    '--no-sandbox',  # Required for running in Docker
                    '--disable-setuid-sandbox',
                ]
            ) # Added await
            context = await browser.new_context( # Added await
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                java_script_enabled=True,
                accept_downloads=False,
                # Consider setting viewport, locale, timezone if needed
                locale=lang,
            )
            page = await context.new_page() # Added await
            if not page:
                await browser.close() # Close browser before raising
                raise Exception("Failed to create a new browser page (context.new_page() returned None).")
            
            search_url = create_search_url(query, lang)
            print(f"Navigating to search URL: {search_url}")
            await page.goto(search_url, wait_until='domcontentloaded') # Added await
            await asyncio.sleep(2) # Changed to asyncio.sleep, added await

            # --- Handle potential consent forms ---
            try:
                # Expanded consent xpath to include Spanish and generic terms, covering both button and input elements
                consent_xpath = "//button[.//span[contains(text(), 'Accept all') or contains(text(), 'Reject all') or contains(text(), 'Aceptar todo') or contains(text(), 'Rechazar todo') or contains(text(), 'Accept')]] | //input[@type='submit' and (@value='Accept all' or @value='Reject all' or @value='Aceptar todo' or @value='Rechazar todo')]"
                
                # Wait briefly for the button to potentially appear
                await page.wait_for_selector(consent_xpath, state='visible', timeout=5000)
                
                # Prioritize "Accept all" / "Aceptar todo"
                accept_button = await page.query_selector("//button[.//span[contains(text(), 'Accept all') or contains(text(), 'Aceptar todo')]] | //input[@type='submit' and (@value='Accept all' or @value='Aceptar todo')]")
                if accept_button:
                    print("Accepting consent form...")
                    await accept_button.click()
                else:
                    # Fallback
                    print("Clicking available consent button...")
                    await page.locator(consent_xpath).first.click()
                
                # Wait for navigation/popup closure
                await page.wait_for_load_state('networkidle', timeout=5000)
            except PlaywrightTimeoutError:
                print("No consent form detected or timed out waiting.")
            except Exception as e:
                print(f"Error handling consent form: {e}")


            # --- Scrolling and Link Extraction ---
            print("Scrolling to load places...")
            feed_selector = '[role="feed"]'
            found_feed = False

            # Attempt to find feed with fallbacks
            try:
                await page.wait_for_selector(feed_selector, state='visible', timeout=10000) # Reduced timeout for primary
                found_feed = True
            except PlaywrightTimeoutError:
                print(f"Primary feed selector '{feed_selector}' not found. Checking fallbacks/alternatives...")
                # Fallback strategies could go here if we identify other containers
                # For now, we'll proceed to check single page or error

            if not found_feed:
                 # Check if it's a single result page (maps/place/)
                if "/maps/place/" in page.url:
                    print("Detected single place page.")
                    place_links.add(page.url)
                else:
                    # DEBUG: Save HTML to file to inspect structure
                    print("Feed not found. Saving HTML to 'debug_page.html'...")
                    with open("debug_page.html", "w", encoding="utf-8") as f:
                        f.write(await page.content())
                    
                    print(f"Page Title: {await page.title()}")
                    
                    # Try to find any place links directly
                    links = await page.locator('a[href*="/maps/place/"]').evaluate_all('elements => elements.map(a => a.href)')
                    if links:
                        print(f"Found {len(links)} place links directly without feed selector.")
                        place_links.update(links)
                        # We might not be able to scroll effectively without the feed container, 
                        # but we can at least scrape what's visible.
                        # Try to guess feed selector from the first link's parent
                        # ... (omitted for now, just proceeding with what we have)
                    else:
                        print(f"Error: Feed element not found. Page content might be unexpected.")
                        await browser.close() # Added await
                        return [] # No results or page structure changed

            if found_feed and await page.locator(feed_selector).count() > 0: # Added await
                last_height = await page.evaluate(f'document.querySelector(\'{feed_selector}\').scrollHeight') # Added await
                while True:
                    # Scroll down
                    await page.evaluate(f'document.querySelector(\'{feed_selector}\').scrollTop = document.querySelector(\'{feed_selector}\').scrollHeight') # Added await
                    await asyncio.sleep(SCROLL_PAUSE_TIME) # Changed to asyncio.sleep, added await

                    # Extract links after scroll
                    current_links_list = await page.locator(f'{feed_selector} a[href*="/maps/place/"]').evaluate_all('elements => elements.map(a => a.href)') # Added await
                    current_links = set(current_links_list)
                    new_links_found = len(current_links - place_links) > 0
                    place_links.update(current_links)
                    print(f"Found {len(place_links)} unique place links so far...")

                    if max_places is not None and len(place_links) >= max_places:
                        print(f"Reached max_places limit ({max_places}).")
                        place_links = set(list(place_links)[:max_places]) # Trim excess links
                        break

                    # Check if scroll height has changed
                    new_height = await page.evaluate(f'document.querySelector(\'{feed_selector}\').scrollHeight') # Added await
                    if new_height == last_height:
                        # Check for the "end of results" marker
                        end_marker_xpath = "//span[contains(text(), \"You've reached the end of the list.\") or contains(text(), \"Has llegado al final de la lista\")]"
                        if await page.locator(end_marker_xpath).count() > 0: # Added await
                            print("Reached the end of the results list.")
                            break
                        else:
                            # If height didn't change but end marker isn't there, maybe loading issue?
                            # Increment no-new-links counter
                            if not new_links_found:
                                scroll_attempts_no_new += 1
                                print(f"Scroll height unchanged and no new links. Attempt {scroll_attempts_no_new}/{MAX_SCROLL_ATTEMPTS_WITHOUT_NEW_LINKS}")
                                if scroll_attempts_no_new >= MAX_SCROLL_ATTEMPTS_WITHOUT_NEW_LINKS:
                                    print("Stopping scroll due to lack of new links.")
                                    break
                            else:
                                scroll_attempts_no_new = 0 # Reset if new links were found this cycle
                    else:
                        last_height = new_height
                        scroll_attempts_no_new = 0 # Reset if scroll height changed

                    # Optional: Add a hard limit on scrolls to prevent infinite loops
                    # if scroll_count > MAX_SCROLLS: break

            # --- Scraping Individual Places ---
            print(f"\nScraping details for {len(place_links)} places...")
            count = 0
            for link in place_links:
                count += 1
                print(f"Processing link {count}/{len(place_links)}: {link}") # Keep sync print
                try:
                    await page.goto(link, wait_until='domcontentloaded') # Added await
                    # Wait a bit for dynamic content if needed, or wait for a specific element
                    # await page.wait_for_load_state('networkidle', timeout=10000) # Or networkidle if needed

                    html_content = await page.content() # Added await
                    place_data = extractor.extract_place_data(html_content)

                    if place_data:
                        place_data['link'] = link # Add the source link
                        results.append(place_data)
                        # print(json.dumps(place_data, indent=2)) # Optional: print data as it's scraped
                    else:
                        print(f"  - Failed to extract data for: {link}")
                        # Optionally save the HTML for debugging
                        # with open(f"error_page_{count}.html", "w", encoding="utf-8") as f:
                        #     f.write(html_content)

                except PlaywrightTimeoutError:
                    print(f"  - Timeout navigating to or processing: {link}")
                except Exception as e:
                    print(f"  - Error processing {link}: {e}")
                await asyncio.sleep(0.5) # Changed to asyncio.sleep, added await

            await browser.close() # Added await

        except PlaywrightTimeoutError:
            print(f"Timeout error during scraping process.")
        except Exception as e:
            print(f"An error occurred during scraping: {e}")
            import traceback
            traceback.print_exc() # Print detailed traceback for debugging
        finally:
            # Ensure browser is closed if an error occurred mid-process
            if browser and browser.is_connected(): # Check if browser exists and is connected
                await browser.close() # Added await

    print(f"\nScraping finished. Found details for {len(results)} places.")
    return results
