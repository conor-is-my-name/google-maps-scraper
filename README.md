# Google Maps Scraper API

A FastAPI service for scraping Google Maps data based on search queries. Ideal for n8n users.

Very high performance, watch out for rate limiting!

Use variables to replace URL parameters

scrape-get?query=hotels%20in%2098392&max_places=100&lang=en&headless=true"

If using n8n or other automation, use the /scrape-get endpoint for it to return results

simple install, copy files and run docker compose up -d

Intened to be used with this n8n build: 
https://github.com/conor-is-my-name/n8n-autoscaling 

## API Endpoints

### POST `/scrape`
Main endpoint for scraping Google Maps data (accepts JSON body)

### GET `/scrape-get`
Alternative GET endpoint with query parameters (recommended for n8n and webhooks)

### GET `/`
Health check endpoint

## API Parameters

All endpoints support the same parameters:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | **Yes** | - | Search query (e.g., "hotels in 98392", "restaurants near Times Square") |
| `max_places` | integer | No | `null` | Maximum number of results to return. If not set, returns all found results |
| `lang` | string | No | `"en"` | Language code for results. Supports: `en`, `es`, `fr`, `de`, `pt`, and more |
| `headless` | boolean | No | `true` | Run browser in headless mode. Set to `false` for debugging |
| `concurrency` | integer | No | `5` | Number of concurrent browser tabs for scraping (range: 1-20). Higher = faster but more detection risk |

### Parameter Notes
- **query**: URL encode special characters when using GET endpoint
- **max_places**: Useful for limiting API costs and response time. Without this, the scraper will continue until all results are found or the end of the list is reached
- **lang**: Affects both the language of results and consent form detection
- **headless**: Set to `false` only for local debugging (not recommended in Docker)
- **concurrency**: Default of 5 is balanced. Increase for speed (max 10 recommended) or decrease to 1-2 if experiencing rate limiting

## Example Requests

### POST Example
```bash
curl -X POST "http://localhost:8001/scrape" \
-H "Content-Type: application/json" \
-d '{
  "query": "hotels in 98392",
  "max_places": 10,
  "lang": "en",
  "headless": true,
  "concurrency": 5
}'
```

### GET Example (URL encoded)
```bash
curl "http://localhost:8001/scrape-get?query=hotels%20in%2098392&max_places=10&lang=en&headless=true&concurrency=5"
```

### Using with Docker service name
```bash
curl "http://gmaps_scraper_api_service:8001/scrape-get?query=coffee%20shops%20in%20seattle&max_places=50&lang=en"
```

### Scraping all results (no limit)
```bash
curl "http://localhost:8001/scrape-get?query=restaurants%20in%20miami&lang=en"
```

### Spanish language results
```bash
curl "http://localhost:8001/scrape-get?query=restaurantes%20en%20barcelona&max_places=20&lang=es"
```

### High-speed scraping (increased concurrency)
```bash
curl -X POST "http://localhost:8001/scrape" \
-H "Content-Type: application/json" \
-d '{
  "query": "gyms in los angeles",
  "max_places": 100,
  "lang": "en",
  "headless": true,
  "concurrency": 10
}'
```


## Running the Service

### Docker
```bash
docker-compose up --build
```

### Local Development
1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the API:
```bash
uvicorn gmaps_scraper_server.main_api:app --reload
```


The API will be available at `http://localhost:8001`

or for docker:

`http://gmaps_scraper_api_service:8001`

## Response Format

Each place in the results includes:

```json
{
  "name": "Starbucks",
  "place_id": "ChIJ...",
  "coordinates": {
    "latitude": 47.6062,
    "longitude": -122.3321
  },
  "address": "1912 Pike Pl, Seattle, WA 98101",
  "rating": 4.3,
  "reviews_count": 1234,
  "reviews_url": "https://search.google.com/local/reviews?placeid=...",
  "categories": ["Coffee shop", "Cafe"],
  "website": "https://www.starbucks.com",
  "phone": "2066241965",
  "thumbnail": "https://...",
  "link": "https://www.google.com/maps/place/..."
}
```

## Features

- ⚡ **Parallel processing**: Scrapes multiple places concurrently (configurable with `concurrency` parameter)
- 🌍 **Multi-language support**: Works with en, es, fr, de, pt, and more
- 🔗 **Direct reviews link**: Each result includes a direct link to the reviews page
- 🛡️ **Anti-detection**: Random delays and user agent rotation to avoid rate limiting
- 🔄 **Robust error handling**: Multiple fallback strategies for consent forms and feed detection

## Troubleshooting

### "Feed element not found" error
- This usually means Google Maps changed its DOM structure or no results were found
- The scraper now has multiple fallback strategies to handle this
- Try with a different query or language parameter

### Empty results
- Check that your query returns results on Google Maps directly
- Try with `headless=false` to see what the browser is doing
- Check Docker logs: `docker logs gmaps_scraper_api_service`

### Slow performance
- Adjust the `concurrency` parameter (higher = faster but more detection risk)
- Default is 5 concurrent tabs, max recommended is 10
- Random delays are added for anti-detection (1-2 seconds per scroll)

### Language-specific issues
- Consent forms are now supported in: en, es, fr, de, pt, and more
- Use the `lang` parameter to match your target region
- Example: `lang=es` for Spanish results

## Notes
- For production use, consider adding authentication
- The scraping process may take several seconds to minutes depending on the number of results
- Recommended rate limiting: Max 500 places/day per IP, min 60s between API calls
- Use the `concurrency` parameter to tune performance vs. detection risk (default: 5)
