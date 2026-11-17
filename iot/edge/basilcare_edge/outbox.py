"""Local queue of messages waiting for the broker (scope sections 2.3, 4.2, 6.2).

Every reading and screening result is written to SQLite first, then published. A row is
deleted only when the broker acknowledged it (QoS 1 PUBACK). So a network outage, a broker
restart or even a power cut of the Pi loses nothing: the rows are sent when the connection
comes back, oldest first.

The queue is bounded (max_rows): during a very long outage the OLDEST readings are dropped
first, so the SD card never fills up ("offline measurements are queued within local storage
limits", scope section 6.2).
"""
import json
import sqlite3
import threading
from pathlib import Path


class Outbox:
    def __init__(self, path, max_rows=100_000):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")    # survives a power cut without corruption
        self.db.execute("""CREATE TABLE IF NOT EXISTS outbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            payload TEXT NOT NULL,
            inflight INTEGER NOT NULL DEFAULT 0)""")
        self.max_rows = max_rows
        self.lock = threading.Lock()
        self.dropped = 0
        # after a restart, nothing is in flight any more: everything pending is sent again
        self.db.execute("UPDATE outbox SET inflight = 0")

    def add(self, topic, payload):
        with self.lock:
            self.db.execute("INSERT INTO outbox (topic, payload) VALUES (?, ?)", (topic, json.dumps(payload)))
            excess = self._count() - self.max_rows
            if excess > 0:
                self.db.execute("DELETE FROM outbox WHERE id IN (SELECT id FROM outbox ORDER BY id LIMIT ?)",
                                (excess,))
                self.dropped += excess

    def take(self, limit=100):
        """Marks up to `limit` pending rows as in flight and returns them as (id, topic, payload)."""
        with self.lock:
            rows = self.db.execute(
                "SELECT id, topic, payload FROM outbox WHERE inflight = 0 ORDER BY id LIMIT ?", (limit,)).fetchall()
            if rows:
                self.db.executemany("UPDATE outbox SET inflight = 1 WHERE id = ?", [(r[0],) for r in rows])
            return [(row_id, topic, json.loads(payload)) for row_id, topic, payload in rows]

    def done(self, row_id):
        """The broker acknowledged the message."""
        with self.lock:
            self.db.execute("DELETE FROM outbox WHERE id = ?", (row_id,))

    def release_inflight(self):
        """Connection lost: rows in flight were maybe not received, send them again later."""
        with self.lock:
            self.db.execute("UPDATE outbox SET inflight = 0")

    def pending(self):
        with self.lock:
            return self._count()

    def _count(self):
        return self.db.execute("SELECT COUNT(*) FROM outbox").fetchone()[0]

    def close(self):
        self.db.close()
