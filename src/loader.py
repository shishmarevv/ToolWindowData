import csv
import threading
import queue
import sqlite3

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
    if not row or all(not c for c in row):
        return None
    try:
        timestamp_raw = row['timestamp'] if row['timestamp'] else None
        timestamp = int(timestamp_raw)
    except ValueError:
        return None

    event = check_event(row['event']) if row['event'] else None
    type_ = check_type(row['open_type']) if row['open_type'] else None

    try:
        user_id = int(row['user_id']) if row['user_id'] else None
    except ValueError:
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
        INSERT INTO events (timestamp, event, type, user_id)
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