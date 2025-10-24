"""
Configuration resolver module.
Reads environment variables and provides default values.
"""

import os
from pathlib import Path


def csv_path():
    """Get CSV file path from environment or use default."""
    root = Path(__file__).resolve().parent.parent
    default_csv_path = root / "data" / "toolwindow_data.csv"
    csv_path = Path(os.getenv("CSV_PATH", str(default_csv_path)))
    return str(csv_path)


def db_path():
    """Get database path from environment or use default."""
    root = Path(__file__).resolve().parent.parent
    default_db_path = root / "database" / "toolwindow.db"
    db_path = Path(os.getenv("DB_PATH", str(default_db_path)))
    return str(db_path)


def max_duration():
    """Get maximum duration threshold in minutes from environment or use default (12 hours)."""
    default_max_duration = 12 * 60  # 12 hours in minutes
    max_duration = int(os.getenv("MAX_DURATION", default_max_duration))
    return max_duration


def workers_count():
    """Get number of worker threads from environment or use default."""
    default_workers_count = 4
    workers_count = int(os.getenv("WORKERS_COUNT", default_workers_count))
    return workers_count


def user_batch_size():
    """Get user batch size from environment or use default."""
    default_user_batch_size = 100
    user_batch_size = int(os.getenv("USER_BATCH_SIZE", default_user_batch_size))
    return user_batch_size


def batch_size():
    """Get database batch size from environment or use default."""
    default_batch_size = 100
    batch_size = int(os.getenv("BATCH_SIZE", default_batch_size))
    return batch_size

