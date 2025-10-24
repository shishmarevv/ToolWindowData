"""
Web application for displaying statistical analysis results.
Uses FastAPI to create interactive report with plots.
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from .science import analyze_data
from .logger import get_logger
from . import resolver

logger = get_logger(__name__)

app = FastAPI(title="ToolWindow Data Analysis")

# Setup templates
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

# Cache for analysis results
analysis_cache = None


def get_analysis_results():
    """
    Gets analysis results (caches for performance).
    Protected from exceptions: logs error and returns None on failure.
    """
    global analysis_cache

    if analysis_cache is None:
        logger.info("Running analysis for the first time")
        db_path = resolver.db_path()

        # Check if database exists
        if not Path(db_path).exists():
            logger.error(f"Database file not found: {db_path}")
            return None

        try:
            # Run analysis with plots
            analysis_cache = analyze_data(db_path, create_plots=True)
            logger.info("Analysis cached successfully")
        except Exception:
            logger.exception("Failed to run analysis")
            return None

    return analysis_cache


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """
    Home page with analysis results.
    """
    logger.info("Home page requested")

    try:
        results = get_analysis_results()
    except Exception:
        logger.exception("Error getting analysis results")
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": "Internal error while loading analysis data. Check logs for details."
        })

    if not results:
        logger.error("Failed to load analysis results")
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": "Failed to load data for analysis. Database may be missing or inaccessible."
        })

    # Format data for template
    context = {
        "request": request,
        "manual_stats": results['manual']['stats'],
        "auto_stats": results['auto']['stats'],
        "test_result": results['test'],
        "effect_size": results['effect_size'],
        "plots": results.get('plots', {})
    }

    return templates.TemplateResponse("analysis.html", context)


@app.get("/api/analysis")
async def get_analysis_api():
    """
    API endpoint to get analysis results in JSON.
    """
    results = get_analysis_results()

    if not results:
        return {"error": "Failed to load data"}

    # Return results without raw data (durations) for smaller size
    return {
        "manual": {
            "stats": results['manual']['stats']
        },
        "auto": {
            "stats": results['auto']['stats']
        },
        "test": results['test'],
        "effect_size": results['effect_size']
    }


@app.post("/api/refresh")
async def refresh_analysis():
    """
    Refreshes analysis cache (recalculates results).
    """
    logger.info("Refresh analysis requested")
    global analysis_cache
    analysis_cache = None

    results = get_analysis_results()
    logger.info("Analysis refreshed successfully")

    return {
        "status": "success",
        "message": "Analysis refreshed",
        "episodes_count": {
            "manual": results['manual']['stats']['count'],
            "auto": results['auto']['stats']['count']
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

