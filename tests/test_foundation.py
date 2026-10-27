import asyncio
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from aura.agents import Orchestrator, Snapshot
from aura.api import create_app
from aura.config import Settings
from aura.mt5 import demo_diagnostics
from aura.risk import Proposal, RiskController
from aura.store import Store
from aura.worker import process_one

ADMIN = "a" * 40
VIEWER = "b" * 40
AUTH = {"Authorization": f"Bearer {ADMIN}"}
VIEW_AUTH = {"Authorization": f"Bearer {VIEWER}"}
BASE = dict(
    symbol="XAUUSD",
    side="buy",
    entry=3000,
    stop_loss=2990,
    take_profit=3020,
    risk_percent=0.25,
    spread=0.2,
    tick_age_seconds=1,
    active_positions=0,
    news_blackout=False,
)
SNAPSHOT = dict(prices=[3000, 3001, 3002], tick_age_seconds=1, source="fixture")


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path)


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(Settings(tmp_path, ADMIN, VIEWER))) as c:
        yield c


def test_ac01_fail_closed_config(tmp_path):
    with pytest.raises(ValueError):
        Settings(tmp_path, "short")
    assert ADMIN not in repr(Settings(tmp_path, ADMIN))


@pytest.mark.parametrize("mode", ["live", "demo", "LIVE", "unknown"])
def test_ac02_modes_cannot_enable_execution(tmp_path, mode):
    with pytest.raises(ValueError):
        Settings(tmp_path, ADMIN, mode=mode)


def test_ac03_authentication_and_authorization(client):
    assert client.get("/health").status_code == 200
    assert client.get("/v1/status").status_code == 401
    assert client.get("/v1/status", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/v1/status", headers=VIEW_AUTH).status_code == 200
    assert (
        client.put("/v1/safety/kill-switch", headers=VIEW_AUTH, json={"enabled": False}).status_code
        == 403
    )
    assert client.get("/openapi.json").status_code == 404


def test_ac04_kill_persists_restart(tmp_path):
    store = Store(tmp_path)
    assert store.killed()
    store.set_kill(False)
    assert not Store(tmp_path).killed()
    Store(tmp_path).set_kill(True)
    assert store.killed()


def test_ac05_environment_isolation_restart(store):
    store.record("historical", "experiment", {"version": "v1"})
    store.record("virtual", "trade", {"cost": 2})
    restarted = Store(store.directory)
    assert restarted.records("historical")[0]["kind"] == "experiment"
    assert restarted.records("virtual")[0]["kind"] == "trade"
    assert restarted.records("demo") == []
    with pytest.raises(ValueError):
        restarted.record("live", "trade", {})


def test_ac06_audit_append_only(store):
    store.audit("test", "safety", {})
    for statement in ("UPDATE audit SET actor='changed'", "DELETE FROM audit"):
        with pytest.raises(sqlite3.IntegrityError):
            with store.connect() as db:
                db.execute(statement)


def test_ac07_default_kill_and_no_execution(store):
    risk = RiskController(store)
    result = risk.evaluate(Proposal(**BASE))
    assert not result["eligible_for_research"]
    store.set_kill(False)
    result = risk.evaluate(Proposal(**BASE))
    assert result["eligible_for_research"]
    assert result["execution_allowed"] is False
    assert result["live_enabled"] is False


@pytest.mark.parametrize(
    "change",
    [
        dict(stop_loss=3010),
        dict(take_profit=2990),
        dict(risk_percent=1),
        dict(spread=1),
        dict(tick_age_seconds=6),
        dict(active_positions=1),
        dict(news_blackout=True),
        dict(symbol="EURUSD"),
    ],
)
def test_ac08_independent_risk_blocks(store, change):
    store.set_kill(False)
    assert RiskController(store).evaluate(Proposal(**(BASE | change)))["reasons"]


@pytest.mark.parametrize(
    "change",
    [
        dict(entry=float("nan")),
        dict(spread=float("inf")),
        dict(stop_loss=0),
        dict(tick_age_seconds=-1),
        dict(side="hold"),
        dict(live_enabled=True),
    ],
)
def test_ac09_invalid_inputs(change):
    with pytest.raises(ValidationError):
        Proposal(**(BASE | change))


def test_ac10_risk_state_failure_closes(store, monkeypatch):
    def broken():
        raise OSError("db offline")

    monkeypatch.setattr(store, "killed", broken)
    result = RiskController(store).evaluate(Proposal(**BASE))
    assert not result["eligible_for_research"]
    assert "fail closed" in result["reasons"][0]


def test_ac11_queue_idempotency(store):
    a = store.enqueue("key", "research.snapshot", SNAPSHOT)
    assert a == store.enqueue("key", "research.snapshot", SNAPSHOT)
    with pytest.raises(ValueError):
        store.enqueue("key", "different", SNAPSHOT)


def test_ac12_concurrent_claim(store):
    store.enqueue("key", "research.snapshot", SNAPSHOT)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: store.claim(), range(8)))
    assert sum(x is not None for x in results) == 1


def test_ac13_restart_lease_and_stale_worker(store):
    store.enqueue("key", "research.snapshot", SNAPSHOT)
    first = store.claim(now=10**12, lease_seconds=10)
    second = Store(store.directory).claim(now=10**12 + 11)
    assert first["id"] == second["id"]
    with pytest.raises(ValueError):
        store.finish(first["id"], first["lease_token"], now=10**12 + 12)
    store.finish(second["id"], second["lease_token"], now=10**12 + 12)
    assert store.claim(now=10**12 + 50) is None


def test_ac14_retry_dead_letter(store):
    store.enqueue("key", "bad.topic", {})
    for attempt in range(3):
        now = 10**12 + attempt * 100
        job = store.claim(now=now)
        store.finish(job["id"], job["lease_token"], False, now=now + 1)
    assert store.claim(now=10**12 + 1000) is None
    with store.connect() as db:
        assert db.execute("SELECT state FROM jobs").fetchone()[0] == "dead"


def test_ac15_independent_agent_tasks_and_memory(store):
    result = asyncio.run(Orchestrator(store).run(Snapshot(**SNAPSHOT)))
    assert len({a["agent"] for a in result["agents"]}) == 3
    assert all(a["status"] == "completed" for a in result["agents"])
    assert result["signal"] == "NO TRADE"
    assert result["provider"] == "local_deterministic"
    assert Store(store.directory).records("historical")[0]["payload"]["signal"] == "NO TRADE"


def test_ac16_agent_failure_does_not_generate_trade(store, monkeypatch):
    async def failed(_):
        raise RuntimeError("agent unavailable")

    monkeypatch.setattr("aura.agents.technical", failed)
    result = asyncio.run(Orchestrator(store).run(Snapshot(**SNAPSHOT)))
    assert result["agents"][0]["status"] == "failed"
    assert result["signal"] == "NO TRADE"


@pytest.mark.parametrize(
    "mode,connected,verified",
    [(0, True, True), (1, True, False), (2, True, False), (0, False, False)],
)
def test_ac17_demo_account_boundary(mode, connected, verified):
    class FakeMT5:
        ACCOUNT_TRADE_MODE_DEMO = 0

        def account_info(self):
            return NS(trade_mode=mode)

        def terminal_info(self):
            return NS(connected=connected)

        def symbols_get(self):
            return [NS(name="XAUUSDm"), NS(name="GOLD"), NS(name="EURUSD")]

        def order_send(self, _):
            pytest.fail("No diagnostic may send any order")

    result = demo_diagnostics(FakeMT5())
    assert result["demo_verified"] == verified
    assert not result["execution_allowed"]


def test_ac18_disconnected_account():
    port = NS(account_info=lambda: None, terminal_info=lambda: None)
    assert demo_diagnostics(port)["reason"] == "Disconnected"


def test_ac19_api_research_workflow(client):
    assert client.post("/v1/research/run", json=SNAPSHOT).status_code == 401
    result = client.post("/v1/research/run", headers=AUTH, json=SNAPSHOT)
    assert result.status_code == 200
    assert result.json()["signal"] == "NO TRADE"
    assert len(client.get("/v1/memory/historical", headers=VIEW_AUTH).json()) == 1
    assert client.get("/v1/memory/live", headers=AUTH).status_code == 422
    status = client.get("/v1/status", headers=AUTH).json()
    assert not status["live_enabled"] and not status["broker_execution_enabled"]
    roles = client.get("/v1/agents", headers=AUTH).json()
    assert len(roles) == 15
    assert sum(r["implementation"] == "local_task" for r in roles) == 3


def test_ac20_api_rejects_mode_injection_and_order_routes(client):
    assert client.post("/v1/orders", json=BASE, headers=AUTH).status_code == 404
    assert (
        client.post("/v1/risk/preview", json=BASE | {"mode": "live"}, headers=AUTH).status_code
        == 422
    )
    assert (
        client.put("/v1/safety/kill-switch", json={"enabled": "false"}, headers=AUTH).status_code
        == 422
    )


def test_ac21_worker_executes_and_acknowledges(store):
    store.enqueue("key", "research.snapshot", SNAPSHOT)
    assert process_one(store)
    assert not process_one(store)
    assert len(store.records("historical")) == 1


def test_ac22_sell_geometry(store):
    store.set_kill(False)
    result = RiskController(store).evaluate(
        Proposal(**(BASE | dict(side="sell", stop_loss=3010, take_profit=2980)))
    )
    assert result["eligible_for_research"]
