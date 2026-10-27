"""Durable quota reservations, circuit health and short-lived review cache."""

import json
import uuid

from .store import Store

SCHEMA = """
CREATE TABLE IF NOT EXISTS provider_quota (
 provider TEXT NOT NULL, bucket INTEGER NOT NULL, calls INTEGER NOT NULL,
 tokens INTEGER NOT NULL, cost INTEGER NOT NULL, PRIMARY KEY(provider,bucket));
CREATE TABLE IF NOT EXISTS provider_health (
 provider TEXT PRIMARY KEY, failures INTEGER NOT NULL, blocked_until REAL NOT NULL,
 last_error TEXT, last_success REAL);
CREATE TABLE IF NOT EXISTS provider_attempts (
 id TEXT PRIMARY KEY, task_id TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL,
 state TEXT NOT NULL, error_code TEXT, usage TEXT, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS review_cache (
 cache_key TEXT PRIMARY KEY, expires REAL NOT NULL, payload TEXT NOT NULL);
INSERT OR IGNORE INTO schema_version VALUES (4);
"""


class GatewayStore:
    def __init__(self, store: Store):
        self.store = store
        with store.connect() as db:
            db.executescript(SCHEMA)

    def cached(self, key, now):
        with self.store.connect() as db:
            row = db.execute(
                "SELECT payload FROM review_cache WHERE cache_key=? AND expires>?", (key, now)
            ).fetchone()
            return json.loads(row[0]) if row else None

    def save_cache(self, key, reply, expires):
        with self.store.connect() as db:
            db.execute(
                "INSERT INTO review_cache VALUES (?,?,?) ON CONFLICT(cache_key) DO UPDATE "
                "SET expires=excluded.expires,payload=excluded.payload",
                (key, expires, json.dumps(reply, allow_nan=False)),
            )

    def reserve(self, task_id, binding, policy, input_estimate, now):
        """Atomically gate health and reserve worst-case per-attempt capacity."""
        bucket = int(now // 60)
        tokens = input_estimate + binding.max_output_tokens
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            health = db.execute(
                "SELECT * FROM provider_health WHERE provider=?", (binding.provider,)
            ).fetchone()
            if health and health["blocked_until"] > now:
                return None, "circuit_open"
            row = db.execute(
                "SELECT * FROM provider_quota WHERE provider=? AND bucket=?",
                (binding.provider, bucket),
            ).fetchone()
            calls, used_tokens, cost = (
                (row["calls"], row["tokens"], row["cost"]) if row else (0, 0, 0)
            )
            if calls + 1 > policy.calls_per_minute:
                return None, "rate_limit"
            if used_tokens + tokens > policy.token_reservations_per_minute:
                return None, "token_budget"
            if cost + binding.max_cost_microusd > policy.cost_reservations_microusd_per_minute:
                return None, "cost_budget"
            db.execute(
                "INSERT INTO provider_quota VALUES (?,?,?,?,?) ON CONFLICT(provider,bucket) "
                "DO UPDATE SET calls=excluded.calls,tokens=excluded.tokens,cost=excluded.cost",
                (
                    binding.provider,
                    bucket,
                    calls + 1,
                    used_tokens + tokens,
                    cost + binding.max_cost_microusd,
                ),
            )
            identifier = str(uuid.uuid4())
            db.execute(
                "INSERT INTO provider_attempts VALUES (?,?,?,?,?,NULL,NULL,?)",
                (identifier, task_id, binding.provider, binding.model, "started", now),
            )
            return identifier, None

    def finish(self, identifier, provider, policy, now, error=None, usage=None):
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT failures FROM provider_health WHERE provider=?", (provider,)
            ).fetchone()
            failures = (row[0] if row else 0) + 1 if error else 0
            until = (
                now + policy.circuit_cooldown_seconds
                if failures >= policy.circuit_failure_threshold
                else 0
            )
            db.execute(
                "INSERT INTO provider_health VALUES (?,?,?,?,?) ON CONFLICT(provider) "
                "DO UPDATE SET failures=excluded.failures,blocked_until=excluded.blocked_until,"
                "last_error=excluded.last_error,last_success=CASE WHEN excluded.last_success "
                "IS NOT NULL THEN excluded.last_success ELSE provider_health.last_success END",
                (provider, failures, until, error, None if error else now),
            )
            db.execute(
                "UPDATE provider_attempts SET state=?,error_code=?,usage=? WHERE id=?",
                (
                    "failed" if error else "completed",
                    error,
                    None if usage is None else json.dumps(usage),
                    identifier,
                ),
            )

    def health(self):
        with self.store.connect() as db:
            return [
                dict(row) for row in db.execute("SELECT * FROM provider_health ORDER BY provider")
            ]
