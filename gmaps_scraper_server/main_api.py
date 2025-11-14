from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import logging

from gmaps_scraper_server.scraper import scrape_google_maps

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Google Maps Scraper API",
    description="API pour scraper Google Maps - Compatible n8n",
    version="2.0.0"
)


class ScrapeRequest(BaseModel):
    """Modèle de requête pour le scraping"""
    query: str
    max_places: Optional[int] = 10
    lang: Optional[str] = "en"
    headless: Optional[bool] = True
    details: Optional[bool] = False


class ScrapeResponse(BaseModel):
    """Modèle de réponse"""
    success: bool
    query: str
    total_results: int
    results: list


@app.get("/")
async def root():
    """Endpoint racine"""
    return {
        "name": "Google Maps Scraper API",
        "version": "2.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "scrape_post": "/scrape (POST)",
            "scrape_get": "/scrape-get (GET)",
            "docs": "/docs"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "google-maps-scraper"
    }


@app.post("/scrape", response_model=ScrapeResponse)
async def scrape_post(request: ScrapeRequest):
    """
    Endpoint POST pour scraper Google Maps
    """
    try:
        logger.info(
            f"Received POST scrape request for query: '{request.query}', "
            f"max_places: {request.max_places}, lang: {request.lang}, "
            f"headless: {request.headless}, details: {request.details}"
        )
        
        if not request.query or request.query.strip() == "":
            raise HTTPException(status_code=400, detail="Query parameter is required")
        
        if request.max_places < 1 or request.max_places > 100:
            raise HTTPException(status_code=400, detail="max_places must be between 1 and 100")
        
        results = await scrape_google_maps(
            query=request.query,
            max_places=request.max_places,
            lang=request.lang,
            headless=request.headless,
            extract_details=request.details
        )
        
        logger.info(f"Scraping finished for query: '{request.query}'. Found {len(results)} results.")
        
        return ScrapeResponse(
            success=True,
            query=request.query,
            total_results=len(results),
            results=results
        )
        
    except Exception as e:
        logger.error(f"Error during scraping: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")


@app.get("/scrape-get")
async def scrape_get(
    query: str = Query(..., description="Search query (e.g., 'hotel in paris')"),
    max_places: int = Query(10, ge=1, le=100, description="Maximum number of results (1-100)"),
    lang: str = Query("en", description="Language code (e.g., 'en', 'fr')"),
    headless: bool = Query(True, description="Run browser in headless mode"),
    details: bool = Query(False, description="Extract detailed info (phone, hours, etc.) - SLOWER")
):
    """
    Endpoint GET pour scraper Google Maps (compatible n8n)
    
    Paramètres:
    - query: Requête de recherche (ex: "restaurant paris")
    - max_places: Nombre max de résultats (1-100)
    - lang: Code langue (en, fr, etc.)
    - headless: Mode headless (true/false)
    - details: Extraire infos détaillées - téléphone, horaires, etc. (LENT: ~2-3 sec par lieu)
    
    Usage rapide (liste):
    /scrape-get?query=restaurant&max_places=20&details=false
    
    Usage détails complets:
    /scrape-get?query=restaurant&max_places=5&details=true
    """
    try:
        logger.info(
            f"Received GET scrape request for query: '{query}', "
            f"max_places: {max_places}, lang: {lang}, headless: {headless}, details: {details}"
        )
        
        if not query or query.strip() == "":
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Query parameter is required",
                    "results": []
                }
            )
        
        results = await scrape_google_maps(
            query=query,
            max_places=max_places,
            lang=lang,
            headless=headless,
            extract_details=details
        )
        
        logger.info(f"Scraping finished for query: '{query}'. Found {len(results)} results.")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "query": query,
                "total_results": len(results),
                "results": results
            }
        )
        
    except Exception as e:
        logger.error(f"Error during scraping: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Scraping failed: {str(e)}",
                "query": query,
                "results": []
            }
        )


@app.get("/debug")
async def debug_info():
    """Endpoint de debug"""
    import sys
    import os
    
    return {
        "python_version": sys.version,
        "working_directory": os.getcwd(),
        "display": os.environ.get("DISPLAY", "Not set"),
        "playwright_installed": True
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

