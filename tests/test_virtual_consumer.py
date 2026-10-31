"""Market-to-virtual consumer restart, provenance and failure gates."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from test_market_data import CONTRACT, FEED, NOW
from test_virtual_ledger import config, intent, quote

from aura.collector import AccountBinding
from aura.market import GoldContract
from aura.market_store import MarketStore
from aura.store import Store
from aura.time_policy import QuoteTimePolicy
from aura.virtual import VirtualLedger
from aura.virtual_consumer import ConsumerError, VirtualQuoteConsumer

BINDING = AccountBinding(12345, "Fixture-Demo")


def setup(tmp_path, correction=False):
    store = Store(tmp_path)
    market = MarketStore(store)
    market.bind(FEED, BINDING.login, BINDING.server)
    contract = GoldContract(**CONTRACT)
    market.append(FEED, contract, NOW)
    tick = quote()
    if correction:
        policy = QuoteTimePolicy(server=BINDING.server, symbol=tick.symbol, offset_seconds=10800,
                                 verified_at_msc=NOW - 1000, expires_at_msc=NOW + 2000,
                                 evidence="Controlled synthetic timestamp check")
        digest = hashlib.sha256(policy.model_dump_json().encode()).hexdigest()
        tick = tick.model_copy(update=dict(raw_time_msc=NOW + 10800000,
                                          time_offset_seconds=10800, time_policy=digest))
        market.bind_quote_time(FEED, 10800, policy)
    else:
        market.bind_quote_time(FEED, 0)
    market.append(FEED, tick, NOW)
    market.set_status(FEED, "healthy", "Fixture", NOW)
    ledger = VirtualLedger(store, "consumer-test", config(), contract, clock=lambda: NOW)
    return VirtualQuoteConsumer(market, ledger, FEED, BINDING), market, ledger, tick


def test_cq01_applies_fresh_quote_once_and_restart_idle(tmp_path):
    consumer, market, ledger, _ = setup(tmp_path)
    assert consumer.step()["state"] == "applied"
    restarted = VirtualQuoteConsumer(market, ledger, FEED, BINDING)
    assert restarted.step()["state"] == "idle"
    assert len(ledger.events()) == 1 and ledger.snapshot()["position"] is None
    assert ledger.store.killed()  # The consumer never arms the global stop.


def test_cq02_corrected_quote_validates_persistent_policy(tmp_path):
    consumer, _, ledger, _ = setup(tmp_path, True)
    assert consumer.step()["state"] == "applied"
    assert ledger.events()[0]["market_quote"]["raw_time_msc"] == NOW + 10800000


def test_cq03_expired_policy_blocks_without_advancing(tmp_path):
    consumer, _, ledger, _ = setup(tmp_path, True)
    ledger.clock = lambda: NOW + 2001
    with pytest.raises(ConsumerError, match="expired"):
        consumer.step()
    assert not ledger.events()


def test_cq04_stale_backlog_is_gap_not_retroactive_fill(tmp_path):
    consumer, _, ledger, _ = setup(tmp_path)
    ledger.clock = lambda: NOW + 5001
    assert consumer.step()["state"] == "skipped_stale_gap"
    assert not ledger.events()
    assert consumer.step()["state"] == "idle"


def test_cq05_crash_after_ledger_before_ack_recovers_even_when_old(tmp_path, monkeypatch):
    consumer, market, ledger, _ = setup(tmp_path)
    def crash(*_):
        raise RuntimeError("injected crash")
    monkeypatch.setattr(consumer, "_ack", crash)
    with pytest.raises(RuntimeError):
        consumer.step()
    assert len(ledger.events()) == 1
    ledger.clock = lambda: NOW + 86400000
    restarted = VirtualQuoteConsumer(market, ledger, FEED, BINDING)
    assert restarted.step()["state"] == "recovered_committed"
    assert len(ledger.events()) == 1


@pytest.mark.parametrize("state,age", [("blocked", 0), ("healthy", 15001), ("healthy", -1)])
def test_cq06_unhealthy_or_invalid_heartbeat_blocks(tmp_path, state, age):
    consumer, market, ledger, _ = setup(tmp_path)
    market.set_status(FEED, state, "Fixture", NOW - age)
    with pytest.raises(ConsumerError, match="feed_not_healthy"):
        consumer.step()
    assert not ledger.events()


def test_cq07_contract_change_requires_reviewed_session(tmp_path):
    consumer, market, ledger, _ = setup(tmp_path)
    market.append(FEED, GoldContract(**(CONTRACT | dict(trade_contract_size=10))), NOW)
    with pytest.raises(ConsumerError, match="contract_changed"):
        consumer.step()
    assert not ledger.events()


def test_cq08_wrong_account_never_binds_or_consumes(tmp_path):
    _, market, ledger, _ = setup(tmp_path)
    with pytest.raises(ConsumerError, match="account_binding_mismatch"):
        VirtualQuoteConsumer(market, ledger, FEED, AccountBinding(99999, BINDING.server))
    assert not ledger.events()


def test_cq09_same_millisecond_changes_survive(tmp_path):
    consumer, market, ledger, _ = setup(tmp_path)
    consumer.step()
    market.append(FEED, quote(bid=3000.1), NOW)
    assert consumer.step()["state"] == "applied"
    assert len(ledger.events()) == 2


def test_cq10_concurrent_consumers_use_one_ledger_transition(tmp_path):
    consumer, market, ledger, _ = setup(tmp_path)
    other = VirtualQuoteConsumer(market, ledger, FEED, BINDING)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda c: c.step(), [consumer, other]))
    assert all(r["state"] in {"applied", "recovered_committed", "idle"} for r in results)
    assert len(ledger.events()) == 1


def test_cq11_existing_bound_position_can_exit_but_no_new_intent_is_created(tmp_path):
    consumer, market, ledger, _ = setup(tmp_path)
    consumer.step()
    ledger.store.set_kill(False)
    ledger.apply("explicit-fixture-entry", quote(), intent())
    ledger.store.set_kill(True)
    ledger.clock = lambda: NOW + 1
    market.append(FEED, quote(NOW + 1, 3010, 3010.2), NOW + 1)
    market.set_status(FEED, "healthy", "Fixture", NOW + 1)
    assert consumer.step()["state"] == "applied"
    assert ledger.snapshot()["position"] is None
    assert ledger.events()[-1]["action"] == "take_profit"
    assert ledger.events()[-1]["intent"] is None


def test_cq12_foreign_database_and_preexisting_unbound_session_rejected(tmp_path):
    _, _, ledger, _ = setup(tmp_path / "one")
    _, other_market, _, _ = setup(tmp_path / "two")
    with pytest.raises(ConsumerError, match="source_binding_conflict"):
        VirtualQuoteConsumer(other_market, ledger, FEED, BINDING)
    standalone = VirtualLedger(ledger.store, "unbound", config(), ledger.contract, clock=lambda: NOW)
    standalone.apply("old-evidence", quote())
    with pytest.raises(ConsumerError, match="session_has_unbound_evidence"):
        VirtualQuoteConsumer(other_market, standalone, FEED, BINDING)


def test_cq13_receipt_keys_dont_contain_login_number(tmp_path):
    consumer, _, ledger, _ = setup(tmp_path)
    consumer.step()
    assert "12345" not in json.dumps(ledger.events())


def test_cq14_missing_policy_and_out_of_order_gap(tmp_path):
    consumer, market, ledger, tick = setup(tmp_path, True)
    consumer.step()
    missing = tick.model_copy(update=dict(time_policy="1" * 64))
    market.append(FEED, missing, NOW)
    with pytest.raises(ConsumerError, match="quote_policy_missing"):
        consumer.step()
    assert len(ledger.events()) == 1


def test_cq15_source_checkpoint_rollback_is_detected(tmp_path):
    consumer, _, ledger, _ = setup(tmp_path)
    consumer.step()
    with ledger.store.connect("virtual") as db:
        db.execute("UPDATE virtual_source_cursors SET row_id=99999 WHERE session=?", (ledger.session,))
    with pytest.raises(ConsumerError, match="source_checkpoint_missing"):
        consumer.step()


def test_cq16_future_reception_and_out_of_order_quotes_are_not_applied(tmp_path):
    consumer, market, ledger, _ = setup(tmp_path)
    consumer.step()
    market.append(FEED, quote(NOW - 1), NOW)
    assert consumer.step()["state"] == "skipped_out_of_order_gap"
    market.append(FEED, quote(bid=3000.15), NOW + 1)
    with pytest.raises(ConsumerError, match="reception_time_invalid"):
        consumer.step()
    assert len(ledger.events()) == 1


def test_cq17_synthetic_cli_keeps_stop_active_and_existing_data_untouched(tmp_path, monkeypatch, capsys):
    from aura.virtual_consumer_fixture import main

    monkeypatch.chdir(tmp_path)
    main()
    result = json.loads(capsys.readouterr().out)
    assert result["states"] == ["applied"] * 3 and result["restart_state"] == "idle"
    assert result["ledger_events"] == 3 and not result["position_open"]
    assert result["emergency_stop_unchanged"] and not result["entries_enabled"]
    assert not result["execution_allowed"] and not result["existing_data_modified"]
    assert not list(tmp_path.iterdir())


def test_cq18_watch_cli_rejects_fixture_as_demo_source(tmp_path, monkeypatch, capsys):
    import sys

    from aura.consume_virtual import main

    path = tmp_path / "config.json"
    path.write_text(json.dumps(dict(session="observe", feed=FEED.model_dump(), symbol="XAUUSDm",
                                    costs=json.loads(config().model_dump_json()))))
    monkeypatch.setattr(sys, "argv", ["consume_virtual", "--config", str(path),
                                      "--data-dir", str(tmp_path / "new-data")])
    with pytest.raises(SystemExit) as caught:
        main()
    assert caught.value.code == 1
    result = json.loads(capsys.readouterr().out)
    assert result["error"] == "demo_observation_config_required"
    assert not (tmp_path / "new-data").exists()


def test_cq19_demo_observer_cli_processes_persisted_quotes_and_restarts(tmp_path, monkeypatch, capsys):
    import sys
    import time

    from aura.consume_virtual import main
    from aura.market import Feed

    feed = Feed(broker="Equiti", source="mt5_demo", stream="demo-test")
    now = int(time.time() * 1000)
    data_dir = tmp_path / "data"
    market = MarketStore(Store(data_dir))
    market.bind(feed, BINDING.login, BINDING.server)
    market.bind_quote_time(feed, 0)
    market.append(feed, GoldContract(**CONTRACT), now)
    market.append(feed, quote(now), now)
    market.set_status(feed, "healthy", "Fixture emulating accepted demo source", now)
    path = tmp_path / "observer.json"
    path.write_text(json.dumps(dict(session="observer", feed=feed.model_dump(), symbol="XAUUSDm",
                                    costs=json.loads(config(evidence_source="demo_observation").model_dump_json()))))
    monkeypatch.setattr(sys, "argv", ["consume_virtual", "--config", str(path), "--data-dir", str(data_dir)])
    monkeypatch.setenv("AURA_MT5_EXPECTED_LOGIN", str(BINDING.login))
    monkeypatch.setenv("AURA_MT5_EXPECTED_SERVER", BINDING.server)
    main()
    first = json.loads(capsys.readouterr().out)
    assert first["states"] == {"applied": 1, "idle": 1}
    main()
    assert json.loads(capsys.readouterr().out)["states"] == {"idle": 1}
    assert market.store.killed()
