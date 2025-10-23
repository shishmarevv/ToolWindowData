"""
Main entry point for ToolWindowData analysis.
Automates the entire pipeline: data loading, cleaning, and analysis.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.logger import get_logger
from src import resolver
from src.loader import run as load_data
from src.janitor import run as clean_data
from src.science import analyze_data

logger = get_logger(__name__)


def main():
    """
    Main pipeline execution.
    """
    logger.info("="*60)
    logger.info("TOOLWINDOW DATA ANALYSIS PIPELINE")
    logger.info("="*60)

    # Get configuration
    csv_path = resolver.csv_path()
    db_path = resolver.db_path()
    max_duration = resolver.max_duration()
    workers_count = resolver.workers_count()
    user_batch_size = resolver.user_batch_size()
    batch_size = resolver.batch_size()

    # Validate CSV exists
    if not Path(csv_path).exists():
        logger.error(f"CSV file not found: {csv_path}")
        logger.error("Please set CSV_PATH environment variable or place file at default location")
        sys.exit(1)

    # Validate database exists
    if not Path(db_path).exists():
        logger.error(f"Database file not found: {db_path}")
        logger.error("Database should be created before running the pipeline")
        sys.exit(1)

    logger.info(f"Configuration:")
    logger.info(f"  CSV Path: {csv_path}")
    logger.info(f"  Database Path: {db_path}")
    logger.info(f"  Max Duration: {max_duration} minutes")
    logger.info(f"  Workers: {workers_count}")
    logger.info(f"  Batch Size: {batch_size}")
    logger.info("")

    # Step 1: Load data from CSV
    logger.info("STEP 1: Loading Data from CSV")
    try:
        load_data(csv_path, db_path, workers_count, batch_size)
        logger.info("Data loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load data: {e}")
        sys.exit(1)
    logger.info("")

    # Step 2: Clean data
    logger.info("STEP 2: Data Cleaning")
    try:
        clean_data(db_path, max_duration, workers_count, user_batch_size, batch_size)
        logger.info("Data cleaned successfully")
    except Exception as e:
        logger.error(f"Failed to clean data: {e}")
        sys.exit(1)
    logger.info("")

    # Step 3: Statistical analysis
    logger.info("STEP 3: Statistical Analysis")
    try:
        results = analyze_data(db_path, create_plots=True)
        if results:
            logger.info("Analysis completed successfully")

            # Save plots
            plots_dir = Path(__file__).parent / 'plots'
            plots_dir.mkdir(exist_ok=True)

            durations_by_type = {
                'manual': results['manual']['durations'],
                'auto': results['auto']['durations']
            }
            stats_by_type = {
                'manual': results['manual']['stats'],
                'auto': results['auto']['stats']
            }

            from src.science import create_histogram, create_boxplot, create_comparison_plot

            create_histogram(durations_by_type, plots_dir / 'histogram.png')
            create_boxplot(durations_by_type, plots_dir / 'boxplot.png')
            create_comparison_plot(durations_by_type, stats_by_type, plots_dir / 'comparison.png')

            logger.info(f"Plots saved to: {plots_dir}")
        else:
            logger.error("Analysis returned no results")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to analyze data: {e}")
        sys.exit(1)
    logger.info("")

    # Success
    logger.info("="*60)
    logger.info("PIPELINE COMPLETED SUCCESSFULLY")
    logger.info("="*60)
    logger.info("")
    logger.info("Next steps:")
    logger.info("  - View plots in ./plots directory")
    logger.info("  - Start web dashboard: uvicorn src.web:app --host 0.0.0.0 --port 8000")
    logger.info("")


if __name__ == '__main__':
    main()