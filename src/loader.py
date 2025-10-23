import csv
import os
import threading
import queue
import sqlite3

from pathlib import Path

producer_queue: queue.Queue[dict] = queue.Queue(maxsize=200)
writer_queue: queue.Queue[tuple] = queue.Queue(maxsize=200)

SENTINEL = None

def check_event(event: str):
    if not event:
        return None
    event = event.strip().lower()
    if event in ("opened", "closed"):
        return event
    return None

def check_type(type_: str):
    if not type_:
        return None
    type_ = type_.strip().lower()
    if type_ in ("auto", "manual"):
        return type_
    return None


def load_event(row: dict):
    if not row or all(not v for v in row.values()):
        return None
    try:
        timestamp_raw = row['timestamp'] if row.get('timestamp') else None
        timestamp = int(timestamp_raw)
    except (ValueError, TypeError):
        return None

    event = check_event(row.get('event')) if row.get('event') else None
    type_ = check_type(row.get('open_type')) if row.get('open_type') else None

    try:
        user_id = int(row['user_id']) if row.get('user_id') else None
    except (ValueError, TypeError):
        return None

    # Валидация: если event невалиден, отбрасываем строку
    if event is None:
        return None
    
    # Валидация: если user_id невалиден, отбрасываем строку
    if user_id is None:
        return None

    result = (timestamp, event, type_, user_id)
    return result

def producer(csv_path :str):
    with open(csv_path, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            producer_queue.put(row)

def worker():
    while True:
        item = producer_queue.get()
        try:
            if item is SENTINEL:
                writer_queue.put(SENTINEL)
                break

            result = load_event(item)
            if result is None:
                continue

            writer_queue.put(result)
        finally:
            producer_queue.task_done()

def writer(db_path: str, batch_size: int = 100, workers_count: int = 1):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=OFF;")

    sql = """
        INSERT OR IGNORE INTO events (timestamp, event, type, user_id)
        VALUES (?, ?, ?, ?)
    """

    batch = []
    seen = 0

    def flush():
        if not batch:
            return
        with conn:
            conn.executemany(sql, batch)
            batch.clear()

    try:
        while True:
            item = writer_queue.get()
            try:
                if item is SENTINEL:
                    seen += 1
                    if seen >=workers_count:
                        break
                    continue

                batch.append(item)
                if len(batch) >= batch_size:
                    flush()
            finally:
                writer_queue.task_done()
        flush()
    finally:
        conn.close()

def run(csv_path: str, db_path: str, batch_size: int = 100, workers_count: int = 1):
    write = threading.Thread(target=writer, args=(db_path, batch_size, workers_count), daemon=True)
    write.start()

    workers = []
    for _ in range(workers_count):
        w = threading.Thread(target=worker, daemon=True)
        w.start()
        workers.append(w)

    producer(csv_path)

    for _ in range(workers_count):
        producer_queue.put(SENTINEL)

    producer_queue.join()
    writer_queue.join()

    for w in workers:
        w.join()

    write.join()

def resolve_paths():
    root = Path(__file__).resolve().parent.parent

    default_csv_path = root / "data" / "toolwindow_data.csv"
    default_db_path = root / "database" / "toolwindow.db"

    csv_path = Path(os.getenv("CSV_PATH", str(default_csv_path)))
    db_path = Path(os.getenv("DB_PATH", str(default_db_path)))

    return str(csv_path), str(db_path)

if __name__ == '__main__':
    csv_path, db_path = resolve_paths()

    run(csv_path, db_path, 50, 4)