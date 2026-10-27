"""Regression tests for the observed collector binding/error-report failure."""

import json

import pytest
from test_market_data import NOW, Terminal

from aura.collector import AccountBinding, Collector, MarketDataError
from aura.diagnose import report_terminal
from aura.market import Feed
from aura.market_store import MarketStore
from aura.store import Store


def memory(tmp_path):
    return MarketStore(Store(tmp_path))


def test_d01_bad_claim_does_not_reserve_stream(tmp_path):
    state = memory(tmp_path)
    terminal = Terminal()
    feed = Feed(broker="Equiti", source="fixture", stream="test")
    with pytest.raises(MarketDataError) as caught:
        Collector(terminal, state, feed, AccountBinding(99999, "Fixture-Demo"))
    assert caught.value.code == "login_mismatch"
    with state.store.connect() as db:
        assert db.execute("SELECT count(*) FROM feed_bindings").fetchone()[0] == 0
    Collector(terminal, state, feed, AccountBinding(12345, "Fixture-Demo"))
    with state.store.connect() as db:
        assert db.execute("SELECT count(*) FROM feed_bindings").fetchone()[0] == 1


@pytest.mark.parametrize(
    "which,code",
    [("server", "server_mismatch"), ("demo", "not_demo"), ("connection", "disconnected")],
)
def test_d02_unverified_terminal_never_binds(tmp_path, which, code):
    terminal = Terminal()
    if which == "server":
        terminal.account.server = "Other-Demo"
    if which == "demo":
        terminal.account.trade_mode = 2
    if which == "connection":
        terminal.connected = False
    state = memory(tmp_path)
    with pytest.raises(MarketDataError) as caught:
        Collector(
            terminal,
            state,
            Feed(broker="Equiti", source="fixture", stream="test"),
            AccountBinding(12345, "Fixture-Demo"),
        )
    assert caught.value.code == code
    with state.store.connect() as db:
        assert db.execute("SELECT count(*) FROM feed_bindings").fetchone()[0] == 0


def test_d03_verified_account_change_does_not_overwrite_binding(tmp_path):
    state = memory(tmp_path)
    terminal = Terminal()
    feed = Feed(broker="Equiti", source="fixture", stream="test")
    Collector(terminal, state, feed, AccountBinding(12345, "Fixture-Demo"))
    terminal.account.login = 67890
    with pytest.raises(MarketDataError) as caught:
        Collector(terminal, state, feed, AccountBinding(67890, "Fixture-Demo"))
    assert caught.value.code == "stream_binding_conflict"
    terminal.account.login = 12345
    Collector(terminal, state, feed, AccountBinding(12345, "Fixture-Demo"))


@pytest.mark.parametrize(
    "change,code",
    [
        (dict(time_msc=NOW - 5001), "stale_tick"),
        (dict(time_msc=NOW + 1), "future_tick"),
        (dict(ask=2999), "quote_invalid"),
    ],
)
def test_d04_safe_specific_poll_errors(tmp_path, change, code):
    terminal = Terminal()
    for key, value in change.items():
        setattr(terminal.tick, key, value)
    collector = Collector(
        terminal,
        memory(tmp_path),
        Feed(broker="Equiti", source="fixture", stream="test"),
        AccountBinding(12345, "Fixture-Demo"),
        clock=lambda: NOW,
    )
    with pytest.raises(MarketDataError) as caught:
        collector.poll("XAUUSDm")
    assert caught.value.code == code


def test_d05_invalid_contract_lists_fields_not_raw_data(tmp_path):
    terminal = Terminal()
    terminal.symbol.trade_tick_value = 0
    collector = Collector(
        terminal,
        memory(tmp_path),
        Feed(broker="Equiti", source="fixture", stream="test"),
        AccountBinding(12345, "Fixture-Demo"),
        clock=lambda: NOW,
    )
    with pytest.raises(MarketDataError) as caught:
        collector.poll("XAUUSDm")
    assert caught.value.code == "contract_invalid"
    assert "trade_tick_value" in str(caught.value)
    assert "12345" not in str(caught.value)


def terminal_report_fixture():
    terminal = Terminal()
    terminal.account.company = "Fixture Broker"
    return terminal


def test_d06_report_is_read_only_and_hides_account_number():
    result = report_terminal(terminal_report_fixture(), "XAUUSDm", 12345, "Fixture-Demo", NOW)
    assert result["terminal_checks_passed"] is True
    assert result["stream_modified"] is result["execution_allowed"] is False
    assert "12345" not in json.dumps(result)
    assert result["contract_valid"] and result["quote_fresh"]


def test_d07_report_distinguishes_wrong_login_and_stale_tick():
    terminal = terminal_report_fixture()
    terminal.tick.time_msc = NOW - 6000
    result = report_terminal(terminal, "XAUUSDm", 99999, "Fixture-Demo", NOW)
    assert result["login_matches"] is False
    assert result["server_matches"] is True
    assert result["tick_age_seconds"] == 6 and not result["quote_fresh"]
    assert not result["terminal_checks_passed"]


def test_d08_report_contract_failure_is_actionable():
    terminal = terminal_report_fixture()
    terminal.symbol.trade_tick_size = 0
    result = report_terminal(terminal, "XAUUSDm", 12345, "Fixture-Demo", NOW)
    assert result["contract_invalid_fields"] == ["trade_tick_size"]
    assert not result["terminal_checks_passed"]


def test_d09_report_does_not_read_symbols_on_real_account():
    terminal = terminal_report_fixture()
    terminal.account.trade_mode = 2

    def forbidden(*_):
        pytest.fail("Not a demo account")

    terminal.symbol_info = forbidden
    assert report_terminal(terminal, "XAUUSDm", 12345, "Fixture-Demo", NOW)["error"] == "not_demo"


def test_d10_report_detects_account_switch_during_read():
    terminal = terminal_report_fixture()
    terminal.after_read = lambda: setattr(terminal.account, "login", 67890)
    result = report_terminal(terminal, "XAUUSDm", 12345, "Fixture-Demo", NOW)
    assert not result["account_stable"] and not result["terminal_checks_passed"]


def test_d11_native_exception_is_sanitized():
    terminal = terminal_report_fixture()

    def broken(*_):
        raise RuntimeError("private-terminal-detail-marker")

    terminal.symbol_info = broken
    result = report_terminal(terminal, "XAUUSDm", 12345, "Fixture-Demo", NOW)
    assert result["error"] == "terminal_read_failed"
    assert "private-terminal-detail-marker" not in json.dumps(result)
