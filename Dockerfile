FROM python:3.12-slim

WORKDIR /app

# Install system dependencies including sqlite3
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Create necessary directories
RUN mkdir -p database plots data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV CSV_PATH=/app/data/toolwindow_data.csv
ENV DB_PATH=/app/database/toolwindow.db
ENV MAX_DURATION=720
ENV WORKERS_COUNT=4
ENV LOG_LEVEL=INFO

# Default command: run analysis
CMD ["python", "run.py"]

