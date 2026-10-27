"""Historical-only market ingestion, deduplication and immutable revisions."""

import hashlib
import json
import time

from .market import Candle, Feed, GoldContract, Quote
from .store import Store

MARKET_SCHEMA = """
CREATE TABLE IF NOT EXISTS market_events (
 event_key TEXT PRIMARY KEY, feed TEXT NOT NULL, symbol TEXT NOT NULL,
 kind TEXT NOT NULL, event_time INTEGER NOT NULL, payload TEXT NOT NULL,
 received_msc INTEGER NOT NULL);
CREATE TRIGGER IF NOT EXISTS market_no_update BEFORE UPDATE ON market_events
 BEGIN SELECT RAISE(ABORT, 'append only'); END;
CREATE TRIGGER IF NOT EXISTS market_no_delete BEFORE DELETE ON market_events
 BEGIN SELECT RAISE(ABORT, 'append only'); END;
CREATE INDEX IF NOT EXISTS market_lookup ON market_events(feed,symbol,kind,event_time);
CREATE TABLE IF NOT EXISTS feed_bindings (
 feed TEXT PRIMARY KEY, fingerprint TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS feed_status (
 feed TEXT PRIMARY KEY, state TEXT NOT NULL, reason TEXT NOT NULL, observed_msc INTEGER NOT NULL);
INSERT OR IGNORE INTO schema_version VALUES (2);
"""


class MarketStore:
    def __init__(self, store: Store):
        self.store = store
        with store.connect("historical") as db:
            db.executescript(MARKET_SCHEMA)

    def bind(self, feed: Feed, login: int, server: str):
        fingerprint = hashlib.sha256(json.dumps([login, server]).encode()).hexdigest()
        with self.store.connect("historical") as db:
            db.execute("INSERT OR IGNORE INTO feed_bindings VALUES (?,?)", (feed.key, fingerprint))
            row = db.execute(
                "SELECT fingerprint FROM feed_bindings WHERE feed=?", (feed.key,)
            ).fetchone()
            if row[0] != fingerprint:
                raise ValueError("Feed already belongs to another account; choose a new stream")

    def append(self, feed: Feed, event: Quote | Candle | GoldContract, received_msc: int):
        payload = event.model_dump_json()
        kind = (
            "quote"
            if isinstance(event, Quote)
            else ("candle" if isinstance(event, Candle) else "contract")
        )
        event_time = (
            event.time_msc
            if isinstance(event, Quote)
            else event.open_time * 1000
            if isinstance(event, Candle)
            else received_msc
        )
        # Quotes have no broker event ID: exact repeats collapse; changed same-ms quotes survive.
        # Candle corrections retain separate immutable versions rather than silently overwriting.
        key = hashlib.sha256(f"{feed.key}:{kind}:{payload}".encode()).hexdigest()
        with self.store.connect("historical") as db:
            cursor = db.execute(
                "INSERT OR IGNORE INTO market_events VALUES (?,?,?,?,?,?,?)",
                (key, feed.key, event.symbol, kind, event_time, payload, received_msc),
            )
            return cursor.rowcount == 1

    def set_status(self, feed: Feed, state, reason, now_msc):
        if state not in {"healthy", "blocked", "disconnected"}:
            raise ValueError("Invalid feed state")
        with self.store.connect("historical") as db:
            db.execute(
                "INSERT INTO feed_status VALUES (?,?,?,?) ON CONFLICT(feed) DO UPDATE SET "
                "state=excluded.state,reason=excluded.reason,observed_msc=excluded.observed_msc",
                (feed.key, state, reason, now_msc),
            )

    def statuses(self, now_msc=None):
        now_msc = int(time.time() * 1000) if now_msc is None else now_msc
        with self.store.connect("historical") as db:
            result = []
            for row in db.execute("SELECT * FROM feed_status ORDER BY feed"):
                item = dict(row)
                age = now_msc - row["observed_msc"]
                item["heartbeat_stale"] = age < 0 or age > 15000
                item["execution_allowed"] = False
                result.append(item)
            return result

    def events(self, feed_key, symbol, kind, limit=100, timeframe=None):
        if kind not in {"quote", "candle", "contract"} or not 1 <= limit <= 500:
            raise ValueError("Invalid event query")
        # For candles, return the latest revision of each bar/timeframe only.
        with self.store.connect("historical") as db:
            rows = db.execute(
                "SELECT payload,received_msc,event_time FROM market_events "
                "WHERE feed=? AND symbol=? AND kind=? "
                "ORDER BY event_time DESC,received_msc DESC,rowid DESC",
                (feed_key, symbol, kind),
            )
            output, seen = [], set()
            for row in rows:
                payload = json.loads(row["payload"])
                if timeframe and payload.get("timeframe") != timeframe:
                    continue
                if kind == "candle":
                    key = (payload["timeframe"], payload["open_time"])
                    if key in seen:
                        continue
                    seen.add(key)
                output.append(
                    {
                        "data": payload,
                        "received_msc": row["received_msc"],
                        "event_time": row["event_time"],
                        "feed": feed_key,
                        "execution_allowed": False,
                    }
                )
                if len(output) >= limit:
                    break
            return output
