"""
Web application for displaying statistical analysis results.
Uses FastAPI to create interactive report with plots.
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import sys

# Add path to science module
sys.path.insert(0, str(Path(__file__).parent))

from science import analyze_data
from logger import get_logger

logger = get_logger(__name__)

app = FastAPI(title="ToolWindow Data Analysis")

# Setup templates
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

# Cache for analysis results
analysis_cache = None


def get_analysis_results():
    """
    Gets analysis results (caches for performance).
    """
        logger.info("Running analysis for the first time")
    global analysis_cache

    if analysis_cache is None:
        logger.info("Analysis cached successfully")
        db_path = Path(__file__).parent.parent / 'database' / 'toolwindow.db'
        # Run analysis with plots
        analysis_cache = analyze_data(str(db_path), create_plots=True)

    return analysis_cache


    logger.info("Home page requested")
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """
        logger.error("Failed to load analysis results")
    Home page with analysis results.
    """
    results = get_analysis_results()

    if not results:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": "Failed to load data for analysis"
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
    logger.info("Refresh analysis requested")



async def refresh_analysis():

    logger.info("Analysis refreshed successfully")
    Refreshes analysis cache (recalculates results).
    """
    global analysis_cache
    analysis_cache = None

    results = get_analysis_results()

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

