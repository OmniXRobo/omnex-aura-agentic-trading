"""Virtual ledger fixtures: no MT5, provider APIs or real execution."""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal as D

import pytest
from test_market_data import CONTRACT, NOW

from aura.market import GoldContract, Quote
from aura.store import Store
from aura.virtual import VirtualConfig, VirtualIntent, VirtualLedger


def config(**change):
    return VirtualConfig(**(dict(evidence_source="fixture", commission_per_lot_side=7,
        slippage_price="0.1", swap_debit_per_lot_utc_day=1) | change))


def intent(**change):
    return VirtualIntent(**(dict(intent_id="signal-1", strategy_version="fixture-v1",
        reason="Synthetic test only", side="buy", volume="0.01", stop_loss=2995,
        take_profit=3010, news_blackout=False, created_msc=NOW, expires_msc=NOW + 60000) | change))


def quote(t=NOW, bid=3000, ask=3000.2):
    return Quote(symbol="XAUUSDm", time_msc=t, bid=bid, ask=ask, flags=6)


def ledger(tmp_path, arm=True, cfg=None):
    store = Store(tmp_path)
    if arm:
        store.set_kill(False)
    return VirtualLedger(store, "fixture", cfg or config(), GoldContract(**CONTRACT),
                         clock=lambda: NOW)


def test_v01_entry_and_long_profit_accounting(tmp_path):
    c = ledger(tmp_path)
    result = c.apply("open", quote(), intent())
    assert result["action"] == "opened" and not result["execution_allowed"]
    assert D(result["state"]["cash"]) == D("9999.93")
    assert D(result["state"]["equity"]) == D("9999.46")
    c.clock = lambda: NOW + 1000
    closed = c.apply("target", quote(NOW + 1000, 3010, 3010.2))
    assert closed["action"] == "take_profit"
    assert D(closed["details"]["gross_pnl"]) == D("9.6")
    assert D(closed["details"]["net_pnl"]) == D("9.46")
    assert D(closed["state"]["cash"]) == D("10009.46")


def test_v02_short_uses_bid_entry_ask_exit(tmp_path):
    c = ledger(tmp_path)
    c.apply("open", quote(), intent(side="sell", stop_loss=3005, take_profit=2990))
    c.clock = lambda: NOW + 1
    result = c.apply("target", quote(NOW + 1, 2989.8, 2990))
    assert result["action"] == "take_profit"
    assert D(result["details"]["net_pnl"]) == D("9.66")


def test_v03_stop_gap_fills_at_available_quote_not_stop_level(tmp_path):
    c = ledger(tmp_path)
    c.apply("open", quote(), intent())
    c.clock = lambda: NOW + 1
    result = c.apply("gap", quote(NOW + 1, 2990, 2990.2))
    assert result["action"] == "stop_loss"
    assert D(result["details"]["exit_price"]) == D("2989.9")
    assert D(result["details"]["net_pnl"]) == D("-10.54")


def test_v04_restart_exact_replay_cannot_refill(tmp_path):
    c = ledger(tmp_path)
    original = c.apply("open", quote(), intent())
    restarted = ledger(tmp_path)
    restarted.clock = lambda: NOW + 86400000
    assert restarted.apply("open", quote(), intent()) == original
    assert len(restarted.events()) == 1
    with pytest.raises(ValueError, match="different input"):
        restarted.apply("open", quote(), intent(volume="0.02"))


@pytest.mark.parametrize("change,reason", [
    (dict(news_blackout=True), "news_blackout"), (dict(volume=1), "risk_limit"),
    (dict(volume="0.015"), "volume_constraints"),
    (dict(stop_loss=3001), "stop_geometry"),
])
def test_v05_entry_rejections_are_durable(tmp_path, change, reason):
    c = ledger(tmp_path)
    result = c.apply("reject", quote(), intent(**change))
    assert result["action"] == "entry_rejected"
    assert reason in result["details"]["entry_rejected"]
    assert result["state"]["position"] is None
    assert D(result["state"]["cash"]) == 10000


def test_v06_default_stop_and_missing_safety_fail_closed(tmp_path, monkeypatch):
    c = ledger(tmp_path, arm=False)
    result = c.apply("default-stop", quote(), intent())
    assert "emergency_stop" in result["details"]["entry_rejected"]
    def broken():
        raise RuntimeError("unavailable")
    monkeypatch.setattr(c.store, "killed", broken)
    result = c.apply("missing-stop", quote(), intent(intent_id="another"))
    assert "safety_state_unavailable" in result["details"]["entry_rejected"]


@pytest.mark.parametrize("age", [5001, -1])
def test_v07_stale_future_quotes_do_not_write_receipts(tmp_path, age):
    c = ledger(tmp_path)
    with pytest.raises(ValueError):
        c.apply("bad", quote(NOW - age), intent())
    assert not c.events()


def test_v08_second_intent_cannot_create_another_position(tmp_path):
    c = ledger(tmp_path)
    c.apply("open", quote(), intent())
    result = c.apply("second", quote(), intent(intent_id="signal-2"))
    assert "position_was_active" in result["details"]["entry_rejected"]
    assert result["state"]["position"]["intent_id"] == "signal-1"


def test_v09_exit_management_continues_when_stop_active(tmp_path):
    c = ledger(tmp_path)
    c.apply("open", quote(), intent())
    c.store.set_kill(True)
    c.clock = lambda: NOW + 1
    result = c.apply("exit", quote(NOW + 1, 2990, 2990.2))
    assert result["action"] == "stop_loss" and result["state"]["position"] is None


def test_v10_overnight_debit_charged_once(tmp_path):
    c = ledger(tmp_path)
    c.apply("open", quote(), intent())
    c.clock = lambda: NOW + 86400000
    result = c.apply("roll", quote(NOW + 86400000))
    assert D(result["state"]["cash"]) == D("9999.92")
    result = c.apply("roll-again", quote(NOW + 86400000))
    assert D(result["state"]["cash"]) == D("9999.92")


def test_v11_configuration_is_immutable_and_memories_separate(tmp_path):
    c = ledger(tmp_path)
    c.apply("open", quote(), intent())
    with pytest.raises(ValueError, match="immutable"):
        ledger(tmp_path, cfg=config(slippage_price="0.2"))
    assert c.store.records("historical") == c.store.records("demo") == []
    with c.store.connect("demo") as db:
        assert not db.execute("SELECT name FROM sqlite_master WHERE name='virtual_sessions'").fetchone()


def test_v12_concurrent_duplicate_delivery(tmp_path):
    c = ledger(tmp_path)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: c.apply("open", quote(), intent()), range(2)))
    assert results[0] == results[1]
    assert len(c.events()) == 1


def test_v13_consumed_signal_cannot_reopen_after_exit(tmp_path):
    c = ledger(tmp_path)
    c.apply("open", quote(), intent())
    c.clock = lambda: NOW + 1
    c.apply("exit", quote(NOW + 1, 3010, 3010.2))
    result = c.apply("reopen", quote(NOW + 1), intent())
    assert "intent_already_consumed" in result["details"]["entry_rejected"]


def test_v14_out_of_order_and_wide_spread(tmp_path):
    c = ledger(tmp_path)
    result = c.apply("wide", quote(ask=3001), intent())
    assert "spread_limit" in result["details"]["entry_rejected"]
    with pytest.raises(ValueError, match="Out-of-order"):
        c.apply("past", quote(NOW - 1))


def test_v15_drawdown_halt_persists_after_restart(tmp_path):
    c = ledger(tmp_path)
    c.apply("open", quote(), intent())
    c.clock = lambda: NOW + 1
    result = c.apply("gap", quote(NOW + 1, 2400, 2400.2))
    assert result["state"]["halted"]
    restarted = ledger(tmp_path)
    assert restarted.snapshot()["halted"]
    restarted.clock = lambda: NOW + 2
    result = restarted.apply("new", quote(NOW + 2), intent(intent_id="new"))
    assert "drawdown_halt" in result["details"]["entry_rejected"]


def test_v16_fixture_cli_has_no_working_directory_side_effects(tmp_path, monkeypatch, capsys):
    import json

    from aura.virtual_fixture import main

    monkeypatch.chdir(tmp_path)
    main()
    report = json.loads(capsys.readouterr().out)
    assert report["entry"] == "opened" and report["exit"] == "take_profit"
    assert report["restart_replay_identical"] and report["ledger_events"] == 2
    assert report["net_pnl"] == "9.4600"
    assert not report["existing_data_modified"] and not report["execution_allowed"]
    assert list(tmp_path.iterdir()) == []


def test_v17_database_failure_rolls_back_position_receipt_and_consumed_intent(tmp_path):
    import sqlite3

    c = ledger(tmp_path)
    with c.store.connect("virtual") as db:
        db.execute("CREATE TRIGGER injected_failure BEFORE INSERT ON virtual_events "
                   "BEGIN SELECT RAISE(ABORT,'fixture storage failure'); END")
    with pytest.raises(sqlite3.IntegrityError):
        c.apply("open", quote(), intent())
    assert c.snapshot()["position"] is None and not c.events()
    with c.store.connect("virtual") as db:
        assert db.execute("SELECT count(*) FROM virtual_receipts").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM virtual_intents").fetchone()[0] == 0
        db.execute("DROP TRIGGER injected_failure")
    assert c.apply("open", quote(), intent())["action"] == "opened"


def test_v18_intent_expiry_and_append_only_audit(tmp_path):
    import sqlite3

    c = ledger(tmp_path)
    result = c.apply("expired", quote(), intent(created_msc=NOW - 2000, expires_msc=NOW - 1))
    assert "intent_time_invalid" in result["details"]["entry_rejected"]
    assert result["market_quote"]["bid"] == 3000
    for table in ("virtual_events", "virtual_receipts", "virtual_intents"):
        with pytest.raises(sqlite3.IntegrityError):
            with c.store.connect("virtual") as db:
                db.execute(f"DELETE FROM {table}")
