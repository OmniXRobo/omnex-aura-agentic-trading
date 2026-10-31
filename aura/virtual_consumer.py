"""At-least-once persisted quote consumer. Observation/exit marking only; never opens."""

import hashlib
import json
import uuid

from .collector import AccountBinding
from .market import Feed, GoldContract, Quote
from .market_store import MarketStore
from .time_policy import QuoteTimePolicy
from .virtual import VirtualLedger, encode


class ConsumerError(RuntimeError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


SCHEMA = """
CREATE TABLE IF NOT EXISTS virtual_source_bindings (
 session TEXT PRIMARY KEY, binding TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS virtual_source_no_update BEFORE UPDATE ON virtual_source_bindings
 BEGIN SELECT RAISE(ABORT,'immutable'); END;
CREATE TRIGGER IF NOT EXISTS virtual_source_no_delete BEFORE DELETE ON virtual_source_bindings
 BEGIN SELECT RAISE(ABORT,'immutable'); END;
CREATE TABLE IF NOT EXISTS virtual_source_cursors (
 session TEXT PRIMARY KEY, row_id INTEGER NOT NULL, event_key TEXT);
CREATE TABLE IF NOT EXISTS virtual_source_events (
 session TEXT NOT NULL, row_id INTEGER NOT NULL, event_key TEXT NOT NULL,
 disposition TEXT NOT NULL, PRIMARY KEY(session,row_id));
CREATE TRIGGER IF NOT EXISTS virtual_source_events_no_update BEFORE UPDATE ON virtual_source_events
 BEGIN SELECT RAISE(ABORT,'append only'); END;
CREATE TRIGGER IF NOT EXISTS virtual_source_events_no_delete BEFORE DELETE ON virtual_source_events
 BEGIN SELECT RAISE(ABORT,'append only'); END;
INSERT OR IGNORE INTO schema_version VALUES (8);
"""


class VirtualQuoteConsumer:
    def __init__(self, market: MarketStore, ledger: VirtualLedger, feed: Feed,
                 account: AccountBinding):
        expected_source = "fixture" if feed.source == "fixture" else "demo_observation"
        if ledger.config.evidence_source != expected_source:
            raise ConsumerError("evidence_source_mismatch")
        self.market, self.ledger, self.feed, self.account = market, ledger, feed, account
        self.fingerprint = hashlib.sha256(json.dumps([account.login, account.server]).encode()).hexdigest()
        with market.store.connect("historical") as db:
            db.execute("CREATE INDEX IF NOT EXISTS market_consumer_lookup "
                       "ON market_events(feed,symbol,kind)")
            db.execute("CREATE TABLE IF NOT EXISTS market_source_identity "
                       "(singleton INTEGER PRIMARY KEY CHECK(singleton=1), id TEXT NOT NULL)")
            db.execute("INSERT OR IGNORE INTO market_source_identity VALUES (1,?)", (str(uuid.uuid4()),))
            self.source_id = db.execute("SELECT id FROM market_source_identity WHERE singleton=1").fetchone()[0]
            self._identity(db)
        binding = encode(dict(source_id=self.source_id, feed=feed.key,
                              symbol=ledger.contract.symbol, fingerprint=self.fingerprint,
                              server=account.server, contract=ledger.contract.model_dump(mode="json")))
        with ledger.store.connect("virtual") as db:
            db.executescript(SCHEMA)
            db.execute("BEGIN IMMEDIATE")
            saved = db.execute("SELECT binding FROM virtual_source_bindings WHERE session=?",
                               (ledger.session,)).fetchone()
            if saved is None:
                if db.execute("SELECT 1 FROM virtual_events WHERE session=? LIMIT 1",
                              (ledger.session,)).fetchone():
                    raise ConsumerError("session_has_unbound_evidence")
                db.execute("INSERT INTO virtual_source_bindings VALUES (?,?)", (ledger.session, binding))
                db.execute("INSERT INTO virtual_source_cursors VALUES (?,0,NULL)", (ledger.session,))
            elif saved[0] != binding:
                raise ConsumerError("source_binding_conflict")

    def _identity(self, db):
        identity = db.execute("SELECT id FROM market_source_identity WHERE singleton=1").fetchone()
        account = db.execute("SELECT fingerprint FROM feed_bindings WHERE feed=?", (self.feed.key,)).fetchone()
        if identity is None or identity[0] != self.source_id:
            raise ConsumerError("source_database_changed")
        if account is None or account[0] != self.fingerprint:
            raise ConsumerError("account_binding_mismatch")

    def _ack(self, row, previous, disposition):
        with self.ledger.store.connect("virtual") as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT event_key,disposition FROM virtual_source_events "
                             "WHERE session=? AND row_id=?", (self.ledger.session, row["row_id"])).fetchone()
            if old:
                if old[0] != row["event_key"]:
                    raise ConsumerError("source_event_changed")
                return old[1]
            cursor = db.execute("SELECT row_id FROM virtual_source_cursors WHERE session=?",
                                (self.ledger.session,)).fetchone()[0]
            if cursor != previous:
                raise ConsumerError("cursor_race_retry")
            db.execute("INSERT INTO virtual_source_events VALUES (?,?,?,?)",
                       (self.ledger.session, row["row_id"], row["event_key"], disposition))
            db.execute("UPDATE virtual_source_cursors SET row_id=?,event_key=? WHERE session=?",
                       (row["row_id"], row["event_key"], self.ledger.session))
        return disposition

    def _validate_fresh(self, db, row, quote, now):
        status = db.execute("SELECT * FROM feed_status WHERE feed=?", (self.feed.key,)).fetchone()
        if status is None or status["state"] != "healthy" or not 0 <= now - status["observed_msc"] <= 15000:
            raise ConsumerError("feed_not_healthy")
        if not 0 <= now - row["received_msc"] <= 5000:
            raise ConsumerError("reception_time_invalid")
        contract = db.execute("SELECT payload,rowid FROM market_events WHERE feed=? AND symbol=? "
                              "AND kind='contract' ORDER BY rowid DESC LIMIT 1",
                              (self.feed.key, self.ledger.contract.symbol)).fetchone()
        if contract is None or contract["rowid"] > row["row_id"] or (
            GoldContract.model_validate_json(contract["payload"]) != self.ledger.contract
        ):
            raise ConsumerError("contract_changed_or_unavailable")
        offset = db.execute("SELECT offset_seconds FROM quote_time_bindings WHERE feed=?",
                            (self.feed.key,)).fetchone()
        if offset is None or offset[0] != quote.time_offset_seconds:
            raise ConsumerError("quote_time_binding_mismatch")
        if quote.time_policy is not None:
            policy = db.execute("SELECT payload FROM quote_time_policies WHERE digest=?",
                                (quote.time_policy,)).fetchone()
            if policy is None or hashlib.sha256(policy[0].encode()).hexdigest() != quote.time_policy:
                raise ConsumerError("quote_policy_missing_or_corrupt")
            try:
                parsed = QuoteTimePolicy.model_validate_json(policy[0])
                for observed in (row["received_msc"], now):
                    if parsed.normalize(quote.raw_time_msc, observed, self.account.server,
                                        quote.symbol) != quote.time_msc:
                        raise ValueError("Time mismatch")
            except ValueError:
                raise ConsumerError("quote_policy_invalid_or_expired") from None
        elif quote.time_offset_seconds:
            raise ConsumerError("quote_policy_required")

    def step(self):
        """Commit one source disposition; replay a ledger receipt after a crash before ack."""
        with self.ledger.store.connect("virtual") as db:
            cursor = db.execute("SELECT row_id,event_key FROM virtual_source_cursors WHERE session=?",
                                (self.ledger.session,)).fetchone()
            if cursor is None:
                raise ConsumerError("consumer_cursor_missing")
            previous, previous_key = cursor
        with self.market.store.connect("historical") as db:
            self._identity(db)
            if previous:
                checkpoint = db.execute("SELECT event_key FROM market_events WHERE rowid=?", (previous,)).fetchone()
                if checkpoint is None or checkpoint[0] != previous_key:
                    raise ConsumerError("source_checkpoint_missing_or_changed")
            raw = db.execute("SELECT rowid AS row_id,* FROM market_events WHERE feed=? AND symbol=? "
                             "AND kind='quote' AND rowid>? ORDER BY rowid LIMIT 1",
                             (self.feed.key, self.ledger.contract.symbol, previous)).fetchone()
            if raw is None:
                return dict(state="idle", entries_enabled=False, execution_allowed=False)
            row = dict(raw)
            expected = hashlib.sha256(f"{self.feed.key}:quote:{row['payload']}".encode()).hexdigest()
            if expected != row["event_key"]:
                raise ConsumerError("source_event_hash_mismatch")
            quote = Quote.model_validate_json(row["payload"])
            if quote.time_msc != row["event_time"] or quote.symbol != self.ledger.contract.symbol:
                raise ConsumerError("source_event_time_or_symbol_mismatch")
            key = "market:" + row["event_key"]
            with self.ledger.store.connect("virtual") as target:
                receipt = target.execute("SELECT digest,result FROM virtual_receipts WHERE session=? AND key=?",
                                         (self.ledger.session, key)).fetchone()
            if receipt:
                request = encode(dict(quote=json.loads(quote.model_dump_json()), intent=None))
                if receipt[0] != hashlib.sha256(request.encode()).hexdigest():
                    raise ConsumerError("ledger_receipt_mismatch")
                # This transition is already committed; no freshness override or refill occurs.
                disposition = "recovered_committed"
            else:
                now = self.ledger.clock()
                if quote.time_msc > now:
                    raise ConsumerError("future_quote")
                if now - quote.time_msc > 5000:
                    disposition = "skipped_stale_gap"
                else:
                    self._validate_fresh(db, row, quote, now)
                    if quote.time_msc < self.ledger.snapshot()["last_time_msc"]:
                        disposition = "skipped_out_of_order_gap"
                    else:
                        # No intent can enter through this consumer. Existing positions may exit.
                        self.ledger.apply(key, quote)
                        disposition = "applied"
        disposition = self._ack(row, previous, disposition)
        return dict(state=disposition, source_row=row["row_id"], entries_enabled=False,
                    execution_allowed=False)
