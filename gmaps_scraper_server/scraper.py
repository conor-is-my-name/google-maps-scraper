import logging
import asyncio
import urllib.parse
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def extract_place_details(page, place_url, extract_full_details=False):
    """
    Extrait les détails d'un lieu en naviguant vers son URL
    """
    try:
        # Extraire nom depuis URL (fallback)
        name = "N/A"
        if place_url and '/maps/place/' in place_url:
            try:
                name_part = place_url.split('/maps/place/')[1].split('/data=')[0]
                name = urllib.parse.unquote_plus(name_part)
            except:
                pass
        
        place_data = {
            'name': name,
            'url': place_url,
        }
        
        # Naviguer vers la page du lieu
        logger.info(f"Processing: {name}")
        await page.goto(place_url, wait_until='domcontentloaded', timeout=15000)
        await asyncio.sleep(2.5)
        
        # RATING
        rating = "N/A"
        try:
            rating_selectors = [
                'div[role="main"] span[aria-label*="star"]',
                'span[role="img"][aria-label*="star"]',
            ]
            for sel in rating_selectors:
                rating_elem = await page.query_selector(sel)
                if rating_elem:
                    aria = await rating_elem.get_attribute('aria-label')
                    if aria and 'star' in aria.lower():
                        rating = aria.split()[0]
                        break
        except Exception as e:
            logger.debug(f"Rating extraction error: {e}")
        
        # REVIEWS COUNT - Amélioration
        reviews_count = "0"
        try:
            # Chercher le bouton avec le nombre d'avis
            reviews_selectors = [
                'button[aria-label*="review"]',
                'div[role="main"] button[jsaction*="pane.rating"]',
            ]
            for sel in reviews_selectors:
                reviews_elem = await page.query_selector(sel)
                if reviews_elem:
                    # Essayer d'abord aria-label
                    aria = await reviews_elem.get_attribute('aria-label')
                    if aria and 'review' in aria.lower():
                        parts = aria.split()
                        if parts:
                            reviews_count = ''.join(filter(str.isdigit, parts[0]))
                            if reviews_count:
                                break
                    
                    # Sinon, essayer le texte intérieur
                    text = await reviews_elem.inner_text()
                    if text and 'review' in text.lower():
                        parts = text.split()
                        if parts:
                            reviews_count = ''.join(filter(str.isdigit, parts[0]))
                            if reviews_count:
                                break
        except Exception as e:
            logger.debug(f"Reviews extraction error: {e}")
        
        # CATEGORY - Amélioration
        category = "N/A"
        try:
            # Chercher le bouton de catégorie juste après le rating
            category_selectors = [
                'button[jsaction*="pane.rating.category"]',
                'div[role="main"] button[class*="DkEaL"]',
                # Nouveau : chercher dans les boutons près du rating
                'div[role="main"] div[class*="F7nice"] button',
            ]
            for sel in category_selectors:
                cat_elem = await page.query_selector(sel)
                if cat_elem:
                    cat_text = await cat_elem.inner_text()
                    if cat_text and cat_text.strip() and len(cat_text) < 50:
                        category = cat_text.strip()
                        break
        except Exception as e:
            logger.debug(f"Category extraction error: {e}")
        
        place_data.update({
            'rating': rating,
            'reviews_count': reviews_count,
            'category': category,
        })
        
        # Détails supplémentaires si demandé
        if extract_full_details:
            # Téléphone
            phone = "N/A"
            try:
                phone_selectors = [
                    'button[data-item-id*="phone"]',
                    'button[aria-label*="Phone"]',
                    'button[aria-label*="phone"]'
                ]
                for sel in phone_selectors:
                    phone_elem = await page.query_selector(sel)
                    if phone_elem:
                        phone_aria = await phone_elem.get_attribute('aria-label')
                        if phone_aria and ':' in phone_aria:
                            phone = phone_aria.split(':')[-1].strip()
                            break
            except Exception as e:
                logger.debug(f"Phone extraction error: {e}")
            
            # Site web
            website = "N/A"
            try:
                website_elem = await page.query_selector('a[data-item-id="authority"]')
                if website_elem:
                    website = await website_elem.get_attribute('href')
            except Exception as e:
                logger.debug(f"Website extraction error: {e}")
            
            # Adresse
            address = "N/A"
            try:
                address_elem = await page.query_selector('button[data-item-id="address"]')
                if address_elem:
                    address_aria = await address_elem.get_attribute('aria-label')
                    if address_aria and ':' in address_aria:
                        address = address_aria.split(':', 1)[-1].strip()
            except Exception as e:
                logger.debug(f"Address extraction error: {e}")
            
            # Horaires - Amélioration
            hours = "N/A"
            try:
                # Méthode 1: Chercher le bouton avec aria-label
                hours_selectors = [
                    'button[data-item-id*="oh"]',
                    'button[aria-label*="Hide open hours"]',
                    'button[aria-label*="Show open hours"]',
                ]
                
                for sel in hours_selectors:
                    hours_elem = await page.query_selector(sel)
                    if hours_elem:
                        hours_aria = await hours_elem.get_attribute('aria-label')
                        if hours_aria and ('open' in hours_aria.lower() or 'close' in hours_aria.lower()):
                            hours = hours_aria
                            break
                
                # Méthode 2: Chercher dans les spans avec "Open" ou "Closed"
                if hours == "N/A":
                    # Chercher spécifiquement dans la section d'information
                    info_divs = await page.query_selector_all('div[role="main"] div[class*="rogA2c"]')
                    for div in info_divs:
                        text = await div.inner_text()
                        if text:
                            text_lower = text.lower()
                            # Vérifier que c'est bien des horaires (contient "open" ou "closed" ET "am" ou "pm")
                            if (('open' in text_lower or 'closed' in text_lower) and 
                                ('am' in text_lower or 'pm' in text_lower or ':' in text)):
                                hours = text
                                break
                
                # Méthode 3: Fallback général (plus large)
                if hours == "N/A":
                    status_texts = await page.query_selector_all('div[role="main"] span')
                    for span in status_texts:
                        text = await span.inner_text()
                        if text:
                            text_lower = text.lower()
                            if (('opens' in text_lower or 'closes' in text_lower or 'open ⋅' in text_lower) and
                                (len(text) < 100)):  # Éviter les longs textes
                                hours = text
                                break
                            
            except Exception as e:
                logger.debug(f"Hours extraction error: {e}")
            
            place_data.update({
                'phone': phone,
                'website': website,
                'address': address,
                'hours': hours,
            })
        
        logger.info(f"✓ Extracted: {name} (rating: {rating}, reviews: {reviews_count}, category: {category})")
        return place_data
        
    except Exception as e:
        logger.error(f"Error extracting place {name}: {e}")
        return None


async def process_places_parallel(context, place_urls, max_places, extract_details, max_workers=3):
    """
    Traite plusieurs lieux en parallèle
    """
    results = []
    semaphore = asyncio.Semaphore(max_workers)
    
    async def worker(place_url):
        async with semaphore:
            page = await context.new_page()
            try:
                result = await extract_place_details(page, place_url, extract_details)
                return result
            finally:
                await page.close()
    
    tasks = [worker(url) for url in place_urls[:max_places]]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    valid_results = [r for r in results if r is not None and not isinstance(r, Exception)]
    
    return valid_results


async def scrape_google_maps(query: str, max_places: int = 10, lang: str = "en", headless: bool = True, extract_details: bool = False):
    """
    Scrape Google Maps avec parallélisation
    """
    results = []
    
    async with async_playwright() as p:
        try:
            logger.info(f"Launching browser (headless={headless})...")
            browser = await p.chromium.launch(
                headless=headless,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--disable-web-security',
                    '--disable-site-isolation-trials',
                    '--disable-gpu',
                    '--disable-software-rasterizer',
                    '--disable-extensions',
                    '--single-process',
                ]
            )
            
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale=lang,
                timezone_id='Europe/Paris',
                geolocation={'latitude': 48.8566, 'longitude': 2.3522},
                permissions=['geolocation']
            )
            
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en', 'fr'] });
                window.chrome = { runtime: {} };
            """)
            
            page = await context.new_page()
            
            search_url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}?hl={lang}"
            logger.info(f"Navigating to: {search_url}")
            
            await page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(2)
            
            # Gérer consentement
            logger.info("Checking for consent form...")
            consent_selectors = [
                'button:has-text("Accept all")',
                'button:has-text("Tout accepter")',
            ]
            
            for selector in consent_selectors:
                try:
                    consent_button = await page.wait_for_selector(selector, timeout=3000)
                    if consent_button:
                        await consent_button.click()
                        logger.info(f"Clicked consent button")
                        await asyncio.sleep(2)
                        break
                except PlaywrightTimeout:
                    continue
            
            # Attendre résultats
            logger.info("Waiting for results...")
            feed_element = await page.wait_for_selector('div[role="feed"]', timeout=10000, state='visible')
            
            if not feed_element:
                raise Exception("Feed element not found.")
            
            # Scroll pour charger les lieux
            logger.info("Scrolling to load places...")
            places_loaded = 0
            scroll_attempts = 0
            
            while places_loaded < max_places and scroll_attempts < 20:
                current_places = await page.query_selector_all('a[href*="/maps/place/"]')
                places_loaded = len(current_places)
                logger.info(f"Loaded {places_loaded} places...")
                
                if places_loaded >= max_places:
                    break
                
                await feed_element.evaluate('element => element.scrollTop = element.scrollHeight')
                await asyncio.sleep(1.5)
                scroll_attempts += 1
            
            # Récupérer toutes les URLs
            place_links = await page.query_selector_all('a[href*="/maps/place/"]')
            place_urls = []
            for link in place_links[:max_places]:
                url = await link.get_attribute('href')
                if url:
                    place_urls.append(url)
            
            logger.info(f"Starting parallel extraction of {len(place_urls)} places...")
            
            # Traitement parallèle avec 3 workers
            results = await process_places_parallel(
                context, 
                place_urls, 
                max_places, 
                extract_details,
                max_workers=3
            )
            
            await page.close()
            await browser.close()
            
        except Exception as e:
            logger.error(f"An error occurred during scraping: {e}")
            if 'browser' in locals():
                await browser.close()
            raise
    
    logger.info(f"Scraping finished. Found {len(results)} places.")
    return results


async def main():
    """Test function"""
    import time
    
    print("\n=== TEST SCRAPER ===")
    start = time.time()
    results = await scrape_google_maps("hotel paris", max_places=3, lang="en", extract_details=True)
    elapsed = time.time() - start
    
    print(f"\n✓ Extracted {len(results)} places in {elapsed:.1f} seconds")
    
    for place in results:
        print(f"\n{place['name']}")
        print(f"  Rating: {place.get('rating', 'N/A')} ({place.get('reviews_count', '0')} reviews)")
        print(f"  Category: {place.get('category', 'N/A')}")
        print(f"  Phone: {place.get('phone', 'N/A')}")
        print(f"  Address: {place.get('address', 'N/A')}")
        print(f"  Hours: {place.get('hours', 'N/A')}")


if __name__ == "__main__":
    asyncio.run(main())
