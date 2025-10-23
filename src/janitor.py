import threading
import queue
import sqlite3
import resolver

from logger import get_logger

logger = get_logger(__name__)

producer_queue = queue.Queue(maxsize=200)
clean_consumer_queue = queue.Queue(maxsize=200)
anomaly_consumer_queue  = queue.Queue(maxsize=200)

SENTINEL = None

def get_users(db_path: str, batch: int = 100):
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT DISTINCT user_id
            FROM events
            ORDER BY user_id ASC
            """
        )
        while True:
            rows = cur.fetchmany(batch)
            if not rows:
                break
            yield [r[0] for r in rows]

def get_events(db_path: str, user_id: int):
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, timestamp, event, type
            FROM events
            WHERE user_id = ?
            ORDER BY timestamp ASC,
                     CASE event WHEN 'closed' THEN 0 ELSE 1 END,
                     id ASC
            """,
            (user_id,)
        )
        rows = cur.fetchall()
        return rows

def check_events(events: list, max_duration: int):
    clean = []
    anomalies = []

    state = None
    last_timestamp = None

    for event_id, timestamp, event, type_ in events:
        # Проверка порядка событий
        if last_timestamp is not None and timestamp < last_timestamp:
            anomalies.append((type_, timestamp, None, event_id, 'out_of_order'))
            continue  # Пропускаем событие с нарушенным порядком
        last_timestamp = timestamp

        # Проверка: closed не должен иметь type
        if event == "closed" and type_ is not None:
            anomalies.append((type_, timestamp, None, event_id, 'closed_not_null_type'))
            type_ = None  # Нормализуем type для дальнейшей обработки

        # Проверка: opened должен иметь type
        if event == "opened" and type_ is None:
            anomalies.append((None, timestamp, None, event_id, 'null_type'))
            continue  # Пропускаем opened без type

        if event == "opened":
            if state is None:
                state = (event_id, timestamp, type_)
            else:
                # Дубль открытия: старое осталось незакрытым
                old_open_id, old_open_ts, old_open_type = state
                anomalies.append((old_open_type, old_open_ts, None, old_open_id, 'missing_close'))
                anomalies.append((type_, timestamp, old_open_id, event_id, 'duplicate_open'))
                # Заменяем state на новое открытие
                state = (event_id, timestamp, type_)

        if event == "closed":
            if state is None:
                anomalies.append((None, timestamp, None, event_id, 'missing_open'))
            else:
                open_id, open_ts, open_type = state
                if timestamp < open_ts:
                    anomalies.append((open_type, timestamp, open_id, event_id, 'negative_duration'))
                    state = None
                elif timestamp > open_ts:
                    # Calculate duration in hours
                    duration_ms = timestamp - open_ts
                    duration = duration_ms / 1000 / 60

                    if duration > max_duration:
                        anomalies.append((open_type, open_ts, open_id, event_id, '>duration'))
                    else:
                        clean.append((open_type, open_ts, timestamp, open_id, event_id))
                    state = None
                else:
                    # Zero duration - still valid pair
                    clean.append((open_type, open_ts, timestamp, open_id, event_id))
                    state = None

    # После обработки всех событий проверяем, остался ли незакрытый эпизод
    if state is not None:
        open_id, open_ts, open_type = state
        anomalies.append((open_type, open_ts, None, open_id, 'missing_close'))

    return clean, anomalies
        

def producer(db_path: str, batch: int = 100):
    for users in get_users(db_path, batch):
        producer_queue.put(users)

def worker(db_path: str, max_duration: int):
    while True:
        item = producer_queue.get()
        try:
            if item is SENTINEL:
                clean_consumer_queue.put(SENTINEL)
                anomaly_consumer_queue.put(SENTINEL)
                break

            for user_id in item:
                rows = get_events(db_path, user_id)
                if not rows:
                    continue
                clean, anomalies = check_events(rows, max_duration)
                for rec in clean:
                    clean_consumer_queue.put(rec)
                for rec in anomalies:
                    anomaly_consumer_queue.put(rec)
        finally:
            producer_queue.task_done()

def clear_writer(db_path: str, batch_size: int = 100, workers_count: int = 1):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=OFF;")

    sql = """
        INSERT OR IGNORE INTO clear(type, start, end, open_event_id, close_event_id)
        VALUES (?, ?, ?, ?, ?) 
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
            item = clean_consumer_queue.get()
            try:
                if item is SENTINEL:
                    seen += 1
                    if seen >= workers_count:
                        break
                    continue

                batch.append(item)
                if len(batch) >= batch_size:
                    flush()
            finally:
                clean_consumer_queue.task_done()
        flush()
    finally:
        conn.close()


def anomaly_writer(db_path: str, batch_size: int = 100, workers_count: int = 1):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=OFF;")

    sql = """
        INSERT OR IGNORE INTO anomaly (type, timestamp, counterparty_event_id , event_id, detail)
        VALUES (?, ?, ?, ?, ?)
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
            item = anomaly_consumer_queue.get()
            try:
                if item is SENTINEL:
                    seen += 1
                    if seen >= workers_count:
                        break
                    continue

                batch.append(item)
                if len(batch) >= batch_size:
                    flush()
            finally:
                anomaly_consumer_queue.task_done()
        flush()
    finally:
        conn.close()

def truncate(db_path: str):
    conn = sqlite3.connect(db_path)
    sql = "DELETE FROM clear"
    conn.execute(sql)
    sql = "DELETE FROM anomaly"
    conn.execute(sql)
    conn.close()

def run(db_path: str, max_duration: int,  workers_count: int = 1, user_batch: int = 100, batch_size: int = 100):
    logger.info(f"Starting data cleaning: workers={workers_count}, max_duration={max_duration}min, batch_size={batch_size}")
    truncate(db_path)
    logger.info("Truncated clear and anomaly tables")
    t_clear = threading.Thread(
        target=clear_writer,
        args=(db_path, batch_size, workers_count),
        daemon=True,
    )
    t_clear.start()

    t_anom = threading.Thread(
        target=anomaly_writer,
        args=(db_path, batch_size, workers_count),
        daemon=True,
        )
    t_anom.start()

    workers = []
    for _ in range(workers_count):
        t = threading.Thread(target=worker, args=(db_path,max_duration), daemon=True)
        t.start()
        workers.append(t)

    producer(db_path, batch=user_batch)

    for _ in range(workers_count):
        producer_queue.put(SENTINEL)

    producer_queue.join()
    clean_consumer_queue.join()
    anomaly_consumer_queue.join()

    for t in workers:
        t.join()

    logger.info("Data cleaning completed")
    t_clear.join()
    t_anom.join()



if __name__ == '__main__':
    run(resolver.db_path(), resolver.max_duration(), resolver.workers_count(), resolver.user_batch_size(), resolver.batch_size())
    logger.info("Janitor pipeline finished")