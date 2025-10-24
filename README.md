# ToolWindow Data Analysis

Statistical analysis of tool window usage patterns in IDE environments.

## Overview

This project analyzes user behavior with IDE tool windows, investigating whether there's a meaningful difference in how long tool windows stay open depending on whether they were opened **manually** (via shortcuts, menus, icons) or **automatically** (triggered by events like debugging or test failures).

The analysis processes real-world event logs, handles messy data, reconstructs usage episodes, and performs rigorous statistical testing to determine if observed differences are significant.

## Task Description

### Objective

Analyze tool window usage data to determine if there's a statistically significant difference in session duration between manual and automatic opening methods.

### Dataset

Event log tracking tool window activity with the following fields:
- `user_id` - Anonymized user identifier
- `timestamp` - Event time in epoch milliseconds
- `event` - Either "opened" or "closed"
- `open_type` - "manual" or "auto" (only present on open events)

### Challenges

Real-world data includes:
- Close events without prior open
- Multiple opens in a row
- Opens without matching closes
- Out-of-order timestamps
- Missing or null values

### Deliverables

1. **Code**: Python pipeline with clear setup/run instructions
2. **Analysis Summary**: PDF report documenting approach, assumptions, data handling, and findings

## Features

- **Data Loading**: Efficient CSV import to SQLite with multithreading
- **Data Cleaning**: Robust anomaly detection and filtering
- **Episode Reconstruction**: Smart open/close event matching per user
- **Statistical Analysis**: 
  - Descriptive statistics (mean, median, std, quartiles)
  - Mann-Whitney U test (non-parametric group comparison)
  - Cliff's Delta effect size measurement
- **Visualization**: Automated plot generation (histograms, box plots, comparison charts)
- **Web Dashboard**: FastAPI-based interactive results viewer

## Technology Stack

- **Python 3.12+** 
- **SQLite3** - Local data storage
- **scipy** - Statistical tests
- **matplotlib** - Data visualization
- **FastAPI + Jinja2** - Web interface
- **Docker** - Containerized deployment

## Requirements

### With Docker (Recommended)
- Docker 20.10+
- Docker Compose 2.0+

### Without Docker
- Python 3.12+
- pip
- SQLite3

## Quick Start with Docker

### 1. Prepare Your Data

Place your CSV file in the `data/` directory:
```bash
cp your_toolwindow_data.csv data/toolwindow_data.csv
```

### 2. Run Complete Pipeline

```bash
make all
```

This will:
1. Build Docker images
2. Initialize SQLite database
3. Load and clean data
4. Perform statistical analysis
5. Generate plots
6. Start web dashboard

### 3. View Results

- **Web Dashboard**: http://localhost:8000
- **Plots**: Check `./plots/` directory
- **Database**: `./database/toolwindow.db`

### Makefile Commands

```bash
make build       # Build Docker images
make init-db     # Initialize database only
make run         # Run analysis pipeline
make web         # Start web dashboard
make all         # Run complete pipeline
make logs        # View container logs
make clean       # Remove containers and volumes
make stop        # Stop running containers
```

## Manual Setup (Without Docker)

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Prepare Database

```bash
# Create database and tables
sqlite3 database/toolwindow.db < database/toolwindow.sql
```

### 3. Place CSV Data

```bash
cp your_data.csv data/toolwindow_data.csv
```

### 4. Run Analysis

```bash
# Set environment variables (optional)
export CSV_PATH=./data/toolwindow_data.csv
export DB_PATH=./database/toolwindow.db
export MAX_DURATION=720
export WORKERS_COUNT=4

# Run pipeline
python run.py
```

### 5. Start Web Dashboard

```bash
uvicorn src.web:app --host 0.0.0.0 --port 8000
```

## Configuration

Environment variables (optional, with defaults):

| Variable | Default | Description |
|----------|---------|-------------|
| `CSV_PATH` | `./data/toolwindow_data.csv` | Input CSV file path |
| `DB_PATH` | `./database/toolwindow.db` | SQLite database path |
| `MAX_DURATION` | `720` | Max episode duration (minutes) |
| `WORKERS_COUNT` | `4` | Number of worker threads |
| `BATCH_SIZE` | `100` | Database batch insert size |
| `LOG_LEVEL` | `INFO` | Logging level |

Create `.env` file in project root to customize:
```bash
CSV_PATH=/app/data/toolwindow_data.csv
MAX_DURATION=720
WORKERS_COUNT=4
LOG_LEVEL=DEBUG
```

## Project Structure

```
ToolWindowData/
├── run.py                      # Main pipeline entry point
├── Dockerfile                  # Docker image definition
├── docker-compose.yml          # Multi-container orchestration
├── Makefile                    # Convenience commands
├── requirements.txt            # Python dependencies
├── src/
│   ├── loader.py              # CSV → SQLite import
│   ├── janitor.py             # Data cleaning & anomaly detection
│   ├── science.py             # Statistical analysis
│   ├── web.py                 # FastAPI web application
│   ├── resolver.py            # Environment configuration
│   └── logger.py              # Logging setup
├── data/
│   └── toolwindow_data.csv    # Input data (user-provided)
├── database/
│   ├── toolwindow.sql         # Database schema
│   └── toolwindow.db          # SQLite database (generated)
├── plots/                      # Generated visualizations
│   ├── histogram.png
│   ├── boxplot.png
│   └── comparison.png
└── templates/                  # HTML templates for web
    ├── analysis.html
    └── error.html
```

## Database Schema

### `events` Table
Raw events loaded from CSV:
- `id` - Auto-increment primary key
- `user_id` - User identifier
- `timestamp` - Event time (milliseconds)
- `event` - 'opened' or 'closed'
- `type` - 'manual', 'auto', or NULL

### `clear` Table
Clean episode records after filtering:
- `id` - Episode identifier
- `type` - 'manual' or 'auto'
- `start` - Opening timestamp
- `end` - Closing timestamp
- `open_event_id` - Reference to events table
- `close_event_id` - Reference to events table

### `anomaly` Table
Filtered anomalous events with reason:
- Same fields as `events` table
- `detail` - Anomaly type (e.g., 'missing_close', 'duplicate_open')

## Analysis Approach

### 1. Data Loading
- Import CSV with multithreaded processing
- Validate and normalize event types
- Store raw events in SQLite

### 2. Data Cleaning
- Match open/close pairs per user chronologically
- Filter anomalies:
  - Missing opens/closes
  - Duplicate opens
  - NULL types
  - Negative durations
  - Duration exceeds threshold
- Store clean episodes and anomalies separately

### 3. Statistical Testing
- Calculate duration statistics for manual/auto groups
- Perform Mann-Whitney U test (non-parametric, no normality assumption)
- Compute Cliff's Delta effect size
- Generate visualizations

### 4. Results Presentation
- Web dashboard with interactive charts
- Downloadable plots
- Detailed statistics and confidence measures

## Results Interpretation

The analysis provides:
- **Descriptive Statistics**: Mean, median, standard deviation, quartiles for both groups
- **Statistical Test**: Mann-Whitney U test p-value (significance threshold: 0.05)
- **Effect Size**: Cliff's Delta magnitude (small: 0.15, medium: 0.33, large: 0.47)
- **Visualizations**: Distribution comparison, box plots, histograms

## License

This project is provided for educational and analysis purposes.

## Author

Developed as part of IDE tool window usage analysis task.

